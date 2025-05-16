# ===== client_qt_stats.py =====
import sys
import cv2
import numpy as np
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QHBoxLayout, QVBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap

# Configuration
PI_IP = '192.168.1.168'
STREAM_URL = f'http://{PI_IP}:5000/video_feed'
STATUS_URL = f'http://{PI_IP}:5000/status'
DISPLAY_FPS = 200  # max display refresh rate

class FrameReader(QThread):
    frame_received = pyqtSignal(np.ndarray)
    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self._running = True
    def run(self):
        cap = cv2.VideoCapture(self.stream_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while self._running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            self.frame_received.emit(frame)
        cap.release()
    def stop(self):
        self._running = False
        self.wait()

class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pi Stream + Stats')
        self.last_display = cv2.getTickCount() / cv2.getTickFrequency()

        # Main layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Video panel
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Ensure pixmap scales to label size
        self.video_label.setScaledContents(True)
        layout.addWidget(self.video_label, 3)

        # Stats panel
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        layout.addWidget(stats_widget, 1)
        self.stat_labels = {}
        for key in ['cpu_temp_c','cpu_util_percent','cpu_freq_mhz']:
            lbl = QLabel(f'{key}: --')
            stats_layout.addWidget(lbl)
            self.stat_labels[key] = lbl
        stats_layout.addStretch()

        # Start frame reader
        self.reader = FrameReader(STREAM_URL)
        self.reader.frame_received.connect(self.on_new_frame)
        self.reader.start()

        # Poll status every second
        self.stat_timer = QTimer(self)
        self.stat_timer.timeout.connect(self.update_stats)
        self.stat_timer.start(1000)

    def on_new_frame(self, frame):
        now = cv2.getTickCount() / cv2.getTickFrequency()
        if now - self.last_display < 1.0 / DISPLAY_FPS:
            return
        self.last_display = now
        # Convert BGR->RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        # Scale pixmap to label dimensions, maintain aspect ratio
        pix = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(),
            self.video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(pix)

    def update_stats(self):
        try:
            r = requests.get(STATUS_URL, timeout=0.5)
            data = r.json()
            self.stat_labels['cpu_temp_c'].setText(f"Temp: {data['cpu_temp_c']:.1f} °C")
            self.stat_labels['cpu_util_percent'].setText(f"CPU Util: {data['cpu_util_percent']:.1f} %")
            self.stat_labels['cpu_freq_mhz'].setText(f"Freq: {data['cpu_freq_mhz']:.0f} MHz")
        except Exception:
            pass

    def closeEvent(self, event):
        self.reader.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = VideoWindow()
    win.resize(1024, 600)
    win.show()
    sys.exit(app.exec())
