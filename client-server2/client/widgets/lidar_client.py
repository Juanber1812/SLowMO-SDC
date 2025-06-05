import sys
import time
import numpy as np
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QTextEdit
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
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
    lidar_data_received = pyqtSignal(list)  # Signal for LIDAR data (distances)
    back_button_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.is_streaming = False
        self.distances = []

        self.init_ui()
        self.init_chart()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Control buttons
        self.start_stop_button = QPushButton("Start LIDAR")
        self.start_stop_button.clicked.connect(self.toggle_lidar)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back_button_clicked.emit)
        self.back_button.setEnabled(False)  # Initially disabled

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_stop_button)
        button_layout.addWidget(self.back_button)

        main_layout.addLayout(button_layout)

        # Distance data display
        self.distance_display = QTextEdit()
        self.distance_display.setReadOnly(True)
        self.distance_display.setFont(QFont(FONT_FAMILY, FONT_SIZE_NORMAL))
        self.distance_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
        """)
        main_layout.addWidget(self.distance_display)

        # Chart area
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.chart_view)

        self.setLayout(main_layout)

    def init_chart(self):
        self.chart = QChart()
        self.chart.setBackgroundBrush(QColor(PLOT_BACKGROUND))
        self.chart.setTitleBrush(QColor(TEXT_COLOR))
        self.chart.setTitle("LIDAR Distance Data")
        self.chart.legend().setVisible(False)

        # Series
        self.series = QLineSeries()
        self.series.setColor(QColor(PLOT_LINE_PRIMARY))
        self.chart.addSeries(self.series)

        # X Axis
        self.x_axis = QValueAxis()
        self.x_axis.setLabelFormat("%i")
        self.x_axis.setTitleText("Index")
        self.x_axis.setTitleBrush(QColor(TEXT_COLOR))
        self.x_axis.setLabelsColor(QColor(TICK_COLOR))
        self.x_axis.setGridLineColor(QColor(GRID_COLOR))
        self.chart.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.series.attachAxis(self.x_axis)

        # Y Axis
        self.y_axis = QValueAxis()
        self.y_axis.setTitleText("Distance")
        self.y_axis.setTitleBrush(QColor(TEXT_COLOR))
        self.y_axis.setLabelsColor(QColor(TICK_COLOR))
        self.y_axis.setGridLineColor(QColor(GRID_COLOR))
        self.chart.addAxis(self.y_axis, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.y_axis)

        self.chart_view.setChart(self.chart)

    def toggle_lidar(self):
        self.is_streaming = not self.is_streaming
        if self.is_streaming:
            self.start_stop_button.setText("Stop LIDAR")
            self.back_button.setEnabled(True)
            self.update_timer.start(100)  # Update every 100 ms
        else:
            self.start_stop_button.setText("Start LIDAR")
            self.back_button.setEnabled(False)
            self.update_timer.stop()

    def update_plot(self):
        if not self.is_streaming:
            return

        self.series.clear()

        if self.distances:
            for i, distance in enumerate(self.distances):
                self.series.append(i, distance)
            self.distance_display.setText(str(self.distances))  # Display distances

            # Adjust axis ranges
            max_distance = max(self.distances)
            self.x_axis.setRange(0, len(self.distances) - 1)
            self.y_axis.setRange(0, max_distance * 1.1)  # Add 10% padding
        else:
            self.distance_display.setText("No data")
            self.x_axis.setRange(0, 1)
            self.y_axis.setRange(0, 1)

    def set_distances(self, distances):
        self.distances = distances

    def stop_lidar(self):
        """Force stop the lidar stream"""
        if self.is_streaming:
            self.toggle_lidar()
