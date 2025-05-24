import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea  # <-- add QScrollArea here
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
from payload import detector4
from widgets.camera_controls import CameraControlsWidget
from widgets.camera_settings import CameraSettingsWidget
from widgets.graph_section import GraphSection
from widgets.detector_output import DetectorOutputWidget
from widgets.detector_control import DetectorControlWidget
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR, 
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE, BUTTON_HEIGHT
)


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
    # --- Sleek Dark Sci-Fi Theme ---
    COLOR_BG = BACKGROUND
    COLOR_BOX_BG = BOX_BACKGROUND
    COLOR_BOX_BORDER = BORDER_COLOR
    COLOR_BOX_BORDER_LIVE = BORDER_COLOR
    COLOR_BOX_BORDER_DETECTOR = BORDER_COLOR
    COLOR_BOX_BORDER_CAMERA_CONTROLS = BORDER_COLOR
    COLOR_BOX_BORDER_CONFIG = BORDER_COLOR
    COLOR_BOX_BORDER_SYSTEM_INFO = BORDER_COLOR
    COLOR_BOX_BORDER_LIDAR = BORDER_COLOR
    COLOR_BOX_BORDER_SUBSYSTEM = BORDER_COLOR
    COLOR_BOX_BORDER_COMM = BORDER_COLOR
    COLOR_BOX_BORDER_ADCS = BORDER_COLOR
    COLOR_BOX_BORDER_PAYLOAD = BORDER_COLOR
    COLOR_BOX_BORDER_CDH = BORDER_COLOR
    COLOR_BOX_BORDER_ERROR = BORDER_ERROR
    COLOR_BOX_BORDER_OVERALL = BORDER_COLOR
    COLOR_BOX_BG_LIDAR = BOX_BACKGROUND
    COLOR_BOX_TEXT_LIDAR = BOX_TITLE_COLOR
    COLOR_BOX_BORDER_GRAPH = BORDER_COLOR

    # --- Border Style Variables ---
    BOX_BORDER_THICKNESS = BORDER_WIDTH
    BOX_BORDER_STYLE = "solid"
    BOX_BORDER_RADIUS = BORDER_RADIUS  # Use theme radius for consistency

    FONT_FAMILY = FONT_FAMILY

    # --- Button Style ---
    BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {BOX_BACKGROUND};
        color: {BUTTON_TEXT};
        border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
        border-radius: {BORDER_RADIUS}px;
        padding: {PADDING_NORMAL}px {PADDING_LARGE}px;
        font-size: {FONT_SIZE_NORMAL}pt;
        font-family: {FONT_FAMILY};
    }}
    QPushButton:hover {{
        background-color: {BUTTON_HOVER};
        color: black;
    }}
    QPushButton:disabled {{
        background-color: {BUTTON_DISABLED};
        color: #777;
        border: {BORDER_WIDTH}px solid #555;
    }}
    """

    # --- Label Style ---
    LABEL_STYLE = f"""
    QLabel {{
        color: {TEXT_COLOR};
        font-size: {FONT_SIZE_NORMAL}pt;
        font-family: {FONT_FAMILY};
    }}
    """

    # --- GroupBox Header Style ---
    GROUPBOX_STYLE = f"""
    QGroupBox {{
        border: 2px solid {BORDER_COLOR};
        border-radius: 4px;
        background-color: {BOX_BACKGROUND};
        margin-top: 10px;
        color: {BOX_TITLE_COLOR};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        font-size: {FONT_SIZE_TITLE}pt;
        font-family: {FONT_FAMILY};
        color: {BOX_TITLE_COLOR};
    }}
    """

    # --- Stream Content Size Constants ---
    STREAM_WIDTH = 384
    STREAM_HEIGHT = 216
    MARGIN = 20

    def __init__(self):
        super().__init__()
        # Set global background and font for the sci-fi theme
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BACKGROUND};
                color: {TEXT_COLOR};
                font-family: {self.FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
        """)
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

    def apply_groupbox_style(self, groupbox, border_color):
        border = f"{self.BOX_BORDER_THICKNESS}px {self.BOX_BORDER_STYLE}"
        radius = f"{self.BOX_BORDER_RADIUS}px"
        bg_color = self.COLOR_BG

        groupbox.setStyleSheet(f"""
            QGroupBox {{
                border: {border} {border_color};
                border-radius: {radius};
                background-color: {bg_color};
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {self.FONT_FAMILY};
                color: {BOX_TITLE_COLOR};
            }}
        """)

    def style_button(self, btn):
        btn.setStyleSheet(self.BUTTON_STYLE)
        btn.setFixedHeight(BUTTON_HEIGHT)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # Uniform spacing and margins for main and sublayouts
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Make left column responsive ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_widget.setFixedWidth(self.STREAM_WIDTH + self.MARGIN * 2)
        left_widget.setMinimumWidth(350)
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- Make right column responsive ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_widget.setFixedWidth(self.STREAM_WIDTH + self.MARGIN * 2)
        right_widget.setMinimumWidth(350)
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- ADCS column (will stretch) ---
        adcs_layout = QVBoxLayout()
        adcs_layout.setSpacing(15)
        adcs_layout.setContentsMargins(10, 10, 10, 10)

        # --- Info column (new, will stretch) ---
        # Create a scrollable container for info layout (4th column)
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(15)
        info_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_container)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")  # Optional: remove border

        # --- Add columns to main layout (no separators) ---
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)
        main_layout.addLayout(adcs_layout)
        main_layout.addWidget(scroll_area)  # Use scroll area for info column

        # --- Live Stream Section ---
        stream_group = QGroupBox("Live Stream")
        stream_layout = QVBoxLayout()
        stream_layout.setSpacing(10)
        stream_layout.setContentsMargins(10, 10, 10, 10)
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(384, 216)  # 16:9 aspect ratio
        self.image_label.setStyleSheet(f"""
            background-color: {STREAM_BACKGROUND};
            border: {BORDER_WIDTH}px solid {BORDER_COLOR};
        """)
        stream_layout.addWidget(self.image_label)
        stream_group.setLayout(stream_layout)
        left_layout.addWidget(stream_group)

        # --- Camera Controls Section ---
        self.camera_controls = CameraControlsWidget()
        self.camera_controls.layout.setSpacing(10)
        self.camera_controls.layout.setContentsMargins(10, 10, 10, 10)
        left_layout.addWidget(self.camera_controls)
        # Apply button style to camera controls buttons
        self.style_button(self.camera_controls.toggle_btn)
        self.style_button(self.camera_controls.reconnect_btn)
        self.style_button(self.camera_controls.capture_btn)
        self.style_button(self.camera_controls.crop_btn)
        self.camera_controls.toggle_btn.clicked.connect(self.toggle_stream)
        self.camera_controls.reconnect_btn.clicked.connect(self.try_reconnect)
        self.camera_controls.capture_btn.setEnabled(False)
        self.camera_controls.crop_btn.setEnabled(False)

        # --- Camera Settings Section ---
        self.camera_settings = CameraSettingsWidget()
        self.camera_settings.layout.setSpacing(10)
        self.camera_settings.layout.setContentsMargins(10, 10, 10, 10)
        left_layout.addWidget(self.camera_settings)
        self.style_button(self.camera_settings.apply_btn)
        self.camera_settings.apply_btn.clicked.connect(self.apply_config)


        # --- ADCS Section (third column) ---
        adcs_group = QGroupBox("ADCS")
        adcs_box_layout = QVBoxLayout()
        adcs_box_layout.setSpacing(10)
        adcs_box_layout.setContentsMargins(10, 10, 10, 10)
        adcs_placeholder = QLabel("ADCS Placeholder\n(More controls coming soon)")
        adcs_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        adcs_placeholder.setMinimumHeight(200)
        adcs_box_layout.addWidget(adcs_placeholder)
        adcs_group.setLayout(adcs_box_layout)
        adcs_layout.addWidget(adcs_group)
        adcs_layout.addStretch()

        # Apply consistent groupbox style to ADCS section
        self.apply_groupbox_style(adcs_group, self.COLOR_BOX_BORDER_ADCS)

        # --- System Info Section (move back to left column) ---
        info_group = QGroupBox("System Info")
        info_layout_inner = QVBoxLayout()
        info_layout_inner.setSpacing(10)
        info_layout_inner.setContentsMargins(10, 10, 10, 10)
        self.info_labels = {
            "temp": QLabel("Temp: -- °C"),
            "cpu": QLabel("CPU: --%"),
            "speed": QLabel("Upload: -- Mbps"),
            "max_frame": QLabel("Max Frame: -- KB"),
            "fps": QLabel("FPS: --"),
            "frame_size": QLabel("Frame Size: -- KB"),
        }
        for label in self.info_labels.values():
            label.setStyleSheet(self.LABEL_STYLE)
            info_layout_inner.addWidget(label)
        info_group.setLayout(info_layout_inner)
        left_layout.addWidget(info_group)
        info_group.setStyleSheet(info_group.styleSheet() + self.LABEL_STYLE)

        # --- Detector Output Section (right column) ---
        self.detector_output = DetectorOutputWidget()
        # FIX: layout is an attribute, not a method
        self.detector_output.layout.setSpacing(10)
        self.detector_output.layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(self.detector_output)

        # --- Detection Control ---
        self.detector_controls = DetectorControlWidget()
        self.detector_controls.apply_style(self.BUTTON_STYLE)  # Apply consistent button style
        self.detector_controls.layout.setSpacing(10)
        self.detector_controls.layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(self.detector_controls)
        self.detector_controls.detector_btn.clicked.connect(self.toggle_detector)

        # --- Graph Display Section (replaced with modular widget) ---
        # Make sure to create the graph_section before using it!
        self.record_btn = QPushButton("Record")
        self.duration_dropdown = QComboBox()
        self.graph_section = GraphSection(self.record_btn, self.duration_dropdown)

        self.graph_section.graph_display_layout.setSpacing(10)
        self.graph_section.graph_display_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(self.graph_section)

        # --- LIDAR Section ---
        lidar_group = QGroupBox("LIDAR")
        lidar_layout = QVBoxLayout()
        lidar_layout.setSpacing(10)
        lidar_layout.setContentsMargins(10, 10, 10, 10)
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
        for text in ["Battery Voltage: Pending...", "Battery Current: Pending...", "Battery Temp: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            power_layout.addWidget(lbl)
        power_group.setLayout(power_layout)
        info_layout.addWidget(power_group)

        # Thermal Subsystem
        thermal_group = QGroupBox("Thermal Subsystem")
        thermal_layout = QVBoxLayout()
        for text in ["Internal Temp: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            thermal_layout.addWidget(lbl)
        thermal_group.setLayout(thermal_layout)
        info_layout.addWidget(thermal_group)

        # Communication Subsystem
        comm_group = QGroupBox("Communication Subsystem")
        comm_layout = QVBoxLayout()
        for text in ["Downlink Frequency: Pending...", "Uplink Frequency: Pending...", "Signal Strength: Pending...", "Data Rate: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            comm_layout.addWidget(lbl)
        self.comms_status_label = QLabel("Status: Disconnected")
        self.comms_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        comm_layout.addWidget(self.comms_status_label)
        comm_group.setLayout(comm_layout)
        info_layout.addWidget(comm_group)

        # ADCS Subsystem
        adcs_info_group = QGroupBox("ADCS Subsystem")
        adcs_info_layout = QVBoxLayout()
        for text in ["Gyro: Pending...", "Orientation: Pending...", "Sun Sensor: Pending...", "Wheel Rpm: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            adcs_info_layout.addWidget(lbl)
        adcs_info_group.setLayout(adcs_info_layout)
        info_layout.addWidget(adcs_info_group)

        # Payload Subsystem
        payload_group = QGroupBox("Payload Subsystem")
        payload_layout = QVBoxLayout()
        self.camera_status_label = QLabel("Camera: Pending...")
        self.camera_status_label.setStyleSheet("color: #bbb;")
        self.camera_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        payload_layout.addWidget(self.camera_status_label)
        self.camera_ready_label = QLabel("Status: Not Ready")
        self.camera_ready_label.setStyleSheet("color: #bbb;")
        self.camera_ready_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
        self.style_button(print_report_btn)
        info_layout.insertWidget(0, print_report_btn)



        self.apply_groupbox_style(stream_group, self.COLOR_BOX_BORDER_LIVE)
        self.apply_groupbox_style(info_group, self.COLOR_BOX_BORDER_SYSTEM_INFO)
        self.apply_groupbox_style(lidar_group, self.COLOR_BOX_BORDER_LIDAR)
        self.apply_groupbox_style(power_group, self.COLOR_BOX_BORDER_SUBSYSTEM)
        self.apply_groupbox_style(thermal_group, self.COLOR_BOX_BORDER_SUBSYSTEM)
        self.apply_groupbox_style(comm_group, self.COLOR_BOX_BORDER_COMM)
        self.apply_groupbox_style(adcs_info_group, self.COLOR_BOX_BORDER_ADCS)
        self.apply_groupbox_style(payload_group, self.COLOR_BOX_BORDER_PAYLOAD)
        self.apply_groupbox_style(cdh_group, self.COLOR_BOX_BORDER_CDH)
        self.apply_groupbox_style(error_group, self.COLOR_BOX_BORDER_ERROR)
        self.apply_groupbox_style(overall_group, self.COLOR_BOX_BORDER_OVERALL)
        self.apply_groupbox_style(self.camera_controls, self.COLOR_BOX_BORDER_CAMERA_CONTROLS)
        self.apply_groupbox_style(self.camera_settings, self.COLOR_BOX_BORDER_CONFIG)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        self.apply_groupbox_style(self.detector_output, self.COLOR_BOX_BORDER_DETECTOR)
        self.apply_groupbox_style(self.detector_controls, self.COLOR_BOX_BORDER_SUBSYSTEM)


    def setup_socket_events(self):
        @sio.event
        def connect():
            self.comms_status_label.setText("Status: Connected")
            self.camera_controls.toggle_btn.setEnabled(True)
            self.detector_controls.detector_btn.setEnabled(True)
            self.apply_config()
            # Delay emits to ensure connection is fully established
            def delayed_emits():
                if not self.streaming:
                    sio.emit("stop_camera")
                sio.emit("get_camera_status")
            QTimer.singleShot(100, delayed_emits)

        @sio.event
        def disconnect(reason=None):
            self.comms_status_label.setText("Status: Disconnected")
            self.camera_controls.toggle_btn.setEnabled(False)
            self.detector_controls.detector_btn.setEnabled(False)

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
        self.camera_controls.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")
    
    def apply_config(self):
        was_streaming = self.streaming
        if was_streaming:
            # Stop stream before applying config
            self.streaming = False
            self.camera_controls.toggle_btn.setText("Start Stream")
            sio.emit("stop_camera")
            time.sleep(0.5)
        config = self.camera_settings.get_config()

        sio.emit("camera_config", config)
        logging.info(f"Sent config: {config}")
        if was_streaming:
            sio.emit("start_camera")
            self.streaming = True
            self.camera_controls.toggle_btn.setText("Stop Stream")

    def toggle_detector(self):
        self.detector_active = not self.detector_active
        self.detector_controls.detector_btn.setText("Stop Detector" if self.detector_active else "Start Detector")
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
                if self.graph_section.graph_widget and pose:
                    rvec, tvec = pose
                    timestamp = time.time()
                    self.graph_section.graph_widget.update(rvec, tvec, timestamp)

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
        pixmap = pixmap.scaled(self.detector_output.label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.detector_output.label.setPixmap(pixmap)

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
                self.camera_controls.toggle_btn.setText("Start Stream")
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
                self.camera_controls.toggle_btn.setText("Stop Stream")
        except Exception as e:
            logging.exception("Reconnect failed")

    def show_message(self, title, message, icon=QMessageBox.Icon.Information):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)

        # Full override of internal structure for best cross-platform results
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #3b3e44;
            }
            QMessageBox QLabel {
                color: #f0f0f0;
                background-color: transparent;
                font-family: 'Roboto Condensed', 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
            QMessageBox QPushButton {
                background-color: #40444b;
                color: #ffcc00;
                border: 2px solid #777;
                border-radius: 2px;
                padding: 6px 12px;
                font-size: 9pt;
                font-family: 'Roboto Condensed', 'Segoe UI', sans-serif;
            }
            QMessageBox QPushButton:hover {
                background-color: #50575f;
                border: 2px solid #ffcc00;
            }
        """)
        msg_box.exec()

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
