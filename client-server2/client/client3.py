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
    QTabWidget, QFileDialog
)

import matplotlib
matplotlib.use('Agg')
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

# Add these lines to suppress ALL logging errors from network libraries
import urllib3
urllib3.disable_warnings()
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)

# Also suppress the problematic Windows logging flush error
class SafeStreamHandler(logging.StreamHandler):
    def flush(self):
        try:
            super().flush()
        except OSError:
            pass  # Ignore Windows flush errors

# Configure logging properly at the module level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client_log.txt'),
        SafeStreamHandler(sys.stdout)
    ]
)


from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QImage, QFont, QPainter, QPen


##############################################################################
#                                IMPORTS                                     #
##############################################################################

# Payload and detection modules
from payload.spin           import AngularPositionPlotter
from payload.distance       import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload import detector4

# UI Components
from widgets.camera_controls import CameraControlsWidget
from widgets.camera_settings import CameraSettingsWidget, CALIBRATION_FILES
from widgets.graph_section import GraphSection
from widgets.detector_control import DetectorControlWidget
from widgets.adcs import ADCSSection
from widgets.detector_settings_widget import DetectorSettingsWidget
from payload.detector4 import detector_instance
from data_analysis import DataAnalysisTab
from widgets.lidar_client import LidarWidget

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
    latencyUpdated = pyqtSignal(float)

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
        self.show_crosshairs = False  # Add this line
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
        # throttle graph redraws
        self._last_graph_draw = 0.0
        # Initialize with a default (e.g., 2 Hz). This will be updated by GraphSection's signal.
        self._graph_update_interval = 1.0 / 2.0 
        # ── end patch ──

        # ── instantiate plotters early ─────────────────────────────
        self.spin_plotter     = AngularPositionPlotter()
        self.distance_plotter = RelativeDistancePlotter()
        self.angular_plotter  = RelativeAnglePlotter()
        # ── end instantiation ───────────────────────────────────────

        # Setup UI and connections
        self.setup_ui() # self.camera_settings and self.graph_section are created here

        # ── Hook the graph‐rate spinbox to each plotter’s redraw rate ─────────
        if hasattr(self, 'graph_section') and self.graph_section:
            # spinbox emits graph_update_frequency_changed(float Hz)
            self.graph_section.graph_update_frequency_changed.connect(self.spin_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.distance_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.angular_plotter.set_redraw_rate)

            # initialize each plotter to the spinbox's default
            # only pull the initial freq if the spinbox already exists
            spin = getattr(self.graph_section, 'freq_spinbox', None)
            if spin is not None:
                try:
                    freq = spin.value()
                    if freq > 0:
                        self.spin_plotter.set_redraw_rate(freq)
                        self.distance_plotter.set_redraw_rate(freq)
                        self.angular_plotter.set_redraw_rate(freq)
                except Exception:
                    pass

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
        self.latencyUpdated.connect(self.detector_settings.set_latency)

        # ── now it's safe to connect the frequency-spinbox signal ──
        self.graph_section.graph_update_frequency_changed.connect(self.spin_plotter.set_redraw_rate)
        self.graph_section.graph_update_frequency_changed.connect(self.distance_plotter.set_redraw_rate)
        self.graph_section.graph_update_frequency_changed.connect(self.angular_plotter.set_redraw_rate)

    def _on_tab_changed(self, index):
        """When the current tab switches, refresh the Data Analysis plots if needed."""
        from data_analysis import DataAnalysisTab
        w = self.tab_widget.widget(index)
        if isinstance(w, DataAnalysisTab):
            w.update_plots()

    def handle_graph_update_frequency_change(self, frequency_hz):
        """Slot to update the graph update interval when GraphSection's spinbox changes."""
        if frequency_hz > 0:
            self._graph_update_interval = 1.0 / frequency_hz
            print(f"[MainWindow] Graph update interval changed to {self._graph_update_interval:.3f}s ({frequency_hz} Hz)")
        else:
            # Fallback to a sensible default if frequency is zero or negative
            self._graph_update_interval = 1.0 / 1.0 # 1 Hz
            print(f"[MainWindow] Warning: Invalid graph update frequency ({frequency_hz} Hz). Defaulting to 1 Hz.")
            

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

        # Data Analysis now lives in its own module
        self.analysis_tab = DataAnalysisTab(parent=self, main_window=self)
        self.tab_widget.addTab(self.analysis_tab, "Data Analysis")

        main_layout.addWidget(self.tab_widget)

    def handle_lidar_back_button(self):
        """Handles the back button click from the LidarWidget."""
        self.lidar_widget.stop_lidar()
        print("Back button clicked in LidarWidget")

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
        """Setup video stream, camera controls, camera settings & detector settings."""
        row1 = QHBoxLayout()
        row1.setSpacing(2)
        row1.setContentsMargins(2, 2, 2, 2)
        row1.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

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

        # Camera settings (fixed size to match video height)
        self.camera_settings = CameraSettingsWidget()
        self.camera_settings.setMaximumWidth(280)
        self.camera_settings.setFixedHeight(video_group.height())
        self.apply_groupbox_style(self.camera_settings, self.COLOR_BOX_BORDER_CONFIG)
        self.camera_settings.apply_btn.setStyleSheet(self.BUTTON_STYLE)
        self.camera_settings.apply_btn.setFixedHeight(BUTTON_HEIGHT)
        self.camera_settings.apply_btn.clicked.connect(self.apply_config)

        row1.addWidget(video_group)
        row1.addWidget(self.camera_controls)
        row1.addWidget(self.camera_settings)

        # ── Detector settings to the RIGHT of camera settings ────────────────
        self.detector_settings = DetectorSettingsWidget()
        self.detector_settings.setMaximumWidth(280)
        self.detector_settings.setFixedHeight(video_group.height())
        self.apply_groupbox_style(self.detector_settings, self.COLOR_BOX_BORDER_DETECTOR)
        self.detector_settings.settingsChanged.connect(
            lambda cfg: detector_instance.update_params(**cfg)
        )
        # Connect the tag size update signal
        self.detector_settings.tagSizeUpdated.connect(
            lambda size: detector4.update_tag_size(size)
        )
        row1.addWidget(self.detector_settings)
        # ─────────────────────────────────────────────────────────────────────

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
        self.graph_section.setFixedSize(560, 280) # Existing size
        self.graph_section.graph_display_layout.setSpacing(1)
        self.graph_section.graph_display_layout.setContentsMargins(1, 1, 1, 1)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        
        row2.addWidget(self.graph_section)

        # LIDAR section (moved here)
        lidar_group = QGroupBox("LIDAR") # Title for the LIDAR group
        lidar_layout = QVBoxLayout()
        lidar_layout.setSpacing(2)
        lidar_layout.setContentsMargins(5, 15, 5, 5) # Adjusted margins for title space

        # ── REPLACE PLACEHOLDER WITH LIDARWIDGET ──────────────────────────────
        # Remove the placeholder:
        # lidar_placeholder = QLabel("LIDAR Placeholder") # Placeholder text
        # lidar_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # lidar_placeholder.setStyleSheet(f"background: {self.COLOR_BOX_BG}; color: {TEXT_SECONDARY}; border: 1px dashed #555; border-radius: {BORDER_RADIUS}px; font-size: {FONT_SIZE_NORMAL}pt;")
        # lidar_layout.addWidget(lidar_placeholder, stretch=1) # Allow placeholder to expand

        # Add the LidarWidget and connect signals:
        self.lidar_widget = LidarWidget()
        
        # Connect LIDAR control signals to server communication
        self.lidar_widget.lidar_start_requested.connect(self.start_lidar_streaming)
        self.lidar_widget.lidar_stop_requested.connect(self.stop_lidar_streaming)
        self.lidar_widget.back_button_clicked.connect(self.handle_lidar_back_button)
            
        lidar_layout.addWidget(self.lidar_widget)
        # ────────────────────────────────────────────────────────────────


        # Adjust LIDAR group's height or the graph section's if they look misaligned.
        # To make LIDAR group take similar height as graph:
        lidar_group.setFixedHeight(self.graph_section.height()) # Match graph height
        # Or allow it to expand:
        # lidar_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        lidar_group.setLayout(lidar_layout)
        self.apply_groupbox_style(lidar_group, self.COLOR_BOX_BORDER_LIDAR, bg_color=self.COLOR_BOX_BG_LIDAR, title_color=self.COLOR_BOX_TEXT_LIDAR)
        # Set a fixed width for LIDAR or let it expand. Example fixed width:
        lidar_group.setFixedWidth(200) # Adjust as needed, e.g., to fill remaining space if graph_section has fixed width

        row2.addWidget(lidar_group)
        
        
        parent_layout.addLayout(row2)

        
    def draw_crosshairs(self, frame):
        """Draw crosshairs at the center of the frame"""
        height, width = frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        
        # Draw horizontal line
        cv2.line(frame, (0, center_y), (width, center_y), (0, 255, 0), 2)
        # Draw vertical line  
        cv2.line(frame, (center_x, 0), (center_x, height), (0, 255, 0), 2)
        
        return frame

    def toggle_orientation(self):
        """Toggle crosshair display for manual orientation reference"""
        self.show_crosshairs = not self.show_crosshairs
        
        if self.show_crosshairs:
            self.camera_controls.orientation_btn.setText("Hide Crosshairs")
            print("[INFO] Manual orientation crosshairs enabled")
        else:
            self.camera_controls.orientation_btn.setText("Manual Orientation")
            print("[INFO] Manual orientation crosshairs disabled")
        
    def setup_subsystem_controls_row(self, parent_layout):
        """Setup ADCS controls using ADCSSection widget"""
        row3 = QHBoxLayout()
        row3.setSpacing(4) 
        row3.setContentsMargins(4, 4, 4, 4) # Standard margins
        row3.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # ADCS section using the new ADCSSection widget
        self.adcs_control_widget = ADCSSection() # Instantiate your custom widget
        
        # Optional: Connect to signals from ADCSSection if needed
        # self.adcs_control_widget.mode_selected.connect(self.handle_adcs_mode_selection)
        # self.adcs_control_widget.adcs_command_sent.connect(self.handle_adcs_command)
                                                                                   
        self.apply_groupbox_style(self.adcs_control_widget, self.COLOR_BOX_BORDER_ADCS)
        # ADCSSection is already a QGroupBox, so styling is applied directly.
        # It will manage its own internal title ("ADCS").
        
        # Adjust sizing as needed. For example, to make it expand:
        self.adcs_control_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Or set a fixed height if desired, e.g., to match other rows or content:
        # self.adcs_control_widget.setFixedHeight(100) 

        row3.addWidget(self.adcs_control_widget)
        parent_layout.addLayout(row3)

    # Optional: Add handler methods in client3.py if you connect signals from ADCSSection
    # def handle_adcs_mode_selection(self, mode_index, mode_name):
    #     print(f"[Client3] ADCS Mode selected: Index {mode_index}, Name '{mode_name}'")
    #     # Add logic here to respond to ADCS mode changes

    # def handle_adcs_command(self, mode_name, command_name):
    #     print(f"[Client3] ADCS Command: Mode '{mode_name}', Command '{command_name}'")
    #     # Here you would typically emit a socketio event to the server
    #     # sio.emit("adcs_command", {"mode": mode_name, "command": command_name})

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

        @sio.on("lidar_broadcast")
        def on_lidar_broadcast(data):
            """Handles incoming LIDAR data from the server."""
            try:
                distance = data.get('distance_cm')
                if distance is not None:
                    print(f"[DEBUG] Received LIDAR data: {distance} cm")
                    # Send data to LIDAR widget
                    self.lidar_widget.set_distances([distance])
                else:
                    print("[WARNING] Received LIDAR data without distance_cm field")
            except Exception as e:
                print(f"[ERROR] Failed to process LIDAR data: {e}")

        @sio.on("lidar_status")
        def on_lidar_status(data):
            """Handle LIDAR status updates from server"""
            try:
                status = data.get('status', 'unknown')
                streaming = data.get('streaming', False)
                print(f"[INFO] LIDAR Status: {status}, Streaming: {streaming}")
                
                # Update LIDAR widget streaming state if needed
                if hasattr(self.lidar_widget, 'is_streaming'):
                    if streaming != self.lidar_widget.is_streaming:
                        # Sync widget state with server state
                        self.lidar_widget.is_streaming = streaming
                        self.lidar_widget.start_stop_button.setText(
                            "Stop LIDAR" if streaming else "Start LIDAR"
                        )
            except Exception as e:
                print(f"[ERROR] Failed to process LIDAR status: {e}")

    def start_lidar_streaming(self):
        """Start LIDAR data streaming from server"""
        if sio.connected:
            print("[INFO] Requesting LIDAR streaming start")
            sio.emit("start_lidar")
            print("[DEBUG] start_lidar event emitted to server")
        else:
            print("[WARNING] Cannot start LIDAR - not connected to server")

    def stop_lidar_streaming(self):
        """Stop LIDAR data streaming from server"""
        if sio.connected:
            print("[INFO] Requesting LIDAR streaming stop")
            sio.emit("stop_lidar")
            print("[DEBUG] stop_lidar event emitted to server")
        else:
            print("[WARNING] Cannot stop LIDAR - not connected to server")

    def handle_lidar_back_button(self):
        """Handles the back button click from the LidarWidget."""
        try:
            # Stop LIDAR streaming on server
            if self.lidar_widget.is_streaming:
                self.stop_lidar_streaming()
            
            # Stop local widget
            self.lidar_widget.stop_lidar()
            print("Back button clicked in LidarWidget - streaming stopped")
        except Exception as e:
            print(f"[ERROR] Failed to handle LIDAR back button: {e}")

    def delayed_server_setup(self):
        """Called shortly after connect—override if needed."""
        pass

    def handle_frame_data(self, data):
        """Process incoming frame data"""
        try:
            arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                # Add crosshairs if manual orientation is enabled
                if self.show_crosshairs:
                    frame = self.draw_crosshairs(frame)
                    
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
        
        # Store the applied configuration for detector use
        self.active_config_for_detector = config.copy()
        
        # Update detector calibration
        self.update_detector_calibration(config)

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
                    # Verify the calibration was actually loaded
                    if hasattr(detector4.detector_instance, 'mtx'):
                        cy = detector4.detector_instance.mtx[1, 2] if detector4.detector_instance.mtx is not None else "None"
                else:
                    print(f"[WARNING] ❌ Failed to update detector calibration")
            else:
                print(f"[WARNING] Detector instance not available for calibration update")
            
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

    def show_full_image(self):
        """Cover UI with a full-screen image and tiny back button."""
        try:
            # Hide main tabs
            self.tab_widget.hide()
            
            # Create full-screen image label
            self._full_lbl = QLabel(self)
            self._full_lbl.setGeometry(0, 0, self.width(), self.height())  # Fill entire window
            self._full_lbl.setStyleSheet("background-color: black;")  # Black background
            
            # Load and scale image
            image_path = r"C:\Users\juanb\OneDrive\Imágenes\Camera Roll\WIN_20250221_12_17_13_Pro.jpg"
            
            if os.path.exists(image_path):
                pix = QPixmap(image_path)
                if not pix.isNull():
                    # Scale image to fit screen while maintaining aspect ratio
                    scaled_pix = pix.scaled(
                        self.size(), 
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self._full_lbl.setPixmap(scaled_pix)
                    self._full_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    print(f"[ERROR] Failed to load image: {image_path}")
                    self._full_lbl.setText("Failed to load image")
                    self._full_lbl.setStyleSheet(f"background-color: black; color: {TEXT_COLOR}; font-size: 24pt;")
                    self._full_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                print(f"[ERROR] Image file not found: {image_path}")
                self._full_lbl.setText("Image file not found")
                self._full_lbl.setStyleSheet(f"background-color: black; color: {TEXT_COLOR}; font-size: 24pt;")
                self._full_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Create back button
            self._back_btn = QPushButton("← Back", self)
            self._back_btn.setGeometry(20, 20, 100, 40)  # Top-left corner
            self._back_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0, 0, 0, 180);
                    color: {TEXT_COLOR};
                    border: 2px solid {BUTTON_COLOR};
                    border-radius: 8px;
                    font-size: 14pt;
                    font-family: {FONT_FAMILY};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {BUTTON_HOVER};
                    color: black;
                }}
            """)
            self._back_btn.clicked.connect(self.hide_full_image)
            
            # Show widgets
            self._full_lbl.show()
            self._back_btn.show()
            
            # Raise to top to ensure they're visible
            self._full_lbl.raise_()
            self._back_btn.raise_()
            
            print("[INFO] Full image view activated")
            
        except Exception as e:
            print(f"[ERROR] Failed to show full image: {e}")
            # Fallback: restore normal view
            if hasattr(self, '_full_lbl'):
                self._full_lbl.hide()
            if hasattr(self, '_back_btn'):
                self._back_btn.hide()
            self.tab_widget.show()

    def hide_full_image(self):
        """Remove full-screen image and back button, restore main UI"""
        try:
            # Remove full-screen image and back button
            if hasattr(self, '_full_lbl'):
                self._full_lbl.hide()
                self._full_lbl.deleteLater()
                delattr(self, '_full_lbl')
                
            if hasattr(self, '_back_btn'):
                self._back_btn.hide()
                self._back_btn.deleteLater()
                delattr(self, '_back_btn')
            
            # Restore main UI
            self.tab_widget.show()
            
            print("[INFO] Returned to normal view")
            
        except Exception as e:
            print(f"[ERROR] Failed to hide full image: {e}")
            # Force restore main UI
            self.tab_widget.show()

    def run_detector(self):
        """Main detector processing loop"""
        while self.detector_active:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                
                # Use the server-acknowledged config (applied settings) instead of live UI
                if self.active_config_for_detector is None:
                    config = self.camera_settings.get_config() # Fallback only
                else:
                    config = self.active_config_for_detector # Use last applied config
                
                is_cropped = config.get('cropped', False)
                
                original_height = None
                if is_cropped:
                    current_height = frame.shape[0]
                    crop_factor = config.get('crop_factor')
                    
                    if crop_factor is not None and crop_factor > 1.0:
                        original_height = int(current_height * crop_factor)
                    else:
                        print(f"[WARNING] Invalid crop_factor: {crop_factor}")
                        original_height = current_height 
                
                # Process frame with detector
                try:
                    if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                        analysed, pose, latency_ms = detector4.detector_instance.detect_and_draw(
                            frame,
                            return_pose=True,
                            is_cropped=is_cropped,
                            original_height=original_height
                        )
                        
                        # Add crosshairs to detector output if enabled
                        if self.show_crosshairs:
                            analysed = self.draw_crosshairs(analysed)
                            
                    else:
                        analysed, pose = detector4.detect_and_draw(frame, return_pose=True)
                

                
                    self.latencyUpdated.emit(latency_ms)
                    bridge.analysed_frame.emit(analysed)

                    # 1) always update all calculators
                    if pose:
                        rvec, tvec = pose
                        self.spin_plotter    .update(rvec, tvec)
                        self.distance_plotter.update(rvec, tvec)
                        self.angular_plotter .update(rvec, tvec)

                        # 2) update the three small live‐value labels WITH UNITS
                        self.graph_section.live_labels["SPIN MODE"]             \
                            .setText(f"{self.spin_plotter.current_angle:.3f}°")  # Added degree symbol
                        self.graph_section.live_labels["DISTANCE MEASURING MODE"] \
                            .setText(f"{self.distance_plotter.current_distance:.3f}m")  # Added meter unit
                        self.graph_section.live_labels["SCANNING MODE"]         \
                            .setText(f"{self.angular_plotter.current_ang:.3f}°")  # Added degree symbol

                        # 2b) update the big "detail" label for the active graph WITH UNITS
                        detail = getattr(self.graph_section, "current_detail_label", None)
                        mode   = getattr(self.graph_section, "current_graph_mode", None)
                        if detail and mode:
                            if mode == "SPIN MODE":
                                v = self.spin_plotter.current_angle
                                detail.setText(f"{v:.3f}°")  # Added degree symbol
                            elif mode == "DISTANCE MEASURING MODE":
                                v = self.distance_plotter.current_distance
                                detail.setText(f"{v:.3f}m")  # Added meter unit
                            else:  # SCANNING MODE
                                v = self.angular_plotter.current_ang
                                detail.setText(f"{v:.3f}°")  # Added degree symbol

                            # ── if we're recording, grab that same label value ─────────────────
                            if self.graph_section.is_recording:
                                # timestamp + float value from the detail label (extract number only)
                                ts = time.time()
                                try:
                                    # Extract numeric value (remove units)
                                    text_val = detail.text().rstrip('°m')  # Remove degree and meter symbols
                                    val = float(text_val)
                                    self.graph_section.add_data_point(ts, val)
                                except ValueError:
                                    pass
                

                        # 3) continue with your throttled redraw / recording logic…
                        if self.should_update_graphs() and self.graph_section.graph_widget and pose:
                            self.graph_section.graph_widget.update(rvec, tvec, None)
                            # … recording code …
                except Exception as e:
                    print(f"[ERROR] Detector processing error: {e}")
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

############################################################################
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
