import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue, os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage, QFont, QPainter, QPen
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
from payload import detector4
from widgets.camera_controls import CameraControlsWidget
from widgets.camera_settings import CameraSettingsWidget, CALIBRATION_FILES
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
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR, SECOND_COLUMN,
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
    speedtest_result = pyqtSignal(float, float)  # upload_mbps, max_frame_size_kb

    # --- Sleek Dark Sci-Fi Theme ---
    COLOR_BG = BACKGROUND
    COLOR_BOX_BG = BOX_BACKGROUND
    COLOR_BOX_BG_RIGHT = SECOND_COLUMN
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
    COLOR_BOX_BORDER_RIGHT = BORDER_COLOR
    COLOR_BOX_RADIUS_RIGHT = BORDER_RADIUS
    COLOR_BOX_TITLE_RIGHT = BOX_TITLE_COLOR
    
    # --- Border Style Variables ---
    BOX_BORDER_THICKNESS = BORDER_WIDTH
    BOX_BORDER_STYLE = "solid"
    BOX_BORDER_RADIUS = BORDER_RADIUS

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

        # Initialize crop_active state
        self.crop_active = False

        # Initialize calibration change tracking
        self.calibration_change_time = None

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

        self.speedtest_result.connect(self.update_speed_labels)

    # --- Improved groupbox styling for left/right columns ---
    def apply_groupbox_style(self, groupbox, border_color, bg_color=None, title_color=None):
        border = f"{self.BOX_BORDER_THICKNESS}px {self.BOX_BORDER_STYLE}"
        radius_value = self.COLOR_BOX_RADIUS_RIGHT if border_color == self.COLOR_BOX_BORDER_RIGHT else self.BOX_BORDER_RADIUS
        radius = f"{radius_value}px"
        bg = bg_color if bg_color else self.COLOR_BG
        title = title_color if title_color else BOX_TITLE_COLOR

        groupbox.setStyleSheet(f"""
            QGroupBox {{
                border: {border} {border_color};
                border-radius: {radius};
                background-color: {bg};
                margin-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                top: 0px;
                padding: 0 8px;
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {self.FONT_FAMILY};
                color: {title};
                background-color: {bg};
            }}
        """)

    def style_button(self, btn):
        btn.setFixedHeight(BUTTON_HEIGHT)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # --- LEFT COLUMN: 3 stacked rows, each a QHBoxLayout ---
        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        left_col.setContentsMargins(10, 10, 10, 10)
        left_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # --- Row 1: Unified Video + Controls ---
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.setContentsMargins(10, 10, 10, 10)
        row1.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # --- Unified Video Stream in Row 1 ---
        video_group = QGroupBox("Video Stream")
        video_layout = QHBoxLayout()
        video_layout.setSpacing(8)
        video_layout.setContentsMargins(5, 5, 5, 5)

        aspect_w, aspect_h = 16, 9
        video_width = 640
        video_height = int(video_width * aspect_h / aspect_w)

        # Unified Video Label
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setFixedSize(video_width, video_height)
        self.video_label.setStyleSheet(f"""
            background-color: {STREAM_BACKGROUND};
            border: {BORDER_WIDTH}px solid {BORDER_COLOR};
        """)
        video_layout.addWidget(self.video_label)

        video_group.setLayout(video_layout)
        video_group.setFixedSize(video_width + 40, video_height + 40)
        self.apply_groupbox_style(video_group, self.COLOR_BOX_BORDER_LIVE)

        # --- Controls: Stack buttons vertically inside a groupbox ---
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.setContentsMargins(10, 10, 10, 10)

        # Stream Controls Buttons
        self.camera_controls = CameraControlsWidget()
        self.camera_controls.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.camera_controls.layout.setSpacing(4)
        self.camera_controls.layout.setContentsMargins(0, 0, 0, 0)
        self.style_button(self.camera_controls.toggle_btn)
        self.style_button(self.camera_controls.reconnect_btn)
        self.style_button(self.camera_controls.capture_btn)
        self.style_button(self.camera_controls.crop_btn)
        self.camera_controls.toggle_btn.setFixedHeight(32)
        self.camera_controls.reconnect_btn.setFixedHeight(32)
        self.camera_controls.capture_btn.setFixedHeight(32)
        self.camera_controls.crop_btn.setFixedHeight(32)
        self.camera_controls.toggle_btn.clicked.connect(self.toggle_stream)
        self.camera_controls.reconnect_btn.clicked.connect(self.try_reconnect)
        self.camera_controls.capture_btn.setEnabled(False)
        self.camera_controls.crop_btn.setEnabled(True)
        self.camera_controls.crop_btn.clicked.connect(self.toggle_crop)
        controls_layout.addWidget(self.camera_controls.toggle_btn)
        controls_layout.addWidget(self.camera_controls.reconnect_btn)
        controls_layout.addWidget(self.camera_controls.capture_btn)
        controls_layout.addWidget(self.camera_controls.crop_btn)

        # Detector Controls Button
        self.detector_controls = DetectorControlWidget()
        self.detector_controls.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.detector_controls.apply_style(self.BUTTON_STYLE)
        self.detector_controls.layout.setSpacing(4)
        self.detector_controls.layout.setContentsMargins(0, 0, 0, 0)
        self.detector_controls.detector_btn.setFixedHeight(32)
        self.detector_controls.detector_btn.clicked.connect(self.toggle_detector)
        controls_layout.addWidget(self.detector_controls.detector_btn)

        controls_layout.addStretch(1)
        controls_group.setLayout(controls_layout)
        controls_group.setFixedHeight(video_height + 40)
        self.apply_groupbox_style(controls_group, self.COLOR_BOX_BORDER_CAMERA_CONTROLS)

        # --- Camera Settings ---
        self.camera_settings = CameraSettingsWidget()
        self.camera_settings.setMaximumWidth(300)
        self.camera_settings.layout.setSpacing(6)
        self.camera_settings.layout.setContentsMargins(5, 5, 5, 5)
        self.style_button(self.camera_settings.apply_btn)
        self.camera_settings.apply_btn.setFixedHeight(32)
        self.camera_settings.apply_btn.setStyleSheet(self.BUTTON_STYLE + "padding: 4px 8px; font-size: 9pt;")
        self.camera_settings.apply_btn.clicked.connect(self.apply_config)
        self.apply_groupbox_style(self.camera_settings, self.COLOR_BOX_BORDER_CONFIG)
        self.camera_settings.setFixedHeight(video_height + 40)

        # Add widgets to row1
        row1.addWidget(video_group)
        row1.addWidget(controls_group)
        row1.addWidget(self.camera_settings)

        # --- Row 2: Graph Display ---
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.setContentsMargins(10, 10, 10, 10)
        row2.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Graph Section
        self.record_btn = QPushButton("Record")
        self.duration_dropdown = QComboBox()
        self.graph_section = GraphSection(self.record_btn, self.duration_dropdown)
        self.graph_section.setFixedSize(580, 300)
        self.graph_section.graph_display_layout.setSpacing(2)
        self.graph_section.graph_display_layout.setContentsMargins(2, 2, 2, 2)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        row2.addWidget(self.graph_section)

        # --- Row 3: LIDAR + ADCS ---
        row3 = QHBoxLayout()
        row3.setSpacing(10)
        row3.setContentsMargins(10, 10, 10, 10)
        row3.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lidar_group = QGroupBox("LIDAR")
        lidar_layout = QVBoxLayout()
        lidar_layout.setSpacing(5)
        lidar_layout.setContentsMargins(5, 5, 5, 5)
        lidar_placeholder = QLabel("LIDAR here")
        lidar_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lidar_placeholder.setStyleSheet("background: white; color: black; border: 1px solid #888; border-radius: 6px; font-size: 14px;")
        lidar_placeholder.setFixedHeight(50)
        lidar_layout.addWidget(lidar_placeholder)
        lidar_group.setLayout(lidar_layout)
        self.apply_groupbox_style(lidar_group, self.COLOR_BOX_BORDER_LIDAR)

        adcs_group = QGroupBox("ADCS")
        adcs_layout = QVBoxLayout()
        adcs_layout.setSpacing(5)
        adcs_layout.setContentsMargins(5, 5, 5, 5)
        adcs_placeholder = QLabel("ADCS Placeholder\n(More controls coming soon)")
        adcs_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        adcs_placeholder.setFixedHeight(50)
        adcs_layout.addWidget(adcs_placeholder)
        adcs_group.setLayout(adcs_layout)
        self.apply_groupbox_style(adcs_group, self.COLOR_BOX_BORDER_ADCS)

        row3.addWidget(lidar_group)
        row3.addWidget(adcs_group)

        # --- Add all rows to left column ---
        left_col.addLayout(row1)
        left_col.addLayout(row2)
        left_col.addLayout(row3)

        # --- RIGHT COLUMN: System Info Panel ---
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(10)
        info_layout.setContentsMargins(10, 10, 10, 10)

        info_container.setStyleSheet(f"background-color: {self.COLOR_BOX_BG_RIGHT};")

        # System Info Group
        info_group = QGroupBox("System Info")
        info_layout_inner = QVBoxLayout()
        info_layout_inner.setSpacing(5)
        info_layout_inner.setContentsMargins(8, 8, 8, 8)
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
        self.apply_groupbox_style(
            info_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
        info_layout.addWidget(info_group)

        # --- Subsystem Info Boxes ---
        # Power Subsystem
        power_group = QGroupBox("Power Subsystem")
        power_layout = QVBoxLayout()
        for text in ["Battery Voltage: Pending...", "Battery Current: Pending...", "Battery Temp: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            power_layout.addWidget(lbl)
        power_group.setLayout(power_layout)
        self.apply_groupbox_style(
            power_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
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
        self.apply_groupbox_style(
            thermal_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
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
        self.apply_groupbox_style(
            comm_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
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
        self.apply_groupbox_style(
            adcs_info_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
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
        self.apply_groupbox_style(
            payload_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
        info_layout.addWidget(payload_group)

        # Command and Data Handling Subsystem
        cdh_group = QGroupBox("Command & Data Handling Subsystem")
        cdh_layout = QVBoxLayout()
        for text in ["Memory Usage: Pending...", "Last Command: Pending...", "Uptime: Pending...", "Status: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            cdh_layout.addWidget(lbl)
        cdh_group.setLayout(cdh_layout)
        self.apply_groupbox_style(
            cdh_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
        info_layout.addWidget(cdh_group)

        # Error Log
        error_group = QGroupBox("Error Log")
        error_layout = QVBoxLayout()
        lbl = QLabel("No Critical Errors Detected: Pending...")
        lbl.setStyleSheet("color: #bbb;")
        error_layout.addWidget(lbl)
        error_group.setLayout(error_layout)
        self.apply_groupbox_style(
            error_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
        info_layout.addWidget(error_group)

        # Overall Status
        overall_group = QGroupBox("Overall Status")
        overall_layout = QVBoxLayout()
        for text in ["No Anomalies Detected: Pending...", "Recommended Actions: Pending..."]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #bbb;")
            overall_layout.addWidget(lbl)
        overall_group.setLayout(overall_layout)
        self.apply_groupbox_style(
            overall_group,
            self.COLOR_BOX_BORDER_RIGHT,
            self.COLOR_BOX_BG_RIGHT,
            self.COLOR_BOX_TITLE_RIGHT
        )
        info_layout.addWidget(overall_group)

        # Print Health Check Report Button
        print_report_btn = QPushButton("Print Health Check Report")
        print_report_btn.setEnabled(False)
        self.style_button(print_report_btn)
        info_layout.insertWidget(0, print_report_btn)

        # Scroll Area for right column
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_container)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid #2b2b2b;
                border-radius: 0px;
                background: {self.COLOR_BOX_BG_RIGHT};
                min-width: 220px;
                max-width: 260px;
            }}
            QScrollBar:horizontal, QScrollBar:vertical {{ height: 0px; width: 0px; background: transparent; }}
            QWidget {{ min-width: 200px; background: {self.COLOR_BOX_BG_RIGHT}; }}
        """)
        info_container.setMinimumWidth(200)
        info_container.setMaximumWidth(240)

        # --- Add columns to main layout ---
        main_layout.addLayout(left_col, stretch=6)
        main_layout.addWidget(scroll_area, stretch=0)
        main_layout.setAlignment(scroll_area, Qt.AlignmentFlag.AlignRight)

    def setup_socket_events(self):
        @sio.event
        def connect():
            print("[DEBUG] ✓ Connected to server")
            self.comms_status_label.setText("Status: Connected")
            self.camera_controls.toggle_btn.setEnabled(True)
            self.detector_controls.detector_btn.setEnabled(True)
            # Enable crop button when connected
            self.camera_controls.crop_btn.setEnabled(True)
            self.apply_config()
            def delayed_emits():
                if not self.streaming:
                    sio.emit("stop_camera")
                sio.emit("get_camera_status")
            QTimer.singleShot(100, delayed_emits)

        @sio.event
        def disconnect(reason=None):
            print(f"[DEBUG] ❌ Disconnected from server: {reason}")
            self.comms_status_label.setText("Status: Disconnected")
            self.camera_controls.toggle_btn.setEnabled(False)
            self.detector_controls.detector_btn.setEnabled(False)
            # Disable crop button when disconnected
            self.camera_controls.crop_btn.setEnabled(False)

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
                    print("[WARNING] Frame decode returned None")
                    logging.warning("Frame decode returned None")
            except Exception as e:
                print(f"[ERROR] Frame decode error: {e}")
                logging.exception("Frame decode error")
                import traceback
                traceback.print_exc()

        @sio.on("sensor_broadcast")
        def on_sensor_data(data):
            try:
                temp = data.get("temperature", 0)
                cpu = data.get("cpu_percent", 0)
                self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
                self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
            except Exception as e:
                print(f"[ERROR] Sensor update error: {e}")
                logging.exception("Sensor update failed")

        @sio.on("camera_status")
        def on_camera_status(data):
            try:
                status = data.get("status", "Unknown")
                print(f"[DEBUG] Camera status received: {status}")
                self.camera_status_label.setText(f"Camera: {status}")
                
                if status.lower() in ("streaming", "idle", "ready"):
                    self.camera_status_label.setStyleSheet("color: white;")
                else:
                    self.camera_status_label.setStyleSheet("color: #bbb;")
                
                error_statuses = {"error", "not connected", "damaged", "not found", "unavailable", "failed"}
                if status.lower() in error_statuses:
                    self.camera_ready_label.setText("Status: Not Ready")
                    self.camera_ready_label.setStyleSheet("color: #f00;")
                else:
                    self.camera_ready_label.setText("Status: Ready")
                    self.camera_ready_label.setStyleSheet("color: #0f0;")
                    
            except Exception as e:
                print(f"[ERROR] Camera status update error: {e}")

    def toggle_stream(self):
        if not sio.connected:
            return
        self.streaming = not self.streaming
        self.camera_controls.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")
    
    def apply_config(self):
        was_streaming = self.streaming
        if was_streaming:
            self.toggle_stream()

        # Get config including calibration file
        config = self.camera_settings.get_config()
        
        # Send config to server
        sio.emit("camera_config", config)
        
        # **PAUSE DISPLAY FOR 1 SECOND - NO VISUAL PLACEHOLDER**
        try:
            print("[DEBUG] 📊 Pausing display for calibration/crop change...")
            self.calibration_change_time = time.time()
            
            # Start a timer to clear the pause after 1 second
            QTimer.singleShot(1000, self.resume_after_calibration_change)
            
        except Exception as e:
            print(f"[DEBUG] Display pause failed (continuing anyway): {e}")

        # Update detector calibration
        try:
            calibration_path = config.get('calibration_file', 'calibrations/calibration_default.npz')
            preset_type = config.get('preset_type', 'standard')
            
            print(f"[DEBUG] Attempting to update calibration: {calibration_path} (type: {preset_type})")
            
            if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                success = detector4.detector_instance.update_calibration(calibration_path)
                if success:
                    if preset_type == "legacy":
                        print(f"[INFO] ✓ Legacy calibration loaded: {calibration_path}")
                    else:
                        print(f"[INFO] ✓ Detector calibration updated: {calibration_path}")
                else:
                    print(f"[WARNING] ❌ Failed to update detector calibration: {calibration_path}")
            
            elif hasattr(detector4, 'update_calibration'):
                success = detector4.update_calibration(calibration_path)
                if success:
                    print(f"[INFO] ✓ Detector calibration updated via function: {calibration_path}")
                else:
                    print(f"[WARNING] ❌ Failed to update detector calibration via function: {calibration_path}")
            
            else:
                print("[WARNING] No calibration update method found in detector4")
                
        except Exception as e:
            print(f"[ERROR] Failed to update detector calibration: {e}")
            import traceback
            traceback.print_exc()

        if was_streaming:
            threading.Timer(0.5, self.toggle_stream).start()

    def resume_after_calibration_change(self):
        """Resume display after calibration/crop change."""
        if hasattr(self, 'calibration_change_time'):
            delattr(self, 'calibration_change_time')
        print("[DEBUG] 📊 Display resumed after calibration/crop pause")

    def check_calibration_status(self):
        """Check and display calibration status for current settings."""
        try:
            config = self.camera_settings.get_config()
            calibration_file = config.get('calibration_file', 'calibrations/calibration_default.npz')
            preset_type = config.get('preset_type', 'standard')
            
            if not os.path.isabs(calibration_file):
                calibration_file = os.path.join(os.path.dirname(__file__), calibration_file)
                calibration_file = os.path.normpath(calibration_file)
            
            if os.path.exists(calibration_file):
                if preset_type == "legacy":
                    print(f"[INFO] ✓ Legacy calibration found (calibration_data.npz, 1536x864): {calibration_file}")
                else:
                    print(f"[INFO] ✓ Calibration found: {calibration_file}")
                return True
            else:
                print(f"[WARNING] ❌ Calibration missing: {calibration_file}")
                return False
        except Exception as e:
            print(f"[ERROR] Calibration status check failed: {e}")
            return False

    def debug_detector_state(self):
        """Print debug info about detector state."""
        try:
            print(f"[DEBUG] Detector active: {self.detector_active}")
            print(f"[DEBUG] Has detector4 module: {hasattr(self, 'detector4') or 'detector4' in globals()}")
            if hasattr(detector4, 'detector_instance'):
                print(f"[DEBUG] Detector instance exists: {detector4.detector_instance is not None}")
                if detector4.detector_instance:
                    print(f"[DEBUG] Detector has calibration: {detector4.detector_instance.mtx is not None}")
            print(f"[DEBUG] Frame queue size: {self.frame_queue.qsize()}")
            config = self.camera_settings.get_config()
            print(f"[DEBUG] Current config: {config}")
        except Exception as e:
            print(f"[ERROR] Debug detector state failed: {e}")

    def toggle_detector(self):
        self.detector_active = not self.detector_active
        self.detector_controls.detector_btn.setText("Stop Detector" if self.detector_active else "Start Detector")
        
        if self.detector_active:
            print("[DEBUG] 🚀 Starting detector...")
            self.check_calibration_status()
            self.debug_detector_state()
            threading.Thread(target=self.run_detector, daemon=True).start()
        else:
            print("[DEBUG] 🛑 Stopping detector...")
            self.clear_queue()

    def run_detector(self):
        while self.detector_active:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            
                config = self.camera_settings.get_config()
                is_cropped = config.get('cropped', False)
                
                original_height = None
                if is_cropped:
                    current_height = frame.shape[0]
                    original_height = int(current_height * 3)
            
                try:
                    if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                        analysed, pose = detector4.detector_instance.detect_and_draw(
                            frame, return_pose=True, is_cropped=is_cropped, original_height=original_height
                        )
                    else:
                        analysed, pose = detector4.detect_and_draw(frame, return_pose=True)
                
                    bridge.analysed_frame.emit(analysed)

                    # **CHECK FOR CALIBRATION PAUSE BEFORE UPDATING GRAPHS**
                    should_update_graphs = True
                    if hasattr(self, 'calibration_change_time'):
                        time_since_change = time.time() - self.calibration_change_time
                        if time_since_change < 1.0:  # 1 second pause
                            should_update_graphs = False
                            if int(time_since_change * 10) % 5 == 0:  # Every 0.5 seconds
                                print(f"[DEBUG] 📊 Skipping graph update - calibration stabilizing ({time_since_change:.1f}s)")

                    if should_update_graphs and self.graph_section.graph_widget and pose:
                        rvec, tvec = pose
                        timestamp = time.time()
                        self.graph_section.graph_widget.update(rvec, tvec, timestamp)
                        
                except Exception as e:
                    print(f"[ERROR] Detector processing error: {e}")
                    bridge.analysed_frame.emit(frame)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ERROR] Detector thread error: {e}")
                import traceback
                traceback.print_exc()

    def update_image(self, frame):
        """Handle live stream frames (only when detector is OFF)."""
        self.last_frame = frame.copy()
        
        # Only show live stream if detector is NOT active
        if not self.detector_active:
            self.display_frame(frame, is_live=True)
        
        # Always queue frames for detector if it's active
        if self.detector_active:
            self.clear_queue()
            self.frame_queue.put(self.last_frame)

    def update_analysed_image(self, frame):
        """Handle detector output frames (only when detector is ON)."""
        # Only show detector output if detector IS active
        if self.detector_active:
            self.display_frame(frame, is_live=False)

    def display_frame(self, frame, is_live=True):
        """Display frame with optional 1-second pause for crop changes."""
        # Check if we should pause display during crop/calibration changes
        if hasattr(self, 'calibration_change_time'):
            time_since_change = time.time() - self.calibration_change_time
            if time_since_change < 1.0:  # 1 second pause
                # Just skip displaying during pause - no placeholder screen
                return
        
        # Normal frame display
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        pixmap = pixmap.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.video_label.setPixmap(pixmap)

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
                fps = self.camera_settings.fps_slider.value()
                max_bytes_per_sec = upload / 8
                max_frame_size = max_bytes_per_sec / fps
                self.speedtest_result.emit(upload_mbps, max_frame_size / 1024)
            except Exception:
                self.speedtest_result.emit(-1, -1)

        threading.Thread(target=run_speedtest, daemon=True).start()

    def update_speed_labels(self, upload_mbps, max_frame_size_kb):
        if upload_mbps < 0:
            self.info_labels["speed"].setText("Upload: Error")
            self.info_labels["max_frame"].setText("Max Frame: -- KB")
        else:
            self.info_labels["speed"].setText(f"Upload: {upload_mbps:.2f} Mbps")
            self.info_labels["max_frame"].setText(f"Max Frame: {max_frame_size_kb:.1f} KB")

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

    def reset_camera_to_default(self):
        if self.crop_active:
            self.crop_active = False
            idx = self.camera_settings.res_dropdown.findText("Custom (Cropped)")
            if idx != -1:
                self.camera_settings.res_dropdown.removeItem(idx)
            from widgets.camera_settings import CameraSettingsWidget
            self.camera_settings.get_config = CameraSettingsWidget.get_config.__get__(self.camera_settings)
            self.camera_settings.set_cropped_label(False)
            self.camera_controls.crop_btn.setText("Crop")
        self.camera_settings.res_dropdown.setCurrentIndex(0)
        config = self.camera_settings.get_config()
        sio.emit("camera_config", config)
        time.sleep(0.2)

    def closeEvent(self, event):
        try:
            print("[DEBUG] 🛑 Closing application...")
            
            if self.detector_active:
                self.detector_active = False
                print("[DEBUG] Detector stopped")
    
            self.reset_camera_to_default()
            time.sleep(0.5)
    
            if self.streaming:
                sio.emit("stop_camera")
                self.streaming = False
                self.camera_controls.toggle_btn.setText("Start Stream")
                time.sleep(0.5)
    
            sio.emit("set_camera_idle")
            time.sleep(0.5)
    
            if sio.connected:
                print("[DEBUG] Disconnecting from server...")
                sio.disconnect()
                time.sleep(0.2)
            
        except Exception as e:
            print(f"[DEBUG] Cleanup error (expected): {e}")

        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def toggle_crop(self):
        print(f"[DEBUG] Toggling crop: {not self.crop_active}")
        
        # No more placeholder - just apply the crop change directly
        self.crop_active = not self.crop_active
        
        try:
            self.camera_settings.set_cropped_label(self.crop_active)
        except Exception as e:
            print(f"[DEBUG] Could not update crop label: {e}")
        
        self.camera_controls.crop_btn.setText("Uncrop" if self.crop_active else "Crop")
        print(f"[DEBUG] Crop now: {'ACTIVE' if self.crop_active else 'INACTIVE'}")
        
        # Apply the configuration (this will trigger the 1-second pause)
        self.apply_config()


def check_all_calibrations():
    """Check status of all calibration files including legacy."""
    print("=== Calibration Status ===")
    total = len(CALIBRATION_FILES)
    found = 0
    
    for resolution, filename in CALIBRATION_FILES.items():
        if not os.path.isabs(filename):
            filepath = os.path.join(os.path.dirname(__file__), filename)
            filepath = os.path.normpath(filepath)
        else:
            filepath = filename
            
        if os.path.exists(filepath):
            if resolution == "legacy":
                print(f"✓ OLD (Legacy) - {filename}")
            else:
                print(f"✓ {resolution[0]}x{resolution[1]} - {filename}")
            found += 1
        else:
            if resolution == "legacy":
                print(f"❌ OLD (Legacy) - {filename} (MISSING)")
            else:
                print(f"❌ {resolution[0]}x{resolution[1]} - {filename} (MISSING)")
    
    print(f"\nStatus: {found}/{total} calibrations available")
    
    if found == total:
        print("🎉 All calibrations complete!")
    else:
        print(f"⚠️  Missing {total - found} calibrations")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setApplicationName("SLowMO Client")
    app.setApplicationVersion("3.0")
    
    window = MainWindow()
    window.showFullScreen()
    
    def connect_to_server():
        try:
            print(f"[DEBUG] Attempting to connect to {SERVER_URL}")
            sio.connect(SERVER_URL, wait_timeout=10)
            print("[DEBUG] Successfully connected to server")
        except Exception as e:
            print(f"[ERROR] Failed to connect to server: {e}")
    
    threading.Thread(target=connect_to_server, daemon=True).start()
    
    sys.exit(app.exec())
