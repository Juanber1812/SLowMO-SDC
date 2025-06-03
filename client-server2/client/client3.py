##############################################################################
#                              SLowMO CLIENT                                #
#                         Satellite Control Interface                       #
##############################################################################

import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue, os
import pandas as pd
import traceback
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea,
    QTabWidget, QFileDialog, QDoubleSpinBox, QSpinBox, QTextEdit
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
from widgets.adcs import ADCSSection # <--- ADD THIS LINE

# Theme and styling
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR, 
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,BUTTON_HEIGHT,
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
        self.smooth_mode = None
        # Window configuration
        self.setWindowTitle("SLowMO Client")
        
        # Initialize state variables
        self.streaming = False
        self.detector_active = False
        # self.crop_active = False # REMOVE THIS LINE
        self.frame_queue = queue.Queue()
        self.last_frame = None
        self.shared_start_time = None
        self.calibration_change_time = None
        # self.active_config_for_detector will be initialized after setup_ui

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
        self.setup_ui() # self.camera_settings is created here

        # Initialize active_config_for_detector with the initial UI settings
        # This will be updated upon server acknowledgment of config changes
        if hasattr(self, 'camera_settings') and self.camera_settings is not None:
             self.active_config_for_detector = self.camera_settings.get_config()
        else:
             # Fallback if camera_settings isn't ready for some reason.
             self.active_config_for_detector = None
             print("[WARNING] MainWindow.__init__: camera_settings not available for initial active_config_for_detector.")

        self.setup_socket_events()
        self.setup_signals()
        self.setup_timers()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        # Graph window reference
        self.graph_window = None

    def setup_signals(self):
        """Connect internal signals"""
        bridge.frame_received.connect(self.update_image)
        bridge.analysed_frame.connect(self.update_analysed_image)
        self.speedtest_result.connect(self.update_speed_labels)

    def _on_tab_changed(self, index):
        pass
        # if switched into the Data Analysis tab, re‐draw with correct labels
        if self.tab_widget.widget(index) is self.analysis_tab and hasattr(self, 'full_df'):
            self.update_analysis_plots()
            
    def set_smoothing_mode(self, mode):
        """Toggle Raw/SMA/EMA buttons and refresh."""
        self.smooth_mode = mode
     # sync button states
        self.raw_btn.setChecked( mode is None )
        self.savgol_btn.setChecked(mode == "SG")
        self.butter_btn.setChecked(mode == "BW")
        # show the matching parameter page
        idx = 0 if mode is None else (1 if mode=="SG" else 2)
        self.filter_param_stack.setCurrentIndex(idx)
         # redraw
        self.update_analysis_plots()

    def setup_timers(self):
        """Initialize performance timers"""
        self.fps_timer = self.startTimer(1000)
        
        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.measure_speed)
        self.speed_timer.start(10000)

    #=========================================================================
    #                          UI SETUP METHODS                             
    #=========================================================================

    def apply_groupbox_style(self, groupbox, border_color, bg_color=None, title_color=None, is_part_of_right_column=False):
        """Apply consistent styling to group boxes, with conditional border thickness."""
        thickness = (
            self.BOX_BORDER_THICKNESS
            if is_part_of_right_column
            else 0  # No border for items not in the right column
        )
        
        radius_value = (
            self.COLOR_BOX_RADIUS_RIGHT
            if is_part_of_right_column
            else self.BOX_BORDER_RADIUS
        )
        actual_radius_str = f"{radius_value}px"

        bg = bg_color if bg_color else self.COLOR_BG 
        title = title_color if title_color else BOX_TITLE_COLOR

        border_style_components = f"{thickness}px {self.BOX_BORDER_STYLE}"

        # Combine QGroupBox styles with the general QPushButton styles
        # This ensures that QPushButtons within this groupbox also get styled.
        groupbox_stylesheet = f"""
            QGroupBox {{
                border: {border_style_components} {border_color}; 
                border-radius: {actual_radius_str};
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
            {self.BUTTON_STYLE}
        """
        groupbox.setStyleSheet(groupbox_stylesheet)
        groupbox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

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
        video_group = QGroupBox()
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
        # margins & spacing
        self.camera_settings.setMaximumWidth(280)
        self.camera_settings.layout.setSpacing(2)
        self.camera_settings.layout.setContentsMargins(2, 2, 2, 2)
        # unify with crop/start-stream button style
        self.camera_settings.apply_btn.setStyleSheet(self.BUTTON_STYLE)
        self.camera_settings.apply_btn.setFixedHeight(BUTTON_HEIGHT)

        self.camera_settings.apply_btn.clicked.connect(self.apply_config)
        # self.camera_settings.crop_config_requested.connect(self.apply_config) # Ensure this is commented out or removed
        # The line above, if active, could cause apply_config to be called when crop UI changes,
        # not just when "Apply Settings" is clicked.

        self.apply_groupbox_style(
            self.camera_settings, self.COLOR_BOX_BORDER_CONFIG
        )
        self.camera_settings.setFixedHeight(video_height + 20)

        # Add to row
        row1.addWidget(video_group)
        row1.addWidget(self.camera_controls)
        row1.addWidget(self.camera_settings)
        
        parent_layout.addLayout(row1)

    def setup_graph_display_row(self, parent_layout):
        """Setup graph display section and LIDAR section"""
        row2 = QHBoxLayout()
        row2.setSpacing(2) # Keep spacing consistent, adjust if needed
        row2.setContentsMargins(2, 2, 2, 2)
        row2.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop) # Align top for differing heights

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

        # LIDAR section (moved here)
        lidar_group = QGroupBox("LIDAR") # Added title for clarity if not already there
        lidar_layout = QVBoxLayout()
        lidar_layout.setSpacing(2)
        lidar_layout.setContentsMargins(2, 2, 2, 2)
        lidar_placeholder = QLabel("LIDAR here")
        lidar_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lidar_placeholder.setStyleSheet("background: white; color: black; border: 1px solid #888; border-radius: 6px; font-size: 14px;")
        lidar_placeholder.setFixedHeight(40) # Current height
        # You might want to adjust LIDAR group's height or the graph section's if they look misaligned.
        # For example, to make LIDAR group take similar height as graph:
        # lidar_group.setFixedSize(DESIRED_WIDTH, self.graph_section.height()) 
        # Or allow it to expand:
        # lidar_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # lidar_group.setMinimumHeight(self.graph_section.height()) # if you want it to match graph height
        
        lidar_layout.addWidget(lidar_placeholder)
        lidar_group.setLayout(lidar_layout)
        self.apply_groupbox_style(lidar_group, self.COLOR_BOX_BORDER_LIDAR)
        # Set a fixed width for LIDAR or let it expand. Example fixed width:
        lidar_group.setFixedWidth(200) # Adjust as needed

        row2.addWidget(lidar_group)
        
        parent_layout.addLayout(row2)

    def setup_subsystem_controls_row(self, parent_layout):
        """Setup ADCS controls using ADCSSection widget"""
        row3 = QHBoxLayout()
        row3.setSpacing(4) 
        row3.setContentsMargins(4, 4, 4, 4)
        row3.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # ADCS section using the new ADCSSection widget
        self.adcs_control_widget = ADCSSection()
        
        # Optional: Connect to the mode_selected signal if you need to react to mode changes
        # self.adcs_control_widget.mode_selected.connect(self.handle_adcs_mode_selection) 
                                                                                       
        self.apply_groupbox_style(self.adcs_control_widget, self.COLOR_BOX_BORDER_ADCS)
        # Adjust sizing as needed, e.g.:
        # self.adcs_control_widget.setFixedWidth(400) 
        # self.adcs_control_widget.setFixedHeight(100) 

        row3.addWidget(self.adcs_control_widget)
        parent_layout.addLayout(row3)

    # Optional: Add a handler method in client3.py if you connect the signal
    # def handle_adcs_mode_selection(self, mode_index, mode_name):
    #     print(f"[Client3] ADCS Mode selected: Index {mode_index}, Name '{mode_name}'")
    #     # Add logic here to respond to ADCS mode changes

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
        self.print_report_btn = QPushButton("Print Health Check Report")
        self.print_report_btn.setEnabled(False)
        self.print_report_btn.clicked.connect(self.export_health_report)
        # unify with crop/start-stream button style
        self.print_report_btn.setStyleSheet(self.BUTTON_STYLE)
        self.print_report_btn.setFixedHeight(BUTTON_HEIGHT)
        self.print_report_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        info_layout.insertWidget(0, self.print_report_btn)
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
                min-width: 240px;  /* Changed from 200px */
                max-width: 240px;  /* Ensures fixed width of 240px */
            }}
            QScrollBar:horizontal, QScrollBar:vertical {{ height: 0px; width: 0px; background: transparent; }}
            QWidget {{ min-width: 180px; background: {self.COLOR_BOX_BG_RIGHT}; }}
        """)
        info_container.setMinimumWidth(180)
        # info_container.setMaximumWidth(220) # Allow info_container to fill the scroll_area width

        # ── start patch ──
        # keep a handle to the container so we can walk its QGroupBoxes later
        self.info_container = info_container
        # ── end patch ──

        return scroll_area



    def export_health_report(self):
        """Export health check report to a text file"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox, QGroupBox, QLabel

        default_name = "health_report.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Health Check Report", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            lines = []

            # 1) system performance labels
            for key, lbl in self.info_labels.items():
                lines.append(lbl.text())

            # 2) each subsystem status group
            if hasattr(self, 'info_container'):
                groups = self.info_container.findChildren(QGroupBox)
                for grp in groups:
                    title = grp.title()
                    lines.append(f"\n=== {title} ===")
                    # all QLabel children under this group
                    for child in grp.findChildren(QLabel):
                        # skip the group title if it's also a QLabel
                        if child is grp:
                            continue
                        lines.append(child.text())

            # write out
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))

            self.show_message(
                "Success",
                f"Health report exported to:\n{file_path}",
                QMessageBox.Icon.Information
            )
            print(f"[INFO] Health report exported to: {file_path}")

        except Exception as e:
            self.show_message(
                "Error",
                f"Failed to export health report:\n{e}",
                QMessageBox.Icon.Critical
            )
            print(f"[ERROR] Health report export failed: {e}")

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
        # ── end patch

        # Corrected stylesheet application
        info_label_style = f"""
            QLabel {{
                color: {TEXT_COLOR};
                font-size: {FONT_SIZE_NORMAL}pt;
                font-family: {FONT_FAMILY};
                margin: 2px 0px; 
                padding: 2px 0px;
            }}
        """
        for lbl in self.info_labels.values():
            lbl.setStyleSheet(info_label_style)
            info_layout_inner.addWidget(lbl)
            
        info_group.setLayout(info_layout_inner)
        self.apply_groupbox_style(
            info_group, 
            self.COLOR_BOX_BORDER_RIGHT, 
            self.COLOR_BOX_BG_RIGHT, 
            self.COLOR_BOX_TITLE_RIGHT,
            is_part_of_right_column=True # Explicitly flag as right column item
        )
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
            layout.setContentsMargins(2, 2, 2, 2)

            if name == "Communication Subsystem":
                # Add standard comm items
                for text in items:
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                # Add special status label
                self.comms_status_label = QLabel("Status: Disconnected")
                self.comms_status_label.setStyleSheet(f"QLabel {{ margin: 2px 0px; padding: 2px 0px; color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.comms_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.comms_status_label)
            elif name == "Payload Subsystem":
                # Special payload status labels
                self.camera_status_label = QLabel("Camera: Pending...")
                self.camera_status_label.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.camera_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.camera_status_label)
                
                self.camera_ready_label = QLabel("Status: Not Ready")
                self.camera_ready_label.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.camera_ready_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.camera_ready_label)
            else:
                # Standard subsystem items
                for text in items:
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    if name != "Error Log" and name != "Overall Status":
                        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)

            group.setLayout(layout)
            self.apply_groupbox_style(
                group,
                self.COLOR_BOX_BORDER_RIGHT,
                self.COLOR_BOX_BG_RIGHT,
                self.COLOR_BOX_TITLE_RIGHT,
                is_part_of_right_column=True # Explicitly flag as right column item
            )
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

        # force this first row to a fixed height so it never collapses
        controls_container.setFixedHeight(150)
        
        # File loading section
        self.setup_file_loading_section_compact(controls_layout)
        
        # ── Analysis mode selector ──
        mode_lbl = QLabel("Analysis Mode:")
        mode_lbl.setStyleSheet(self.LABEL_STYLE)
        controls_layout.addWidget(mode_lbl)

        self.analysis_mode_combo = QComboBox()
        self.analysis_mode_combo.addItems([
            "Relative Distance",
            "Relative Angle",
            "Angular Position"
        ])
        self.analysis_mode_combo.setFixedWidth(150)
        # replot & rename metrics whenever user changes mode
        self.analysis_mode_combo.currentIndexChanged.connect(self.update_analysis_plots)
        controls_layout.addWidget(self.analysis_mode_combo)
        self.setup_range_selection_section_compact(controls_layout)
        
        # ── smoothing controls ──
        from PyQt6.QtWidgets import QButtonGroup
        smooth_container = QWidget()
        smooth_layout = QHBoxLayout(smooth_container)
        smooth_layout.setSpacing(8)
        smooth_layout.setContentsMargins(0, 0, 0, 0)

        # define buttons: (label, mode_key, tooltip)
        smooth_defs = [
            ("Raw",    None,  "No filtering – raw data"),
            ("SavGol", "SG",  "Savitzky–Golay filter"),
            ("Butter", "BW",  "Butterworth filter")
        ]
        btn_group = QButtonGroup(self)       # exclusive toggling
        btn_group.setExclusive(True)
        for text, mode, tip in smooth_defs:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            # unify with main buttons
            btn.setStyleSheet(self.BUTTON_STYLE)
            btn.setFixedHeight(BUTTON_HEIGHT)
            btn.clicked.connect(lambda _, m=mode: self.set_smoothing_mode(m))
            setattr(self, f"{text.lower()}_btn", btn)
            btn_group.addButton(btn)
            smooth_layout.addWidget(btn)
        # default selection
        self.raw_btn.setChecked(True)
        controls_layout.addWidget(smooth_container)

        # ── per-filter parameter panels ──
        from PyQt6.QtWidgets import QStackedWidget
        self.filter_param_stack = QStackedWidget()

        # 0: raw → empty
        self.filter_param_stack.addWidget(QWidget())

        # 1: SavGol params
        sg_panel = QWidget()
        sg_lay   = QHBoxLayout(sg_panel)
        sg_lay.setSpacing(4)
        sg_lay.addWidget(QLabel("Win len:"))
        self.sg_window_len = QSpinBox()
        self.sg_window_len.setRange(3, 101)
        self.sg_window_len.setSingleStep(2)
        self.sg_window_len.setValue(5)
        self.sg_window_len.valueChanged.connect(self.update_analysis_plots)
        sg_lay.addWidget(self.sg_window_len)
        sg_lay.addWidget(QLabel("Poly:"))
        self.sg_poly = QSpinBox()
        self.sg_poly.setRange(1, 10)
        self.sg_poly.setValue(2)
        self.sg_poly.valueChanged.connect(self.update_analysis_plots)
        sg_lay.addWidget(self.sg_poly)
        self.filter_param_stack.addWidget(sg_panel)

        # 2: Butter params
        bw_panel = QWidget()
        bw_lay   = QHBoxLayout(bw_panel)
        bw_lay.setSpacing(4)
        bw_lay.addWidget(QLabel("Cutoff:"))
        self.butter_cutoff = QDoubleSpinBox()
        self.butter_cutoff.setRange(0.1, 100.0)
        self.butter_cutoff.setSingleStep(0.1)
        self.butter_cutoff.setValue(1.0)
        self.butter_cutoff.valueChanged.connect(self.update_analysis_plots)
        bw_lay.addWidget(self.butter_cutoff)
        self.butter_type = QComboBox()
        self.butter_type.addItems(["Low-pass", "High-pass"])
        self.butter_type.currentIndexChanged.connect(self.update_analysis_plots)
        bw_lay.addWidget(self.butter_type)
        bw_lay.addWidget(QLabel("Order:"))
        self.butter_order = QSpinBox()
        self.butter_order.setRange(1, 10)
        self.butter_order.setValue(2)
        self.butter_order.valueChanged.connect(self.update_analysis_plots)
        bw_lay.addWidget(self.butter_order)
        self.filter_param_stack.addWidget(bw_panel)

        controls_layout.addWidget(self.filter_param_stack)
         # spacer
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

        metrics_layout = QVBoxLayout(metrics_container)
        metrics_layout.setSpacing(2)                   # less spacing
        metrics_layout.setContentsMargins(4, 4, 4, 4)  # slimmer margins


        # match Mission Control info panel width
        metrics_container.setMinimumWidth(180)
        metrics_container.setMaximumWidth(220)
        
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
        self.export_btn.setStyleSheet(self.BUTTON_STYLE)
        self.export_btn.setFixedHeight(BUTTON_HEIGHT)
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
         self.load_csv_btn.setFixedHeight(BUTTON_HEIGHT)
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

        
        # End time controls
        self.end_label = QLabel("End (s):")
        self.end_label.setStyleSheet(self.LABEL_STYLE)
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setDecimals(2)
        self.end_spin.setFixedWidth(80)
        self.end_spin.setFixedHeight(28)

    
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
        """Update the metrics display with all calculated statistics"""
        if not hasattr(self, 'metrics'):
            self.metrics_display.setText("No metrics available")
            return

        try:
            # rename based on current graph mode
            gm = self.analysis_mode_combo.currentText()
            if   gm == "Relative Distance":
                P, D = "Distance",       "Velocity"
            elif gm == "Relative Angle":
                P, D = "Rel. Angle",     "Rate of Change"
            else:
                P, D = "Angl. Pos.",     "Spin Rate"

            m = self.metrics
            text = "\n".join([
                f"Data Points:    {m['data_points']}",
                f"Time Range:     {m['time_range']:.2f} s",
                f"Peak {P}:       {m['peak_value']:.4f}",
                f"Min {P}:        {m['min_value']:.4f}",
                f"▶ Avg {P}:      {m['avg_value']:.4f}",
                f"{P} Range:      {m['value_range']:.4f}",
                f"Peak {D}:       {m['peak_velocity']:.4f}",
                f"Min {D}:        {m['min_velocity']:.4f}",
                f"▶ Avg {D}:      {m['avg_velocity']:.4f}",
            ])
            self.metrics_display.setText(text)

        except Exception as e:
            print(f"[ERROR] update_metrics_display: {e}")
            self.metrics_display.setText(f"Error displaying metrics: {e}")

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
            end   = self.end_spin.value()
            if end <= start:
                return

            df        = self.full_df
            df_range  = df[(df['relative_time'] >= start) & (df['relative_time'] <= end)]
            if len(df_range) < 2:
                self.metrics_display.setText("Not enough data points in selected range")
                return

            # full series for context
            full_ts = df["relative_time"].values
            full_v  = df["value"].values

            # selected range
            ts       = df_range["relative_time"].values
            raw_vals = df_range["value"].values

            # apply filtering if requested
            mode = self.smooth_mode
            if mode == "SG":
                from scipy.signal import savgol_filter
                wl = self.sg_window_len.value()
                if wl % 2 == 0: 
                    wl += 1
                poly = self.sg_poly.value()
                vals = savgol_filter(raw_vals, window_length=wl, polyorder=poly)
            elif mode == "BW":
                from numpy import mean, diff
                from scipy.signal import butter, filtfilt
                # cutoff freq and order from UI
                cutoff = self.butter_cutoff.value()
                order  = self.butter_order.value()
                # sampling rate from timestamps
                dt0 = diff(ts)
                fs  = 1.0/(mean(dt0) if len(dt0)>0 else 1.0)
                nyq = 0.5*fs
                btype = 'low' if self.butter_type.currentText()=="Low-pass" else 'high'
                b, a  = butter(order, cutoff/nyq, btype=btype)
                vals = filtfilt(b, a, raw_vals)
            else:
                vals = raw_vals

            # compute velocity
            from numpy import diff
            dts = diff(ts)
            dvs = diff(vals)
            dts[dts==0] = 1e-6
            vel = dvs/dts
            vel_ts = ts[1:]

            # clear & redraw
            self.raw_canvas.figure.clear()
            self.vel_canvas.figure.clear()

            # Raw plot
            raw_ax = self.raw_canvas.figure.add_subplot(111)
            raw_ax.set_facecolor(PLOT_BACKGROUND)
            raw_ax.plot(full_ts, full_v, color=PLOT_LINE_ALT, alpha=0.4, label="Full Data")
            raw_ax.plot(ts, vals, color=PLOT_LINE_PRIMARY, linewidth=2, label="Selected Range")

            # overlay filter legend with the correct parameters
            if mode == "SG":
                lbl = f"SavGol (wl={self.sg_window_len.value()}, poly={self.sg_poly.value()})"
            elif mode == "BW":
                lbl = (
                    f"Butterworth ({self.butter_type.currentText()}, "
                    f"fc={self.butter_cutoff.value():.2f}, "
                    f"ord={self.butter_order.value()})"
                )
            else:
                lbl = None
            if lbl:
                raw_ax.plot(
                    ts, vals,
                    linestyle="--",
                    color=PLOT_LINE_SECONDARY,
                    linewidth=2,
                    label=lbl
                )

            # vertical markers
            raw_ax.axvline(start, color=SUCCESS_COLOR, linestyle='--', label="Start")
            raw_ax.axvline(end,   color=ERROR_COLOR,   linestyle='--', label="End")

            raw_ax.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)

            # pick axis labels by mode
            gm = self.analysis_mode_combo.currentText()
            if   gm == "Relative Distance":
                y_raw, y_vel = "Distance (m)",        "Velocity (m/s)"
            elif gm == "Relative Angle":
                y_raw, y_vel = "Relative Angle (°)",  "Rate of Change (°/s)"
            else:  # Angular Position
                y_raw, y_vel = "Angular Position (°)", "Spin Rate (°/s)"

            raw_ax.set_ylabel(y_raw, color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            raw_ax.grid(True, color=GRID_COLOR, alpha=0.3)
            raw_ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            raw_ax.legend(facecolor=BOX_BACKGROUND, edgecolor=BORDER_COLOR, fontsize=8)
            self.raw_canvas.figure.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.15)

            # Velocity plot
            vel_ax = self.vel_canvas.figure.add_subplot(111)
            vel_ax.set_facecolor(PLOT_BACKGROUND)
            vel_ax.plot(vel_ts, vel, color=PLOT_LINE_SECONDARY, linewidth=2, label=y_vel)
            vel_ax.axvline(start, color=SUCCESS_COLOR, linestyle='--')
            vel_ax.axvline(end,   color=ERROR_COLOR,   linestyle='--')
            vel_ax.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            vel_ax.set_ylabel(y_vel,   color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=10)
            vel_ax.grid(True, color=GRID_COLOR, alpha=0.3)
            vel_ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            vel_ax.legend(facecolor=BOX_BACKGROUND, edgecolor=BORDER_COLOR, fontsize=8)
            self.vel_canvas.figure.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.15)

            self.raw_canvas.draw()
            self.vel_canvas.draw()

            # update metrics
            self.metrics = {
                "data_points": len(df_range),
                "time_range":  end - start,
                "peak_value":  vals.max(),
                "min_value":   vals.min(),
                "avg_value":   vals.mean(),
                "value_range": vals.max() - vals.min(),
                "peak_velocity": float(vel.max()) if len(vel)>0 else 0.0,
                "min_velocity":  float(vel.min()) if len(vel)>0 else 0.0,
                "avg_velocity":  float(vel.mean())if len(vel)>0 else 0.0,
            }
            self.update_metrics_display()

        except Exception as e:
            print(f"[ERROR] update_analysis_plots: {e}")
            traceback.print_exc()
            self.metrics_display.setText(f"Error plotting data: {e}")

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
            self.start_spin.setSingleStep(1)
            self.end_spin.setSingleStep(1)
            
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
        
        # guard against None
        mode = self.graph_section.current_graph_mode or self.analysis_mode_combo.currentText() or ""
        key = mode.replace(" ", "_").lower() if mode else "analysis"
        default_name = f"{key}_analysis.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis", default_name, "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.metrics_display.toPlainText())
                self.show_message("Success", f"Analysis exported to:\n{file_path}", QMessageBox.Icon.Information)
                print(f"[INFO] Analysis exported to: {file_path}")
            except Exception as e:
                self.show_message("Error", f"Failed to export analysis:\n{e}", QMessageBox.Icon.Critical)
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
            # self.camera_controls.crop_btn.setEnabled(True) # DELETED
            self.camera_controls.capture_btn.setEnabled(True)

            # ── start patch: enable health‐report button on connect
            self.print_report_btn.setEnabled(True)
            # ── end patch

            self.apply_config()
            QTimer.singleShot(100, self.delayed_server_setup)

        @sio.event
        def disconnect(reason=None):
            print(f"[INFO] ❌ Disconnected from server: {reason}")
            self.comms_status_label.setText("Status: Disconnected")
            self.camera_controls.toggle_btn.setEnabled(False)
            self.detector_controls.detector_btn.setEnabled(False)
            # self.camera_controls.crop_btn.setEnabled(False) # DELETED
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
        print("[INFO] Apply config pressed. Initiating 0.5s pause for stream and graph before sending config.")
        
        # Capture current streaming state for this specific call
        was_streaming_for_this_call = self.streaming

        # 1. Pause stream immediately if active
        if was_streaming_for_this_call:
            # self.toggle_stream() # This stops the stream and updates self.streaming
            # Avoid calling toggle_stream here if it has complex side effects or emits signals
            # that might interfere with rapid calls. Instead, manage stream state directly for pause.
            if self.streaming: # Double check, as state might change
                sio.emit("stop_camera")
                self.streaming = False
                self.camera_controls.toggle_btn.setText("Start Stream")
                print("[INFO] Stream paused for config application.")


        # 2. Initiate graph pause immediately
        self.calibration_change_time = time.time()
        # Keep the existing 1-second timer for resuming graphs.
        QTimer.singleShot(1000, self.resume_after_calibration_change)

        # 3. Schedule the actual config sending and detector update after 0.5 seconds
        # Pass the captured streaming state as an argument
        QTimer.singleShot(500, lambda: self._execute_config_application_after_pause(was_streaming_for_this_call))

    def _execute_config_application_after_pause(self, was_streaming_at_call_time):
        """Helper method to get/send config and update detector after the initial 0.5s pause."""
        print(f"[INFO] 0.5s pause complete. Getting/sending configuration (stream was {was_streaming_at_call_time}).")
        
        # Get and send configuration
        config = self.camera_settings.get_config()
        sio.emit("camera_config", config)
        
        #Update detector calibration (this will also update self.active_config_for_detector via server ack)
        self.update_detector_calibration(config) # This is now handled by camera_config_updated

        # Resume stream if it was active before applying config
        if was_streaming_at_call_time:
            # Add a small delay for server to process config before restarting stream
            def restart_stream_if_needed():
                if not self.streaming: # Check if it wasn't restarted by another process
                    sio.emit("start_camera")
                    self.streaming = True
                    self.camera_controls.toggle_btn.setText("Stop Stream")
                    print("[INFO] Stream restart scheduled (if it was on before apply_config).")

            threading.Timer(0.2, restart_stream_if_needed).start()
        
        # No need to delete an instance attribute as it's passed by argument.

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
                
                # Use the server-acknowledged and locally cached configuration
                if self.active_config_for_detector is None:
                    # Fallback if not initialized, though it should be in __init__ or connect event
                    print("[WARNING] run_detector: active_config_for_detector is None. Using live UI settings as fallback.")
                    config = self.camera_settings.get_config() # Fallback, not ideal
                else:
                    config = self.active_config_for_detector # CORRECT: Use cached config
                
                is_cropped = config.get('cropped', False)
                
                original_height = None
                if is_cropped:
                    current_height = frame.shape[0]
                    crop_factor = config.get('crop_factor') # This is set in camera_settings.get_config()
                    
                    # Ensure crop_factor is valid and positive before division
                    if crop_factor is not None and crop_factor > 0.001: # MIN_CROP_FACTOR is likely 0.1
                        original_height = int(current_height / crop_factor)
                    else:
                        # Fallback if crop_factor is somehow invalid (should not happen with current setup)
                        print(f"[WARNING] Invalid crop_factor: {crop_factor} during detection. Using current_height as original_height.")
                        original_height = current_height 
                
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
                        # ── end patch

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
        # Set the crop state to False using the CameraSettingsWidget's method
        # This will also trigger UI updates within CameraSettingsWidget
        self.camera_settings.set_crop_state(False) 

        # The following logic for "Custom (Cropped)" might need review.
        # _populate_res_dropdown in CameraSettingsWidget should handle the (Cropped) suffix.
        # If a specific "Custom (Cropped)" item needs explicit removal, that logic would remain,
        # but ensure it's still relevant with the new setup.
        # For now, assuming set_crop_state(False) and subsequent apply_config is sufficient.
        # idx = self.camera_settings.res_dropdown.findText("Custom (Cropped)") 
        # if idx != -1:
        #     self.camera_settings.res_dropdown.removeItem(idx)
        
        self.camera_settings.res_dropdown.setCurrentIndex(0) # Reset dropdown to the first item
        
        # Apply the configuration which will now have cropping disabled
        config = self.camera_settings.get_config() 
        sio.emit("camera_config", config)
        time.sleep(0.2) # Keep delay if necessary for server to process

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
