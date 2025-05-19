# client2.py

import sys, base64, socketio, cv2, numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QSlider, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage

SERVER_URL = "http://192.168.65.89:5000"  # ← Update to your Pi IP

sio = socketio.Client()

RES_PRESETS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080)
}

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    sensor_received = pyqtSignal(float, float)
    server_status = pyqtSignal(str)

bridge = Bridge()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client GUI")
        self.streaming = False

        # ─ UI Elements ─
        self.status_label = QLabel("Status: Disconnected")
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(640, 480)

        self.temp_label = QLabel("Temp: N/A")
        self.cpu_label = QLabel("CPU: N/A")

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.clicked.connect(self.toggle_stream)

        # Config controls
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setMinimum(10)
        self.jpeg_slider.setMaximum(100)
        self.jpeg_slider.setValue(70)

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setMinimum(1)
        self.fps_slider.setMaximum(30)
        self.fps_slider.setValue(10)

        self.res_dropdown = QComboBox()
        self.res_dropdown.addItems(RES_PRESETS.keys())

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        # ─ Layout ─
        top = QHBoxLayout()
        top.addWidget(self.status_label)
        top.addStretch()
        top.addWidget(self.toggle_btn)

        sensors = QHBoxLayout()
        sensors.addWidget(self.temp_label)
        sensors.addStretch()
        sensors.addWidget(self.cpu_label)

        config_group = QGroupBox("Camera Settings")
        config_layout = QVBoxLayout()
        config_layout.addWidget(QLabel("JPEG Quality"))
        config_layout.addWidget(self.jpeg_slider)
        config_layout.addWidget(QLabel("FPS"))
        config_layout.addWidget(self.fps_slider)
        config_layout.addWidget(QLabel("Resolution"))
        config_layout.addWidget(self.res_dropdown)
        config_layout.addWidget(self.apply_btn)
        config_group.setLayout(config_layout)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.image_label)
        layout.addLayout(sensors)
        layout.addWidget(config_group)

        # ─ Signal Connections ─
        bridge.frame_received.connect(self.update_image)
        bridge.sensor_received.connect(self.update_sensor)
        bridge.server_status.connect(self.update_status)

    def toggle_stream(self):
        self.streaming = not self.streaming
        if self.streaming:
            self.toggle_btn.setText("Stop Stream")
            sio.emit("start_camera")
        else:
            self.toggle_btn.setText("Start Stream")
            sio.emit("stop_camera")

    def apply_config(self):
        res_text = self.res_dropdown.currentText()
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": RES_PRESETS[res_text]
        }
        sio.emit("camera_config", config)
        print("📤 Sent config:", config)

    def update_image(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))

    def update_sensor(self, temp, cpu):
        self.temp_label.setText(f"Temp: {temp:.1f} °C")
        self.cpu_label.setText(f"CPU: {cpu:.1f} %")

    def update_status(self, text):
        self.status_label.setText(f"Status: {text}")


# ─ Socket.IO Events ─
@sio.event
def connect():
    print("✅ Connected")
    bridge.server_status.emit("Connected")

@sio.event
def disconnect():
    print("🔌 Disconnected")
    bridge.server_status.emit("Disconnected")

@sio.on('frame')
def on_frame(data):
    try:
        arr = np.frombuffer(base64.b64decode(data), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            bridge.frame_received.emit(frame)
    except Exception as e:
        print("❌ Frame error:", e)

@sio.on('sensor')
def on_sensor(payload):
    try:
        t = float(payload.get("temperature", 0.0))
        c = float(payload.get("cpu_percent", 0.0))
        bridge.sensor_received.emit(t, c)
    except Exception as e:
        print("❌ Sensor error:", e)


# ─ Main ─
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    try:
        sio.connect(SERVER_URL, wait_timeout=5)
    except Exception as e:
        print("❌ Could not connect:", e)
        win.update_status("Conn Error")

    sys.exit(app.exec())
