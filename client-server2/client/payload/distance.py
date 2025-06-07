import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QFrame, QSizePolicy, QWidget, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from collections import deque
import numpy as np
import time
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    GRAPH_MODE_COLORS
)

# === Font size configuration ===
AXIS_LABEL_SIZE = 9      # Change this value to adjust axis label font size
AXIS_NUMBER_SIZE = 9     # Change this value to adjust axis number/tick font size

# === Distance Plot Configuration ===
DISTANCE_Y_MIN = 0       # Minimum Y-axis value (meters)
DISTANCE_Y_MAX = 2       # Maximum Y-axis value (meters)
VELOCITY_Y_MIN = -5      # Minimum velocity Y-axis value (m/s)
VELOCITY_Y_MAX = 5       # Maximum velocity Y-axis value (m/s)
DISTANCE_X_WINDOW = 10   # Time window in seconds
AVERAGE_TIME_WINDOW = 5.0  # Time window for calculating averages (seconds)

class RelativeDistancePlotter(QFrame):
    def __init__(self):
        super().__init__()
        # Set global PyQtGraph options
        pg.setConfigOptions(antialias=True)
        
        # === Customizable label and tick sizes ===
        self.axis_label_size = AXIS_LABEL_SIZE
        self.axis_number_size = AXIS_NUMBER_SIZE

        # === Customizable axis ranges ===
        self.y_axis_min = DISTANCE_Y_MIN
        self.y_axis_max = DISTANCE_Y_MAX
        self.velocity_y_min = VELOCITY_Y_MIN
        self.velocity_y_max = VELOCITY_Y_MAX
        self.x_axis_window = DISTANCE_X_WINDOW
        self.average_time_window = AVERAGE_TIME_WINDOW  # Configurable averaging window

        # === Theme colors from theme.py ===
        self.bg_color = PLOT_BACKGROUND
        self.line_color = GRAPH_MODE_COLORS["DISTANCE MEASURING MODE"]
        self.velocity_line_color = PLOT_LINE_SECONDARY  # Different color for velocity
        self.tick_color = self.line_color
        self.grid_color = self.line_color

        # === Current values ===
        self.current_distance = 0.0
        self.current_velocity = 0.0
        
        # === Average distance metrics ===
        self.average_distance = 0.0    # Average distance over configurable time window
        self.average_velocity = 0.0    # Average velocity over configurable time window
        
        # === Recording attributes ===
        self.is_recording = False
        self.recorded_data = []

        # === Data storage ===
        self.data = deque(maxlen=500)
        self.velocity_data = deque(maxlen=500)
        self.time_data = deque(maxlen=500)
        self.start_time = time.time()
        
        # === Velocity calculation variables ===
        self.last_distance = None
        self.last_time = None

        # Set widget properties
        self.setMinimumSize(384, 216)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {self.bg_color}; border: none;")

        # Create the layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 10, 32)
        layout.setSpacing(0)

        # Create PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(self.bg_color)
        
        # Configure plot appearance
        self.setup_plot()

        # Add widgets to layout
        layout.addWidget(self.plot_widget)

        # Create distance plot curve (left Y-axis)
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=self.line_color, width=4),
            symbol=None,
            symbolSize=3,
            symbolBrush=self.line_color,
            name='Distance (m)'
        )

        # Create second Y-axis for velocity
        self.velocity_viewbox = pg.ViewBox()
        self.plot_widget.scene().addItem(self.velocity_viewbox)
        self.plot_widget.getAxis('right').linkToView(self.velocity_viewbox)
        self.velocity_viewbox.setXLink(self.plot_widget)

        # Create velocity plot curve (right Y-axis)
        self.velocity_curve = pg.PlotCurveItem(
            pen=pg.mkPen(color=self.velocity_line_color, width=2),
            name='Velocity (m/s)'
        )
        self.velocity_viewbox.addItem(self.velocity_curve)



        # Setup redraw timer
        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_interval_ms = 10   # 100 Hz (10 ms)
        
        # Initial draw
        self.redraw()

    def setup_plot(self):
        """Configure the PyQtGraph plot appearance"""
        # Configure plot labels
        self.plot_widget.setLabel('left', 'Distance (m)', color=self.tick_color, size=f'{self.axis_label_size}pt')
        self.plot_widget.setLabel('right', 'Velocity (m/s)', color=self.velocity_line_color, size=f'{self.axis_label_size}pt')
        self.plot_widget.setLabel('bottom', 'Time (s)', color=self.tick_color, size=f'{self.axis_label_size}pt')
        
        # Show grid
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Style the axes
        self.plot_widget.getAxis('left').setPen(color=self.tick_color, width=1)
        self.plot_widget.getAxis('right').setPen(color=self.velocity_line_color, width=1)
        self.plot_widget.getAxis('bottom').setPen(color=self.tick_color, width=1)
        self.plot_widget.getAxis('left').setTextPen(color=self.tick_color)
        self.plot_widget.getAxis('right').setTextPen(color=self.velocity_line_color)
        self.plot_widget.getAxis('bottom').setTextPen(color=self.tick_color)
        
        # Set tick font size
        font = QFont(FONT_FAMILY, self.axis_number_size)
        self.plot_widget.getAxis('left').setTickFont(font)
        self.plot_widget.getAxis('right').setTickFont(font)
        self.plot_widget.getAxis('bottom').setTickFont(font)
        
        # Set fixed Y-axis ranges
        self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
        self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
        
        # Lock Y-axis range and enable X-axis auto-scrolling
        self.plot_widget.setLimits(yMin=self.y_axis_min, yMax=self.y_axis_max)
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=False)
        
        # Set tick spacing
        self.plot_widget.getAxis('left').setTickSpacing(major=0.5, minor=0.1)
        self.plot_widget.getAxis('right').setTickSpacing(major=2.0, minor=0.5)
        self.plot_widget.getAxis('bottom').setTickSpacing(major=1.0, minor=0.5)

        # Show right axis
        self.plot_widget.showAxis('right')

    def update_views(self):
        """Update the velocity viewbox to match the main plot"""
        self.velocity_viewbox.setGeometry(self.plot_widget.getViewBox().sceneBoundingRect())
        self.velocity_viewbox.linkedViewChanged(self.plot_widget.getViewBox(), self.velocity_viewbox.XAxis)

    def showEvent(self, event):
        super().showEvent(event)
        # Connect viewbox synchronization
        self.plot_widget.getViewBox().sigResized.connect(self.update_views)
        # Start throttled redraws when widget appears
        self._redraw_timer.start(self._redraw_interval_ms)

    def hideEvent(self, event):
        # Stop redraws immediately when widget is hidden
        self._redraw_timer.stop()
        super().hideEvent(event)

    def calculate_average_distance(self):
        """Calculate average distance for all points in the configurable time window"""
        if len(self.time_data) == 0 or len(self.data) == 0:
            return 0.0
        
        current_time = self.time_data[-1]  # Most recent timestamp
        window_ago = current_time - self.average_time_window
        
        # Find all data points within the time window
        recent_distances = []
        for i in range(len(self.time_data) - 1, -1, -1):  # Go backwards from most recent
            if self.time_data[i] >= window_ago:
                recent_distances.append(self.data[i])
            else:
                break  # Stop when we go beyond the time window
        
        if len(recent_distances) == 0:
            return self.current_distance  # Return current if no data in time window
        
        return float(np.mean(recent_distances))

    def calculate_average_velocity(self):
        """Calculate average velocity for all points in the configurable time window"""
        if len(self.time_data) == 0 or len(self.velocity_data) == 0:
            return 0.0
        
        current_time = self.time_data[-1]  # Most recent timestamp
        window_ago = current_time - self.average_time_window
        
        # Find all velocity points within the time window
        recent_velocities = []
        for i in range(len(self.time_data) - 1, -1, -1):  # Go backwards from most recent
            if self.time_data[i] >= window_ago:
                recent_velocities.append(self.velocity_data[i])
            else:
                break  # Stop when we go beyond the time window
        
        if len(recent_velocities) == 0:
            return self.current_velocity  # Return current if no data in time window
        
        return float(np.mean(recent_velocities))

    def update(self, rvec, tvec, timestamp=None):
        """Update the plot with new distance data"""
        if timestamp is None:
            timestamp = time.time()
        elapsed = timestamp - self.start_time
        distance = float(np.linalg.norm(tvec))

        # Calculate velocity (change in distance over time)
        velocity = 0.0
        if self.last_distance is not None and self.last_time is not None:
            time_diff = elapsed - self.last_time
            if time_diff > 0:
                velocity = (distance - self.last_distance) / time_diff

        # Store and record every point
        self.current_distance = distance
        self.current_velocity = velocity
        self.time_data.append(elapsed)
        self.data.append(distance)
        self.velocity_data.append(velocity)
        
        # Update last values for next velocity calculation
        self.last_distance = distance
        self.last_time = elapsed
        
        # Calculate averages
        self.average_distance = self.calculate_average_distance()
        self.average_velocity = self.calculate_average_velocity()
        
        # Timer will call redraw()

    def redraw(self):
        """Redraw the plot with current data"""
        if len(self.time_data) > 0 and len(self.data) > 0:
            # Convert deques to numpy arrays for plotting
            time_array = np.array(self.time_data)
            data_array = np.array(self.data)
            velocity_array = np.array(self.velocity_data)
            
            # Update the distance curve
            self.plot_curve.setData(time_array, data_array)
            
            # Update the velocity curve
            self.velocity_curve.setData(time_array, velocity_array)
            
            # Set X-axis range for scrolling window
            if time_array[-1] > self.x_axis_window:
                x_min = time_array[-1] - self.x_axis_window
                x_max = time_array[-1]
                self.plot_widget.setXRange(x_min, x_max, padding=0)
            else:
                self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
            
            # Keep Y-axis fixed for distance
            self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
            
            # Keep Y-axis fixed for velocity
            self.velocity_viewbox.setYRange(self.velocity_y_min, self.velocity_y_max, padding=0)
            
            # Update views
            self.update_views()
        else:
            # Clear plots if no data
            self.plot_curve.clear()
            self.velocity_curve.clear()
            self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
            self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
            self.velocity_viewbox.setYRange(self.velocity_y_min, self.velocity_y_max, padding=0)

    def set_average_time_window(self, window_seconds):
        """Set the time window for calculating averages"""
        self.average_time_window = window_seconds

    def set_redraw_rate(self, rate_hz: float):
        """Adjust the redraw frequency (Hz)."""
        interval = max(1, int(1000.0 / rate_hz))
        self._redraw_interval_ms = interval
        self._redraw_timer.setInterval(interval)

    def clear_data(self):
        """Clear all plot data"""
        self.data.clear()
        self.velocity_data.clear()
        self.time_data.clear()
        self.current_distance = 0.0
        self.current_velocity = 0.0
        self.average_distance = 0.0
        self.average_velocity = 0.0
        self.last_distance = None
        self.last_time = None
        self.start_time = time.time()
        # Clear reference to distance_label if it doesn't exist yet
        if hasattr(self, 'distance_label'):
            self.distance_label.setText("0.0000 m")
        self.plot_curve.clear()
        self.velocity_curve.clear()

    def start_recording(self):
        """Start recording distance data"""
        self.is_recording = True
        self.recorded_data = []

    def stop_recording(self):
        """Stop recording and return recorded data"""
        self.is_recording = False
        return self.recorded_data.copy()

    def set_y_range(self, y_min, y_max):
        """Set custom Y-axis range"""
        self.y_axis_min = y_min
        self.y_axis_max = y_max
        self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
        self.plot_widget.setLimits(yMin=self.y_axis_min, yMax=self.y_axis_max)

    def set_x_window(self, window_seconds):
        """Set the time window for X-axis"""
        self.x_axis_window = window_seconds

    def get_distance_metrics(self):
        """Get comprehensive distance and velocity metrics"""
        return {
            'current': self.current_distance,
            'average': self.average_distance,
            'current_velocity': self.current_velocity,
            'average_velocity': self.average_velocity,
        }
