##############################################################################
#                              SLowMO CLIENT                                #
#                         Satellite Control Interface                       #
##############################################################################

import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue, os
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea,
    QTabWidget, QFileDialog, QDoubleSpinBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage, QFont, QPainter, QPen

##############################################################################
#                                IMPORTS                                     #
##############################################################################

# Payload and detection modules
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
from payload import detector4

# UI Components
from widgets.camera_controls import CameraControlsWidget
from widgets.camera_settings import CameraSettingsWidget, CALIBRATION_FILES
from widgets.graph_section import GraphSection
from widgets.detector_control import DetectorControlWidget

# Theme and styling
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

##############################################################################
#                            CONFIGURATION                                  #
##############################################################################

logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
SERVER_URL = "http://192.168.1.146:5000"

##############################################################################
#                        SOCKETIO AND BRIDGE SETUP                         #
##############################################################################

sio = socketio.Client()

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    analysed_frame = pyqtSignal(np.ndarray)

bridge = Bridge()

##############################################################################
#                            MAIN WINDOW CLASS                              #
##############################################################################

class MainWindow(QWidget):
    speedtest_result = pyqtSignal(float, float)  # upload_mbps, max_frame_size_kb

    #=========================================================================
    #                         THEME CONFIGURATION                            
    #=========================================================================
    
    # Color scheme
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
    
    # Border configuration
    BOX_BORDER_THICKNESS = BORDER_WIDTH
    BOX_BORDER_STYLE = "solid"
    BOX_BORDER_RADIUS = BORDER_RADIUS
    FONT_FAMILY = FONT_FAMILY

    # Style definitions
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

    LABEL_STYLE = f"""
    QLabel {{
        color: {TEXT_COLOR};
        font-size: {FONT_SIZE_NORMAL}pt;
        font-family: {FONT_FAMILY};
    }}
    """

    GROUPBOX_STYLE = f"""
    QGroupBox {{
        border: 2px solid {BORDER_COLOR};
        border-radius: 4px;
        background-color: {BOX_BACKGROUND};
        margin-top: 6px;
        color: {BOX_TITLE_COLOR};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 6px;
        padding: 0 2px;
        font-size: {FONT_SIZE_TITLE}pt;
        font-family: {FONT_FAMILY};
        color: {BOX_TITLE_COLOR};
    }}
    """

    # Display constants
    STREAM_WIDTH = 384
    STREAM_HEIGHT = 216
    MARGIN = 10

    #=========================================================================
    #                           INITIALIZATION                               
    #=========================================================================

    def __init__(self):
        super().__init__()
        # Set global styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BACKGROUND};
                color: {TEXT_COLOR};
                font-family: {self.FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
        """)
        
        # Window configuration
        self.setWindowTitle("SLowMO Client")
        
        # Initialize state variables
        self.streaming = False
        self.detector_active = False
        self.crop_active = False
        self.frame_queue = queue.Queue()
        self.last_frame = None
        self.shared_start_time = None
        self.calibration_change_time = None

        # Performance tracking
        self.last_frame_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        self.current_frame_size = 0


        # display‐FPS counters
        self.display_frame_counter = 0
        self.current_display_fps   = 0
        # ── end patch ──

        # ── start patch ──
        # throttle graph redraws to 10 Hz
        self._last_graph_draw = 0.0
        self._graph_update_interval = 0.
        # ── end patch ──

        # Setup UI and connections
        self.setup_ui()
        self.setup_socket_events()
        self.setup_signals()
        self.setup_timers()

        # Graph window reference
        self.graph_window = None

    def setup_signals(self):
        """Connect internal signals"""
        bridge.frame_received.connect(self.update_image)
        bridge.analysed_frame.connect(self.update_analysed_image)
        self.speedtest_result.connect(self.update_speed_labels)

    def setup_timers(self):
        """Initialize performance timers"""
        self.fps_timer = self.startTimer(1000)
        
        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.measure_speed)
        self.speed_timer.start(10000)

    #=========================================================================
    #                          UI SETUP METHODS                             
    #=========================================================================

    def apply_groupbox_style(self, groupbox, border_color, bg_color=None, title_color=None):
        """Apply consistent styling to group boxes"""
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
                margin-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 6px;
                top: 0px;
                padding: 0 4px;
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {self.FONT_FAMILY};
                color: {title};
                background-color: {bg};
            }}
        """)

    def style_button(self, btn):
        """Apply standard button styling"""
        btn.setFixedHeight(24)

    def setup_ui(self):
        """Initialize the main user interface"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(2, 2, 2, 2)

        # Create main tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER_COLOR};
                background-color: {BACKGROUND};
            }}
            QTabBar::tab {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                padding: 8px 16px;
                margin-right: 2px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
            QTabBar::tab:selected {{
                background-color: {BUTTON_COLOR};
                color: black;
            }}
            QTabBar::tab:hover {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
        """)

        # Setup tabs
        self.main_tab = QWidget()
        self.setup_main_tab()
        self.tab_widget.addTab(self.main_tab, "Mission Control")

        self.analysis_tab = QWidget()
        self.setup_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "Data Analysis")

        main_layout.addWidget(self.tab_widget)

    def setup_main_tab(self):
        """Setup the main mission control interface"""
        tab_layout = QHBoxLayout(self.main_tab)
        tab_layout.setSpacing(2)
        tab_layout.setContentsMargins(2, 2, 2, 2)

        # Left column with control panels
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        left_col.setContentsMargins(2, 2, 2, 2)
        left_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Setup control rows
        self.setup_video_controls_row(left_col)
        self.setup_graph_display_row(left_col)
        self.setup_subsystem_controls_row(left_col)

        # Right column with system information
        scroll_area = self.setup_system_info_panel()

        # Add to main layout
        tab_layout.addLayout(left_col, stretch=6)
        tab_layout.addWidget(scroll_area, stretch=0)
        tab_layout.setAlignment(scroll_area, Qt.AlignmentFlag.AlignRight)

    def setup_video_controls_row(self, parent_layout):
        """Setup video stream and camera controls"""
        row1 = QHBoxLayout()
        row1.setSpacing(2)
        row1.setContentsMargins(2, 2, 2, 2)
        row1.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Video stream display
        video_group = QGroupBox("Video Stream")
        video_layout = QHBoxLayout()
        video_layout.setSpacing(4)
        video_layout.setContentsMargins(3, 3, 3, 3)

        aspect_w, aspect_h = 16, 9
        video_width = 640
        video_height = int(video_width * aspect_h / aspect_w)

        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setFixedSize(video_width, video_height)
        self.video_label.setStyleSheet(f"""
            background-color: {STREAM_BACKGROUND};
            border: {BORDER_WIDTH}px solid {BORDER_COLOR};
        """)
        video_layout.addWidget(self.video_label)

        video_group.setLayout(video_layout)
        video_group.setFixedSize(video_width + 20, video_height + 20)
        self.apply_groupbox_style(video_group, self.COLOR_BOX_BORDER_LIVE)

        # Camera controls
        self.camera_controls = CameraControlsWidget(parent_window=self)
        self.camera_controls.setFixedHeight(video_height + 20)
        self.apply_groupbox_style(self.camera_controls, self.COLOR_BOX_BORDER_CAMERA_CONTROLS)
        
        # Backward compatibility
        self.detector_controls = type('obj', (object,), {'detector_btn': self.camera_controls.detector_btn})()

        # Camera settings
        self.camera_settings = CameraSettingsWidget()
        self.camera_settings.setMaximumWidth(280)
        self.camera_settings.layout.setSpacing(2)
        self.camera_settings.layout.setContentsMargins(2, 2, 2, 2)
        self.style_button(self.camera_settings.apply_btn)
        self.camera_settings.apply_btn.setFixedHeight(24)
        self.camera_settings.apply_btn.setStyleSheet(self.BUTTON_STYLE + "padding: 2px 4px; font-size: 9pt;")
        self.camera_settings.apply_btn.clicked.connect(self.apply_config)
        self.apply_groupbox_style(self.camera_settings, self.COLOR_BOX_BORDER_CONFIG)
        self.camera_settings.setFixedHeight(video_height + 20)

        # Add to row
        row1.addWidget(video_group)
        row1.addWidget(self.camera_controls)
        row1.addWidget(self.camera_settings)
        
        parent_layout.addLayout(row1)

    def setup_graph_display_row(self, parent_layout):
        """Setup graph display section"""
        row2 = QHBoxLayout()
        row2.setSpacing(2)
        row2.setContentsMargins(2, 2, 2, 2)
        row2.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Graph section with recording capabilities
        self.record_btn = QPushButton("Record")
        self.duration_dropdown = QComboBox()
        # ← hide the dropdown so it never shows up
        self.duration_dropdown.setVisible(False)

        self.graph_section = GraphSection(self.record_btn, self.duration_dropdown)
        self.graph_section.setFixedSize(560, 280)
        self.graph_section.graph_display_layout.setSpacing(1)
        self.graph_section.graph_display_layout.setContentsMargins(1, 1, 1, 1)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        
        row2.addWidget(self.graph_section)
        parent_layout.addLayout(row2)

    def setup_subsystem_controls_row(self, parent_layout):
        """Setup LIDAR and ADCS controls"""
        row3 = QHBoxLayout()
        row3.setSpacing(4)
        row3.setContentsMargins(4, 4, 4, 4)
        row3.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # LIDAR section
        lidar_group = QGroupBox("LIDAR")
        lidar_layout = QVBoxLayout()
        lidar_layout.setSpacing(2)
        lidar_layout.setContentsMargins(2, 2, 2, 2)
        lidar_placeholder = QLabel("LIDAR here")
        lidar_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lidar_placeholder.setStyleSheet("background: white; color: black; border: 1px solid #888; border-radius: 6px; font-size: 14px;")
        lidar_placeholder.setFixedHeight(40)
        lidar_layout.addWidget(lidar_placeholder)
        lidar_group.setLayout(lidar_layout)
        self.apply_groupbox_style(lidar_group, self.COLOR_BOX_BORDER_LIDAR)

        # ADCS section
        adcs_group = QGroupBox("ADCS")
        adcs_layout = QVBoxLayout()
        adcs_layout.setSpacing(2)
        adcs_layout.setContentsMargins(2, 2, 2, 2)
        adcs_placeholder = QLabel("ADCS Placeholder\n(More controls coming soon)")
        adcs_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        adcs_placeholder.setFixedHeight(40)
        adcs_layout.addWidget(adcs_placeholder)
        adcs_group.setLayout(adcs_layout)
        self.apply_groupbox_style(adcs_group, self.COLOR_BOX_BORDER_ADCS)

        row3.addWidget(lidar_group)
        row3.addWidget(adcs_group)
        parent_layout.addLayout(row3)

    def setup_system_info_panel(self):
        """Setup right column system information panel"""
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(2, 2, 2, 2)
        info_container.setStyleSheet(f"background-color: {self.COLOR_BOX_BG_RIGHT};")

        # System performance info
        self.setup_system_performance_group(info_layout)
        
        # Subsystem status groups
        self.setup_subsystem_status_groups(info_layout)
        
        # Health report button
        print_report_btn = QPushButton("Print Health Check Report")
        print_report_btn.setEnabled(False)
        self.style_button(print_report_btn)
        info_layout.insertWidget(0, print_report_btn)

        # Scroll area wrapper
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
                min-width: 200px;
                max-width: 240px;
            }}
            QScrollBar:horizontal, QScrollBar:vertical {{ height: 0px; width: 0px; background: transparent; }}
            QWidget {{ min-width: 180px; background: {self.COLOR_BOX_BG_RIGHT}; }}
        """)
        info_container.setMinimumWidth(180)
        info_container.setMaximumWidth(220)

        return scroll_area

    def setup_system_performance_group(self, parent_layout):
        """Setup system performance monitoring group"""
        info_group = QGroupBox("System Info")
        info_layout_inner = QVBoxLayout()
        # ── patch ──
        # add fps_server label
        self.info_labels = {
            "temp":      QLabel("Temp: -- °C"),
            "cpu":       QLabel("CPU: --%"),
            "speed":     QLabel("Upload: -- Mbps"),
            "max_frame": QLabel("Max Frame: -- KB"),
            "fps":       QLabel("Live FPS: --"),
            "frame_size":QLabel("Frame Size: -- KB"),
        }
        
        # ── start patch ──
        # add display‐FPS label
        self.info_labels["disp_fps"] = QLabel("Display FPS: --")
        # ── end patch ──

        for lbl in self.info_labels.values():
            lbl.setStyleSheet(self.LABEL_STYLE + "margin: 2px 0px; padding: 2px 0px;")
            info_layout_inner.addWidget(lbl)
            
        info_group.setLayout(info_layout_inner)
        self.apply_groupbox_style(info_group, self.COLOR_BOX_BORDER_RIGHT, self.COLOR_BOX_BG_RIGHT, self.COLOR_BOX_TITLE_RIGHT)
        parent_layout.addWidget(info_group)

    def setup_subsystem_status_groups(self, parent_layout):
        """Setup all subsystem status monitoring groups"""
        subsystems = [
            ("Power Subsystem", ["Battery Voltage: Pending...", "Battery Current: Pending...", "Battery Temp: Pending...", "Status: Pending..."]),
            ("Thermal Subsystem", ["Internal Temp: Pending...", "Status: Pending..."]),
            ("Communication Subsystem", ["Downlink Frequency: Pending...", "Uplink Frequency: Pending...", "Signal Strength: Pending...", "Data Rate: Pending..."]),
            ("ADCS Subsystem", ["Gyro: Pending...", "Orientation: Pending...", "Sun Sensor: Pending...", "Wheel Rpm: Pending...", "Status: Pending..."]),
            ("Payload Subsystem", []),  # Special handling for payload
            ("Command & Data Handling Subsystem", ["Memory Usage: Pending...", "Last Command: Pending...", "Uptime: Pending...", "Status: Pending..."]),
            ("Error Log", ["No Critical Errors Detected: Pending..."]),
            ("Overall Status", ["No Anomalies Detected: Pending...", "Recommended Actions: Pending..."])
        ]

        for name, items in subsystems:
            group = QGroupBox(name)
            layout = QVBoxLayout()
            layout.setSpacing(2)
            layout.setContentsMargins(4, 4, 4, 4)

            if name == "Communication Subsystem":
                # Add standard comm items
                for text in items:
                    lbl = QLabel(text)
                    lbl.setStyleSheet("color: #bbb; margin: 2px 0px; padding: 2px 0px;")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                # Add special status label
                self.comms_status_label = QLabel("Status: Disconnected")
                self.comms_status_label.setStyleSheet("margin: 2px 0px; padding: 2px 0px;")
                self.comms_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.comms_status_label)
            elif name == "Payload Subsystem":
                # Special payload status labels
                self.camera_status_label = QLabel("Camera: Pending...")
                self.camera_status_label.setStyleSheet("color: #bbb; margin: 2px 0px; padding: 2px 0px;")
                self.camera_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.camera_status_label)
                
                self.camera_ready_label = QLabel("Status: Not Ready")
                self.camera_ready_label.setStyleSheet("color: #bbb; margin: 2px 0px; padding: 2px 0px;")
                self.camera_ready_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.camera_ready_label)
            else:
                # Standard subsystem items
                for text in items:
                    lbl = QLabel(text)
                    lbl.setStyleSheet("color: #bbb; margin: 2px 0px; padding: 2px 0px;")
                    if name != "Error Log" and name != "Overall Status":
                        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)

            group.setLayout(layout)
            self.apply_groupbox_style(group, self.COLOR_BOX_BORDER_RIGHT, self.COLOR_BOX_BG_RIGHT, self.COLOR_BOX_TITLE_RIGHT)
            parent_layout.addWidget(group)

    #=========================================================================
    #                        DATA ANALYSIS TAB                              
    #=========================================================================

    def setup_analysis_tab(self):
        """Setup the data analysis interface with full window utilization"""
        analysis_layout = QVBoxLayout(self.analysis_tab)
        analysis_layout.setSpacing(8)
        analysis_layout.setContentsMargins(8, 8, 8, 8)
        
        # Top controls section - simplified without quick stats
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setSpacing(15)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # File loading section
        self.setup_file_loading_section_compact(controls_layout)
        
        # Range selection section
        self.setup_range_selection_section_compact(controls_layout)
        
        # Add spacer to push content to left
        controls_layout.addStretch()
        
        analysis_layout.addWidget(controls_container)
        
        # Main content area - full width layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        
        # Left side: plots container - takes most of the space
        plots_container = QWidget()
        plots_layout = QVBoxLayout(plots_container)
        plots_layout.setSpacing(6)
        plots_layout.setContentsMargins(8, 8, 8, 8)
        
        plots_container.setStyleSheet(f"""
            QWidget {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {BOX_BACKGROUND};
            }}
        """)
        
        self.plots_container_parent = plots_container
        
        content_layout.addWidget(plots_container, stretch=5)  # Takes 5/7 of space
        
        # Right side: detailed metrics display - maximize vertical space
        self.setup_metrics_display_section_compact(content_layout)  # Takes 2/7 of space
        
        analysis_layout.addLayout(content_layout)

    def setup_metrics_display_section_compact(self, parent_layout):
        """Setup compact metrics display section with export button at top"""
        metrics_container = QWidget()
        # match Mission Control info panel width
        metrics_container.setMinimumWidth(180)
        metrics_container.setMaximumWidth(220)

        metrics_layout = QVBoxLayout(metrics_container)
        metrics_layout.setSpacing(2)                # less spacing
        metrics_layout.setContentsMargins(4, 4, 4, 4)  # slimmer margins
        
        # Title at the very top
        title_label = QLabel("Analysis Results")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {BOX_TITLE_COLOR};
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                padding: 6px 0px;
                border-bottom: 1px solid {BORDER_COLOR};
                margin-bottom: 6px;
            }}
        """)
        metrics_layout.addWidget(title_label)
        
        # Export button
        self.export_btn = QPushButton("Export Analysis")
        self.export_btn.setStyleSheet(self.BUTTON_STYLE + f"""
            QPushButton {{ 
                margin-bottom: 8px; 
                font-size: {FONT_SIZE_NORMAL-1}pt;
            }}
        """)
        self.export_btn.setFixedHeight(28)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_analysis)
        metrics_layout.addWidget(self.export_btn)
        
        # Direct metrics display without scroll bars:
        self.metrics_display = QTextEdit()
        self.metrics_display.setReadOnly(True)
        self.metrics_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: none;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {FONT_SIZE_NORMAL-1}pt;
                line-height: 1.3;
            }}
        """)
        self.metrics_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.metrics_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.metrics_display.setText("Load a CSV file to see detailed analysis...")
        metrics_layout.addWidget(self.metrics_display, stretch=1)
        # ===================================================
        
        metrics_container.setStyleSheet(f"background-color: {BOX_BACKGROUND};")
        parent_layout.addWidget(metrics_container, stretch=0)

    def setup_file_loading_section_compact(self, parent_layout):
        """Setup compact file loading controls"""
        file_group = QGroupBox("Load CSV Data")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(8)
        file_layout.setContentsMargins(15, 15, 15, 15)
        
        # Load button
        self.load_csv_btn = QPushButton("Browse & Load CSV")
        self.load_csv_btn.setStyleSheet(self.BUTTON_STYLE)
        self.load_csv_btn.setFixedHeight(32)
        self.load_csv_btn.clicked.connect(self.load_csv_file)
        
        # Compact status label
        self.csv_path_label = QLabel("No file loaded")
        self.csv_path_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_NORMAL-1}pt;
                font-family: {FONT_FAMILY};
                background-color: {BOX_BACKGROUND};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 6px;
                margin: 2px 0px;
            }}
        """)
        self.csv_path_label.setWordWrap(True)
        self.csv_path_label.setMaximumHeight(60)
        
        file_layout.addWidget(self.load_csv_btn)
        file_layout.addWidget(self.csv_path_label)
        file_group.setLayout(file_layout)
        file_group.setFixedWidth(280)
        self.apply_groupbox_style(file_group, self.COLOR_BOX_BORDER)
        parent_layout.addWidget(file_group)

    def setup_range_selection_section_compact(self, parent_layout):
        """Setup compact time range selection controls"""
        range_group = QGroupBox("Time Range")
        range_layout = QGridLayout()
        range_layout.setSpacing(8)
        range_layout.setContentsMargins(15, 15, 15, 15)
        
        # Start time controls
        self.start_label = QLabel("Start (s):")
        self.start_label.setStyleSheet(self.LABEL_STYLE)
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setDecimals(2)
        self.start_spin.setFixedWidth(80)
        self.start_spin.setFixedHeight(28)
        self.start_spin.setStyleSheet(f"""
        QDoubleSpinBox {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 4px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QDoubleSpinBox:focus {{
            border: 1px solid {BORDER_HIGHLIGHT};
        }}
    """)
        
        # End time controls
        self.end_label = QLabel("End (s):")
        self.end_label.setStyleSheet(self.LABEL_STYLE)
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setDecimals(2)
        self.end_spin.setFixedWidth(80)
        self.end_spin.setFixedHeight(28)
        self.end_spin.setStyleSheet(f"""
        QDoubleSpinBox {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 4px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QDoubleSpinBox:focus {{
            border: 1px solid {BORDER_HIGHLIGHT};
        }}
    """)
    
        # Grid layout for compact arrangement
        range_layout.addWidget(self.start_label, 0, 0)
        range_layout.addWidget(self.start_spin, 0, 1)
        range_layout.addWidget(self.end_label, 1, 0)
        range_layout.addWidget(self.end_spin, 1, 1)
        
        range_group.setLayout(range_layout)
        range_group.setFixedWidth(180)
        self.apply_groupbox_style(range_group, self.COLOR_BOX_BORDER)
        parent_layout.addWidget(range_group)
    
        # Initially disable until CSV is loaded
        self.start_spin.setEnabled(False)
        self.end_spin.setEnabled(False)

        # ── patch ──
        # Use 1 second increments on the time spins (keep decimals)
        self.start_spin.setSingleStep(1.0)
        self.end_spin.setSingleStep(1.0)
        # ── end patch ──
    def update_metrics_display(self):
        """Update the metrics display with only the average velocity"""
        if not hasattr(self, 'metrics'):
            self.metrics_display.setText("No metrics available")
            return
        try:
            avg_vel = self.metrics.get('avg_velocity', 0.0)
            self.metrics_display.setText(f"Average Velocity: {avg_vel:.6f} m/s")
        except Exception as e:
            print(f"[ERROR] Failed to update metrics display: {e}")
            self.metrics_display.setText(f"Error displaying metrics: {str(e)}")

    def calculate_std_dev(self):
        """Calculate standard deviation of values"""
        if not hasattr(self, 'full_df'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            return df_range['value'].std()
        except:
            return 0.0

    def calculate_variance(self):
        """Calculate variance of values"""
        if not hasattr(self, 'full_df'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            return df_range['value'].var()
        except:
            return 0.0

    def calculate_rms_velocity(self):
        """Calculate RMS velocity"""
        if not hasattr(self, 'metrics'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            timestamps = df_range["relative_time"].values
            values = df_range["value"].values
            
            if len(timestamps) > 1:
                dt = np.diff(timestamps)
                dv = np.diff(values)
                dt[dt == 0] = 1e-6
                velocity = dv / dt
                return np.sqrt(np.mean(velocity**2))
            return 0.0
        except:
            return 0.0

    def assess_data_quality(self):
        """Assess overall data quality"""
        if not hasattr(self, 'metrics'):
            return "Unknown"
        try:
            points = self.metrics['data_points']
            duration = self.metrics['time_range']
            sampling_rate = points / duration if duration > 0 else 0
            
            if sampling_rate > 20:
                return "Excellent"
            elif sampling_rate > 10:
                return "Good"
            elif sampling_rate > 5:
                return "Fair"
            else:
                return "Poor"
        except:
            return "Unknown"

    def estimate_noise_level(self):
        """Estimate noise level in the data"""
        if not hasattr(self, 'full_df'):
            return "Unknown"
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            # Use standard deviation as a proxy for noise
            std_dev = df_range['value'].std()
            range_val = df_range['value'].max() - df_range['value'].min()
            
            if range_val == 0:
                return "Minimal"
            
            noise_ratio = std_dev / range_val
            
            if noise_ratio < 0.01:
                return "Very Low"
            elif noise_ratio < 0.05:
                return "Low"
            elif noise_ratio < 0.1:
                return "Moderate"
            else:
                return "High"
        except:
            return "Unknown"

    def analyze_trend(self):
        """Analyze overall trend in the data"""
        if not hasattr(self, 'metrics'):
            return "Unknown"
        try:
            avg_velocity = self.metrics['avg_velocity']
            
            if abs(avg_velocity) < 0.001:
                return "Stable"
            elif avg_velocity > 0.001:
                return "Increasing"
            else:
                return "Decreasing"
        except:
            return "Unknown"

    def assess_stability(self):
        """Assess data stability"""
        if not hasattr(self, 'full_df'):
            return "Unknown"
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            values = df_range['value'].values
            if len(values) < 2:
                return "Insufficient Data"
            
            # Calculate coefficient of variation
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if mean_val == 0:
                return "Constant"
            
            cv = std_val / abs(mean_val)
            
            if cv < 0.01:
                return "Very Stable"
            elif cv < 0.05:
                return "Stable"
            elif cv < 0.1:
                return "Moderately Stable"
            else:
                return "Unstable"
        except:
            return "Unknown"

    def count_outliers(self):
        """Count statistical outliers in the data"""
        if not hasattr(self, 'full_df'):
            return 0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            values = df_range['value'].values
            if len(values) < 4:
                return 0
            
            # Use IQR method to detect outliers
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = np.sum((values < lower_bound) | (values > upper_bound))
            return int(outliers)
        except:
            return 0

    def signal_quality_score(self):
        """Calculate a signal quality score out of 10"""
        if not hasattr(self, 'metrics'):
            return 0.0
        try:
            points = self.metrics['data_points']
            duration = self.metrics['time_range']
            sampling_rate = points / duration if duration > 0 else 0
            
            # Base score on sampling rate
            if sampling_rate > 30:
                score = 10.0
            elif sampling_rate > 20:
                score = 8.5
            elif sampling_rate > 10:
                score = 7.0
            elif sampling_rate > 5:
                score = 5.5
            else:
                score = 3.0
            
            # Adjust for noise level
            noise = self.estimate_noise_level()
            if noise == "Very Low":
                score += 0.0
            elif noise == "Low":
                score -= 0.5
            elif noise == "Moderate":
                score -= 1.0
            else:
                score -= 2.0
            
            return max(0.0, min(10.0, score))
        except:
            return 0.0

    def min_time_step(self):
        """Calculate minimum time step"""
        if not hasattr(self, 'full_df'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            timestamps = df_range["relative_time"].values
            if len(timestamps) > 1:
                dt = np.diff(timestamps)
                return np.min(dt[dt > 0])
            return 0.0
        except:
            return 0.0

    def max_time_step(self):
        """Calculate maximum time step"""
        if not hasattr(self, 'full_df'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            timestamps = df_range["relative_time"].values
            if len(timestamps) > 1:
                dt = np.diff(timestamps)
                return np.max(dt)
            return 0.0
        except:
            return 0.0

    def avg_time_step(self):
        """Calculate average time step"""
        if not hasattr(self, 'full_df'):
            return 0.0
        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            df_range = self.full_df[(self.full_df['relative_time'] >= start) & (self.full_df['relative_time'] <= end)]
            
            timestamps = df_range["relative_time"].values
            if len(timestamps) > 1:
                dt = np.diff(timestamps)
                return np.mean(dt)
            return 0.0
        except:
            return 0.0

    def update_analysis_plots(self):
        """Update plots based on selected time range"""
        if not hasattr(self, 'full_df'):
            return

        try:
            start = self.start_spin.value()
            end = self.end_spin.value()
            
            # Ensure end > start
            if end <= start:
                return
                
            df = self.full_df
            df_range = df[(df['relative_time'] >= start) & (df['relative_time'] <= end)]

            if len(df_range) < 2:
                self.metrics_display.setText("Not enough data points in selected range")
                return

            # Use relative_time for analysis but show full data for context
            full_timestamps = self.full_df["relative_time"].values
            full_values = self.full_df["value"].values
            
            timestamps = df_range["relative_time"].values
            values = df_range["value"].values
            
            # Compute derivative (velocity) for selected range
            dt = np.diff(timestamps)
            dv = np.diff(values)
            # Avoid division by zero
            dt[dt == 0] = 1e-6
            velocity = dv / dt
            velocity_times = timestamps[1:]

            # Clear and recreate plots - always show full data with range markers
            self.raw_canvas.figure.clear()
            self.vel_canvas.figure.clear()

            # Raw Data Plot - show full data with range selection highlighted
            raw_ax = self.raw_canvas.figure.add_subplot(111)
            raw_ax.set_facecolor(PLOT_BACKGROUND)
            
            # Plot full data in lighter color
            raw_ax.plot(full_timestamps, full_values, color=PLOT_LINE_ALT, alpha=0.5, linewidth=1, label="Full Data")
            
            # Highlight selected range
            raw_ax.plot(timestamps, values, label="Selected Range", color=PLOT_LINE_PRIMARY, linewidth=2)
            
            # Add range markers
            raw_ax.axvline(start, color=SUCCESS_COLOR, linestyle='--', alpha=0.8, linewidth=2, label="Start")
            raw_ax.axvline(end, color=ERROR_COLOR, linestyle='--', alpha=0.8, linewidth=2, label="End")
            
            # raw_ax.set_title("Raw Data (Distance vs Time)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=11, pad=8)
            raw_ax.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            
            # pick axis labels based on current graph mode
            mode = self.graph_section.current_graph_mode
            if mode == "Relative Distance":
                raw_ylabel, vel_ylabel = "Distance (m)", "Velocity (m/s)"
            elif mode == "Relative Angle":
                raw_ylabel, vel_ylabel = "Angle (°)", "Angular Velocity (°/s)"
            elif mode == "Angular Position":
                raw_ylabel, vel_ylabel = "Position (°)", "Spin Rate (°/s)"
            else:
                raw_ylabel, vel_ylabel = "Value", "Rate"
            raw_ax.set_ylabel(raw_ylabel, color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            
            raw_ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            raw_ax.grid(True, color=GRID_COLOR, alpha=0.3)
            raw_ax.legend(facecolor=BOX_BACKGROUND, edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
            
            # Better margins for space efficiency
            self.raw_canvas.figure.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.15)

            # Velocity Plot - only show selected range data
            vel_ax = self.vel_canvas.figure.add_subplot(111)
            vel_ax.set_facecolor(PLOT_BACKGROUND)
            vel_ax.plot(velocity_times, velocity, label="Velocity (Selected Range)", color=PLOT_LINE_SECONDARY, linewidth=2)
            vel_ax.axvline(start, color=SUCCESS_COLOR, linestyle='--', alpha=0.8, linewidth=2, label="Start")
            vel_ax.axvline(end, color=ERROR_COLOR, linestyle='--', alpha=0.8, linewidth=2, label="End")
            # vel_ax.set_title("Velocity (Selected Range)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=11, pad=8)
            vel_ax.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            vel_ax.set_ylabel(vel_ylabel, color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            vel_ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            vel_ax.grid(True, color=GRID_COLOR, alpha=0.3)
            vel_ax.legend(facecolor=BOX_BACKGROUND, edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
            
            # Better margins for space efficiency
            self.vel_canvas.figure.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.15)

            # Redraw canvases
            self.raw_canvas.draw()
            self.vel_canvas.draw()

            # Calculate and store metrics
            self.metrics = {
                "data_points": len(df_range),
                "time_range": end - start,
                "peak_value": values.max(),
                "min_value": values.min(),
                "avg_value": values.mean(),
                "value_range": values.max() - values.min(),
                "peak_velocity": velocity.max() if len(velocity) > 0 else 0,
                "min_velocity": velocity.min() if len(velocity) > 0 else 0,
                "avg_velocity": velocity.mean() if len(velocity) > 0 else 0,
                "start_time": start,
                "end_time": end
            }

            # Update metrics display
            self.update_metrics_display()
            
            print(f"[INFO] Analysis updated - Range: {start:.2f}s to {end:.2f}s ({len(df_range)} points)")

        except Exception as e:
            print(f"[ERROR] Failed to update analysis plots: {e}")
            import traceback
            traceback.print_exc()
            self.metrics_display.setText(f"Error updating plots: {str(e)}")

    def load_csv_file(self):
        """Load and process CSV file for analysis"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_dialog = QFileDialog()
        # ── start patch ──
        recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "Open CSV File",
            recordings_dir,
            "CSV Files (*.csv);;All Files (*)"
        )
        # ── end patch ──
        
        if not file_path:
            return

        self.csv_path_label.setText(f"Loaded: {os.path.basename(file_path)}")
        try:
            df = pd.read_csv(file_path)
            
            # Check for required columns
            if "timestamp" not in df.columns or "value" not in df.columns:
                self.show_message("Error", "CSV must have 'timestamp' and 'value' columns.", QMessageBox.Icon.Critical)
                return
            
            # Add relative time column
            df['relative_time'] = df['timestamp'] - df['timestamp'].min()
            self.full_df = df
            
            # Setup time range controls
            min_time = df["relative_time"].min()
            max_time = df["relative_time"].max()
            
            self.start_spin.setRange(min_time, max_time)
            self.end_spin.setRange(min_time, max_time)
            self.start_spin.setValue(min_time)
            self.end_spin.setValue(max_time)
            self.start_spin.setSingleStep(0.01)
            self.end_spin.setSingleStep(0.01)
            
            # Enable controls
            self.start_spin.setEnabled(True)
            self.end_spin.setEnabled(True)
            self.export_btn.setEnabled(True)
            
            # Connect signals if not already connected
            try:
                self.start_spin.valueChanged.disconnect()
                self.end_spin.valueChanged.disconnect()
            except:
                pass
            
            self.start_spin.valueChanged.connect(self.update_analysis_plots)
            self.end_spin.valueChanged.connect(self.update_analysis_plots)
            
            # Create plots if they don't exist
            self.create_analysis_plots()
            
            # Initial plot update
            self.update_analysis_plots()
            
            # === NEW: switch to Data Analysis tab ===
            self.tab_widget.setCurrentWidget(self.analysis_tab)
            print("[INFO] 🔄 Switched to Data Analysis tab")
            
            print(f"[INFO] CSV loaded successfully: {len(df)} data points")
        except Exception as e:
            print(f"[ERROR] Failed to load CSV: {e}")
            self.show_message("Error", f"Failed to load CSV file:\n{str(e)}", QMessageBox.Icon.Critical)

    def create_analysis_plots(self):
        """Create matplotlib plots for analysis tab"""
        if hasattr(self, 'raw_canvas'):
            return  # Already created
            
        try:
            from matplotlib.backends.qt_compat import QtCore, QtWidgets
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            
            # Clear existing layout
            layout = self.plots_container_parent.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # Create matplotlib figures
            self.raw_figure = Figure(figsize=(8, 4), facecolor=PLOT_BACKGROUND)
            self.vel_figure = Figure(figsize=(8, 4), facecolor=PLOT_BACKGROUND)
            
            self.raw_canvas = FigureCanvas(self.raw_figure)
            self.vel_canvas = FigureCanvas(self.vel_figure)
            
            # Style canvases
            self.raw_canvas.setStyleSheet(f"background-color: {PLOT_BACKGROUND};")
            self.vel_canvas.setStyleSheet(f"background-color: {PLOT_BACKGROUND};")
            
            # Add to layout
            layout.addWidget(self.raw_canvas)
            layout.addWidget(self.vel_canvas)
            
            print("[INFO] Analysis plots created successfully")
            
        except Exception as e:
            print(f"[ERROR] Failed to create analysis plots: {e}")

    def export_analysis(self):
        """Export analysis results to file"""
        if not hasattr(self, 'metrics'):
            self.show_message("Error", "No analysis data to export.", QMessageBox.Icon.Warning)
            return
        
        from PyQt6.QtWidgets import QFileDialog
        
        # suggest default filename based on selected mode
        mode_key = self.graph_section.current_graph_mode.replace(" ", "_").lower()
        default_name = f"{mode_key}_analysis.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis", default_name, "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.metrics_display.toPlainText())
                self.show_message("Success", f"Analysis exported to:\n{file_path}", QMessageBox.Icon.Information)
                print(f"[INFO] Analysis exported to: {file_path}")
            except Exception as e:
                self.show_message("Error", f"Failed to export analysis:\n{str(e)}", QMessageBox.Icon.Critical)
                print(f"[ERROR] Export failed: {e}")

    def update_image(self, frame):
        """Update video display with new frame"""
        try:
            # Only display raw frames if detector is NOT active
            if self.detector_active:
                # Just add to queue, don't display
                if self.frame_queue.qsize() < 5:
                    self.frame_queue.put(frame.copy())
                return
            
            # Display raw frame when detector is off
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            
            # Scale to fit display
            scaled = q_image.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled)
            self.video_label.setPixmap(pixmap)
                
            # ── patch ──
            self.display_frame_counter += 1
        except Exception as e:
            print(f"[ERROR] Failed to update image: {e}")

    def update_analysed_image(self, frame):
        """Update video display with analyzed frame"""
        try:
            # Only display analyzed frames when detector is active
            if not self.detector_active:
                return
                
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            
            # Scale to fit display
            scaled = q_image.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled)
            self.video_label.setPixmap(pixmap)
            self.display_frame_counter += 1
        except Exception as e:
            print(f"[ERROR] Failed to update analyzed image: {e}")

    #=========================================================================
    #                          SOCKET COMMUNICATION                          
    #=========================================================================

    def setup_socket_events(self):
        """Configure all socket event handlers"""
        
        @sio.event
        def connect():
            print("[INFO] ✓ Connected to server")
            self.comms_status_label.setText("Status: Connected")
            self.camera_controls.toggle_btn.setEnabled(True)
            self.detector_controls.detector_btn.setEnabled(True)
            self.camera_controls.crop_btn.setEnabled(True)
            self.camera_controls.capture_btn.setEnabled(True)
            
            self.apply_config()
            QTimer.singleShot(100, self.delayed_server_setup)

        @sio.event
        def disconnect(reason=None):
            print(f"[INFO] ❌ Disconnected from server: {reason}")
            self.comms_status_label.setText("Status: Disconnected")
            self.camera_controls.toggle_btn.setEnabled(False)
            self.detector_controls.detector_btn.setEnabled(False)
            self.camera_controls.crop_btn.setEnabled(False)
            self.camera_controls.capture_btn.setEnabled(False)

        @sio.on("frame")
        def on_frame(data):
            self.handle_frame_data(data)

        @sio.on("sensor_broadcast")
        def on_sensor_data(data):
            # update temps/CPU
            self.update_sensor_display(data)
            # server already computes FPS in camera.py and sends it
            if "fps" in data:
                # format with one decimal place
                self.info_labels["fps_server"].setText(
                    f"Server FPS: {data['fps']:.1f}"
                )

        @sio.on("camera_status")
        def on_camera_status(data):
            self.update_camera_status(data)

        @sio.on("image_captured")
        def on_image_captured(data):
            self.handle_image_capture_response(data)

        @sio.on("image_download")
        def on_image_download(data):
            self.handle_image_download(data)

    def delayed_server_setup(self):
        """Called shortly after connect—override if needed."""
        pass

    def handle_frame_data(self, data):
        """Process incoming frame data"""
        try:
            arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                self.current_frame_size = len(data)
                self.frame_counter += 1
                bridge.frame_received.emit(frame)
            else:
                print("[WARNING] Frame decode failed")
        except Exception as e:
            print(f"[ERROR] Frame processing error: {e}")

    def update_sensor_display(self, data):
        """Update sensor information display"""
        try:
            temp = data.get("temperature", 0)
            cpu = data.get("cpu_percent", 0)
            self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
            self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
        except Exception as e:
            print(f"[ERROR] Sensor update error: {e}")

    def update_camera_status(self, data):
        """Update camera status display"""
        try:
            status = data.get("status", "Unknown")
            self.camera_status_label.setText(f"Camera: {status}")
            
            if status.lower() in ("streaming", "idle", "ready"):
                self.camera_status_label.setStyleSheet("color: white;")
                self.camera_ready_label.setText("Status: Ready")
                self.camera_ready_label.setStyleSheet("color: #0f0;")
            else:
                self.camera_status_label.setStyleSheet("color: #bbb;")
                self.camera_ready_label.setText("Status: Not Ready")
                self.camera_ready_label.setStyleSheet("color: #f00;")
                
        except Exception as e:
            print(f"[ERROR] Camera status update error: {e}")

    def handle_image_capture_response(self, data):
        """Handle server response to image capture request"""
        try:
            if data["success"]:
                print(f"[INFO] ✓ Image captured: {data['path']} ({data['size_mb']} MB)")
                self.download_captured_image(data['path'])
            else:
                print(f"[ERROR] ❌ Image capture failed: {data['error']}")
        except Exception as e:
            print(f"[ERROR] Failed to handle capture response: {e}")

    def handle_image_download(self, data):
        """Handle downloaded image from server"""
        try:
            if data["success"]:
                image_data = base64.b64decode(data["data"])
                
                local_dir = os.path.join(os.path.dirname(__file__), "captured_images")
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, data["filename"])
                
                with open(local_path, 'wb') as f:
                    f.write(image_data)
                
                print(f"[INFO] ✅ Image saved: {local_path} ({data['size']/1024:.1f} KB)")
            else:
                print(f"[ERROR] ❌ Image download failed: {data['error']}")
                
        except Exception as e:
            print(f"[ERROR] Failed to save downloaded image: {e}")

    #=========================================================================
    #                        CAMERA AND DETECTION                           
    #=========================================================================

    def toggle_stream(self):
        """Toggle video stream on/off"""
        if not sio.connected:
            return
        self.streaming = not self.streaming
        self.camera_controls.toggle_btn.setText("Stop Stream" if self.streaming else "Start Stream")
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        """Apply camera configuration changes"""
        was_streaming = self.streaming
        if was_streaming:
            self.toggle_stream()

        config = self.camera_settings.get_config()
        sio.emit("camera_config", config)
        
        # Pause display during configuration change
        self.calibration_change_time = time.time()
        QTimer.singleShot(1000, self.resume_after_calibration_change)
        
        # Update detector calibration
        self.update_detector_calibration(config)

        if was_streaming:
            threading.Timer(0.5, self.toggle_stream).start()

    def resume_after_calibration_change(self):
        """Resume display after configuration change"""
        if hasattr(self, 'calibration_change_time'):
            delattr(self, 'calibration_change_time')

    def update_detector_calibration(self, config):
        """Update detector with new calibration settings"""
        try:
            calibration_path = config.get('calibration_file', 'calibrations/calibration_default.npz')
            preset_type = config.get('preset_type', 'standard')
            
            if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                success = detector4.detector_instance.update_calibration(calibration_path)
                if success:
                    print(f"[INFO] ✓ Detector calibration updated: {calibration_path}")
                else:
                    print(f"[WARNING] ❌ Failed to update detector calibration")
            
        except Exception as e:
            print(f"[ERROR] Calibration update failed: {e}")

    def toggle_detector(self):
        """Toggle object detection on/off"""
        self.detector_active = not self.detector_active
        self.detector_controls.detector_btn.setText("Stop Detector" if self.detector_active else "Start Detector")
        
        if self.detector_active:
            print("[INFO] 🚀 Starting detector...")
            threading.Thread(target=self.run_detector, daemon=True).start()
        else:
            print("[INFO] 🛑 Stopping detector...")
            self.clear_queue()

    def run_detector(self):
        """Main detector processing loop"""
        while self.detector_active:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                
                config = self.camera_settings.get_config()
                is_cropped = config.get('cropped', False)
                
                original_height = None
                if is_cropped:
                    current_height = frame.shape[0]
                    original_height = int(current_height * 3)
                
                # Process frame with detector
                try:
                    if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                        analysed, pose = detector4.detector_instance.detect_and_draw(
                            frame, return_pose=True, is_cropped=is_cropped, original_height=original_height
                        )
                    else:
                        analysed, pose = detector4.detect_and_draw(frame, return_pose=True)
                
                    bridge.analysed_frame.emit(analysed)

                    # only update graphs if needed
                    if self.should_update_graphs() and self.graph_section.graph_widget and pose:
                        rvec, tvec = pose
                        ts = time.time()

                        # ── start patch ──
                        now = time.time()
                        if now - self._last_graph_draw >= self._graph_update_interval:
                            self._last_graph_draw = now
                            self.graph_section.graph_widget.update(rvec, tvec, ts)
                        # ── end patch ──

                        # always record every data point
                        value = None
                        mode = self.graph_section.current_graph_mode
                        widget = self.graph_section.graph_widget
                        if mode == "Relative Distance" and hasattr(widget, 'current_distance'):
                            value = widget.current_distance
                        elif mode == "Relative Angle" and hasattr(widget, 'current_ang'):
                            value = widget.current_ang
                        elif mode == "Angular Position" and hasattr(widget, 'current_angle'):
                            value = widget.current_angle

                        if value is not None:
                            self.graph_section.add_data_point(ts, value)
                except Exception as e:
                    print(f"[ERROR] Detector processing error: {e}")
                    bridge.analysed_frame.emit(frame)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ERROR] Detector thread error: {e}")

    def should_update_graphs(self):
        """Check if graphs should be updated (not during calibration pause)"""
        if hasattr(self, 'calibration_change_time'):
            time_since_change = time.time() - self.calibration_change_time
            return time_since_change >= 1.0
        return True

    def toggle_crop(self):
        """Toggle camera crop mode"""
        self.crop_active = not self.crop_active
        
        try:
            self.camera_settings.set_cropped_label(self.crop_active)
        except Exception as e:
            print(f"[DEBUG] Could not update crop label: {e}")
        
        self.camera_controls.crop_btn.setText("Uncrop" if self.crop_active else "Crop")
        self.apply_config()

    def capture_image(self):
        """Request image capture from server"""
        if not sio.connected:
            print("[WARNING] Cannot capture image - not connected to server")
            return
        
        try:
            sio.emit("capture_image", {})
            print("[INFO] 📸 Image capture requested")
        except Exception as e:
            print(f"[ERROR] Failed to request image capture: {e}")

    def download_captured_image(self, server_path):
        """Download captured image from server"""
        try:
            filename = os.path.basename(server_path)
            sio.emit("download_image", {"server_path": server_path, "filename": filename})
        except Exception as e:
            print(f"[ERROR] Failed to request image download: {e}")

    def clear_queue(self):
        """Clear the frame queue"""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    #=========================================================================
    #                       PERFORMANCE MONITORING                          
    #=========================================================================

    def measure_speed(self):
        """Measure internet speed for performance monitoring"""
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
        """Update speed test results in UI"""
        if upload_mbps < 0:
            self.info_labels["speed"].setText("Upload: Error")
            self.info_labels["max_frame"].setText("Max Frame: -- KB")
        else:
            self.info_labels["speed"].setText(f"Upload: {upload_mbps:.2f} Mbps")
            self.info_labels["max_frame"].setText(f"Max Frame: {max_frame_size_kb:.1f} KB")

    def timerEvent(self, event):
        """Handle timer events for FPS calculation"""
        # live FPS (incoming)
        self.current_fps = self.frame_counter
        self.frame_counter = 0

        # display FPS
        self.current_display_fps   = self.display_frame_counter
        self.display_frame_counter = 0

        # update labels
        self.info_labels["fps"].setText(f"Live FPS: {self.current_fps}")
        self.info_labels["disp_fps"].setText(f"Display FPS: {self.current_display_fps}")
        self.info_labels["frame_size"].setText(f"Frame Size: {self.current_frame_size/1024:.1f} KB")
    #=========================================================================
    #                          UTILITY METHODS                              
    #=========================================================================

    def try_reconnect(self):
        """Attempt to reconnect to server"""
        threading.Thread(target=self.reconnect_socket, daemon=True).start()

    def reconnect_socket(self):
        """Handle socket reconnection logic"""
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
        """Display styled message box"""
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
        """Reset camera to default configuration"""
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

    #=========================================================================
    #                           EVENT HANDLERS                              
    #=========================================================================

    def closeEvent(self, event):
        """Handle application close event"""
        try:
            print("[INFO] 🛑 Closing application...")
            
            if self.detector_active:
                self.detector_active = False
    
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
                sio.disconnect()
                time.sleep(0.2)
            
        except Exception as e:
            print(f"[DEBUG] Cleanup error: {e}")

        event.accept()

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

##############################################################################
#                            UTILITY FUNCTIONS                              #
##############################################################################

def check_all_calibrations():
    """Check status of all calibration files"""
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

##############################################################################
#                              MAIN EXECUTION                               #
##############################################################################

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setApplicationName("SLowMO Client")
    app.setApplicationVersion("3.0")
    
    window = MainWindow()
    window.showMaximized()
    
    def connect_to_server():
        try:
            print(f"[INFO] Attempting to connect to {SERVER_URL}")
            sio.connect(SERVER_URL, wait_timeout=10)
            print("[INFO] Successfully connected to server")
        except Exception as e:
            print(f"[ERROR] Failed to connect to server: {e}")
    
    threading.Thread(target=connect_to_server, daemon=True).start()
    
    sys.exit(app.exec())
