import sys
import time
import csv # Make sure csv is imported
import os  # Make sure os is imported
import logging
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

# LIDAR Plot Configuration - These are no longer needed
# LIDAR_Y_MIN = 0
# LIDAR_Y_MAX = 2
# X-axis fixed to 10 seconds range

class LidarWidget(QWidget):
    lidar_metrics_received = pyqtSignal(dict)
    back_button_clicked = pyqtSignal()
    lidar_start_requested = pyqtSignal()
    lidar_stop_requested = pyqtSignal()
    recording_saved = pyqtSignal(str) # New signal for when CSV is saved

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        self.data_mutex = QMutex()

        self.live_distance_history = deque(maxlen=70) 

        # Recording attributes
        self.is_recording = False
        self.recording_start_time = 0 # To store the start time of a recording session
        # Store (relative_timestamp_seconds, live_distance_cm)
        self.recorded_data = [] 

        # Initialize UI
        self.init_ui()
        
        # Connect the signal to update method
        self.lidar_metrics_received.connect(self.update_metrics_slot)

    # init_plot method is removed

    def init_ui(self):
        """Build the widget UI with layout and style matching other graphs"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        main_layout.setSpacing(PADDING_NORMAL)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {BACKGROUND};")
        
        # Page 1: Big LIDAR Button
        self.button_page = QWidget()
        button_layout = QVBoxLayout(self.button_page)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_lidar_button = QPushButton("LIDAR\nMetrics Monitor")
        self.big_lidar_button.setObjectName("big_lidar_button")
        self.big_lidar_button.clicked.connect(self.show_lidar_interface)
        self.big_lidar_button.setMinimumSize(180, 250) 

        accent_color_big_button = BUTTON_COLOR 
        
        self.big_lidar_button.setStyleSheet(f"""
            QPushButton#big_lidar_button {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 2px solid {accent_color_big_button}; /* Accent color for border */
                border-radius: 2px; 
                padding: 8px 14px; 
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt; 
                font-weight: bold; 
            }}
            QPushButton#big_lidar_button:hover, QPushButton#big_lidar_button:pressed {{
                background-color: {BUTTON_HOVER};
                color: black; /* Text color for hover/pressed */
                border: 2px solid {BUTTON_HOVER}; /* Optional: change border on hover too */
            }}
            QPushButton#big_lidar_button:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777; /* Disabled text color from CameraControlsWidget */
                border: 2px solid #555; /* Disabled border color from CameraControlsWidget */
            }}
        """)
        button_layout.addWidget(self.big_lidar_button)
        self.stacked_widget.addWidget(self.button_page)
        
        # Page 2: LIDAR Interface (Metrics Display)
        self.lidar_page = QWidget()
        main_lidar_layout = QVBoxLayout(self.lidar_page)
        main_lidar_layout.setSpacing(PADDING_NORMAL)
        main_lidar_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        main_lidar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        metrics_panel = QWidget()
        metrics_layout = QVBoxLayout(metrics_panel)
        metrics_layout.setSpacing(PADDING_NORMAL + 5) 
        metrics_layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE) 
        metrics_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {BACKGROUND}; 
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
        """)
        metrics_panel.setMinimumWidth(200) 
        metrics_panel.setMaximumWidth(200) 

        metric_label_style = f"""
            QLabel {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_TITLE - 2}pt; 
                padding: 5px;
                background-color: transparent; 
                border: none; 
            }}
        """

        self.live_distance_label = QLabel("Live Distance: -- cm")
        self.live_distance_label.setStyleSheet(metric_label_style)
        self.live_distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.average_distance_label = QLabel("5s Average: -- cm")
        self.average_distance_label.setStyleSheet(metric_label_style)
        self.average_distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.show_button_interface)
        self.back_button.setFixedHeight(BUTTON_HEIGHT+10) 

        accent_color_back_button = ERROR_COLOR 

        self.back_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 2px solid {accent_color_back_button}; /* Accent color for border */
                border-radius: 2px; 
                padding: 8px 14px; 
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt; 
                margin-top: {PADDING_NORMAL}px; 
            }}
            QPushButton:hover, QPushButton:pressed {{
                background-color: {BUTTON_HOVER}; /* Or a hover color related to ERROR_COLOR if desired */
                color: black; /* Text color for hover/pressed */
                border: 2px solid {BUTTON_HOVER}; /* Optional: change border on hover too */
            }}
            QPushButton:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777; /* Disabled text color from CameraControlsWidget */
                border: 2px solid #555; /* Disabled border color from CameraControlsWidget */
            }}
        """)
        
        metrics_layout.addWidget(self.live_distance_label)
        metrics_layout.addWidget(self.average_distance_label)
        metrics_layout.addStretch()
        metrics_layout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_lidar_layout.addWidget(metrics_panel)
        
        self.stacked_widget.addWidget(self.lidar_page)
        main_layout.addWidget(self.stacked_widget)
        
        self.setLayout(main_layout)
        self.stacked_widget.setCurrentWidget(self.button_page)

    def show_lidar_interface(self):
        self.stacked_widget.setCurrentWidget(self.lidar_page)
        if not self.is_streaming:
            # Reset labels when showing interface before streaming starts
            self.live_distance_label.setText("Live Distance: -- cm")
            self.average_distance_label.setText("5s Average: -- cm")
            self.toggle_lidar_streaming() # Start streaming when interface is shown

    def show_button_interface(self):
        if self.is_streaming:
            self.toggle_lidar_streaming() # Stop streaming when going back
        self.stacked_widget.setCurrentWidget(self.button_page)
        self.back_button_clicked.emit()

    def toggle_lidar_streaming(self):
        with QMutexLocker(self.data_mutex):
            self.is_streaming = not self.is_streaming
            streaming_state = self.is_streaming
        
        if streaming_state:
            self.lidar_start_requested.emit()
            # self.lidar_start_time = time.time() # Not strictly needed without plot
        else:
            self.lidar_stop_requested.emit()

    def set_metrics(self, metrics_data: dict): # New method to receive data
        """Slot to receive metrics data from the main client."""
        if metrics_data:
            self.lidar_metrics_received.emit(metrics_data)

    def update_metrics_slot(self, metrics: dict):
        """Update display labels with new metrics data.
        Calculates 5s average client-side if not provided by server.
        Records live distance with relative timestamp if recording is active.
        """
        if not self.is_streaming: 
            return

        live_distance = metrics.get("live_distance_cm")
        server_avg_distance = metrics.get("average_distance_cm_5s")
        
        current_time = time.time() # Get current time for potential recording
        current_displayed_average = None

        if live_distance is not None:
            self.live_distance_label.setText(f"Live Distance: {live_distance:.2f} cm")
            with QMutexLocker(self.data_mutex):
                self.live_distance_history.append(live_distance)
        else:
            self.live_distance_label.setText("Live Distance: N/A")

        if server_avg_distance is not None:
            current_displayed_average = server_avg_distance
        else:
            with QMutexLocker(self.data_mutex):
                if self.live_distance_history: 
                    current_displayed_average = sum(self.live_distance_history) / len(self.live_distance_history)

        if current_displayed_average is not None:
            self.average_distance_label.setText(f"5s Average: {current_displayed_average:.2f} cm")
        else:
            self.average_distance_label.setText("5s Average: N/A")

        if self.is_recording and live_distance is not None:
            with QMutexLocker(self.data_mutex):
                # Calculate relative timestamp
                relative_timestamp = current_time - self.recording_start_time
                self.recorded_data.append((relative_timestamp, live_distance))

    # update_plot method is removed

    def start_recording(self):
        if self.is_streaming: 
            with QMutexLocker(self.data_mutex):
                self.is_recording = True
                self.recorded_data = [] 
                self.recording_start_time = time.time() # Set recording start time
                logging.info("LIDAR metrics recording started (live data only, relative timestamps).")
        else:
            logging.warning("LIDAR not streaming. Cannot start recording metrics.")

    def stop_recording(self):
        data_to_save = []
        was_recording = False 
        with QMutexLocker(self.data_mutex):
            was_recording = self.is_recording 
            self.is_recording = False
            if hasattr(self, 'recorded_data'):
                data_to_save = self.recorded_data.copy()
                self.recorded_data = [] 
        
        if was_recording and data_to_save: 
            self.save_lidar_recording(data_to_save)
        elif was_recording: 
            logging.info("LIDAR metrics recording stopped. No data to save.")


    def save_lidar_recording(self, data):
        rec_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "recordings") 
        )
        os.makedirs(rec_dir, exist_ok=True)

        timestr = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()) 
        fname = f"lidar_{timestr}.csv" 
        fullpath = os.path.join(rec_dir, fname)

        try:
            with open(fullpath, "w", newline="") as f:
                writer = csv.writer(f)
                # Updated headers for relative timestamp and live distance only
                writer.writerow(["timestamp", "value"])
                for row_data in data: 
                    writer.writerow(row_data)
            logging.info(f"LIDAR metrics recording saved to {fullpath}")
            self.recording_saved.emit(fullpath) 
        except Exception as e:
            logging.error(f"Error saving LIDAR metrics recording: {e}")

    def stop_lidar(self): # Renamed from stop_lidar_process for clarity
        if self.is_streaming:
            self.toggle_lidar_streaming()

    def clear_history(self):
        with QMutexLocker(self.data_mutex):
            self.live_distance_history.clear() # Clear the client-side history
            if hasattr(self, 'recorded_data'): 
                 self.recorded_data = []
        self.live_distance_label.setText("Live Distance: -- cm")
        self.average_distance_label.setText("5s Average: -- cm")
        logging.info("LIDAR metrics display and history cleared.")
