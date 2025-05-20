import sys, socketio, logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt

SERVER_URL = "http://192.168.1.146:5000"
VIDEO_URL = "http://192.168.1.146:8000/video"  # <-- Update to your Pi's IP

sio = socketio.Client()
RES_PRESETS = [
    ("640x480", (640, 480)),
    ("1280x720", (1280, 720)),
    ("1920x1080", (1920, 1080)),
    ("2592x1944", (2592, 1944)),
]
FPS_LIMITS = {
    (640, 480): 120,
    (1280, 720): 60,
    (1920, 1080): 30,
    (2592, 1944): 15,
}

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Native Video Client")
        layout = QVBoxLayout(self)

        self.video_widget = QVideoWidget()
        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)
        self.player.setSource(QUrl(VIDEO_URL))

        layout.addWidget(QLabel("Live Video Stream:"))
        layout.addWidget(self.video_widget)

        config_group = QGroupBox("Camera Settings")
        grid = QGridLayout()

        self.res_dropdown = QComboBox()
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)
        self.res_dropdown.currentIndexChanged.connect(self.update_fps_range)

        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(10, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda v: self.jpeg_label.setText(f"JPEG: {v}"))

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda v: self.fps_label.setText(f"FPS: {v}"))

        self.update_fps_range()

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        grid.addWidget(QLabel("Resolution"), 0, 0)
        grid.addWidget(self.res_dropdown, 0, 1)
        grid.addWidget(self.jpeg_label, 1, 0)
        grid.addWidget(self.jpeg_slider, 1, 1)
        grid.addWidget(self.fps_label, 2, 0)
        grid.addWidget(self.fps_slider, 2, 1)
        grid.addWidget(self.apply_btn, 3, 0, 1, 2)

        config_group.setLayout(grid)
        layout.addWidget(config_group)

        self.sensor_label = QLabel("Sensor Info: (waiting...)")
        layout.addWidget(self.sensor_label)

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.clicked.connect(self.toggle_stream)
        layout.addWidget(self.toggle_btn)

    def update_fps_range(self):
        _, res = RES_PRESETS[self.res_dropdown.currentIndex()]
        max_fps = FPS_LIMITS.get(res, 30)
        self.fps_slider.setRange(1, max_fps)
        self.fps_slider.setValue(min(self.fps_slider.value(), max_fps))
        self.fps_label.setText(f"FPS: {self.fps_slider.value()}")

    def toggle_stream(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
            self.toggle_btn.setText("Start Stream")
        else:
            self.player.play()
            self.toggle_btn.setText("Stop Stream")

    def apply_config(self):
        res_idx = self.res_dropdown.currentIndex()
        _, resolution = RES_PRESETS[res_idx]
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": resolution
        }
        sio.emit("camera_config", config)

@sio.on("sensor_broadcast")
def on_sensor_data(data):
    try:
        temp = data.get("temperature", "N/A")
        cpu = data.get("cpu_percent", "N/A")
        win.sensor_label.setText(f"🌡️ {temp:.1f}°C | 🧠 CPU: {cpu:.1f}%")
    except Exception as e:
        print("Sensor update failed:", e)

@sio.event
def connect():
    print("✅ Connected to server")

@sio.event
def disconnect():
    print("❌ Disconnected from server")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    import threading
    threading.Thread(target=lambda: sio.connect(SERVER_URL), daemon=True).start()

    sys.exit(app.exec())
