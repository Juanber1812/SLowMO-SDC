from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
import time

class YawGraphWidget(QWidget):
    def __init__(self, parent=None, width=300, height=220, window_seconds=20):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.window_seconds = window_seconds
        self.data = []  # List of (timestamp, target_yaw, current_yaw)
        self.bg_color = QColor("#23272e")
        self.line_target = QColor("#ffb300")  # Orange/yellow
        self.line_current = QColor("#00e676") # Green
        self.grid_color = QColor("#444")
        self.pen_width = 2

        # Timer for repainting at 5Hz
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(200)  # 5Hz

    def push_data(self, target_yaw, current_yaw):
        now = time.time()
        self.data.append((now, float(target_yaw), float(current_yaw)))
        # Remove old data
        cutoff = now - self.window_seconds
        self.data = [d for d in self.data if d[0] >= cutoff]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.bg_color)

        if len(self.data) < 2:
            return

        # Find time and yaw ranges
        times = [d[0] for d in self.data]
        t_min, t_max = times[0], times[-1]
        yaws = [d[1] for d in self.data] + [d[2] for d in self.data]
        y_min, y_max = min(yaws), max(yaws)
        if y_max == y_min:
            y_max += 1  # Avoid div by zero

        # Margins
        left, right, top, bottom = 8, 8, 8, 8
        w = self.width() - left - right
        h = self.height() - top - bottom

        # Draw grid lines (horizontal)
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
        for frac in [0.25, 0.5, 0.75]:
            y = top + h * frac
            painter.drawLine(left, int(y), left + w, int(y))

        # Draw target yaw line
        painter.setPen(QPen(self.line_target, self.pen_width))
        self._draw_line(painter, left, top, w, h, t_min, t_max, y_min, y_max, [ (d[0], d[1]) for d in self.data ])

        # Draw current yaw line
        painter.setPen(QPen(self.line_current, self.pen_width))
        self._draw_line(painter, left, top, w, h, t_min, t_max, y_min, y_max, [ (d[0], d[2]) for d in self.data ])

        # Optionally, draw a border
        painter.setPen(QPen(QColor("#888"), 1))
        painter.drawRect(0, 0, self.width()-1, self.height()-1)

    def _draw_line(self, painter, left, top, w, h, t_min, t_max, y_min, y_max, points):
        if len(points) < 2:
            return
        scale_x = lambda t: left + w * (t - t_min) / max(0.01, t_max - t_min)
        scale_y = lambda y: top + h - h * (y - y_min) / max(0.01, y_max - y_min)
        prev = points[0]
        for pt in points[1:]:
            painter.drawLine(
                int(scale_x(prev[0])), int(scale_y(prev[1])),
                int(scale_x(pt[0])), int(scale_y(pt[1]))
            )
            prev = pt

# Example usage in your ADCSSection or MainWindow:
# self.yaw_graph = YawGraphWidget()
# row3.addWidget(self.yaw_graph)
# Then call self.yaw_graph.push_data(target_yaw, current_yaw) whenever new data arrives.