import sys, base64, socketio, cv2, numpy as np, logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)

SERVER_URL = "http://192.168.1.146:5000"

RES_PRESETS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
    "2592x1944": (2592, 1944),
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

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 120)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(
            lambda val: self.fps_label.setText(f"FPS: {val}")
        )

        self.res_dropdown = QComboBox()
        self.res_dropdown.addItems(RES_PRESETS.keys())

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.image_label)

        config_group = QGroupBox("Camera Settings")
        grid = QGridLayout()
        grid.addWidget(self.jpeg_label, 0, 0)
        grid.addWidget(self.jpeg_slider, 0, 1)
        grid.addWidget(self.fps_label, 1, 0)
        grid.addWidget(self.fps_slider, 1, 1)
        grid.addWidget(QLabel("Resolution"), 2, 0)
        grid.addWidget(self.res_dropdown, 2, 1)
        grid.addWidget(self.apply_btn, 3, 0, 1, 2)
        config_group.setLayout(grid)

        layout.addWidget(config_group)
        layout.addWidget(self.toggle_btn)

        bridge.frame_received.connect(self.update_image)

    def toggle_stream(self):
        self.streaming = not self.streaming
        self.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        if self.streaming:
            QMessageBox.warning(self, "Stream Active",
                                "Stop the stream before changing camera settings.")
            return

        res_text = self.res_dropdown.currentText()
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": RES_PRESETS[res_text]
        }
        sio.emit("camera_config", config)
        print("📤 Sent config:", config)

    def update_image(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h * ch, QImage.Format.Format_RGB888)
            self.image_label.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            logging.exception("❌ GUI image update error")


# Socket.IO Events

@sio.event
def connect():
    print("✅ Connected")
    win.status_label.setText("Status: Connected")

@sio.event
def disconnect():
    print("🔌 Disconnected")
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

    import threading
    threading.Thread(target=socket_thread, daemon=True).start()

    sys.exit(app.exec())
