import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QFrame, QSizePolicy, QWidget
from collections import deque
import numpy as np
import time
from matplotlib.ticker import MultipleLocator
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

class RelativeDistancePlotter(QFrame):
    def __init__(self):
        super().__init__()
        # === Customizable label and tick sizes ===
        self.axis_label_size = AXIS_LABEL_SIZE      # Size for axis labels ("Distance (m)", "Time (s)")
        self.axis_number_size = AXIS_NUMBER_SIZE     # Size for axis numbers/ticks

        # === Customizable axis ranges ===
        self.y_axis_min = 0           # Minimum value for y-axis
        self.y_axis_max = 2           # Maximum value for y-axis
        self.x_axis_window = 10       # Width of the x-axis window in seconds

        # === Customizable subplot margins ===
        self.subplot_left = 0.14      # Move graph closer to left edge
        self.subplot_right = 0.94
        self.subplot_top = 0.93
        self.subplot_bottom = 0.18

        # === Theme colors from theme.py ===
        self.bg_color = PLOT_BACKGROUND
        self.line_color = GRAPH_MODE_COLORS["Relative Distance"]
        self.tick_color = self.line_color
        self.grid_color = self.line_color

        self.setMinimumSize(384, 216)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.data = deque(maxlen=100)
        self.time_data = deque(maxlen=100)
        self.start_time = time.time()

        self.figure = Figure(facecolor=self.bg_color)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {self.bg_color}; border: none;")
        self.setStyleSheet(f"background-color: {self.bg_color}; border: none;")
        if self.parent():
            self.parent().setStyleSheet(f"background-color: {self.bg_color}; border: none;")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(384, 216)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.bg_color)
        self.ax.tick_params(colors=self.tick_color, labelsize=self.axis_number_size, width=0.5)
        self.ax.xaxis.label.set_color(self.tick_color)
        self.ax.yaxis.label.set_color(self.tick_color)
        self.ax.title.set_color(self.tick_color)
        self.ax.grid(True, color=self.grid_color, linestyle='--', linewidth=0.2, alpha=0.5)
        self.figure.subplots_adjust(
            left=self.subplot_left,
            right=self.subplot_right,
            top=self.subplot_top,
            bottom=self.subplot_bottom
        )

        self.ax.xaxis.label.set_fontsize(self.axis_label_size)
        self.ax.yaxis.label.set_fontsize(self.axis_label_size)
        self.ax.xaxis.label.set_fontfamily('Segoe UI')
        self.ax.yaxis.label.set_fontfamily('Segoe UI')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.redraw()  # <-- Add this line at the end of __init__

    def update(self, rvec, tvec, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        elapsed = timestamp - self.start_time
        distance = np.linalg.norm(tvec)
        self.time_data.append(elapsed)
        self.data.append(distance)
        self.redraw()

    def redraw(self):
        self.ax.clear()
        self.ax.set_facecolor(self.bg_color)
        self.ax.tick_params(colors=self.tick_color, labelsize=self.axis_number_size, width=0.5)

        # Only show integer seconds on x axis
        self.ax.xaxis.set_major_locator(MultipleLocator(1))
        self.ax.xaxis.set_major_formatter(lambda x, pos: f"{int(x)}")

        # Always show 0, 0.5, 1, 1.5, 2 on y axis
        self.ax.yaxis.set_major_locator(MultipleLocator(0.5))
        self.ax.yaxis.set_major_formatter(lambda y, pos: f"{y:.1f}".rstrip('0').rstrip('.'))

        self.ax.xaxis.label.set_color(self.tick_color)
        self.ax.yaxis.label.set_color(self.tick_color)
        self.ax.title.set_color(self.tick_color)
        self.ax.grid(True, color=self.grid_color, linestyle='--', linewidth=0.5, alpha=0.2)
        self.figure.subplots_adjust(
            left=self.subplot_left,
            right=self.subplot_right,
            top=self.subplot_top,
            bottom=self.subplot_bottom
        )
        self.ax.plot(self.time_data, self.data, color=self.line_color, linewidth=2)
        self.ax.set_ylim(self.y_axis_min, self.y_axis_max)
        self.ax.set_yticks([0, 0.5, 1, 1.5, 2])  # Ensure these ticks are always present
        self.ax.set_ylabel("Distance (m)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
        self.ax.set_xlabel("Time (s)", fontsize=self.axis_label_size, fontfamily='Segoe UI')

        # Fixed x-axis window
        if self.time_data:
            xmax = max(self.time_data[-1], self.x_axis_window)
            xmin = xmax - self.x_axis_window
            self.ax.set_xlim(xmin, xmax)
        else:
            self.ax.set_xlim(0, self.x_axis_window)

        self.canvas.draw()
