import sys, socketio, logging, threading, time, base64, numpy as np, cv2
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QMediaFormat, QMediaContent
from PyQt6.QtMultimediaWidgets import QVideoWidget

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
SERVER_URL = "http://192.168.1.146:5000"

RES_PRESETS = [
    ("640x480", (640, 480)),
    ("1280x720", (1280, 720)),
    ("1920x1080", (1920, 1080)),
    ("2592x1944", (2592, 1944)),
]

FPS_LIMITS = {
    (640, 480): 200,
    (1280, 720): 100,
    (1920, 1080): 50,
    (2592, 1944): 30,
}

sio = socketio.Client()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client (Native Video)")
        self.streaming = False

        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.status_label = QLabel("Status: Disconnected")
        left_layout.addWidget(self.status_label)

        # Video widget
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedSize(640, 480)
        left_layout.addWidget(self.video_widget)

        # Player
        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)

        # Info labels
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
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)
        self.res_dropdown.currentIndexChanged.connect(self.update_fps_slider)

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 10)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda val: self.fps_label.setText(f"FPS: {val}"))
        self.update_fps_slider()

        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.clicked.connect(self.toggle_stream)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)

        # Camera config panel
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

        right_layout.addWidget(config_group)
        right_layout.addWidget(self.toggle_btn)

        self.last_frame_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        self.current_frame_size = 0
        self.fps_timer = self.startTimer(1000)

        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.measure_speed)
        self.speed_timer.start(30000)  # every 30 sec

    def update_fps_slider(self):
        _, res = RES_PRESETS[self.res_dropdown.currentIndex()]
        max_fps = FPS_LIMITS.get(res, 10)
        self.fps_slider.setRange(1, max_fps)
        self.fps_slider.setValue(min(self.fps_slider.value(), max_fps))
        self.fps_label.setText(f"FPS: {self.fps_slider.value()}")

    def toggle_stream(self):
        self.streaming = not self.streaming
        self.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")
        if self.streaming:
            # Stream is rendered from an MJPEG endpoint served by Flask
            stream_url = QUrl("http://192.168.1.146:8000/video")  # <- make sure this is served by Pi
            self.player.setSource(stream_url)
            self.player.play()
        else:
            self.player.stop()

    def apply_config(self):
        if self.streaming:
            QMessageBox.warning(self, "Stream Active", "Stop the stream to change camera settings.")
            return
        idx = self.res_dropdown.currentIndex()
        _, resolution = RES_PRESETS[idx]
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": resolution
        }
        sio.emit("camera_config", config)
        logging.info(f"Sent config: {config}")

    def timerEvent(self, event):
        self.current_fps = self.frame_counter
        self.frame_counter = 0
        self.info_labels["fps"].setText(f"FPS: {self.current_fps}")
        self.info_labels["frame_size"].setText(f" Frame Size: {self.current_frame_size / 1024:.1f} KB")

    def measure_speed(self):
        self.info_labels["speed"].setText("Upload: Testing...")
        self.info_labels["max_frame"].setText("Max Frame: ...")

        def run_speedtest():
            try:
                import speedtest
                st = speedtest.Speedtest()
                upload = st.upload()
                upload_mbps = upload / 1_000_000
                self.info_labels["speed"].setText(f"Upload: {upload_mbps:.2f} Mbps")
                fps = self.fps_slider.value()
                max_bytes_per_sec = upload / 8
                max_frame_size = max_bytes_per_sec / fps
                self.info_labels["max_frame"].setText(f"Max Frame: {max_frame_size / 1024:.1f} KB")
            except:
                self.info_labels["speed"].setText("Upload: Error")
                self.info_labels["max_frame"].setText("Max Frame: --")

        threading.Thread(target=run_speedtest, daemon=True).start()

@sio.on("sensor_broadcast")
def on_sensor_data(data):
    try:
        temp = data.get("temperature", 0)
        cpu = data.get("cpu_percent", 0)
        win.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
        win.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
    except Exception as e:
        print("Sensor update failed:", e)

@sio.event
def connect():
    win.status_label.setText("Status: Connected")

@sio.event
def disconnect():
    win.status_label.setText("Status: Disconnected")

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
