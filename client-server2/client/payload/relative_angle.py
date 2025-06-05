# relative_angle_plotter.py
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
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
from PyQt6.QtCore import QTimer

# === Font size configuration ===
AXIS_LABEL_SIZE = 9      # Change this value to adjust axis label font size
AXIS_NUMBER_SIZE = 9     # Change this value to adjust axis number/tick font size

class RelativeAnglePlotter(QWidget):
    def __init__(self):
        super().__init__()
        # --- Customizable style variables ---
        self.axis_label_size = AXIS_LABEL_SIZE
        self.axis_number_size = AXIS_NUMBER_SIZE
        self.subplot_left = 0.14
        self.subplot_right = 0.94
        self.subplot_top = 0.93
        self.subplot_bottom = 0.18
        self.bg_color = PLOT_BACKGROUND
        self.line_color = GRAPH_MODE_COLORS["SCANNING MODE"]
        self.tick_color = self.line_color
        self.grid_color = self.line_color

        # --- Customizable axis limits ---
        self.y_axis_min = -30      # Minimum value for y-axis
        self.y_axis_max = 30       # Maximum value for y-axis
        self.x_axis_window = 10    # Width of the x-axis window in seconds

        self.data = deque(maxlen=100)
        self.time_data = deque(maxlen=100)
        self.start_time = time.time()
        self.current_ang = 0.0  # Initialize current angle  

        self.figure = Figure(facecolor=self.bg_color)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.bg_color)
        self.ax.tick_params(colors=self.tick_color, labelsize=self.axis_number_size, width=0.5)
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

         
        
        self.ax.set_xlabel("Time (s)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
        self.ax.set_ylabel("Angle (deg)", fontsize=self.axis_label_size, fontfamily='Segoe UI')

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # ── setup redraw timer (don't start until shown) ───────────────
        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_interval_ms = 100  # default 10 Hz

    def showEvent(self, event):
        super().showEvent(event)
        # start throttled redraws when widget appears
        self._redraw_timer.start(self._redraw_interval_ms)

    def hideEvent(self, event):
        # stop redraws immediately when widget is hidden
        self._redraw_timer.stop()
        super().hideEvent(event)

    def update(self, rvec, tvec, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        elapsed = timestamp - self.start_time
        angle_rad = np.arctan2(tvec[0], tvec[2])
        angle_deg = np.degrees(angle_rad)
        
        self.current_ang = float(angle_deg)
        self.time_data.append(elapsed)
        self.data.append(angle_deg)
        # now redraw only happens at timer intervals

    def set_redraw_rate(self, rate_hz: float):
        """Adjust the redraw frequency (Hz)."""
        interval = max(1, int(1000.0 / rate_hz))
        self._redraw_interval_ms = interval
        self._redraw_timer.setInterval(interval)

    def redraw(self):
        try:
            self.ax.clear()
            self.ax.set_facecolor(self.bg_color)
            self.ax.tick_params(colors=self.tick_color, labelsize=self.axis_number_size, width=0.5)
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
            
            self.ax.set_xlabel("Time (s)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
            self.ax.set_ylabel("Angle (deg)", fontsize=self.axis_label_size, fontfamily='Segoe UI')
            
            # Only plot if we have data
            if self.time_data and self.data:
                self.ax.plot(self.time_data, self.data, color=self.line_color, linewidth=2)
            
            self.ax.set_ylim(self.y_axis_min, self.y_axis_max)
            
            if self.time_data:
                xmax = max(self.time_data[-1], self.x_axis_window)
                xmin = xmax - self.x_axis_window
                self.ax.set_xlim(xmin, xmax)
            else:
                self.ax.set_xlim(0, self.x_axis_window)

            # Add current angle display - with safety check
            try:
                self.ax.text(0.98, 0.95, f'{float(self.current_ang):.3f}°', 
                            transform=self.ax.transAxes,
                            fontsize=self.axis_label_size,
                            fontweight='bold',
                            fontfamily='Segoe UI',
                            color=self.line_color,
                            bbox=dict(boxstyle='round,pad=0.3', 
                                     facecolor=self.bg_color, 
                                     edgecolor=self.line_color, 
                                     alpha=0.8),
                            horizontalalignment='right',
                            verticalalignment='top')
            except Exception as text_error:
                print(f"[RelativeAngle] Text error: {text_error}")
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"[RelativeAngle] Redraw error: {e}")
            import traceback; traceback.print_exc()
