import sys
import time
from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSpinBox
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
import pyqtgraph as pg
import numpy as np

# Try to import theme constants
try:
    from theme import (
        BACKGROUND, TEXT_COLOR, BORDER_COLOR, BUTTON_COLOR, BUTTON_TEXT, BUTTON_HOVER,
        FONT_FAMILY, FONT_SIZE_NORMAL, BORDER_RADIUS, BORDER_WIDTH
    )
except ImportError:
    # Fallback colors
    BACKGROUND = "#2b2b2b"
    TEXT_COLOR = "white"
    BORDER_COLOR = "#555555"
    BUTTON_COLOR = "#444444"
    BUTTON_TEXT = "white"
    BUTTON_HOVER = "#666666"
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_NORMAL = 10
    BORDER_RADIUS = 3
    BORDER_WIDTH = 1

class ADCSGraphWidget(QWidget):
    """
    A compact widget that plots live ADCS data including:
    - Z-axis angle from MPU (left Y-axis) - primary control angle
    - Target angle value (left Y-axis)
    - Three LUX sensor values (right Y-axis)
    All plotted against time. Optimized for row 3 layout.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ADCSGraphWidget")
        
        # Data storage - using deque for efficient append/pop operations
        self.max_points = 300  # Reduced for better performance in compact layout
        self.time_data = deque(maxlen=self.max_points)
        
        # Angle data (left Y-axis)
        self.z_angle_data = deque(maxlen=self.max_points)
        self.target_angle_data = deque(maxlen=self.max_points)
        
        # LUX data (right Y-axis)
        self.lux1_data = deque(maxlen=self.max_points)
        self.lux2_data = deque(maxlen=self.max_points)
        self.lux3_data = deque(maxlen=self.max_points)
        
        # Current values
        self.current_z_angle = 0.0
        self.current_target = 0.0
        self.current_lux1 = 0.0
        self.current_lux2 = 0.0
        self.current_lux3 = 0.0
        
        # Time tracking
        self.start_time = time.time()
        
        # Setup UI
        self.setup_ui()
        
        # Setup update timer - reduced frequency to prevent GUI lag
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(500)  # Update every 500ms (2 Hz) to reduce lag
        
    def setup_ui(self):
        """Setup the compact user interface with vertical checkboxes on the right."""
        main_layout = QHBoxLayout(self)  # Changed to horizontal layout
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(2, 2, 2, 2)
        
        # Left side: Plot widget
        plot_container = QVBoxLayout()
        
        # Create the plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(BACKGROUND)
        self.plot_widget.setLabel('left', 'Angle (°)', color=TEXT_COLOR, size='9pt')
        self.plot_widget.setLabel('bottom', 'Time (s)', color=TEXT_COLOR, size='9pt')
        self.plot_widget.setLabel('right', 'LUX', color=TEXT_COLOR, size='9pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        
        # Set fixed time range to 10 seconds
        self.plot_widget.setXRange(0, 10)
        self.plot_widget.setMinimumHeight(180)
        
        # Create right Y-axis for LUX values
        self.lux_axis = pg.ViewBox()
        self.plot_widget.plotItem.scene().addItem(self.lux_axis)
        self.plot_widget.plotItem.getAxis('right').linkToView(self.lux_axis)
        self.lux_axis.setXLink(self.plot_widget.plotItem)
        
        # Style the axes with smaller fonts
        for axis in ['left', 'bottom', 'right']:
            ax = self.plot_widget.plotItem.getAxis(axis)
            ax.setPen(color=TEXT_COLOR)
            ax.setTextPen(color=TEXT_COLOR)
            ax.setStyle(tickFont=pg.QtGui.QFont(FONT_FAMILY, 8))
        
        # Initialize plot curves
        self.setup_plot_curves()
        
        # Handle view box resizing
        self.plot_widget.plotItem.vb.sigResized.connect(self.update_lux_axis)
        
        plot_container.addWidget(self.plot_widget)
        
        # Add clear button below plot
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_COLOR};
                color: {BUTTON_TEXT};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 2px 6px;
                font-family: {FONT_FAMILY};
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
            }}
        """)
        clear_btn.clicked.connect(self.clear_data)
        plot_container.addWidget(clear_btn)
        
        main_layout.addLayout(plot_container, 4)  # Plot takes most space
        
        # Right side: Vertical checkbox panel
        checkbox_panel = self.create_vertical_checkbox_panel()
        main_layout.addWidget(checkbox_panel, 1)  # Checkboxes take less space
        
    def create_vertical_checkbox_panel(self):
        """Create vertical panel with checkboxes for toggling plot lines."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Title
        title = QLabel("Show Lines:")
        title.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: 10pt; font-weight: bold;")
        layout.addWidget(title)
        
        # Checkboxes stacked vertically
        self.z_angle_checkbox = QCheckBox("Z-Angle")
        self.z_angle_checkbox.setChecked(True)
        self.z_angle_checkbox.setStyleSheet(f"color: #00ff88; font-family: {FONT_FAMILY}; font-size: 9pt;")
        self.z_angle_checkbox.toggled.connect(self.toggle_z_angle)
        layout.addWidget(self.z_angle_checkbox)
        
        self.target_checkbox = QCheckBox("Target")
        self.target_checkbox.setChecked(True)
        self.target_checkbox.setStyleSheet(f"color: #ff8800; font-family: {FONT_FAMILY}; font-size: 9pt;")
        self.target_checkbox.toggled.connect(self.toggle_target)
        layout.addWidget(self.target_checkbox)
        
        self.lux1_checkbox = QCheckBox("LUX1")
        self.lux1_checkbox.setChecked(True)
        self.lux1_checkbox.setStyleSheet(f"color: #ff0088; font-family: {FONT_FAMILY}; font-size: 9pt;")
        self.lux1_checkbox.toggled.connect(self.toggle_lux1)
        layout.addWidget(self.lux1_checkbox)
        
        self.lux2_checkbox = QCheckBox("LUX2")
        self.lux2_checkbox.setChecked(True)
        self.lux2_checkbox.setStyleSheet(f"color: #0088ff; font-family: {FONT_FAMILY}; font-size: 9pt;")
        self.lux2_checkbox.toggled.connect(self.toggle_lux2)
        layout.addWidget(self.lux2_checkbox)
        
        self.lux3_checkbox = QCheckBox("LUX3")
        self.lux3_checkbox.setChecked(True)
        self.lux3_checkbox.setStyleSheet(f"color: #88ff00; font-family: {FONT_FAMILY}; font-size: 9pt;")
        self.lux3_checkbox.toggled.connect(self.toggle_lux3)
        layout.addWidget(self.lux3_checkbox)
        
        layout.addStretch()  # Push checkboxes to top
        
        return panel
        
    def create_compact_status_panel(self):
        """Create compact status panel showing current values."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setSpacing(8)  # Tighter spacing
        layout.setContentsMargins(3, 1, 3, 1)  # Smaller margins
        
        # Current values display with smaller fonts
        self.z_angle_label = QLabel("Z-Angle: 0.0°")
        self.z_angle_label.setStyleSheet(f"color: #00ff88; font-family: {FONT_FAMILY}; font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.z_angle_label)
        
        self.target_label = QLabel("Target: 0.0°")
        self.target_label.setStyleSheet(f"color: #ff8800; font-family: {FONT_FAMILY}; font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.target_label)
        
        self.lux1_label = QLabel("LUX1: 0.0")
        self.lux1_label.setStyleSheet(f"color: #ff0088; font-family: {FONT_FAMILY}; font-size: 9pt;")
        layout.addWidget(self.lux1_label)
        
        self.lux2_label = QLabel("LUX2: 0.0")
        self.lux2_label.setStyleSheet(f"color: #0088ff; font-family: {FONT_FAMILY}; font-size: 9pt;")
        layout.addWidget(self.lux2_label)
        
        self.lux3_label = QLabel("LUX3: 0.0")
        self.lux3_label.setStyleSheet(f"color: #88ff00; font-family: {FONT_FAMILY}; font-size: 9pt;")
        layout.addWidget(self.lux3_label)
        
        layout.addStretch()
        
        return panel
        
    def setup_plot_curves(self):
        """Initialize plot curves with different colors and styles."""
        # Z-axis angle curve (left axis) - bright green
        self.z_angle_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#00ff88', width=2),
            name='Z-Axis Angle'
        )
        
        # Target angle curve (left axis) - orange
        self.target_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#ff8800', width=2, style=Qt.PenStyle.DashLine),
            name='Target Angle'
        )
        
        # LUX curves (right axis) - different colors
        self.lux1_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color='#ff0088', width=1.5),
            name='LUX1'
        )
        self.lux2_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color='#0088ff', width=1.5),
            name='LUX2'
        )
        self.lux3_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color='#88ff00', width=1.5),
            name='LUX3'
        )
        
        # Add LUX curves to the right axis
        self.lux_axis.addItem(self.lux1_curve)
        self.lux_axis.addItem(self.lux2_curve)
        self.lux_axis.addItem(self.lux3_curve)
        
    def update_lux_axis(self):
        """Update the LUX axis geometry to match the main plot."""
        self.lux_axis.setGeometry(self.plot_widget.plotItem.vb.sceneBoundingRect())
        self.lux_axis.linkedViewChanged(self.plot_widget.plotItem.vb, self.lux_axis.XAxis)
        
    def add_data_point(self, z_angle=None, target_angle=None, lux1=None, lux2=None, lux3=None):
        """Add a new data point to the plot with optimized 10-second rolling window."""
        current_time = time.time() - self.start_time
        
        # Update current values if provided
        if z_angle is not None:
            self.current_z_angle = float(z_angle)
        if target_angle is not None:
            self.current_target = float(target_angle)
        if lux1 is not None:
            self.current_lux1 = float(lux1)
        if lux2 is not None:
            self.current_lux2 = float(lux2)
        if lux3 is not None:
            self.current_lux3 = float(lux3)
            
        # Add data points
        self.time_data.append(current_time)
        self.z_angle_data.append(self.current_z_angle)
        self.target_angle_data.append(self.current_target)
        self.lux1_data.append(self.current_lux1)
        self.lux2_data.append(self.current_lux2)
        self.lux3_data.append(self.current_lux3)
        
        # Remove old data points beyond 10 seconds to maintain fixed window
        while len(self.time_data) > 1 and (current_time - self.time_data[0]) > 10.0:
            self.time_data.popleft()
            self.z_angle_data.popleft()
            self.target_angle_data.popleft()
            self.lux1_data.popleft()
            self.lux2_data.popleft()
            self.lux3_data.popleft()
        
    def clear_data(self):
        """Clear all data and reset the plot."""
        self.time_data.clear()
        self.z_angle_data.clear()
        self.target_angle_data.clear()
        self.lux1_data.clear()
        self.lux2_data.clear()
        self.lux3_data.clear()
        
        # Reset start time
        self.start_time = time.time()
        
        # Clear all curves
        self.z_angle_curve.clear()
        self.target_curve.clear()
        self.lux1_curve.clear()
        self.lux2_curve.clear()
        self.lux3_curve.clear()
        
    # Toggle methods for checkboxes
    def toggle_z_angle(self, checked):
        """Toggle Z-axis angle curve visibility."""
        if not checked:
            self.z_angle_curve.clear()
            
    def toggle_target(self, checked):
        """Toggle target angle curve visibility."""
        if not checked:
            self.target_curve.clear()
            
    def toggle_lux1(self, checked):
        """Toggle LUX1 curve visibility."""
        if not checked:
            self.lux1_curve.clear()
            
    def toggle_lux2(self, checked):
        """Toggle LUX2 curve visibility."""
        if not checked:
            self.lux2_curve.clear()
            
    def toggle_lux3(self, checked):
        """Toggle LUX3 curve visibility."""
        if not checked:
            self.lux3_curve.clear()
            
    def update_from_adcs_data(self, adcs_data):
        """Update the graph with actual ADCS data from the server broadcast."""
        try:
            # Extract Z-axis angle (primary control angle) - remove any unit suffixes
            angle_z_str = adcs_data.get('angle_z', '0.0')
            z_angle = float(str(angle_z_str).replace('°', '').strip()) if angle_z_str != '--' else self.current_z_angle
            
            # Extract LUX values - remove any unit suffixes  
            lux1_str = adcs_data.get('lux1', '0.0')
            lux1 = float(str(lux1_str).replace('lux', '').strip()) if lux1_str != '--' else self.current_lux1
            
            lux2_str = adcs_data.get('lux2', '0.0')
            lux2 = float(str(lux2_str).replace('lux', '').strip()) if lux2_str != '--' else self.current_lux2
            
            lux3_str = adcs_data.get('lux3', '0.0')
            lux3 = float(str(lux3_str).replace('lux', '').strip()) if lux3_str != '--' else self.current_lux3
            
            # Target angle comes from control widget (will be updated separately)
            target = self.current_target
            
            # Add the data point with actual sensor values
            self.add_data_point(
                z_angle=z_angle,
                target_angle=target,
                lux1=lux1,
                lux2=lux2,
                lux3=lux3
            )
            
        except (ValueError, TypeError) as e:
            # Handle conversion errors gracefully - use previous values
            print(f"ADCS Graph: Error parsing data: {e}")
            self.add_data_point()  # Add point with current values
        
    def update_target_angle(self, target_angle):
        """Update the target angle value."""
        self.current_target = float(target_angle)


# Example usage and testing
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import random
    
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("ADCS Graph Test")
    main_window.setGeometry(100, 100, 1000, 600)
    
    # Create and set the graph widget
    graph_widget = ADCSGraphWidget()
    main_window.setCentralWidget(graph_widget)
    
    # Create a timer to simulate incoming data
    test_timer = QTimer()
    def add_test_data():
        # Simulate some realistic ADCS data
        z_angle = 45 + 10 * np.sin(time.time() * 0.5) + random.uniform(-2, 2)
        target = 45 + 5 * np.sin(time.time() * 0.2)
        lux1 = 1000 + 200 * np.sin(time.time() * 0.3) + random.uniform(-50, 50)
        lux2 = 800 + 150 * np.cos(time.time() * 0.4) + random.uniform(-30, 30)
        lux3 = 1200 + 100 * np.sin(time.time() * 0.6) + random.uniform(-40, 40)
        
        graph_widget.add_data_point(
            z_angle=z_angle,
            target_angle=target,
            lux1=lux1,
            lux2=lux2,
            lux3=lux3
        )
    
    test_timer.timeout.connect(add_test_data)
    test_timer.start(200)  # Add test data every 200ms
    
    main_window.show()
    sys.exit(app.exec())
