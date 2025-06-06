import sys
import time
import numpy as np
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QTextEdit, QStackedWidget
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QMutex, QMutexLocker, QMargins
from PyQt6.QtGui import QFont, QColor, QPainter
from PyQt6.QtCharts import QChartView, QChart, QLineSeries, QValueAxis

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

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        self.distances = []
        self.distance_history = []  # Keep history of readings
        self.max_history = 50  # Keep last 50 readings
        self.data_mutex = QMutex()

        self.init_ui()
        self.init_chart()
        
        # Connect the signal to update method
        self.lidar_data_received.connect(self.update_distances_slot)

    def init_chart(self):
        self.chart = QChart()
        self.chart.setBackgroundBrush(QColor(PLOT_BACKGROUND))
        self.chart.setTitleBrush(QColor(TEXT_COLOR))
        # Remove title to save space
        # self.chart.setTitle("LIDAR Distance Measurements")
        self.chart.legend().setVisible(False)
        
        # Reduce margins to maximize plot area
        self.chart.setMargins(QMargins(5, 5, 5, 5))

        # Series
        self.series = QLineSeries()
        self.series.setColor(QColor(PLOT_LINE_PRIMARY))
        self.chart.addSeries(self.series)

        # X Axis
        self.x_axis = QValueAxis()
        self.x_axis.setLabelFormat("%i")
        self.x_axis.setTitleText("Time Index")
        self.x_axis.setTitleBrush(QColor(TEXT_COLOR))
        self.x_axis.setLabelsColor(QColor(TICK_COLOR))
        self.x_axis.setGridLineColor(QColor(GRID_COLOR))
        self.chart.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.series.attachAxis(self.x_axis)

        # Y Axis
        self.y_axis = QValueAxis()
        self.y_axis.setTitleText("Distance (cm)")
        self.y_axis.setTitleBrush(QColor(TEXT_COLOR))
        self.y_axis.setLabelsColor(QColor(TICK_COLOR))
        self.y_axis.setGridLineColor(QColor(GRID_COLOR))
        self.chart.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.y_axis)

        self.chart_view.setChart(self.chart)

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

        # Chart area (left side - takes most space)
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setStyleSheet(f"""
            QChartView {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {PLOT_BACKGROUND};
            }}
        """)
        chart_controls_layout.addWidget(self.chart_view, stretch=3)  # Takes 3/4 of space

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
        
        # Start/Stop button
        self.start_stop_button = QPushButton("Start LIDAR")
        self.start_stop_button.clicked.connect(self.toggle_lidar_streaming)
        self.start_stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_COLOR};
                color: {BUTTON_TEXT};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 8px 12px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}px;
                min-height: 30px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
            }}
        """)
        
        # Clear button
        self.clear_button = QPushButton("Clear History")
        self.clear_button.clicked.connect(self.clear_history)
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {WARNING_COLOR};
                color: white;
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 8px 12px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}px;
                min-height: 30px;
            }}
            QPushButton:hover {{
                background-color: #e68a00;
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
        controls_layout.addWidget(self.start_stop_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addStretch()  # Push back button to bottom
        controls_layout.addWidget(self.back_button)
        
        # Set fixed width for controls panel
        controls_panel.setFixedWidth(120)
        
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
            self.start_stop_button.setText("Stop LIDAR")
            self.start_stop_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ERROR_COLOR};
                    color: white;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 8px 16px;
                    font-family: {FONT_FAMILY};
                    font-size: {FONT_SIZE_NORMAL}px;
                }}
                QPushButton:hover {{
                    background-color: #cc0000;
                }}
            """)
            print("[DEBUG] LIDAR streaming started")
        else:
            self.start_stop_button.setText("Start LIDAR")
            self.start_stop_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BUTTON_COLOR};
                    color: {BUTTON_TEXT};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 8px 16px;
                    font-family: {FONT_FAMILY};
                    font-size: {FONT_SIZE_NORMAL}px;
                }}
                QPushButton:hover {{
                    background-color: {BUTTON_HOVER};
                }}
            """)
            print("[DEBUG] LIDAR streaming stopped")

    # Keep the existing methods but update toggle_lidar to use new method
    def toggle_lidar(self):
        """Legacy method - redirect to new method"""
        self.toggle_lidar_streaming()

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
        
        # Remove the streaming check for now to force plotting
        # if not self.is_streaming:
        #     print("[DEBUG] Not streaming, skipping plot update")
        #     return

        self.series.clear()

        if current_distances:
            print(f"[DEBUG] Plotting {len(current_distances)} distances: {current_distances}")
            
            # Add all points to the series
            for i, distance in enumerate(current_distances):
                self.series.append(i, distance)
            
            # Update text display with latest readings and statistics
            latest_reading = current_distances[-1]
            avg_distance = sum(current_distances) / len(current_distances) if current_distances else 0
            self.distance_display.setText(
                f"Current: {latest_reading} cm | "
                f"Average: {avg_distance:.1f} cm | "
                f"Points: {len(current_distances)} | "
                f"Streaming: {self.is_streaming}"
            )

            # Adjust axis ranges
            if len(current_distances) > 1:
                max_distance = max(current_distances)
                min_distance = min(current_distances)
                padding = (max_distance - min_distance) * 0.1 if max_distance != min_distance else 5
            else:
                max_distance = current_distances[0] + 10
                min_distance = current_distances[0] - 10
                padding = 5
            
            self.x_axis.setRange(0, max(len(current_distances) - 1, 1))
            self.y_axis.setRange(min_distance - padding, max_distance + padding)
            
            print(f"[DEBUG] Chart updated - X: 0 to {len(current_distances)-1}, Y: {min_distance-padding} to {max_distance+padding}")
            
            # Force chart refresh
            self.chart.update()
            self.chart_view.repaint()
            self.chart_view.update()
            
        else:
            print("[DEBUG] No distances to plot")
            self.distance_display.setText("No data available")
            self.x_axis.setRange(0, 10)
            self.y_axis.setRange(0, 100)

    def stop_lidar(self):
        """Force stop the lidar stream"""
        if self.is_streaming:
            self.toggle_lidar_streaming()

    def clear_history(self):
        """Clear the distance history"""
        print("[DEBUG] Clearing LIDAR history")
        self.distance_history.clear()
        self.distances.clear()
        self.distance_display.setText("History cleared - waiting for new data")
        if self.is_streaming:
            print("[DEBUG] Calling update_plot after clearing history")
            self.update_plot()
