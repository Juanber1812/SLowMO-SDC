from PyQt6.QtWidgets import QWidget, QStackedWidget, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
import time
from collections import deque

from theme import (
    PLOT_BACKGROUND, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY,
    GRID_COLOR, TICK_COLOR,
    FONT_FAMILY, FONT_SIZE_LABEL, FONT_SIZE_NORMAL,
    BORDER_COLOR, BUTTON_COLOR, BUTTON_TEXT, BUTTON_DISABLED, BUTTON_HOVER, BOX_BACKGROUND, BORDER_RADIUS,
    TEXT_COLOR, BACKGROUND
)

class YawGraphWidget(QWidget):
    def __init__(self, parent=None, width=400, height=180, window_seconds=10):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.window_seconds = window_seconds
        self.data = deque()  # Use deque for efficient pops
        self.bg_color = QColor(PLOT_BACKGROUND)
        self.line_target = QColor(PLOT_LINE_PRIMARY)
        self.line_current = QColor(PLOT_LINE_SECONDARY)
        self.grid_color = QColor(GRID_COLOR)
        self.tick_color = QColor(TICK_COLOR)
        self.pen_width = 1  # thinner plot lines
        self.font_label = QFont(FONT_FAMILY, 8)  # smaller font for axis numbers
        self.setStyleSheet("border: none; background-color: %s;" % PLOT_BACKGROUND)
        self.t0 = None  # zero time for the graph

        # Timer for repainting at 5Hz
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(200)  # 5Hz

    def reset_time(self):
        self.t0 = time.time()
        self.data.clear()

    def push_data(self, target_yaw, current_yaw):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        t_rel = now - self.t0
        self.data.append((t_rel, float(target_yaw), float(current_yaw)))
        # Remove old data efficiently with deque
        cutoff = t_rel - self.window_seconds
        while self.data and self.data[0][0] < cutoff:
            self.data.popleft()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.bg_color)

        if len(self.data) < 2:
            return

        # Find time and yaw ranges
        times = [d[0] for d in self.data]
        t_now = times[-1]
        t_min = max(0, t_now - self.window_seconds)
        t_max = t_now

        # Auto y-axis: pad 10% above/below min/max, min range 40 deg, clamp to [-180, 180]
        yaws = [d[1] for d in self.data] + [d[2] for d in self.data]
        y_min_data, y_max_data = min(yaws), max(yaws)
        y_range = max(40, (y_max_data - y_min_data) * 1.2)
        y_mid = (y_max_data + y_min_data) / 2
        y_min = max(-180, y_mid - y_range / 2)
        y_max = min(180, y_mid + y_range / 2)

        # Margins
        left, right, top, bottom = 44, 12, 16, 28
        w = self.width() - left - right
        h = self.height() - top - bottom

        # Draw grid lines (horizontal, every 40 deg, max 6 lines)
        grid_pen = QPen(self.grid_color, 2, Qt.PenStyle.DashLine)
        grid_pen.setCosmetic(True)
        painter.setPen(grid_pen)
        y_grid_step = max(40, int((y_max - y_min) / 5 // 10 * 10))  # round to nearest 10
        y_grid_start = int(y_min // 10 * 10)
        for deg in range(y_grid_start, int(y_max) + 1, y_grid_step):
            frac = (y_max - deg) / (y_max - y_min)
            y = top + h * frac
            painter.drawLine(left, int(y), left + w, int(y))

        # Draw grid lines (vertical, 5 lines)
        for frac in [i / 4.0 for i in range(5)]:
            x = left + w * frac
            painter.drawLine(int(x), top, int(x), top + h)

        # Draw axis numbers (left: yaw, bottom: time)
        painter.setPen(QPen(self.tick_color, 1))
        painter.setFont(self.font_label)
        # Yaw axis (left, every grid step)
        for deg in range(y_grid_start, int(y_max) + 1, y_grid_step):
            frac = (y_max - deg) / (y_max - y_min)
            y_pix = top + h * frac
            painter.drawText(4, int(y_pix + 5), f"{deg}")

        # Time axis (bottom, left-to-right, rightmost is now)
        for frac in [i / 4.0 for i in range(5)]:
            t_val = t_min + frac * (t_max - t_min)
            x_pix = left + w * frac
            painter.drawText(int(x_pix - 10), self.height() - 8, f"{int(t_val):d}")

        # Draw target yaw line
        painter.setPen(QPen(self.line_target, self.pen_width))
        self._draw_line(painter, left, top, w, h, t_min, t_max, y_min, y_max, [ (d[0], d[1]) for d in self.data ])

        # Draw current yaw line
        painter.setPen(QPen(self.line_current, self.pen_width))
        self._draw_line(painter, left, top, w, h, t_min, t_max, y_min, y_max, [ (d[0], d[2]) for d in self.data ])

        # Draw a thin border only on the X and Y axes (bottom and left sides of plot area)
        border_pen = QPen(QColor(BORDER_COLOR), 1)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.drawLine(left, top, left, top + h)
        painter.drawLine(left, top + h, left + w, top + h)

    def _draw_line(self, painter, left, top, w, h, t_min, t_max, y_min, y_max, points):
        if len(points) < 2:
            return
        scale_x = lambda t: left + w * ((t - t_min) / max(0.01, t_max - t_min))
        scale_y = lambda y: top + h - h * (y - y_min) / max(0.01, y_max - y_min)
        prev = points[0]
        for pt in points[1:]:
            painter.drawLine(
                int(scale_x(prev[0])), int(scale_y(prev[1])),
                int(scale_x(pt[0])), int(scale_y(pt[1]))
            )
            prev = pt

class YawGraphStacked(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stacked = QStackedWidget(self)
        self.page0 = QWidget()
        self.page1 = QWidget()
        self.graph = YawGraphWidget(self.page1)

        # --- Use ADCS_BUTTON_STYLE for all buttons in this widget ---
        self.BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: 2px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 6px 12px;
            font-size: {FONT_SIZE_NORMAL}pt;
            font-family: "{FONT_FAMILY}";
        }}
        QPushButton:hover, QPushButton:pressed {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:checked {{
            background-color: {PLOT_LINE_PRIMARY};
            color: black;
        }}
        QPushButton:checked:hover {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
            border: 0px solid #555;
        }}
        """

        # --- GroupBox style for the graph box, matching video box ---
        self.BOX_STYLE = f"""
        QGroupBox {{
            background-color: {PLOT_BACKGROUND};
            border: 0px solid {BORDER_COLOR};
            border-radius: 8px;
            font-size: {FONT_SIZE_NORMAL}pt;
            font-family: "{FONT_FAMILY}";
            color: {BUTTON_TEXT};
        }}
        """

        # Page 0: just a button to start the graph
        vbox0 = QVBoxLayout(self.page0)
        self.start_btn = QPushButton("Start ADCS Graph")
        self.start_btn.setStyleSheet(self.BUTTON_STYLE)
        self.start_btn.setFixedSize(300, 150)
        vbox0.addStretch(1)
        vbox0.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        vbox0.addStretch(1)

        # Page 1: the graph and a back button, in a styled box
        self.graph_group = QGroupBox()
        self.graph_group.setStyleSheet(self.BOX_STYLE)
        graph_layout = QVBoxLayout(self.graph_group)
        hbox = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setStyleSheet(self.BUTTON_STYLE)
        self.back_btn.setFixedSize(70, 30)

        hbox.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        hbox.addStretch(1)
        graph_layout.addLayout(hbox)
        graph_layout.addWidget(self.graph)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        self.graph_group.setFixedSize(self.graph.width() + 20, self.graph.height() + 60)

        vbox1 = QVBoxLayout(self.page1)
        vbox1.addWidget(self.graph_group)
        vbox1.setContentsMargins(0, 0, 0, 0)

        self.stacked.addWidget(self.page0)
        self.stacked.addWidget(self.page1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stacked)
        layout.setContentsMargins(0, 0, 0, 0)

        self.start_btn.clicked.connect(self.show_graph)
        self.back_btn.clicked.connect(self.show_start)

    def show_graph(self):
        self.graph.reset_time()
        self.stacked.setCurrentIndex(1)

    def show_start(self):
        self.stacked.setCurrentIndex(0)

    def push_data(self, target_yaw, current_yaw):
        self.graph.push_data(target_yaw, current_yaw)