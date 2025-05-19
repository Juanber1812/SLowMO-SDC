# viewer.py

import sys, base64, cv2, numpy as np, socketio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject

# ─── Config ─────────────────────────────────────────────────────────────
SERVER_URL = "http://192.168.65.89:5000"

sio = socketio.Client()

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    sensor_received = pyqtSignal(float, float)
    server_status = pyqtSignal(str)

bridge = Bridge()

# ─── Main GUI Window ────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pi Stream & Sensor Monitor")
        self.streaming = False

        # UI elements
        self.status_label = QLabel("Status: Connecting…")
        self.start_button = QPushButton("Start Stream")
        self.start_button.clicked.connect(self.toggle_stream)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(640, 480)

        self.temp_label = QLabel("Temp: N/A")
        self.cpu_label = QLabel("CPU: N/A")

        # Layouts
        top = QHBoxLayout()
        top.addWidget(self.status_label)
        top.addStretch()
        top.addWidget(self.start_button)

        sensors = QHBoxLayout()
        sensors.addWidget(self.temp_label)
        sensors.addStretch()
        sensors.addWidget(self.cpu_label)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.image_label)
        layout.addLayout(sensors)
        self.setLayout(layout)

        # Connect signal bridge
        bridge.frame_received.connect(self.update_image)
        bridge.sensor_received.connect(self.update_sensor)
        bridge.server_status.connect(self.update_status)

        # Start the data polling loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.request_data)

    
    def toggle_stream(self):
        self.streaming = not self.streaming
        if self.streaming:
            self.start_button.setText("Stop Stream")
            sio.emit("start_camera")
        else:
            self.start_button.setText("Start Stream")
            sio.emit("stop_camera")

    def request_data(self):
        if sio.connected:
            sio.emit("request_data")

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


# ─── Socket.IO Events ────────────────────────────────────────────────────
@sio.event
def connect():
    print("✅ Connected to server")
    bridge.server_status.emit("Connected")

@sio.event
def disconnect():
    print("🔌 Disconnected from server")
    bridge.server_status.emit("Disconnected")

@sio.on('frame')
def on_frame(data):
    try:
        arr = np.frombuffer(base64.b64decode(data), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            bridge.frame_received.emit(frame)
    except Exception as e:
        print("❌ Frame decode error:", e)

@sio.on('sensor')
def on_sensor(payload):
    try:
        t = float(payload.get("temperature", 0.0))
        c = float(payload.get("cpu_percent", 0.0))
        bridge.sensor_received.emit(t, c)
    except Exception as e:
        print("❌ Sensor parse error:", e)


# ─── Entry ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    try:
        win.update_status("Connecting...")
        sio.connect(SERVER_URL, wait_timeout=5)
    except Exception as e:
        print("❌ Initial connect failed:", e)
        win.update_status("Connection Error")

    sys.exit(app.exec())
