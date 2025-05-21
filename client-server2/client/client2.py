import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage
import detector4  # Make sure detector4.py is in the same folder

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
SERVER_URL = "http://192.168.1.146:5000"

RES_PRESETS = [
    ("192x108", (192, 108)),
    ("256x144", (256, 144)),
    ("384x216", (384, 216)),
    ("768x432", (768, 432)),
    ("1024x576", (1024, 576)),
    ("1536x864", (1536, 864)),
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

        self.setup_ui()
        self.setup_socket_events()

        bridge.frame_received.connect(self.update_image)
        bridge.analysed_frame.connect(self.update_analysed_image)

        self.last_frame_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        self.current_frame_size = 0
        self.fps_timer = self.startTimer(1000)

        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.measure_speed)
        self.speed_timer.start(10000)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        # --- Status Section ---
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Disconnected")
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # --- Live Stream Section ---
        stream_group = QGroupBox("Live Stream")
        stream_layout = QVBoxLayout()
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(384, 216)  # 16:9 aspect ratio
        self.image_label.setStyleSheet("background: #222; border: 1px solid #888;")
        stream_layout.addWidget(self.image_label)
        stream_group.setLayout(stream_layout)
        left_layout.addWidget(stream_group)

        # --- Stream Control Section ---
        control_group = QGroupBox("Stream Controls")
        control_layout = QVBoxLayout()
        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_stream)
        self.reconnect_btn = QPushButton("Reconnect")
        self.reconnect_btn.clicked.connect(self.try_reconnect)
        control_layout.addWidget(self.toggle_btn)
        control_layout.addWidget(self.reconnect_btn)
        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)

        # --- Capture Image Button ---
        capture_btn_group = QGroupBox("Image Capture")
        capture_btn_layout = QVBoxLayout()
        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.setEnabled(False)  # Dead button for now
        capture_btn_layout.addWidget(self.capture_btn)
        capture_btn_group.setLayout(capture_btn_layout)
        left_layout.addWidget(capture_btn_group)

        # --- Camera Settings Section ---
        config_group = QGroupBox("Camera Settings")
        grid = QGridLayout()
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(1, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda val: self.jpeg_label.setText(f"JPEG: {val}"))
        self.res_dropdown = QComboBox()
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)
        self.res_dropdown.currentIndexChanged.connect(self.update_fps_slider)
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 120)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda val: self.fps_label.setText(f"FPS: {val}"))
        self.update_fps_slider()
        grid.addWidget(self.jpeg_label, 0, 0)
        grid.addWidget(self.jpeg_slider, 0, 1)
        grid.addWidget(QLabel("Resolution"), 1, 0)
        grid.addWidget(self.res_dropdown, 1, 1)
        grid.addWidget(self.fps_label, 2, 0)
        grid.addWidget(self.fps_slider, 2, 1)
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_config)
        grid.addWidget(self.apply_btn, 3, 0, 1, 2)
        config_group.setLayout(grid)
        left_layout.addWidget(config_group)

        # --- System Info Section (moved to left column, bottom) ---
        info_group = QGroupBox("System Info")
        info_layout = QVBoxLayout()
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
            info_layout.addWidget(label)
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)

        left_layout.addStretch()

        # --- Detector Output Section (right column) ---
        detector_group = QGroupBox("Detector Output")
        detector_layout = QVBoxLayout()
        self.analysed_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.analysed_label.setFixedSize(384, 216)  # 16:9 aspect ratio
        self.analysed_label.setStyleSheet("background: #222; border: 1px solid #888;")
        detector_layout.addWidget(self.analysed_label)
        detector_group.setLayout(detector_layout)
        right_layout.addWidget(detector_group)

        # --- Detection Control ---
        detector_btn_group = QGroupBox("Detection Control")
        detector_btn_layout = QVBoxLayout()
        self.detector_btn = QPushButton("Start Detector")
        self.detector_btn.setEnabled(False)
        self.detector_btn.clicked.connect(self.toggle_detector)
        detector_btn_layout.addWidget(self.detector_btn)
        detector_btn_group.setLayout(detector_btn_layout)
        right_layout.addWidget(detector_btn_group)

        # --- Payload Mode Section ---
        payload_group = QGroupBox("Payload Mode")
        payload_layout = QVBoxLayout()
        self.graph_mode_label = QLabel("Payload Mode:")
        self.graph_dropdown = QComboBox()
        self.graph_dropdown.addItems([
            "None",
            "Relative Distance",
            "Relative Angle",
            "Angular Position"
        ])
        self.launch_graph_btn = QPushButton("Launch Payload")
        self.launch_graph_btn.clicked.connect(self.launch_graph)
        payload_layout.addWidget(self.graph_mode_label)
        payload_layout.addWidget(self.graph_dropdown)
        payload_layout.addWidget(self.launch_graph_btn)
        payload_group.setLayout(payload_layout)
        right_layout.addWidget(payload_group)

        # --- Record Button with Duration Selection ---
        record_group = QGroupBox("Record Payload")
        record_layout = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.record_btn.setEnabled(False)  # Dead button for now
        self.duration_dropdown = QComboBox()
        self.duration_dropdown.addItems(["5s", "10s", "30s", "60s"])
        record_layout.addWidget(self.record_btn)
        record_layout.addWidget(self.duration_dropdown)
        record_group.setLayout(record_layout)
        right_layout.addWidget(record_group)

        # --- Graph Display Placeholder ---
        graph_display_group = QGroupBox("Graph Display")
        graph_display_layout = QVBoxLayout()
        self.graph_display_label = QLabel("Graph will appear here.")
        self.graph_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.graph_display_label.setMinimumSize(384, 216)
        self.graph_display_label.setStyleSheet("background: #eee; border: 1px dashed #aaa; color: #888;")
        graph_display_layout.addWidget(self.graph_display_label)
        graph_display_group.setLayout(graph_display_layout)
        right_layout.addWidget(graph_display_group)

        right_layout.addStretch()

    def launch_graph(self):
        mode = self.graph_dropdown.currentText()
        print(f"[DEBUG] Launch Graph clicked - Mode selected: {mode}")
        # We'll wire this up to graph classes later

    def setup_socket_events(self):
        @sio.event
        def connect():
            self.status_label.setText("Status: Connected")
            self.toggle_btn.setEnabled(True)
            self.detector_btn.setEnabled(True)
            self.apply_config()  # <-- Automatically apply current settings on connect

        @sio.event
        def disconnect():
            self.status_label.setText("Status: Disconnected")
            self.toggle_btn.setEnabled(False)
            self.detector_btn.setEnabled(False)

        @sio.on("frame")
        def on_frame(data):
            try:
                arr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    self.current_frame_size = len(data)
                    self.frame_counter += 1
                    bridge.frame_received.emit(frame)
                else:
                    logging.warning("Frame decode returned None")
            except Exception as e:
                logging.exception("Frame decode error")

        @sio.on("sensor_broadcast")
        def on_sensor_data(data):
            try:
                temp = data.get("temperature", 0)
                cpu = data.get("cpu_percent", 0)
                self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
                self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
            except Exception as e:
                logging.exception("Sensor update failed")

    def update_fps_slider(self):
        self.fps_slider.setRange(1, 120)
        self.fps_label.setText(f"FPS: {self.fps_slider.value()}")

    def toggle_stream(self):
        if not sio.connected:
            return
        self.streaming = not self.streaming
        self.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        was_streaming = self.streaming
        if was_streaming:
            # Stop stream before applying config
            self.streaming = False
            self.toggle_btn.setText("Start Stream")
            sio.emit("stop_camera")
            time.sleep(0.5)
        res_idx = self.res_dropdown.currentIndex()
        _, resolution = RES_PRESETS[res_idx]
        fps = self.fps_slider.value()
        config = {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": fps,
            "resolution": resolution
        }
        sio.emit("camera_config", config)
        logging.info(f"Sent config: {config}")
        if was_streaming:
            sio.emit("start_camera")
            self.streaming = True
            self.toggle_btn.setText("Stop Stream")

    def toggle_detector(self):
        self.detector_active = not self.detector_active
        self.detector_btn.setText("Stop Detector" if self.detector_active else "Start Detector")
        if self.detector_active:
            threading.Thread(target=self.run_detector, daemon=True).start()
        else:
            self.clear_queue()

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
            self.clear_queue()
            self.frame_queue.put(self.last_frame)

    def update_analysed_image(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        pixmap = pixmap.scaled(self.analysed_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.analysed_label.setPixmap(pixmap)

    def clear_queue(self):
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

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
            except Exception:
                self.info_labels["speed"].setText("Upload: Error")
                self.info_labels["max_frame"].setText("Max Frame: -- KB")

        threading.Thread(target=run_speedtest, daemon=True).start()

    def timerEvent(self, event):
        self.current_fps = self.frame_counter
        self.frame_counter = 0
        self.info_labels["fps"].setText(f"FPS: {self.current_fps}")
        self.info_labels["frame_size"].setText(f"Frame Size: {self.current_frame_size / 1024:.1f} KB")

    def try_reconnect(self):
        threading.Thread(target=self.reconnect_socket, daemon=True).start()

    def reconnect_socket(self):
        was_streaming = self.streaming
        try:
            if was_streaming:
                self.streaming = False
                self.toggle_btn.setText("Start Stream")
                sio.emit("stop_camera")
                time.sleep(0.5)
            sio.disconnect()
        except:
            pass
        try:
            sio.connect(SERVER_URL, wait_timeout=5)
            # Apply config after reconnect
            self.apply_config()
            if was_streaming:
                sio.emit("start_camera")
                self.streaming = True
                self.toggle_btn.setText("Stop Stream")
        except Exception as e:
            logging.exception("Reconnect failed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    def socket_thread():
        while True:
            try:
                sio.connect(SERVER_URL, wait_timeout=5)
                sio.wait()
            except Exception as e:
                logging.exception("SocketIO connection error")
                time.sleep(5)

    threading.Thread(target=socket_thread, daemon=True).start()
    sys.exit(app.exec())
