import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage
import detector4  # Make sure detector4.py is in the same folder

from distance import RelativeDistancePlotter
from relative_angle import RelativeAnglePlotter
from spin import AngularPositionPlotter

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
    # --- GUI Color & Style Variables ---
    COLOR_BG = "#222"
    COLOR_BOX_BG = "#222"
    COLOR_BOX_BORDER = "#888"
    COLOR_BOX_BORDER_LIVE = "#ff0000"
    COLOR_BOX_BORDER_DETECTOR = "#ff2222"
    COLOR_BOX_BORDER_CAMERA_CONTROLS = "#888"
    COLOR_BOX_BORDER_CONFIG = "#888"
    COLOR_BOX_BORDER_SYSTEM_INFO = "#888"
    COLOR_BOX_BORDER_LIDAR = "#888"
    COLOR_BOX_BORDER_SUBSYSTEM = "#888"
    COLOR_BOX_BORDER_COMM = "#888"
    COLOR_BOX_BORDER_ADCS = "#888"
    COLOR_BOX_BORDER_PAYLOAD = "#888"
    COLOR_BOX_BORDER_CDH = "#888"
    COLOR_BOX_BORDER_ERROR = "#888"
    COLOR_BOX_BORDER_OVERALL = "#888"
    COLOR_BOX_BG_LIDAR = "white"
    COLOR_BOX_TEXT_LIDAR = "black"

    # --- Border Style Variables ---
    BOX_BORDER_THICKNESS = 1
    BOX_BORDER_STYLE = "solid"
    BOX_BORDER_RADIUS = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client")
        self.streaming = False
        self.detector_active = False
        self.frame_queue = queue.Queue()
        self.last_frame = None

        self.shared_start_time = None


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

        self.graph_window = None

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Make left column fixed width ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_widget.setFixedWidth(420)

        # --- Make right column fixed width ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_widget.setFixedWidth(420)

        # --- ADCS column (will stretch) ---
        adcs_layout = QVBoxLayout()

        # --- Info column (new, will stretch) ---
        info_layout = QVBoxLayout()

        # --- Add columns to main layout (no separators) ---
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)
        main_layout.addLayout(adcs_layout)
        main_layout.addLayout(info_layout)

        # --- Status Section ---
        #status_group = QGroupBox("Connection Status")
        #status_layout = QVBoxLayout()
        #self.status_label = QLabel("Status: Disconnected")
        #status_layout.addWidget(self.status_label)
        #status_group.setLayout(status_layout)
        #left_layout.addWidget(status_group)

        # --- Live Stream Section ---
        stream_group = QGroupBox("Live Stream")
        stream_layout = QVBoxLayout()
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(384, 216)  # 16:9 aspect ratio
        self.image_label.setStyleSheet("background: #222; border: 1px solid #888;")
        stream_layout.addWidget(self.image_label)
        stream_group.setLayout(stream_layout)
        left_layout.addWidget(stream_group)

        # --- Camera Controls Section (combining Stream and Capture) ---
        camera_controls_group = QGroupBox("Camera Controls")
        camera_controls_layout = QGridLayout()

        # Stream controls
        self.toggle_btn = QPushButton("Start Stream")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_stream)

        self.reconnect_btn = QPushButton("Reconnect")
        self.reconnect_btn.clicked.connect(self.try_reconnect)

        # Image controls
        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.setEnabled(False)  # Dead button for now

        self.crop_btn = QPushButton("Crop")
        self.crop_btn.setEnabled(False)  # Enable as needed

        # Arrange buttons in a 2x2 grid
        camera_controls_layout.addWidget(self.toggle_btn, 0, 0)
        camera_controls_layout.addWidget(self.reconnect_btn, 0, 1)
        camera_controls_layout.addWidget(self.capture_btn, 1, 0)
        camera_controls_layout.addWidget(self.crop_btn, 1, 1)

        camera_controls_group.setLayout(camera_controls_layout)
        left_layout.addWidget(camera_controls_group)

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

        # --- ADCS Section (third column) ---
        adcs_group = QGroupBox("ADCS")
        adcs_box_layout = QVBoxLayout()
        adcs_placeholder = QLabel("ADCS Placeholder\n(More controls coming soon)")
        adcs_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        adcs_placeholder.setMinimumHeight(200)
        adcs_box_layout.addWidget(adcs_placeholder)
        adcs_group.setLayout(adcs_box_layout)
        adcs_layout.addWidget(adcs_group)
        adcs_layout.addStretch()

        # --- System Info Section (move back to left column) ---
        info_group = QGroupBox("System Info")
        info_layout_inner = QVBoxLayout()
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
            info_layout_inner.addWidget(label)
        info_group.setLayout(info_layout_inner)
        left_layout.addWidget(info_group)

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



        # --- Prepare Record Button for dynamic use ---
        self.record_btn = QPushButton("Record")
        self.record_btn.setEnabled(False)  # Enable as needed
        self.duration_dropdown = QComboBox()
        self.duration_dropdown.addItems(["5s", "10s", "30s", "60s"])

        # --- Graph Display Placeholder ---
        graph_display_group = QGroupBox("Graph Display")
        self.graph_display_layout = QVBoxLayout()
        self.graph_display_placeholder = QWidget()
        self.graph_display_placeholder_layout = QVBoxLayout(self.graph_display_placeholder)
        self.graph_display_placeholder_layout.setContentsMargins(10, 10, 10, 10)
        self.graph_display_placeholder_layout.setSpacing(15)

        # Set fixed height for the graph display group and placeholder (adjust as needed)
        graph_display_group.setFixedHeight(300)  # Half of previous 360, adjust as needed
        self.graph_display_placeholder.setFixedHeight(260)  # Slightly less than group to allow for margins

        self.graph_modes = ["Relative Distance", "Relative Angle", "Angular Position"]
        self.select_buttons = {}

        for mode in self.graph_modes:
            btn = QPushButton(mode)
            btn.setMinimumHeight(60)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    background-color: #444;
                    color: white;
                    border: 2px solid #888;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #666;
                }
            """)
            btn.clicked.connect(lambda _, m=mode: self.load_graph(m))
            self.graph_display_placeholder_layout.addWidget(btn)
            self.select_buttons[mode] = btn

        self.graph_display_layout.addWidget(self.graph_display_placeholder)
        graph_display_group.setLayout(self.graph_display_layout)
        right_layout.addWidget(graph_display_group)

        # --- LIDAR Section ---
        lidar_group = QGroupBox("LIDAR")
        lidar_layout = QVBoxLayout()
        lidar_placeholder = QLabel("LIDAR here")
        lidar_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lidar_placeholder.setStyleSheet("background: white; color: black; border: 1px solid #888; border-radius: 6px; font-size: 16px;")
        lidar_placeholder.setFixedHeight(60)
        lidar_layout.addWidget(lidar_placeholder)
        lidar_group.setLayout(lidar_layout)
        right_layout.addWidget(lidar_group)

        right_layout.addStretch()

        # --- Subsystem Info Boxes (templates) ---
        # Power Subsystem
        power_group = QGroupBox("Power Subsystem")
        power_layout = QVBoxLayout()
        lbl = QLabel("Battery Voltage: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        power_layout.addWidget(lbl)
        lbl = QLabel("Battery Current: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        power_layout.addWidget(lbl)
        lbl = QLabel("Battery Temp: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        power_layout.addWidget(lbl)
        lbl = QLabel("Status: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        power_layout.addWidget(lbl)
        power_group.setLayout(power_layout)
        info_layout.addWidget(power_group)

        # Thermal Subsystem
        thermal_group = QGroupBox("Thermal Subsystem")
        thermal_layout = QVBoxLayout()
        lbl = QLabel("Internal Temp: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        thermal_layout.addWidget(lbl)
        lbl = QLabel("Status: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        thermal_layout.addWidget(lbl)
        thermal_group.setLayout(thermal_layout)
        info_layout.addWidget(thermal_group)

        # Communication Subsystem
        comm_group = QGroupBox("Communication Subsystem")
        comm_layout = QVBoxLayout()
        lbl = QLabel("Downlink Frequency: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        comm_layout.addWidget(lbl)
        lbl = QLabel("Uplink Frequency: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        comm_layout.addWidget(lbl)
        lbl = QLabel("Signal Strength: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        comm_layout.addWidget(lbl)
        lbl = QLabel("Data Rate: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        comm_layout.addWidget(lbl)
        self.comms_status_label = QLabel("Status: Disconnected")
        comm_layout.addWidget(self.comms_status_label)
        comm_group.setLayout(comm_layout)
        info_layout.addWidget(comm_group)

        # ADCS Subsystem
        adcs_info_group = QGroupBox("ADCS Subsystem")
        adcs_info_layout = QVBoxLayout()
        for text in ["Gyro: Pending...", "Orientation: Pending...", "Sun Sensor: Pending...", "Wheel Rpm: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            adcs_info_layout.addWidget(lbl)
        adcs_info_group.setLayout(adcs_info_layout)
        info_layout.addWidget(adcs_info_group)

        # Payload Subsystem
        payload_group = QGroupBox("Payload Subsystem")
        payload_layout = QVBoxLayout()
        self.camera_status_label = QLabel("Camera: Pending...")
        self.camera_status_label.setStyleSheet("color: #bbb;")
        payload_layout.addWidget(self.camera_status_label)
        self.camera_ready_label = QLabel("Status: Not Ready")
        self.camera_ready_label.setStyleSheet("color: #bbb;")
        payload_layout.addWidget(self.camera_ready_label)
        payload_group.setLayout(payload_layout)
        info_layout.addWidget(payload_group)

        # Command and Data Handling Subsystem
        cdh_group = QGroupBox("Command & Data Handling Subsystem")
        cdh_layout = QVBoxLayout()
        for text in ["Memory Usage: Pending...", "Last Command: Pending...", "Uptime: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            cdh_layout.addWidget(lbl)
        cdh_group.setLayout(cdh_layout)
        info_layout.addWidget(cdh_group)

        # Error Log
        error_group = QGroupBox("Error Log")
        error_layout = QVBoxLayout()
        lbl = QLabel("No Critical Errors Detected: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        error_layout.addWidget(lbl)
        error_group.setLayout(error_layout)
        info_layout.addWidget(error_group)

        # Overall Status
        overall_group = QGroupBox("Overall Status")
        overall_layout = QVBoxLayout()
        for text in ["No Anomalies Detected: Pending...", "Recommended Actions: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            overall_layout.addWidget(lbl)
        overall_group.setLayout(overall_layout)
        info_layout.addWidget(overall_group)

        # --- Print Health Check Report Button above column 4 ---
        print_report_btn = QPushButton("Print Health Check Report")
        print_report_btn.setEnabled(False)  # Dead button
        info_layout.insertWidget(0, print_report_btn)

        # --- Apply Stylesheets to Groups ---
        border = f"{self.BOX_BORDER_THICKNESS}px {self.BOX_BORDER_STYLE}"
        radius = f"{self.BOX_BORDER_RADIUS}px"
        bg = self.COLOR_BOX_BG

        stream_group.setStyleSheet(f"""
            QGroupBox {{
                border: {border} {self.COLOR_BOX_BORDER_LIVE};
                border-radius: {radius};
                margin-top: 10px;
                background: {bg};
            }}
            QGroupBox:title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """)

        camera_controls_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_CAMERA_CONTROLS}; border-radius: {radius}; background: {bg}; }}"
        )

        config_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_CONFIG}; border-radius: {radius}; background: {bg}; }}"
        )

        info_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_SYSTEM_INFO}; border-radius: {radius}; background: {bg}; }}"
        )

        detector_group.setStyleSheet(f"""
            QGroupBox {{
                border: {border} {self.COLOR_BOX_BORDER_DETECTOR};
                border-radius: {radius};
                margin-top: 10px;
                background: {bg};
            }}
            QGroupBox:title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """)

        detector_btn_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_DETECTOR}; border-radius: {radius}; background: {bg}; }}"
        )

        graph_display_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER}; border-radius: {radius}; background: {bg}; }}"
        )

        lidar_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_LIDAR}; border-radius: {radius}; background: {bg}; }}"
        )

        power_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_SUBSYSTEM}; border-radius: {radius}; background: {bg}; }}"
        )

        thermal_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_SUBSYSTEM}; border-radius: {radius}; background: {bg}; }}"
        )

        comm_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_COMM}; border-radius: {radius}; background: {bg}; }}"
        )

        adcs_info_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_ADCS}; border-radius: {radius}; background: {bg}; }}"
        )

        payload_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_PAYLOAD}; border-radius: {radius}; background: {bg}; }}"
        )

        cdh_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_CDH}; border-radius: {radius}; background: {bg}; }}"
        )

        error_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_ERROR}; border-radius: {radius}; background: {bg}; }}"
        )

        overall_group.setStyleSheet(
            f"QGroupBox {{ border: {border} {self.COLOR_BOX_BORDER_OVERALL}; border-radius: {radius}; background: {bg}; }}"
        )

    def load_graph(self, mode):
        # Remove the placeholder with buttons
        self.graph_display_placeholder.setParent(None)

        # Load the selected graph
        if mode == "Relative Distance":
            self.graph_widget = RelativeDistancePlotter()
        elif mode == "Relative Angle":
            self.graph_widget = AngularPositionPlotter()
        elif mode == "Angular Position":
            self.graph_widget = AngularPositionPlotter()
        else:
            return

        self.shared_start_time = time.time()
        self.graph_widget.start_time = self.shared_start_time
        self.graph_widget.setFixedHeight(230)  # Match the placeholder height
        self.graph_display_layout.addWidget(self.graph_widget)

        # Add Exit and Record buttons in a horizontal layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Add Record button (to the left)
        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.duration_dropdown)

        # Add Exit button (to the right)
        self.exit_graph_btn = QPushButton("← Back")
        self.exit_graph_btn.setMinimumHeight(self.record_btn.minimumHeight())
        self.exit_graph_btn.setMaximumHeight(self.record_btn.maximumHeight())
        self.exit_graph_btn.setMinimumWidth(self.record_btn.minimumWidth())
        self.exit_graph_btn.setMaximumWidth(self.record_btn.maximumWidth())
        self.exit_graph_btn.setStyleSheet("""
            QPushButton {
                font-size: 9pt;
                background-color: #222;
                color: white;
                border: 1px solid #888;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        self.exit_graph_btn.clicked.connect(self.exit_graph)
        btn_layout.addWidget(self.exit_graph_btn)

        # Set the same size policy as record_btn
        self.exit_graph_btn.setSizePolicy(self.record_btn.sizePolicy())

        # Add the button layout to the graph display
        self.graph_display_layout.addLayout(btn_layout)

    def exit_graph(self):
        if hasattr(self, "graph_widget") and self.graph_widget:
            self.graph_widget.setParent(None)
            self.graph_widget = None

        if hasattr(self, "exit_graph_btn"):
            self.exit_graph_btn.setParent(None)
        if hasattr(self, "record_btn"):
            self.record_btn.setParent(None)
        if hasattr(self, "duration_dropdown"):
            self.duration_dropdown.setParent(None)

        self.graph_display_layout.addWidget(self.graph_display_placeholder)

    def launch_graph(self):
        mode = self.graph_dropdown.currentText()
        print(f"[DEBUG] Launch Graph clicked - Mode selected: {mode}")

        # Remove all widgets from the graph display layout
        while self.graph_display_layout.count():
            item = self.graph_display_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        self.graph_widget = None

        # If "None" is selected, show the original placeholder label
        if mode == "None":
            self.graph_display_layout.addWidget(self.graph_display_label)
            return

        # Create new graph widget
        if mode == "Relative Distance":
            from distance import RelativeDistancePlotter
            self.graph_widget = RelativeDistancePlotter()
        elif mode == "Relative Angle":
            from relative_angle import RelativeAnglePlotter
            self.graph_widget = RelativeAnglePlotter()
        elif mode == "Angular Position":
            from spin import AngularPositionPlotter
            self.graph_widget = AngularPositionPlotter()
        else:
            QMessageBox.warning(self, "Invalid Selection", "Please choose a valid mode.")
            return

        self.shared_start_time = time.time()
        self.graph_widget.start_time = self.shared_start_time

        # Add the new graph widget into the placeholder layout
        self.graph_display_layout.addWidget(self.graph_widget)

    def setup_socket_events(self):
        @sio.event
        def connect():
            print("Connected event fired")
            self.comms_status_label.setText("Status: Connected")
            self.toggle_btn.setEnabled(True)
            self.detector_btn.setEnabled(True)
            self.apply_config()
            # Ensure camera is idle unless streaming is already True
            if not self.streaming:
                sio.emit("stop_camera")
            sio.emit("get_camera_status")

        @sio.event
        def disconnect():
            self.comms_status_label.setText("Status: Disconnected")
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

        @sio.on("camera_status")
        def on_camera_status(data):
            status = data.get("status", "Unknown")
            self.camera_status_label.setText(f"Camera: {status}")
            self.camera_status_label.setStyleSheet(
                "color: white;" if status.lower() in ("streaming", "idle", "ready") else "color: #bbb;"
            )
            # Only show "Not Ready" in red if status is a known error/problem
            error_statuses = {"error", "not connected", "damaged", "not found", "unavailable", "failed"}
            if status.lower() in error_statuses:
                self.camera_ready_label.setText("Status: Not Ready")
                self.camera_ready_label.setStyleSheet("color: #f00;")  # Red for not ready
            else:
                self.camera_ready_label.setText("Status: Ready")
                self.camera_ready_label.setStyleSheet("color: #0f0;")  # Green for ready

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
            
                # Get both the analysed frame and pose (if available)
                analysed, pose = detector4.detect_and_draw(frame, return_pose=True)
                bridge.analysed_frame.emit(analysed)

                # Feed pose data to graph if graph is active
                if hasattr(self, "graph_widget") and self.graph_widget and pose:
                    rvec, tvec = pose
                    timestamp = time.time()
                    self.graph_widget.update(rvec, tvec, timestamp)

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
    win.showMaximized()

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
