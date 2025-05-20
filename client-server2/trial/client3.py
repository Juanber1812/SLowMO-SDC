import sys, requests, threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Replace with the IP address of your Raspberry Pi
SERVER_URL = "http://localhost:8080"

RES_FPS_PRESETS = [
    ("640x480 @ 30 FPS", (640, 480), 30),
    ("1280x720 @ 25 FPS", (1280, 720), 25),
    ("1920x1080 @ 15 FPS", (1920, 1080), 15),
]

class MJPEGClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MJPEG Camera Client")
        self.setMinimumSize(800, 600)

        self.streaming = False

        # Layouts
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.status_label = QLabel("Status: Disconnected")
        left_layout.addWidget(self.status_label)

        self.webview = QWebEngineView()
        self.webview.setUrl(QUrl(SERVER_URL + "/video_feed"))
        left_layout.addWidget(self.webview)

        # Controls
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(10, 100)
        self.jpeg_slider.setValue(80)
        self.jpeg_label = QLabel("JPEG: 80")
        self.jpeg_slider.valueChanged.connect(
            lambda val: self.jpeg_label.setText(f"JPEG: {val}")
        )

        self.res_dropdown = QComboBox()
        for label, _, _ in RES_FPS_PRESETS:
            self.res_dropdown.addItem(label)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.clicked.connect(self.toggle_stream)

        # Group box for camera settings
        config_group = QGroupBox("Camera Settings")
        grid = QGridLayout()
        grid.addWidget(self.jpeg_label, 0, 0)
        grid.addWidget(self.jpeg_slider, 0, 1)
        grid.addWidget(QLabel("Resolution"), 1, 0)
        grid.addWidget(self.res_dropdown, 1, 1)
        grid.addWidget(self.apply_btn, 2, 0, 1, 2)
        config_group.setLayout(grid)

        right_layout.addWidget(config_group)
        right_layout.addWidget(self.toggle_btn)

    def toggle_stream(self):
        try:
            if not self.streaming:
                requests.post(SERVER_URL + "/start")
                self.status_label.setText("Status: Streaming")
                self.toggle_btn.setText("Stop Stream")
                self.streaming = True
            else:
                requests.post(SERVER_URL + "/stop")
                self.status_label.setText("Status: Stopped")
                self.toggle_btn.setText("Start Stream")
                self.streaming = False
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def apply_config(self):
        if self.streaming:
            QMessageBox.warning(self, "Stream Running", "Stop the stream to apply settings.")
            return

        res_idx = self.res_dropdown.currentIndex()
        _, resolution, fps = RES_FPS_PRESETS[res_idx]
        jpeg_quality = self.jpeg_slider.value()

        config = {
            "resolution": resolution,
            "fps": fps,
            "jpeg_quality": jpeg_quality
        }

        try:
            requests.post(SERVER_URL + "/config", json=config)
            QMessageBox.information(self, "Config Applied", f"Settings: {config}")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MJPEGClient()
    win.show()
    sys.exit(app.exec())
