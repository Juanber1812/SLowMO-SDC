# angular_position_plotter.py
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from collections import deque
import time
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR, GRAPH_MODE_COLORS
)

# === Font size configuration ===
AXIS_LABEL_SIZE = 9      # Adjust axis label font size
AXIS_NUMBER_SIZE = 9     # Adjust axis number/tick font size

# === Spin Plot Configuration ===
SPIN_Y_MIN = -80        # Minimum Y-axis value (degrees)
SPIN_Y_MAX = 80         # Maximum Y-axis value (degrees)
SPIN_X_WINDOW = 5       # Time window in seconds
AVERAGE_TIME_WINDOW = 5.0  # Time window for calculating averages (seconds)

class AngularPositionPlotter(QFrame):
    def __init__(self):
        super().__init__()
        pg.setConfigOptions(antialias=True)
        
        self.axis_label_size = AXIS_LABEL_SIZE
        self.axis_number_size = AXIS_NUMBER_SIZE

        self.y_axis_min = SPIN_Y_MIN
        self.y_axis_max = SPIN_Y_MAX
        self.x_axis_window = SPIN_X_WINDOW
        self.average_time_window = AVERAGE_TIME_WINDOW

        self.bg_color = PLOT_BACKGROUND
        self.line_color = GRAPH_MODE_COLORS["SPIN MODE"]

        # Current angle values and average metric
        self.current_angle = 0.0
        self.average_angle = 0.0
        
        # Recording attributes
        self.is_recording = False
        self.recorded_data = []

        # Data storage
        self.data = deque(maxlen=200)
        self.time_data = deque(maxlen=200)
        self.start_time = time.time()
        
        # Variables for calculating differences (if needed later)
        self.last_angle = None
        self.last_time = None

        self.setMinimumSize(384, 216)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {self.bg_color}; border: none;")

        # Create layout and plot widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 10, 32)
        layout.setSpacing(2)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(self.bg_color)
        self.setup_plot()
        layout.addWidget(self.plot_widget)

        # Create angle plot curve (only one curve, left Y-axis) with a label for the legend.
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=self.line_color, width=4),
            symbol=None,
            symbolSize=3,
            symbolBrush=self.line_color,
            name='Angle (deg)'     # This is the label shown in the legend.
        )


        # Setup redraw timer
        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_interval_ms = 10   # 100 Hz (10 ms)
        
        # Initial draw
        self.redraw()

    def setup_plot(self):
        """Configure the PyQtGraph plot appearance"""
        
        # Font for the main axis labels ("Angle (deg)", "Time (s)")
        axis_label_font = QFont(FONT_FAMILY, self.axis_label_size)

        # Configure Left Axis Label
        self.plot_widget.setLabel('left', 'Angle (deg)', color=self.line_color) # Set text and color
        left_axis = self.plot_widget.getAxis('left')
        if hasattr(left_axis, 'label') and left_axis.label is not None: # 'label' is the TextItem
            left_axis.label.setFont(axis_label_font) # Apply the font (family and size)

        # Configure Bottom Axis Label
        self.plot_widget.setLabel('bottom', 'Time (s)', color=self.line_color) # Set text and color
        bottom_axis = self.plot_widget.getAxis('bottom')
        if hasattr(bottom_axis, 'label') and bottom_axis.label is not None: # 'label' is the TextItem
            bottom_axis.label.setFont(axis_label_font) # Apply the font (family and size)

        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        self.plot_widget.getAxis('left').setPen(color=self.line_color, width=1)
        self.plot_widget.getAxis('bottom').setPen(color=self.line_color, width=1)
        
        # For axis tick numbers - this part was already correct
        tick_font = QFont(FONT_FAMILY, self.axis_number_size)
        self.plot_widget.getAxis('left').setTickFont(tick_font)
        self.plot_widget.getAxis('left').setTextPen(color=self.line_color) # Ensure tick text color is set
        self.plot_widget.getAxis('bottom').setTickFont(tick_font)
        self.plot_widget.getAxis('bottom').setTextPen(color=self.line_color) # Ensure tick text color is set
        
        self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
        self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
        self.plot_widget.setLimits(yMin=self.y_axis_min, yMax=self.y_axis_max)
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=False)
        # Set tick spacing if desired
        self.plot_widget.getAxis('left').setTickSpacing(major=45, minor=15)
        self.plot_widget.getAxis('bottom').setTickSpacing(major=1.0, minor=0.5)

    def showEvent(self, event):
        super().showEvent(event)
        self.plot_widget.getViewBox().sigResized.connect(self.redraw)
        self._redraw_timer.start(self._redraw_interval_ms)

    def hideEvent(self, event):
        self._redraw_timer.stop()
        super().hideEvent(event)

    def calculate_average_angle(self):
        """Calculate average angle over the configurable time window"""
        if len(self.time_data) == 0 or len(self.data) == 0:
            return 0.0
        
        current_time = self.time_data[-1]
        window_ago = current_time - self.average_time_window
        
        recent_angles = []
        for i in range(len(self.time_data) - 1, -1, -1):
            if self.time_data[i] >= window_ago:
                recent_angles.append(self.data[i])
            else:
                break
        
        if len(recent_angles) == 0:
            return self.current_angle
        return float(np.mean(recent_angles))

    def update(self, rvec, tvec, timestamp=None):
        """Update the plot with new spin (angle) data"""
        if timestamp is None:
            timestamp = time.time()
        elapsed = float(timestamp - self.start_time)
        # Compute angle in degrees from rvec (using second component)
        angle_deg = float(np.degrees(rvec[1]))
        
        self.current_angle = angle_deg
        self.time_data.append(elapsed)
        self.data.append(angle_deg)
        
        self.last_angle = angle_deg
        self.last_time = elapsed
        
        # Calculate average angle over the latest window
        self.average_angle = self.calculate_average_angle()
        # Redraw will be triggered by the timer

    def redraw(self):
        """Redraw the plot with current angle data"""
        if len(self.time_data) > 0 and len(self.data) > 0:
            time_array = np.array(self.time_data, dtype=float).flatten()
            data_array = np.array(self.data, dtype=float).flatten()
            
            self.plot_curve.setData(time_array, data_array)
            
            if time_array[-1] > self.x_axis_window:
                x_min = time_array[-1] - self.x_axis_window
                x_max = time_array[-1]
                self.plot_widget.setXRange(x_min, x_max, padding=0)
            else:
                self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
            
            self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
        else:
            self.plot_curve.clear()
            self.plot_widget.setXRange(0, self.x_axis_window, padding=0)
            self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)

    def set_average_time_window(self, window_seconds):
        self.average_time_window = window_seconds

    def set_redraw_rate(self, rate_hz: float):
        interval = max(1, int(1000.0 / rate_hz))
        self._redraw_interval_ms = interval
        self._redraw_timer.setInterval(interval)

    def clear_data(self):
        self.data.clear()
        self.time_data.clear()
        self.current_angle = 0.0
        self.average_angle = 0.0
        self.last_angle = None
        self.last_time = None
        self.start_time = time.time()
        self.plot_curve.clear()

    def start_recording(self):
        self.is_recording = True
        self.recorded_data = []

    def stop_recording(self):
        self.is_recording = False
        return self.recorded_data.copy()

    def set_y_range(self, y_min, y_max):
        self.y_axis_min = y_min
        self.y_axis_max = y_max
        self.plot_widget.setYRange(self.y_axis_min, self.y_axis_max, padding=0)
        self.plot_widget.setLimits(yMin=self.y_axis_min, yMax=self.y_axis_max)

    def set_x_window(self, window_seconds):
        self.x_axis_window = window_seconds

    def get_spin_metrics(self):
        return {
            'current': self.current_angle,
            'average': self.average_angle,
        }
