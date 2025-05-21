# relative_angle_plotter.py
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import deque
import time

class RelativeAnglePlotter(QWidget):
    def __init__(self):
        super().__init__()
        # --- Customizable style variables ---
        self.axis_label_size = 6
        self.axis_number_size = 6
        self.subplot_left = 0.12
        self.subplot_right = 0.98
        self.subplot_top = 0.93
        self.subplot_bottom = 0.18
        self.bg_color = "#111111"  # Black background

        # --- Customizable axis limits ---
        self.y_axis_min = -30      # Minimum value for y-axis
        self.y_axis_max = 30       # Maximum value for y-axis
        self.x_axis_window = 10    # Width of the x-axis window in seconds

        self.data = deque(maxlen=100)
        self.time_data = deque(maxlen=100)
        self.start_time = time.time()

        self.figure = Figure(facecolor=self.bg_color)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.bg_color)
        self.ax.tick_params(colors='#eee', labelsize=self.axis_number_size, width=0.5)
        self.ax.xaxis.label.set_color('#eee')
        self.ax.yaxis.label.set_color('#eee')
        self.ax.title.set_color('#eee')
        self.ax.grid(True, color='#888', linestyle='--', linewidth=0.2, alpha=0.5)
        self.figure.subplots_adjust(
            left=self.subplot_left,
            right=self.subplot_right,
            top=self.subplot_top,
            bottom=self.subplot_bottom
        )

        self.ax.set_xlabel("Time (s)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
        self.ax.set_ylabel("Angle (deg)", fontsize=self.axis_label_size, fontfamily='Segoe UI')

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update(self, rvec, tvec, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        elapsed = timestamp - self.start_time
        angle_rad = np.arctan2(tvec[0], tvec[2])
        angle_deg = np.degrees(angle_rad)
        self.time_data.append(elapsed)
        self.data.append(angle_deg)
        self.redraw()

    def redraw(self):
        self.ax.clear()
        self.ax.set_facecolor(self.bg_color)
        self.ax.tick_params(colors='#eee', labelsize=self.axis_number_size, width=0.5)
        self.ax.xaxis.label.set_color('#eee')
        self.ax.yaxis.label.set_color('#eee')
        self.ax.title.set_color('#eee')
        self.ax.grid(True, color='#888', linestyle='--', linewidth=0.2, alpha=0.5)
        self.figure.subplots_adjust(
            left=self.subplot_left,
            right=self.subplot_right,
            top=self.subplot_top,
            bottom=self.subplot_bottom
        )
        self.ax.set_xlabel("Time (s)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
        self.ax.set_ylabel("Angle (deg)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
        self.ax.plot(self.time_data, self.data, color="red")
        self.ax.set_ylim(self.y_axis_min, self.y_axis_max)  # Use defined limits
        # Fixed 10s window on x-axis
        if self.time_data:
            xmax = max(self.time_data[-1], self.x_axis_window)
            xmin = xmax - self.x_axis_window
            self.ax.set_xlim(xmin, xmax)
        else:
            self.ax.set_xlim(0, self.x_axis_window)
        self.canvas.draw()
