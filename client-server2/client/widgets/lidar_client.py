import sys
import time
# import numpy as np # No longer needed for plotting
import logging
# import pyqtgraph as pg # No longer needed
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
    lidar_metrics_received = pyqtSignal(dict) # Changed signal to accept a dictionary
    back_button_clicked = pyqtSignal()
    lidar_start_requested = pyqtSignal()
    lidar_stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        # Deques for history are no longer needed here as server sends average
        # self.distance_history = deque(maxlen=50)
        # self.timestamp_history = deque(maxlen=50)
        self.data_mutex = QMutex()

        # Recording attributes
        self.is_recording = False
        # Store (timestamp, live_distance_cm, average_distance_cm_5s)
        self.recorded_data = [] 

        # Initialize UI (plot initialization is removed)
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
        self.big_lidar_button = QPushButton("LIDAR\nMetrics Monitor") # Updated button text
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
        
        # Page 2: LIDAR Interface (Metrics Display)
        self.lidar_page = QWidget()
        main_lidar_layout = QVBoxLayout(self.lidar_page)
        main_lidar_layout.setSpacing(PADDING_NORMAL)
        main_lidar_layout.setContentsMargins(PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL, PADDING_NORMAL)
        main_lidar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the metrics panel

        # Metrics display panel
        metrics_panel = QWidget()
        metrics_layout = QVBoxLayout(metrics_panel)
        metrics_layout.setSpacing(PADDING_NORMAL + 5) # Increased spacing
        metrics_layout.setContentsMargins(PADDING_LARGE, PADDING_LARGE, PADDING_LARGE, PADDING_LARGE) # More padding
        metrics_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {BOX_BACKGROUND};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
        """)
        metrics_panel.setMinimumWidth(300) # Ensure a decent width
        metrics_panel.setMaximumWidth(400) # Prevent it from becoming too wide

        metric_label_style = f"""
            QLabel {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_TITLE - 2}pt; /* Slightly larger font */
                padding: 5px;
                background-color: transparent; /* Ensure no double background */
                border: none; /* Ensure no double border */
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
                margin-top: {PADDING_NORMAL}px; /* Add some space above the back button */
            }}
            QPushButton:hover {{
                background-color: #cc0000;
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
        """Update display labels with new metrics data."""
        if not self.is_streaming: # Don't update if not supposed to be streaming
            return

        live_distance = metrics.get("live_distance_cm")
        avg_distance = metrics.get("average_distance_cm_5s")
        timestamp = time.time() # For recording

        if live_distance is not None:
            self.live_distance_label.setText(f"Live Distance: {live_distance:.2f} cm")
        else:
            self.live_distance_label.setText("Live Distance: N/A")

        if avg_distance is not None:
            self.average_distance_label.setText(f"5s Average: {avg_distance:.2f} cm")
        else:
            self.average_distance_label.setText("5s Average: N/A")

        if self.is_recording and live_distance is not None: # Also check avg_distance if you want to ensure both are present for recording
            with QMutexLocker(self.data_mutex):
                self.recorded_data.append((timestamp, live_distance, avg_distance if avg_distance is not None else -1.0)) # Store -1 if avg is None

    # update_plot method is removed

    def start_recording(self):
        if self.is_streaming:
            with QMutexLocker(self.data_mutex):
                self.is_recording = True
                self.recorded_data = []
                logging.info("LIDAR metrics recording started.")

    def stop_recording(self):
        data_to_save = []
        with QMutexLocker(self.data_mutex):
            self.is_recording = False
            if hasattr(self, 'recorded_data'):
                data_to_save = self.recorded_data.copy()
                self.recorded_data = []
        
        if data_to_save:
            self.save_lidar_recording(data_to_save)
        else:
            logging.info("No LIDAR metrics data to save.")


    def save_lidar_recording(self, data):
        import csv
        # Consider making filename more dynamic or configurable
        filename = "lidar_metrics_recording.csv" 
        try:
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Live Distance (cm)", "5s Average (cm)"])
                for row_data in data: # Ensure row_data is a tuple/list
                    writer.writerow(row_data)
            logging.info(f"LIDAR metrics recording saved to {filename}")
        except Exception as e:
            logging.error(f"Error saving LIDAR metrics recording: {e}")

    def stop_lidar(self): # Renamed from stop_lidar_process for clarity
        if self.is_streaming:
            self.toggle_lidar_streaming()

    def clear_history(self): # This method might be less relevant now
        with QMutexLocker(self.data_mutex):
            # self.distance_history.clear() # Removed
            # self.timestamp_history.clear() # Removed
            if hasattr(self, 'recorded_data'): # Clear any pending recorded data if needed
                 self.recorded_data = []
        self.live_distance_label.setText("Live Distance: -- cm")
        self.average_distance_label.setText("5s Average: -- cm")
        logging.info("LIDAR metrics display cleared.")
