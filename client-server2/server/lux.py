import sys
import time
import datetime
from collections import deque
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import random

# Dummy I2C read function (replace with your actual sensor reading logic)
def read_lux_sensor(sensor_id):
    return 100 + 50 * random.random() + 50 * (sensor_id + 1) * (0.5 - random.random())

class LuxTracker:
    def __init__(self, history_len=300):
        self.history_len = history_len
        self.timestamps = deque(maxlen=history_len)
        self.values = [deque(maxlen=history_len) for _ in range(3)]
        self.maxima = [(-float('inf'), None) for _ in range(3)]  # (max_value, timestamp)

    def update(self):
        now = time.time()
        self.timestamps.append(now)
        for i in range(3):
            val = read_lux_sensor(i)
            self.values[i].append(val)
            if val > self.maxima[i][0]:
                self.maxima[i] = (val, now)

    def get_current(self):
        return [v[-1] if v else None for v in self.values]

    def get_maxima(self):
        return self.maxima

class LuxPlotter(QtWidgets.QWidget):
    def __init__(self, tracker):
        super().__init__()
        self.tracker = tracker
        self.plot_widget = pg.PlotWidget(title="Live Lux Sensor Readings and Maxima")
        self.curves = [self.plot_widget.plot(pen=pg.mkPen(color, width=2), name=f"Lux {i+1}") for i, color in enumerate(['r', 'g', 'b'])]
        self.max_dots = [self.plot_widget.plot(pen=None, symbol='o', symbolBrush=color, symbolSize=12) for color in ['r', 'g', 'b']]
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)
        self.plot_widget.addLegend()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(500)

    def update_plot(self):
        self.tracker.update()
        times = [datetime.datetime.fromtimestamp(ts) for ts in self.tracker.timestamps]
        if not times:
            return
        t0 = times[0]
        x = [(t-t0).total_seconds() for t in times]
        for i in range(3):
            y = list(self.tracker.values[i])
            self.curves[i].setData(x, y, name=f"Lux {i+1} (now: {y[-1]:.1f})")
            max_val, max_ts = self.tracker.maxima[i]
            if max_ts:
                max_x = (datetime.datetime.fromtimestamp(max_ts)-t0).total_seconds()
                self.max_dots[i].setData([max_x], [max_val])
            else:
                self.max_dots[i].setData([], [])

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    tracker = LuxTracker()
    win = LuxPlotter(tracker)
    win.setWindowTitle("Lux Sensors Live (PyQtGraph)")
    win.resize(900, 500)
    win.show()
    sys.exit(app.exec())