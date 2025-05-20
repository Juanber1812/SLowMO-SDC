import sys, socketio, base64, numpy as np, cv2
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QSlider, QPushButton,
    QGroupBox, QComboBox, QGridLayout
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

SERVER_URL = "http://192.168.1.146:5000"  # Replace with your Pi IP
sio = socketio.Client()

RES_PRESETS = [
    ("640x480", (640, 480)),
    ("1280x720", (1280, 720)),
    ("1920x1080", (1920, 1080)),
]
FPS_LIMITS = {
    (640, 480): 120,
    (1280, 720): 60,
    (1920, 1080): 30,
}

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client (OpenCV QLabel)")
        self.image_label = QLabel()
        self.image_label.setFixedSize(640, 480)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label)

        # Controls
        self.res_dropdown = QComboBox()
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)
        self.res_dropdown.currentIndexChanged.connect(self.update_fps_slider)

        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(10, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda v: self.jpeg_label.setText(f"JPEG: {v}"))

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda v: self.fps_label.setText(f"FPS: {v}"))

        self.update_fps_slider()

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        grid = QGridLayout()
        grid.addWidget(QLabel("Resolution"), 0, 0)
        grid.addWidget(self.res_dropdown, 0, 1)
        grid.addWidget(self.jpeg_label, 1, 0)
        grid.addWidget(self.jpeg_slider, 1, 1)
        grid.addWidget(self.fps_label, 2, 0)
        grid.addWidget(self.fps_slider, 2, 1)
        grid.addWidget(self.apply_btn, 3, 0, 1, 2)

        group = QGroupBox("Camera Settings")
        group.setLayout(grid)
        layout.addWidget(group)

    def update_fps_slider(self):
        _, res = RES_PRESETS[self.res_dropdown.currentIndex()]
        max_fps = FPS_LIMITS.get(res, 30)
        self.fps_slider.setRange(1, max_fps)
        self.fps_slider.setValue(min(self.fps_slider.value(), max_fps))
        self.fps_label.setText(f"FPS: {self.fps_slider.value()}")

    def apply_config(self):
        idx = self.res_dropdown.currentIndex()
        _, res = RES_PRESETS[idx]
        config = {
            "resolution": res,
            "fps": self.fps_slider.value(),
            "jpeg_quality": self.jpeg_slider.value()
        }
        sio.emit("camera_config", config)

@sio.on("frame_data")
def on_frame_data(data):
    arr = np.frombuffer(base64.b64decode(data), np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg).scaled(win.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
    win.image_label.setPixmap(pixmap)

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
