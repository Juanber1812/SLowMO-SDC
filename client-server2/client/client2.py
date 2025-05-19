# viewer.py

import sys, base64, cv2, numpy as np, socketio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal, QObject

# ─── Globals and Socket.IO setup ─────────────────────────────────────────────
SERVER_URL = "http://192.168.65.89:5000"  # ← change this if needed

sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1,
)

# A tiny QObject to carry signals safely into the Qt main thread
class Bridge(QObject):
    frame_received  = pyqtSignal(np.ndarray)
    sensor_received = pyqtSignal(float, float)

bridge = Bridge()


# ─── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pi Live Feed & Sensors")

        # — Widgets —
        self.status_label  = QLabel("Status: Disconnected")
        self.connect_btn   = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_button)

        self.image_label   = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(640, 480)

        self.temp_label    = QLabel("Temp: N/A")
        self.cpu_label     = QLabel("CPU: N/A")

        # — Layout —
        top_bar = QHBoxLayout()
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        top_bar.addWidget(self.connect_btn)

        sensor_bar = QHBoxLayout()
        sensor_bar.addWidget(self.temp_label)
        sensor_bar.addStretch()
        sensor_bar.addWidget(self.cpu_label)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.image_label)
        main_layout.addLayout(sensor_bar)
        self.setLayout(main_layout)

        # — Signals from Socket.IO thread —
        bridge.frame_received.connect(self._update_image)
        bridge.sensor_received.connect(self._update_sensor)

    def _on_connect_button(self):
        if sio.connected:
            sio.disconnect()
        else:
            try:
                sio.connect(SERVER_URL, wait_timeout=5)
            except Exception as e:
                self.status_label.setText(f"Status: Error")
                print("Connection failed:", e)

    def _update_image(self, frame: np.ndarray):
        """Receive a cv2 image, convert to QImage, and display."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))

    def _update_sensor(self, temp: float, cpu: float):
        """Update sensor labels."""
        self.temp_label.setText(f"Temp: {temp:.1f} °C")
        self.cpu_label.setText(f"CPU: {cpu:.1f} %")


# ─── Socket.IO Event Handlers ────────────────────────────────────────────────
@sio.event
def connect():
    print("→ Connected to server")
    bridge.frame_received.emit(np.zeros((480,640,3), dtype=np.uint8))  # clear
    bridge.sensor_received.emit(0.0, 0.0)
    app_window.status_label.setText("Status: Connected")
    app_window.connect_btn.setText("Disconnect")

@sio.event
def disconnect():
    print("→ Disconnected from server")
    app_window.status_label.setText("Status: Disconnected")
    app_window.connect_btn.setText("Connect")

@sio.on('frame')
def on_frame(data):
    # data is a base64-encoded JPEG
    try:
        arr = np.frombuffer(base64.b64decode(data), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        bridge.frame_received.emit(frame)
    except Exception as e:
        print("Frame decode error:", e)

@sio.on('sensor')
def on_sensor(payload):
    # payload is a dict: {"temperature":…, "cpu_percent":…}
    try:
        t = float(payload.get('temperature', 0.0))
        c = float(payload.get('cpu_percent', 0.0))
        bridge.sensor_received.emit(t, c)
    except Exception as e:
        print("Sensor parse error:", e)


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app       = QApplication(sys.argv)
    app_window = MainWindow()
    app_window.show()
    sys.exit(app.exec())
