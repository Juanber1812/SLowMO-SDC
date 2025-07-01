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
        BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, TEXT_COLOR, TEXT_SECONDARY, 
        BOX_TITLE_COLOR, LABEL_COLOR, GRID_COLOR, TICK_COLOR, 
        PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
        BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
        BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
        FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
        ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
        BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, BUTTON_HEIGHT
    )
except ImportError:
    # Fallback colors
    BACKGROUND = "#000000"
    BOX_BACKGROUND = "#050A1F"
    PLOT_BACKGROUND = "#000000"
    TEXT_COLOR = "#00FFFF"
    TEXT_SECONDARY = "#60AFFF"
    BOX_TITLE_COLOR = "#00FFFF"
    LABEL_COLOR = "#60AFFF"
    GRID_COLOR = "#001A33"
    TICK_COLOR = "#007FFF"
    PLOT_LINE_PRIMARY = "#00FFFF"
    PLOT_LINE_SECONDARY = "#007FFF"
    PLOT_LINE_ALT = "#33FFDD"
    BUTTON_COLOR = "#00224D"
    BUTTON_HOVER = "#00BFFF"
    BUTTON_DISABLED = "#001126"
    BUTTON_TEXT = "#FFFFFF"
    BORDER_COLOR = "#007FFF"
    BORDER_ERROR = "#FF3333"
    BORDER_HIGHLIGHT = "#00FFFF"
    FONT_FAMILY = "Consolas, 'Courier New', monospace"
    FONT_SIZE_NORMAL = 10
    FONT_SIZE_LABEL = 9
    FONT_SIZE_TITLE = 11
    ERROR_COLOR = "#FF3333"
    SUCCESS_COLOR = "#33FFDD"
    WARNING_COLOR = "#FFD700"
    BORDER_WIDTH = 1
    BORDER_RADIUS = 4
    PADDING_NORMAL = 8
    BUTTON_HEIGHT = 32

class ADCSGraphWidget(QWidget):
    """
    A compact widget that plots live ADCS data including:
    - Z-axis angle from MPU - primary control angle
    - Target angle value
    All plotted against time with fixed ranges. Optimized for row 3 layout.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ADCSGraphWidget")
        
        # Set size constraints to prevent overlap - CHANGE THESE VALUES TO RESIZE THE WIDGET
        self.setMaximumSize(500, 180)  # Width: 500px, Height: 180px - MODIFY HERE
        self.setMinimumSize(400, 150)  # Width: 400px, Height: 150px - MODIFY HERE
        
        # Data storage - using deque for efficient append/pop operations
        self.max_points = 300  # Reduced for better performance in compact layout
        self.time_data = deque(maxlen=self.max_points)
        
        # Angle data only (no LUX sensors)
        self.z_angle_data = deque(maxlen=self.max_points)
        self.target_angle_data = deque(maxlen=self.max_points)
        
        # Current values
        self.current_z_angle = 0.0
        self.current_target = 0.0
        
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
        self.plot_widget.setBackground(PLOT_BACKGROUND)
        self.plot_widget.setLabel('left', 'Angle (°)', color=TEXT_COLOR, size=f'{FONT_SIZE_LABEL}pt')
        self.plot_widget.setLabel('bottom', 'Time (s)', color=TEXT_COLOR, size=f'{FONT_SIZE_LABEL}pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getPlotItem().getViewBox().setBackgroundColor(PLOT_BACKGROUND)
        
        # Set fixed ranges - CHANGE THESE VALUES TO MODIFY PLOT RANGES
        self.plot_widget.setXRange(0, 10)  # Time: 0-10 seconds - MODIFY HERE
        self.plot_widget.setYRange(-180, 180)  # Angle: -180 to +180 degrees - MODIFY HERE
        self.plot_widget.setMinimumHeight(200)  # Plot height: 120px minimum - MODIFY HERE
        self.plot_widget.setMinimumWidth(400)  # Plot width: 400px minimum - MODIFY HERE        
        # Disable auto-ranging to keep fixed ranges
        self.plot_widget.disableAutoRange()
        
        # Set custom ticks for time axis (1, 2, 3, 4, 5 seconds)
        time_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        time_axis.setTicks([[(i, str(i)) for i in range(0, 11)]])  # 0, 1, 2, ..., 10 seconds
        
        # Style the axes with theme colors and fonts
        for axis in ['left', 'bottom']:  # Only left and bottom axes now
            ax = self.plot_widget.plotItem.getAxis(axis)
            ax.setPen(color=BORDER_COLOR, width=BORDER_WIDTH)
            ax.setTextPen(color=TEXT_COLOR)
            ax.setStyle(tickFont=pg.QtGui.QFont(FONT_FAMILY, FONT_SIZE_LABEL))
        
        # Set grid pen color
        self.plot_widget.getPlotItem().getViewBox().setBackgroundColor(PLOT_BACKGROUND)
        
        # Initialize plot curves
        self.setup_plot_curves()
        
        plot_container.addWidget(self.plot_widget)
        
        main_layout.addLayout(plot_container, 4)  # Plot takes most space
        
        # Right side: Vertical checkbox panel (simplified)
        checkbox_panel = self.create_vertical_checkbox_panel()
        main_layout.addWidget(checkbox_panel, 1)  # Checkboxes take less space
        
    def create_vertical_checkbox_panel(self):
        """Create vertical panel with checkboxes for toggling plot lines (angles only)."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(4)  # Reduced spacing
        layout.setContentsMargins(6, 6, 6, 6)  # Reduced margins
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Only angle checkboxes now
        self.z_angle_checkbox = QCheckBox("Z-Angle")
        self.z_angle_checkbox.setChecked(True)
        self.z_angle_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {PLOT_LINE_PRIMARY}; 
                font-family: {FONT_FAMILY}; 
                font-size: {FONT_SIZE_LABEL}pt;
                spacing: 3px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: {BORDER_WIDTH}px solid {PLOT_LINE_PRIMARY};
                border-radius: 2px;
                background-color: {BOX_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {PLOT_LINE_PRIMARY};
            }}
        """)
        self.z_angle_checkbox.toggled.connect(self.toggle_z_angle)
        layout.addWidget(self.z_angle_checkbox)
        
        self.target_checkbox = QCheckBox("Target")
        self.target_checkbox.setChecked(True)
        self.target_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {WARNING_COLOR}; 
                font-family: {FONT_FAMILY}; 
                font-size: {FONT_SIZE_LABEL}pt;
                spacing: 3px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: {BORDER_WIDTH}px solid {WARNING_COLOR};
                border-radius: 2px;
                background-color: {BOX_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {WARNING_COLOR};
            }}
        """)
        self.target_checkbox.toggled.connect(self.toggle_target)
        layout.addWidget(self.target_checkbox)
        
        # Add clear button below checkboxes
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 4px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_LABEL}pt;
                min-height: 20px;
                max-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
            QPushButton:pressed {{
                background-color: {BORDER_HIGHLIGHT};
                color: black;
            }}
        """)
        clear_btn.clicked.connect(self.clear_data)
        layout.addWidget(clear_btn)
        
        layout.addStretch()  # Push content to top
        
        return panel
        
    def setup_plot_curves(self):
        """Initialize plot curves with theme colors and styles (angles only)."""
        # Z-axis angle curve - electric cyan
        self.z_angle_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=PLOT_LINE_PRIMARY, width=2),
            name='Z-Axis Angle'
        )
        
        # Target angle curve - gold/warning color with dashed line
        self.target_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=WARNING_COLOR, width=2, style=Qt.PenStyle.DashLine),
            name='Target Angle'
        )
        
    def add_data_point(self, z_angle=None, target_angle=None):
        """Add a new data point to the plot with optimized 10-second rolling window."""
        current_time = time.time() - self.start_time
        
        # Update current values if provided
        if z_angle is not None:
            self.current_z_angle = float(z_angle)
        if target_angle is not None:
            self.current_target = float(target_angle)
            
        # Add data points
        self.time_data.append(current_time)
        self.z_angle_data.append(self.current_z_angle)
        self.target_angle_data.append(self.current_target)
        
        # Remove old data points beyond 10 seconds to maintain fixed window
        while len(self.time_data) > 1 and (current_time - self.time_data[0]) > 10.0:
            self.time_data.popleft()
            self.z_angle_data.popleft()
            self.target_angle_data.popleft()
    
    def update_plot(self):
        """Update the plot with current data using fixed ranges and time window."""
        if len(self.time_data) < 2:
            return
            
        # Convert deques to numpy arrays for plotting
        time_array = np.array(self.time_data)
        
        # Keep fixed ranges - no automatic scaling
        if len(time_array) > 0:
            current_time = time_array[-1]
            window_start = max(0, current_time - 10.0)
            # Update time range to show current 10-second window
            self.plot_widget.setXRange(window_start, current_time + 0.5)
        
        # Update angle curves with fixed Y range
        if self.z_angle_checkbox.isChecked():
            z_angle_array = np.array(self.z_angle_data)
            self.z_angle_curve.setData(time_array, z_angle_array)
        else:
            self.z_angle_curve.clear()
            
        if self.target_checkbox.isChecked():
            target_array = np.array(self.target_angle_data)
            self.target_curve.setData(time_array, target_array)
        else:
            self.target_curve.clear()
        
    def clear_data(self):
        """Clear all data and reset the plot."""
        self.time_data.clear()
        self.z_angle_data.clear()
        self.target_angle_data.clear()
        
        # Reset start time
        self.start_time = time.time()
        
        # Clear all curves
        self.z_angle_curve.clear()
        self.target_curve.clear()
        
    # Toggle methods for checkboxes (simplified)
    def toggle_z_angle(self, checked):
        """Toggle Z-axis angle curve visibility."""
        if not checked:
            self.z_angle_curve.clear()
            
    def toggle_target(self, checked):
        """Toggle target angle curve visibility."""
        if not checked:
            self.target_curve.clear()
            
    def update_from_adcs_data(self, adcs_data):
        """Update the graph with actual ADCS data from the server broadcast."""
        try:
            # Extract Z-axis angle (primary control angle) - remove any unit suffixes
            angle_z_str = adcs_data.get('angle_z', '0.0')
            z_angle = float(str(angle_z_str).replace('°', '').strip()) if angle_z_str != '--' else self.current_z_angle
            
            # Target angle comes from control widget (will be updated separately)
            target = self.current_target
            
            # Add the data point with actual sensor values (angles only)
            self.add_data_point(
                z_angle=z_angle,
                target_angle=target
            )
            
        except (ValueError, TypeError) as e:
            # Handle conversion errors gracefully - use previous values
            print(f"ADCS Graph: Error parsing data: {e}")
            self.add_data_point()  # Add point with current values
        
    def update_target_angle(self, target_angle):
        """Update the target angle value."""
        self.current_target = float(target_angle)

