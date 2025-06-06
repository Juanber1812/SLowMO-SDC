import sys
import time
import numpy as np
import logging
import pyqtgraph as pg

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

class LidarWidget(QWidget):
    lidar_data_received = pyqtSignal(list)
    back_button_clicked = pyqtSignal()
    lidar_start_requested = pyqtSignal()  # Signal to start LIDAR
    lidar_stop_requested = pyqtSignal()   # Signal to stop LIDAR

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        self.distances = []
        self.distance_history = []
        self.max_history = 50
        self.data_mutex = QMutex()

        # Initialize plot first, then UI
        self.init_plot()
        self.init_ui()
        
        # Connect the signal to update method
        self.lidar_data_received.connect(self.update_distances_slot)

    def init_plot(self):
        """Initialize PyQtGraph plot widget"""
        # Set global PyQtGraph options
        pg.setConfigOptions(antialias=True)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(PLOT_BACKGROUND)
        
        # Configure plot
        self.plot_widget.setLabel('left', 'Distance (cm)', color=TEXT_COLOR, size='12pt')
        self.plot_widget.setLabel('bottom', 'Time Index', color=TEXT_COLOR, size='12pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Style the plot
        self.plot_widget.getAxis('left').setPen(color=TICK_COLOR, width=1)
        self.plot_widget.getAxis('bottom').setPen(color=TICK_COLOR, width=1)
        self.plot_widget.getAxis('left').setTextPen(color=TICK_COLOR)
        self.plot_widget.getAxis('bottom').setTextPen(color=TICK_COLOR)
        
        # Set grid color
        self.plot_widget.getAxis('left').setGrid(128)  # Grid opacity
        self.plot_widget.getAxis('bottom').setGrid(128)
        
        # Create plot curve
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=PLOT_LINE_PRIMARY, width=2),
            symbol='o',
            symbolSize=4,
            symbolBrush=PLOT_LINE_PRIMARY,
            name='Distance'
        )
        
        # Set initial ranges
        self.plot_widget.setXRange(0, 10, padding=0)
        self.plot_widget.setYRange(0, 100, padding=0.1)
        
        # Enable auto-ranging
        self.plot_widget.enableAutoRange('xy', True)

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create stacked widget to switch between button and graph views
        self.stacked_widget = QStackedWidget()
        
        # ========== PAGE 1: BIG LIDAR BUTTON ==========
        self.button_page = QWidget()
        button_layout = QVBoxLayout(self.button_page)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Big LIDAR button
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
                padding: 20px;
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

        # ========== PAGE 2: LIDAR INTERFACE ==========
        self.lidar_page = QWidget()
        main_lidar_layout = QVBoxLayout(self.lidar_page)
        main_lidar_layout.setSpacing(3)
        main_lidar_layout.setContentsMargins(3, 3, 3, 3)

        # Create horizontal layout for chart and controls
        chart_controls_layout = QHBoxLayout()
        chart_controls_layout.setSpacing(5)

        # Plot area (left side - takes most space)
        self.plot_widget.setStyleSheet(f"""
            QWidget {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {PLOT_BACKGROUND};
            }}
        """)
        chart_controls_layout.addWidget(self.plot_widget, stretch=3)  # Takes 3/4 of space

        # Control buttons panel (right side)
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setSpacing(5)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {BOX_BACKGROUND};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
        """)
        
        
        
        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.show_button_interface)
        self.back_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: white;
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 8px 12px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}px;
                min-height: 30px;
            }}
            QPushButton:hover {{
                background-color: #cc0000;
            }}
        """)

        # Add buttons to controls layout with spacing
        controls_layout.addStretch()  # Push back button to bottom
        controls_layout.addWidget(self.back_button)
        
        # Set fixed width for controls panel
        controls_panel.setFixedWidth(300)
        
        chart_controls_layout.addWidget(controls_panel)  # Takes 1/4 of space

        main_lidar_layout.addLayout(chart_controls_layout, stretch=1)

        # Distance data display (bottom - compact)
        self.distance_display = QTextEdit()
        self.distance_display.setReadOnly(True)
        self.distance_display.setMaximumHeight(60)  # Reduced height
        self.distance_display.setFont(QFont(FONT_FAMILY, FONT_SIZE_NORMAL - 1))  # Smaller font
        self.distance_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 3px;
            }}
        """)
        self.distance_display.setText("Click 'Start LIDAR' to begin monitoring")
        main_lidar_layout.addWidget(self.distance_display)
        
        self.stacked_widget.addWidget(self.lidar_page)

        # Add stacked widget to main layout
        main_layout.addWidget(self.stacked_widget)
        self.setLayout(main_layout)

        # Start with button interface
        self.stacked_widget.setCurrentWidget(self.button_page)

    def show_lidar_interface(self):
        """Switch to the LIDAR interface and start streaming"""
        print("[DEBUG] Switching to LIDAR interface")
        self.stacked_widget.setCurrentWidget(self.lidar_page)
        # Auto-start streaming when interface is shown
        if not self.is_streaming:
            self.toggle_lidar_streaming()

    def show_button_interface(self):
        """Switch back to the button interface and stop streaming"""
        print("[DEBUG] Switching to button interface")
        if self.is_streaming:
            self.toggle_lidar_streaming()  # Stop streaming
        self.stacked_widget.setCurrentWidget(self.button_page)

    def toggle_lidar_streaming(self):
        """Toggle LIDAR streaming on/off"""
        with QMutexLocker(self.data_mutex):
            self.is_streaming = not self.is_streaming
            streaming_state = self.is_streaming
            
        print(f"[DEBUG] toggle_lidar_streaming: is_streaming = {streaming_state}")
        
        if streaming_state:
            # Emit signal to request server start streaming
            self.lidar_start_requested.emit()
            print("[DEBUG] LIDAR streaming started")
        else:
            # Emit signal to request server stop streaming
            self.lidar_stop_requested.emit()
            print("[DEBUG] LIDAR streaming stopped")

    def show_lidar_interface(self):
        """Switch to the LIDAR interface and start streaming"""
        print("[DEBUG] Switching to LIDAR interface")
        self.stacked_widget.setCurrentWidget(self.lidar_page)
        # Auto-start streaming when interface is shown
        if not self.is_streaming:
            self.toggle_lidar_streaming()

    def show_button_interface(self):
        """Switch back to the button interface and stop streaming"""
        print("[DEBUG] Switching to button interface")
        if self.is_streaming:
            self.toggle_lidar_streaming()  # Stop streaming
        self.stacked_widget.setCurrentWidget(self.button_page)

    # Keep the existing methods
    def toggle_lidar(self):
        """Legacy method - redirect to new method"""
        self.toggle_lidar_streaming()

    def set_distances(self, distances):
        print(f"[DEBUG] Setting distances via signal: {distances}")
        # Emit signal instead of directly setting
        self.lidar_data_received.emit(distances.copy() if distances else [])

    def set_distances(self, distances):
        print(f"[DEBUG] Setting distances via signal: {distances}")
        # Emit signal instead of directly setting
        self.lidar_data_received.emit(distances.copy() if distances else [])

    def update_distances_slot(self, distances):
        """Slot to handle distance updates in the main thread"""
        print(f"[DEBUG] update_distances_slot called with is_streaming = {self.is_streaming}")
        
        if distances:
            # Use thread-safe mutex for data access
            with QMutexLocker(self.data_mutex):
                # Add new readings to history
                for distance in distances:
                    self.distance_history.append(distance)
                
                # Keep only the last max_history readings
                if len(self.distance_history) > self.max_history:
                    self.distance_history = self.distance_history[-self.max_history:]
                
                # Update current distances for display
                self.distances = self.distance_history.copy()
                
                print(f"[DEBUG] Distance updated: current={distances}, history={len(self.distance_history)} points")
            
            # ALWAYS call update_plot when data arrives (if streaming)
            if self.is_streaming:
                print(f"[DEBUG] Calling update_plot from update_distances_slot")
                self.update_plot()
            else:
                print(f"[DEBUG] Not streaming, skipping plot update")

    def update_plot(self):
        with QMutexLocker(self.data_mutex):
            current_distances = self.distances.copy() if self.distances else []
            
        print(f"[DEBUG] update_plot called - streaming: {self.is_streaming}, distances count: {len(current_distances)}")
        
        if current_distances:
            print(f"[DEBUG] Plotting {len(current_distances)} distances: {current_distances}")
            
            # Create x and y data arrays
            x_data = np.arange(len(current_distances))
            y_data = np.array(current_distances)
            
            # Update the plot curve with new data
            self.plot_curve.setData(x_data, y_data)
            
            # Update text display with latest readings and statistics
            latest_reading = current_distances[-1]
            avg_distance = sum(current_distances) / len(current_distances) if current_distances else 0
            self.distance_display.setText(
                f"Current: {latest_reading} cm | "
                f"Average: {avg_distance:.1f} cm | "
                f"Points: {len(current_distances)} | "
                f"Streaming: {self.is_streaming}"
            )

            # Auto-range the plot to fit the data
            self.plot_widget.autoRange()
            
            print(f"[DEBUG] PyQtGraph plot updated with {len(current_distances)} points")
            
        else:
            print("[DEBUG] No distances to plot")
            self.distance_display.setText("No data available")
            self.plot_curve.clear()

    def stop_lidar(self):
        """Force stop the lidar stream"""
        if self.is_streaming:
            self.toggle_lidar_streaming()

    def clear_history(self):
        """Clear the distance history"""
        print("[DEBUG] Clearing LIDAR history")
        self.distance_history.clear()
        self.distances.clear()
        self.plot_curve.clear()  # Clear the plot curve
        self.distance_display.setText("History cleared - waiting for new data")
        if self.is_streaming:
            print("[DEBUG] Calling update_plot after clearing history")
            self.update_plot()
