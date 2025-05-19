import sys, base64, socketio, cv2, numpy as np, logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
import threading

SERVER_URL = "http://192.168.1.146:5000"

RES_PRESETS = [
    ("640x480", (640, 480)),
    ("1280x720", (1280, 720)),
    ("1920x1080", (1920, 1080)),
    ("2592x1944", (2592, 1944)),
    ("4608x2592", (4608, 2592)),
]

FPS_LIMITS = {
    (640, 480): 200,
    (1280, 720): 100,
    (1920, 1080): 50,
    (2592, 1944): 20,
    (4608, 2592): 10,
}

sio = socketio.Client()

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)

bridge = Bridge()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client")
        self.streaming = False

        self.status_label = QLabel("Status: Disconnected")
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(640, 480)

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.clicked.connect(self.toggle_stream)
        
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(10, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(
            lambda val: self.jpeg_label.setText(f"JPEG: {val}")
        )

        # Resolution dropdown
        self.res_dropdown = QComboBox()
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)
        self.res_dropdown.currentIndexChanged.connect(self.update_fps_slider)

        # FPS slider
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 10)  # Will be updated by update_fps_slider
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(
            lambda val: self.fps_label.setText(f"FPS: {val}")
        )

        self.update_fps_slider()  # Set initial FPS range

        self.sensor_status = QLabel("Sensor status: waiting...")
        self.sensor_status.setStyleSheet("color: lightgreen; font-family: monospace;")

        self.speed_label = QLabel("Internet speed: N/A")
        self.limit_label = QLabel("Recommended max frame size: N/A")
        self.speed_btn = QPushButton("Test Internet Speed")
        self.speed_btn.clicked.connect(self.measure_speed)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.sensor_status)

        config_group = QGroupBox("Camera Settings")
        grid = QGridLayout()
        grid.addWidget(self.jpeg_label, 0, 0)
        grid.addWidget(self.jpeg_slider, 0, 1)
        grid.addWidget(QLabel("Resolution"), 1, 0)
        grid.addWidget(self.res_dropdown, 1, 1)
        grid.addWidget(self.fps_label, 2, 0)
        grid.addWidget(self.fps_slider, 2, 1)
        grid.addWidget(self.apply_btn, 3, 0, 1, 2)
        config_group.setLayout(grid)

        layout.addWidget(config_group)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.limit_label)
        layout.addWidget(self.speed_btn)
        layout.addWidget(self.toggle_btn)

        bridge.frame_received.connect(self.update_image)

    def update_fps_slider(self):
        idx = self.res_dropdown.currentIndex()
        _, res = RES_PRESETS[idx]
        max_fps = FPS_LIMITS.get(res, 10)
        self.fps_slider.setRange(1, max_fps)
        if self.fps_slider.value() > max_fps:
            self.fps_slider.setValue(max_fps)
        self.fps_label.setText(f"FPS: {self.fps_slider.value()}")

    def toggle_stream(self):
        self.streaming = not self.streaming
        self.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        if self.streaming:
            QMessageBox.warning(self, "Stream Active",
                                "Stop the stream before changing camera settings.")
            return

        res_idx = self.res_dropdown.currentIndex()
        _, resolution = RES_PRESETS[res_idx]
        fps = self.fps_slider.value()
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": fps,
            "resolution": resolution
        }
        sio.emit("camera_config", config)
        logging.info(f"📤 Sent config: {config}")

    def update_image(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            pixmap = pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            logging.exception("❌ GUI image update error")

    def measure_speed(self):
        self.speed_label.setText("Internet speed: Testing...")
        self.limit_label.setText("Recommended max frame size: ...")
        def run_speedtest():
            try:
                import speedtest
                st = speedtest.Speedtest()
                upload = st.upload()
                upload_mbps = upload / 1_000_000
                self.speed_label.setText(f"Internet upload speed: {upload_mbps:.2f} Mbps")
                fps = self.fps_slider.value()
                # Calculate recommended max frame size in KB
                max_bytes_per_sec = upload / 8
                max_frame_size = max_bytes_per_sec / fps
                self.limit_label.setText(f"Recommended max frame size: {max_frame_size/1024:.1f} KB @ {fps} fps")
            except Exception as e:
                self.speed_label.setText("Internet speed: Error")
                self.limit_label.setText("Recommended max frame size: Error")
                logging.exception("Speedtest failed")
        threading.Thread(target=run_speedtest, daemon=True).start()

# Socket.IO Events
@sio.on("sensor_broadcast")
def on_sensor_data(data):
    try:
        temp = data.get("temperature", "N/A")
        cpu = data.get("cpu_percent", "N/A")
        msg = f"🌡️ {temp:.1f}°C | 🧠 CPU: {cpu:.1f}%"
        win.sensor_status.setText(msg)
    except Exception as e:
        print("Sensor update failed:", e)

@sio.event
def connect():
    win.status_label.setText("Status: Connected")

@sio.event
def disconnect():
    win.status_label.setText("Status: Disconnected")

@sio.on("frame")
def on_frame(data):
    try:
        arr = np.frombuffer(base64.b64decode(data), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            bridge.frame_received.emit(frame)
            logging.debug(f"Frame size: {len(data)} bytes")
        else:
            logging.warning("⚠️ Frame decode returned None")
    except Exception as e:
        logging.exception("❌ Frame decode error")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    def socket_thread():
        try:
            sio.connect(SERVER_URL, wait_timeout=5)
            sio.wait()
        except Exception as e:
            logging.exception("❌ SocketIO connection error")

    threading.Thread(target=socket_thread, daemon=True).start()
    sys.exit(app.exec())
