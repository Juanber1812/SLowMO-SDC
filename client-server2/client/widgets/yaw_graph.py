import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton, QWidget, QFrame, QSizePolicy
from PyQt6.QtCore import QTimer, Qt
from collections import deque
import time
from theme import (
    PLOT_BACKGROUND, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY,
    TICK_COLOR, TEXT_COLOR
)

class YawGraphWidget(QFrame):
    def __init__(self, parent=None, window_seconds=10):
        super().__init__(parent)
        self.window_seconds = window_seconds
        self.data = deque()
        self.setMinimumSize(400, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {PLOT_BACKGROUND}; border: none;")

        self.stacked = QStackedWidget(self)
        self.page0 = QWidget()
        self.page1 = QWidget()
        self._init_page0()
        self._init_page1()
        self.stacked.addWidget(self.page0)
        self.stacked.addWidget(self.page1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stacked)
        layout.setContentsMargins(0, 0, 0, 0)
        self.t0 = None

    def _init_page0(self):
        vbox0 = QVBoxLayout(self.page0)
        self.start_btn = QPushButton("Start ADCS Graph")
        self.start_btn.setFixedSize(300, 150)
        vbox0.addStretch(1)
        vbox0.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        vbox0.addStretch(1)
        self.start_btn.clicked.connect(self.show_graph)

    def _init_page1(self):
        graph_layout = QVBoxLayout(self.page1)
        hbox = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedSize(70, 20)
        hbox.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        hbox.addStretch(1)
        graph_layout.addLayout(hbox)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(PLOT_BACKGROUND)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Yaw (deg)', **{'color': TEXT_COLOR, 'font-size': '10pt'})
        self.plot_widget.getAxis('left').setPen(pg.mkPen(TICK_COLOR))
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(TICK_COLOR))
        self.plot_widget.getAxis('left').setTextPen(pg.mkPen(TEXT_COLOR))
        self.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(TEXT_COLOR))
        self.target_curve = self.plot_widget.plot(pen=pg.mkPen(PLOT_LINE_PRIMARY, width=2), name='Target Yaw')
        self.current_curve = self.plot_widget.plot(pen=pg.mkPen(PLOT_LINE_SECONDARY, width=2), name='Current Yaw')
        graph_layout.addWidget(self.plot_widget)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        self.back_btn.clicked.connect(self.show_start)
        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_timer.start(200)  # 5Hz

    def show_graph(self):
        self.reset_time()
        self.stacked.setCurrentIndex(1)

    def show_start(self):
        self.stacked.setCurrentIndex(0)

    def reset_time(self):
        self.t0 = time.time()
        self.data.clear()

    def push_data(self, target_yaw, current_yaw):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        t_rel = now - self.t0
        self.data.append((t_rel, float(target_yaw), float(current_yaw)))
        cutoff = t_rel - self.window_seconds
        while self.data and self.data[0][0] < cutoff:
            self.data.popleft()

    def redraw(self):
        if len(self.data) < 2:
            self.target_curve.setData([], [])
            self.current_curve.setData([], [])
            return
        times = [d[0] for d in self.data]
        target_yaws = [d[1] for d in self.data]
        current_yaws = [d[2] for d in self.data]
        self.target_curve.setData(times, target_yaws)
        self.current_curve.setData(times, current_yaws)
