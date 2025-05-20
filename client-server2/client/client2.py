import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage
import detector4

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
SERVER_URL = "http://192.168.65.89:5000"

RES_FPS_PRESETS = [
    ("1536x864 @ 120 FPS", (1536, 864), 120),
    ("2304x1296 @ 50 FPS", (2304, 1296), 50),
    ("4608x2592 @ 14 FPS", (4608, 2592), 14),
]


sio = socketio.Client()

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    analysed_frame = pyqtSignal(np.ndarray)

bridge = Bridge()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client")
        self.streaming = False
        self.detector_active = False
        self.frame_queue = queue.Queue()
        self.last_frame = None

        # Layouts
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.status_label = QLabel("Status: Disconnected")
        left_layout.addWidget(self.status_label)

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(320, 240)
        left_layout.addWidget(self.image_label)

        self.analysed_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.analysed_label.setFixedSize(320, 240)
        left_layout.addWidget(self.analysed_label)

        self.detector_btn = QPushButton("Start Detector")
        self.detector_btn.setEnabled(False)
        self.detector_btn.clicked.connect(self.toggle_detector)
        left_layout.addWidget(self.detector_btn)

        # Info panel
        self.info_labels = {
            "temp": QLabel("Temp: -- °C"),
            "cpu": QLabel("CPU: --%"),
            "speed": QLabel("Upload: -- Mbps"),
            "max_frame": QLabel("Max Frame: -- KB"),
            "fps": QLabel("FPS: --"),
            "frame_size": QLabel("Frame Size: -- KB"),
        }
        for label in self.info_labels.values():
            label.setStyleSheet("font-family: monospace;")
            right_layout.addWidget(label)

        # Camera settings
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(10, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda val: self.jpeg_label.setText(f"JPEG: {val}"))

        self.res_dropdown = QComboBox()
        for label, _, _ in RES_FPS_PRESETS:
            self.res_dropdown.addItem(label)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_stream)

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

        bridge.frame_received.connect(self.update_image)
        bridge.analysed_frame.connect(self.update_analysed_image)

        self.last_frame_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        self.current_frame_size = 0
        self.fps_timer = self.startTimer(1000)

        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.measure_speed)
        self.speed_timer.start(30000)

    def toggle_stream(self):
        if not sio.connected:
            QMessageBox.warning(self, "Not Connected", "Not connected to server yet.")
            return
        self.streaming = not self.streaming
        self.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        if self.streaming:
            QMessageBox.warning(self, "Stream Active", "Stop the stream before changing settings.")
            return
        res_idx = self.res_dropdown.currentIndex()
        _, resolution, fps = RES_FPS_PRESETS[res_idx]
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": fps,
            "resolution": resolution
        }
        sio.emit("camera_config", config)
        logging.info(f"Sent config: {config}")

    def toggle_detector(self):
        self.detector_active = not self.detector_active
        self.detector_btn.setText("Stop Detector" if self.detector_active else "Start Detector")
        if self.detector_active:
            threading.Thread(target=self.run_detector, daemon=True).start()
        else:
            with self.frame_queue.mutex:
                self.frame_queue.queue.clear()

    def run_detector(self):
        while self.detector_active:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                analysed = detector4.detect_and_draw(frame)
                bridge.analysed_frame.emit(analysed)
            except queue.Empty:
                continue
            except Exception as e:
                logging.exception("Detector error")

    def update_image(self, frame):
        self.last_frame = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        pixmap = pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.image_label.setPixmap(pixmap)
        if self.detector_active:
            with self.frame_queue.mutex:
                self.frame_queue.queue.clear()
            self.frame_queue.put(self.last_frame)

    def update_analysed_image(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        pixmap = pixmap.scaled(self.analysed_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.analysed_label.setPixmap(pixmap)

    def measure_speed(self):
        self.info_labels["speed"].setText("Upload: Testing...")
        self.info_labels["max_frame"].setText(" Max Frame: ...")

        def run_speedtest():
            try:
                import speedtest
                st = speedtest.Speedtest()
                upload = st.upload()
                upload_mbps = upload / 1_000_000
                self.info_labels["speed"].setText(f" Upload: {upload_mbps:.2f} Mbps")
                res_idx = self.res_dropdown.currentIndex()
                _, _, fps = RES_FPS_PRESETS[res_idx]
                max_bytes_per_sec = upload / 8
                max_frame_size = max_bytes_per_sec / fps
                self.info_labels["max_frame"].setText(f" Max Frame: {max_frame_size / 1024:.1f} KB")
            except Exception:
                self.info_labels["speed"].setText(" Upload: Error")
                self.info_labels["max_frame"].setText(" Max Frame: -- KB")

        threading.Thread(target=run_speedtest, daemon=True).start()

    def timerEvent(self, event):
        self.current_fps = self.frame_counter
        self.frame_counter = 0
        self.info_labels["fps"].setText(f"FPS: {self.current_fps}")
        self.info_labels["frame_size"].setText(f" Frame Size: {self.current_frame_size / 1024:.1f} KB")

@sio.on("sensor_broadcast")
def on_sensor_data(data):
    try:
        temp = data.get("temperature", 0)
        cpu = data.get("cpu_percent", 0)
        win.info_labels["temp"].setText(f" Temp: {temp:.1f} °C")
        win.info_labels["cpu"].setText(f" CPU: {cpu:.1f} %")
    except Exception as e:
        print("Sensor update failed:", e)

@sio.event
def connect():
    win.status_label.setText("Status: Connected")
    win.toggle_btn.setEnabled(True)
    win.detector_btn.setEnabled(True)
    sio.emit("start_camera")

@sio.event
def disconnect():
    win.status_label.setText("Status: Disconnected")
    win.toggle_btn.setEnabled(False)
    win.detector_btn.setEnabled(False)

@sio.on("frame")
def on_frame(data):
    try:
        arr = np.frombuffer(base64.b64decode(data), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            win.current_frame_size = len(data)
            win.frame_counter += 1
            bridge.frame_received.emit(frame)
        else:
            logging.warning("Frame decode returned None")
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
