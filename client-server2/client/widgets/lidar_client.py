import sys
import time
import numpy as np
import logging
import pyqtgraph as pg
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QTextEdit, QStackedWidget
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QMutex, QMutexLocker, QMargins
from PyQt6.QtGui import QFont, QColor, QPainter

# Import theme elements
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT, BUTTON_HEIGHT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR, SECOND_COLUMN,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE, BUTTON_HEIGHT
)

# LIDAR Plot Configuration
LIDAR_Y_MIN = 0      # Minimum Y-axis value (m)
LIDAR_Y_MAX = 2      # Maximum Y-axis value (m) - 200 cm equals 2 m
# X-axis fixed to 10 seconds range

class LidarWidget(QWidget):
    lidar_data_received = pyqtSignal(list)
    back_button_clicked = pyqtSignal()
    lidar_start_requested = pyqtSignal()  # Signal to start LIDAR
    lidar_stop_requested = pyqtSignal()   # Signal to stop LIDAR

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        # Use deque for history storage with a maximum length.
        self.distance_history = deque(maxlen=500)
        self.timestamp_history = deque(maxlen=500)
        self.data_mutex = QMutex()

        # Recording attributes – now controlled externally (no record button in this widget)
        self.is_recording = False
        self.recorded_data = []  # List of tuples (timestamp, distance in cm)

        # Initialize plot first, then UI
        self.init_plot()
        self.init_ui()
        
        # Connect the signal to update method
        self.lidar_data_received.connect(self.update_distances_slot)

    def init_plot(self):
        """Initialize PyQtGraph plot widget with consistent style and fixed 10 sec X-axis"""
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumSize(384, 216)
        self.plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plot_widget.setBackground(PLOT_BACKGROUND)
        self.plot_widget.setLabel('left', 'Distance (m)', color=TEXT_COLOR, size='12pt')
        self.plot_widget.setLabel('bottom', 'Time (s)', color=TEXT_COLOR, size='12pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getAxis('left').setPen(color=TICK_COLOR, width=1)
        self.plot_widget.getAxis('bottom').setPen(color=TICK_COLOR, width=1)
        self.plot_widget.getAxis('left').setTextPen(color=TICK_COLOR)
        self.plot_widget.getAxis('bottom').setTextPen(color=TICK_COLOR)
        self.plot_widget.getAxis('left').setGrid(128)
        self.plot_widget.getAxis('bottom').setGrid(128)
        
        # Create a continuous line (no symbols)
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=PLOT_LINE_PRIMARY, width=2),
            symbol=None,
            name='Distance'
        )
        
        self.plot_widget.setYRange(LIDAR_Y_MIN, LIDAR_Y_MAX, padding=0)
        # Fix X-axis to exactly 10 sec
        self.plot_widget.setXRange(0, 10, padding=0)
        self.plot_widget.setLimits(yMin=LIDAR_Y_MIN, yMax=LIDAR_Y_MAX)
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=False)

    def init_ui(self):
        """Build the widget UI with layout and style matching other graphs"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        main_layout.setSpacing(PADDING_NORMAL)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {BACKGROUND};")
        
        # Page 1: Big LIDAR Button (consistent styling)
        self.button_page = QWidget()
        button_layout = QVBoxLayout(self.button_page)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_lidar_button = QPushButton("LIDAR\nDistance Monitor")
        self.big_lidar_button.setObjectName("big_lidar_button")
        self.big_lidar_button.clicked.connect(self.show_lidar_interface)
        self.big_lidar_button.setMinimumSize(300, 200)
        self.big_lidar_button.setStyleSheet(f"""
            QPushButton#big_lidar_button {{
                background-color: {BUTTON_COLOR};
                color: {BUTTON_TEXT};
                border: 2px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                font-family: {FONT_FAMILY};
                font-size: 18px;
                font-weight: bold;
                padding: {PADDING_LARGE}px;
            }}
            QPushButton#big_lidar_button:hover {{
                background-color: {BUTTON_HOVER};
                border-color: {BORDER_HIGHLIGHT};
            }}
            QPushButton#big_lidar_button:pressed {{
                background-color: {PLOT_LINE_PRIMARY};
            }}
        """)
        button_layout.addWidget(self.big_lidar_button)
        self.stacked_widget.addWidget(self.button_page)
        
        # Page 2: LIDAR Interface
        self.lidar_page = QWidget()
        main_lidar_layout = QVBoxLayout(self.lidar_page)
        main_lidar_layout.setSpacing(PADDING_NORMAL)
        main_lidar_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        
        chart_controls_layout = QHBoxLayout()
        chart_controls_layout.setSpacing(PADDING_NORMAL)
        
        # Apply consistent styling to the plot widget container
        self.plot_widget.setStyleSheet(f"""
            QWidget {{
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {PLOT_BACKGROUND};
            }}
        """)
        
        # Control panel – without a record button (recording handled externally)
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setSpacing(PADDING_NORMAL)
        controls_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        controls_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {BOX_BACKGROUND};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
        """)
        
        self.distance_display = QTextEdit()
        self.distance_display.setReadOnly(True)
        self.distance_display.setFont(QFont(FONT_FAMILY, FONT_SIZE_NORMAL - 1))
        self.distance_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {STREAM_BACKGROUND};
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: {PADDING_NORMAL}px;
            }}
        """)
        self.distance_display.setText("Click 'Start LIDAR' to begin monitoring")
        self.distance_display.setMaximumHeight(80)
        
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.show_button_interface)
        self.back_button.setFixedHeight(BUTTON_HEIGHT)
        self.back_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: white;
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 4px 8px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL - 1}px;
            }}
            QPushButton:hover {{
                background-color: #cc0000;
            }}
        """)
        
        controls_layout.addWidget(self.distance_display)
        controls_layout.addStretch()
        controls_layout.addWidget(self.back_button)
        controls_panel.setFixedWidth(220)
        
        chart_controls_layout.addWidget(self.plot_widget, stretch=4)
        chart_controls_layout.addWidget(controls_panel, stretch=1)
        main_lidar_layout.addLayout(chart_controls_layout, stretch=1)
        
        self.stacked_widget.addWidget(self.lidar_page)
        main_layout.addWidget(self.stacked_widget)
        
        self.setLayout(main_layout)
        self.stacked_widget.setCurrentWidget(self.button_page)

    def show_lidar_interface(self):
        self.stacked_widget.setCurrentWidget(self.lidar_page)
        if not self.is_streaming:
            self.toggle_lidar_streaming()

    def show_button_interface(self):
        if self.is_streaming:
            self.toggle_lidar_streaming()
        self.stacked_widget.setCurrentWidget(self.button_page)
        self.back_button_clicked.emit()

    def toggle_lidar_streaming(self):
        with QMutexLocker(self.data_mutex):
            self.is_streaming = not self.is_streaming
            streaming_state = self.is_streaming
        
        if streaming_state:
            self.lidar_start_requested.emit()
            self.lidar_start_time = time.time()
        else:
            self.lidar_stop_requested.emit()

    def set_distances(self, distances):
        self.lidar_data_received.emit(distances.copy() if distances else [])

    def update_distances_slot(self, distances):
        """Update history and timestamps with new data"""
        if distances:
            timestamp = time.time()
            with QMutexLocker(self.data_mutex):
                for distance in distances:
                    self.distance_history.append(distance)
                    self.timestamp_history.append(timestamp)
                    if self.is_recording:
                        self.recorded_data.append((timestamp, distance))
                self.distances = list(self.distance_history)
            if self.is_streaming:
                self.update_plot()

    def update_plot(self):
        """Update the PyQtGraph plot with current distance data using a sliding 10-second window 
        and converting distances from cm to m. The average is computed over the last 5 seconds."""
        with QMutexLocker(self.data_mutex):
            current_distances = list(self.distance_history)
            current_timestamps = list(self.timestamp_history)
        
        if current_distances and current_timestamps:
            # Use absolute time axis (seconds since epoch)
            x_data = np.array(current_timestamps, dtype=float)
            current_time = current_timestamps[-1]
            x_min = current_time - 10  # 10-second window lower bound
            x_max = current_time       # current time as upper bound

            # Convert distances from cm to m.
            y_data = np.array(current_distances, dtype=float) / 100.0
            
            self.plot_curve.setData(x_data, y_data)
            self.plot_widget.setXRange(x_min, x_max, padding=0.02)
            self.plot_widget.setYRange(LIDAR_Y_MIN, LIDAR_Y_MAX, padding=0)

            # Latest distance (in m) and timestamp
            latest_distance_m = current_distances[-1] / 100.0
            latest_ts = time.strftime("%H:%M:%S", time.localtime(current_time))
            
            # Calculate the average over the last 5 seconds.
            recent_values = [current_distances[i] for i, t in enumerate(current_timestamps) if t >= current_time - 5]
            if recent_values:
                avg_distance_m = np.mean(recent_values) / 100.0
            else:
                avg_distance_m = latest_distance_m
            
            self.distance_display.setText(
                f"Current: {latest_distance_m:.3f} m at {latest_ts}\n"
                f"Average (last 5 sec): {avg_distance_m:.3f} m\n"
                f"Points: {len(current_distances)} | Streaming: {self.is_streaming}"
            )
            
        else:
            self.distance_display.setText("No data available")
            self.plot_curve.clear()
            self.plot_widget.setXRange(0, 10, padding=0)
            self.plot_widget.setYRange(LIDAR_Y_MIN, LIDAR_Y_MAX, padding=0)

    # Methods to control recording from the Graph Section
    def start_recording(self):
        """Called externally when the graph section record button is pressed.
        Begins recording LIDAR data if streaming is active."""
        if self.is_streaming:
            with QMutexLocker(self.data_mutex):
                self.is_recording = True
                self.recorded_data = []  # Clear previous recording

    def stop_recording(self):
        """Called externally when recording is stopped.
        Saves the recorded LIDAR data to a CSV file named 'lidar_otherinfo.csv'."""
        with QMutexLocker(self.data_mutex):
            self.is_recording = False
            data_to_save = self.recorded_data.copy()
            self.recorded_data = []
        if data_to_save:
            self.save_lidar_recording(data_to_save)

    def save_lidar_recording(self, data):
        """Save recorded LIDAR data (timestamp, distance in cm) to CSV file"""
        import csv
        filename = "lidar_otherinfo.csv"
        try:
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Distance (cm)"])
                for row in data:
                    writer.writerow(row)
            logging.info(f"LIDAR recording saved to {filename}")
        except Exception as e:
            logging.error(f"Error saving LIDAR recording: {e}")

    def stop_lidar(self):
        if self.is_streaming:
            self.toggle_lidar_streaming()

    def clear_history(self):
        with QMutexLocker(self.data_mutex):
            self.distance_history.clear()
            self.timestamp_history.clear()
            self.distances.clear()
        self.plot_curve.clear()
        self.distance_display.setText("History cleared - waiting for new data")
        if self.is_streaming:
            self.update_plot()
