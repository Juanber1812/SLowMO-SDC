##############################################################################
#                              SLowMO CLIENT                                #
#                         Satellite Control Interface                       #
##############################################################################

import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue, os
import pandas as pd
import traceback
import platform
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea,
    QTabWidget, QFileDialog, QTextEdit
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

SERVER_URL = "http://192.168.1.146:5000"

##############################################################################
#                        SOCKETIO AND BRIDGE SETUP                         #
##############################################################################

sio = socketio.Client()

class QtLogHandler(logging.Handler, QObject):
    """
    Custom logging handler that emits a signal for each log record.
    """
    new_log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        logging.Handler.__init__(self)
        QObject.__init__(self, parent)
        # Set a default formatter, can be customized
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record):
        if record:
            msg = self.format(record)
            print(f"[DEBUG QtLogHandler.emit] Emitting: {msg}") # <<< ADD THIS DEBUG PRINT

            self.new_log_message.emit(msg)

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    analysed_frame = pyqtSignal(np.ndarray)

bridge = Bridge()

##############################################################################
#                            MAIN WINDOW CLASS                              #
##############################################################################

class MainWindow(QWidget):
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
        self.show_crosshairs = False 
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
        
        # Client-side communication metrics
        self.client_uplink_frequency = 0.0
        self.client_signal_strength = 0


        # display‐FPS counters
        self.display_frame_counter = 0
        self.current_display_fps   = 0
  
        # throttle graph redraws
        self._last_graph_draw = 0.0

        # ── instantiate plotters early ─────────────────────────────
        self.spin_plotter     = AngularPositionPlotter()
        self.distance_plotter = RelativeDistancePlotter()
        self.angular_plotter  = RelativeAnglePlotter()
        # ── end instantiation ───────────────────────────────────────

        # Setup Log Display Widget
        self.log_display_widget = QTextEdit()
        self.log_display_widget.setReadOnly(True)
        # Use theme variables for styling if available, otherwise fallbacks
        log_text_color = getattr(self, 'TEXT_COLOR', 'white')
        log_border_color = getattr(self, 'BORDER_COLOR', '#333333')
        log_font_family = getattr(self, 'FONT_FAMILY', 'Consolas, "Courier New", monospace')
        
        self.log_display_widget.setStyleSheet(f"""
            QTextEdit {{
                background-color: {SECOND_COLUMN}; 
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: 9pt;
                border: 0px solid {BORDER_COLOR};
            }}
        """)

        # Setup custom log handler
        self.qt_log_handler = QtLogHandler(self) # Pass self as parent
        self.qt_log_handler.new_log_message.connect(self.append_log_message)
        
        self.qt_log_handler.setLevel(logging.INFO) # Or logging.DEBUG for more detail
        
        logging.getLogger().addHandler(self.qt_log_handler)

        # Setup UI and connections
        self.setup_ui() # self.camera_settings and self.graph_section are created here

        # ── Hook the graph‐rate spinbox to each plotter’s redraw rate ─────────
        if hasattr(self, 'graph_section') and self.graph_section:
            # spinbox emits graph_update_frequency_changed(float Hz)
            self.graph_section.graph_update_frequency_changed.connect(self.spin_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.distance_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.angular_plotter.set_redraw_rate)

            # initialize each plotter to the spinbox's default
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
             logging("[WARNING] MainWindow.__init__: camera_settings not available for initial active_config_for_detector.")

        self.setup_socket_events()
        self.setup_signals()
        self.setup_timers()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        # Graph window reference
        self.graph_window = None

    def append_log_message(self, message: str):
        """Appends a message to the log display widget and auto-scrolls."""
        print(f"[DEBUG MainWindow.append_log_message] Received for GUI: {message}") 

        self.log_display_widget.append(message)
        scrollbar = self.log_display_widget.verticalScrollBar()
        if scrollbar: # Check if scrollbar exists
            scrollbar.setValue(scrollbar.maximum())

    def setup_signals(self):
        """Connect internal signals"""
        bridge.frame_received.connect(self.update_image)
        bridge.analysed_frame.connect(self.update_analysed_image)
        self.latencyUpdated.connect(self.detector_settings.set_latency)

        # ── now it's safe to connect the frequency-spinbox signal ──
        self.graph_section.graph_update_frequency_changed.connect(self.spin_plotter.set_redraw_rate)
        self.graph_section.graph_update_frequency_changed.connect(self.distance_plotter.set_redraw_rate)
        self.graph_section.graph_update_frequency_changed.connect(self.angular_plotter.set_redraw_rate)

        self.graph_section.payload_recording_started.connect(self.lidar_widget.start_recording)
        self.graph_section.payload_recording_stopped.connect(self.lidar_widget.stop_recording)


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
            logging.info(f"Graph update interval changed to {self._graph_update_interval:.3f}s ({frequency_hz} Hz)")
        else:
            # Fallback to a sensible default if frequency is zero or negative
            self._graph_update_interval = 1.0 / 1.0 # 1 Hz
            logging.warning(f"Invalid graph update frequency ({frequency_hz} Hz). Defaulting to 1 Hz.")
            

    def setup_timers(self):
        """Initialize performance timers"""
        self.fps_timer = self.startTimer(1000)
        
        # Add client communication metrics timer (every 5 seconds)
        self.client_comm_timer = QTimer()
        self.client_comm_timer.timeout.connect(self.update_client_communication_metrics)
        self.client_comm_timer.start(5000)

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
        logging.info("Back button clicked in LidarWidget")

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

        # Setup control rows - swapped order to make video stream row in the middle
        self.setup_graph_display_row(left_col)
        self.setup_video_controls_row(left_col)
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

        # Detector settings (fixed size to match video height)
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

        row1.addWidget(self.camera_controls)
        row1.addWidget(video_group)
        row1.addWidget(self.camera_settings)
        row1.addWidget(self.detector_settings)
        # ─────────────────────────────────────────────────────────────────────

        parent_layout.addLayout(row1)

    def setup_graph_display_row(self, parent_layout):
        """Setup graph display section and LIDAR section"""
        row2 = QHBoxLayout()
        row2.setSpacing(0) # No spacing between widgets to make LiDAR as close as possible to graph
        row2.setContentsMargins(2, 2, 2, 2)
        row2.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop) # Align top for differing heights

        # Graph section with recording capabilities
        self.record_btn = QPushButton("Record")
        self.duration_dropdown = QComboBox()
        self.duration_dropdown.setVisible(False)

        self.graph_section = GraphSection(self.record_btn, self.duration_dropdown)
        self.graph_section.setFixedSize(620, 224)  # 4/5 of original (620*0.8, 280*0.8)
        self.graph_section.graph_display_layout.setSpacing(1)
        self.graph_section.graph_display_layout.setContentsMargins(1, 1, 1, 1)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        
        row2.addWidget(self.graph_section)

        self.lidar_widget = LidarWidget()
        self.lidar_widget.back_button_clicked.connect(self.handle_lidar_back_button)
        if hasattr(self.lidar_widget, 'lidar_start_requested'):
            self.lidar_widget.lidar_start_requested.connect(self.start_lidar_streaming)
        if hasattr(self.lidar_widget, 'lidar_stop_requested'):
            self.lidar_widget.lidar_stop_requested.connect(self.stop_lidar_streaming)
         
        # Apply sizing directly to self.lidar_widget - make it narrower to move closer to graph
        self.lidar_widget.setFixedHeight(self.graph_section.height()) # Match graph height
        self.lidar_widget.setFixedWidth(160) # Reduced from 200 to move closer to graph

        # Add LiDAR widget with vertical centering alignment
        row2.addWidget(self.lidar_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Console Log Display Section - expanded to use space freed from narrower LiDAR widget
        log_display_group = QGroupBox()
        log_display_layout = QVBoxLayout() 
        log_display_layout.setContentsMargins(2, 2, 2, 2)  # Add some padding
        log_display_layout.setSpacing(1)
        
        # self.log_display_widget was created in __init__
        # Set minimum size to make it bigger and match graph section height
        self.log_display_widget.setMinimumHeight(self.graph_section.height() - 10)  # Slightly smaller than graph for padding
        self.log_display_widget.setMinimumWidth(300)  # Ensure reasonable minimum width
        log_display_layout.addWidget(self.log_display_widget)
        log_display_group.setLayout(log_display_layout)

        # Use theme variables for styling the log group box
        log_group_border_color = getattr(self, 'COLOR_BOX_BORDER_RIGHT', self.COLOR_BOX_BORDER) 
        log_group_bg_color = getattr(self, 'COLOR_BOX_BG_RIGHT', self.COLOR_BOX_BG) 
        log_group_title_color = getattr(self, 'COLOR_BOX_TITLE_RIGHT', self.COLOR_BOX_TITLE_RIGHT) # Changed self.BOX_TITLE_COLOR to self.COLOR_BOX_TITLE_RIGHT

        self.apply_groupbox_style(
            log_display_group, 
            log_group_border_color, 
            log_group_bg_color, 
            log_group_title_color,
            is_part_of_right_column=False # Explicitly flag as right column item
        )
        
        # Add stretch factor to expand log widget into freed space from narrower LiDAR
        row2.addWidget(log_display_group, 1)  # stretch factor 1 to expand
        
        parent_layout.addLayout(row2)

        
    def draw_crosshairs(self, frame):
        """Draw crosshairs at the center of the frame"""
        height, width = frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        
        # Draw horizontal line
        cv2.line(frame, (0, center_y), (width, center_y), (0, 255, 0), 1)
        # Draw vertical line  
        cv2.line(frame, (center_x, 0), (center_x, height), (0, 255, 0), 1)
        
        return frame

    def toggle_orientation(self):
        """Toggle crosshair display for manual orientation reference"""
        self.show_crosshairs = not self.show_crosshairs
        
        if self.show_crosshairs:
            logging.info("Manual orientation crosshairs enabled")
        else:
            logging.info("Manual orientation crosshairs disabled")
        
    def setup_subsystem_controls_row(self, parent_layout):
        """Setup ADCS controls using ADCSSection widget"""
        row3 = QHBoxLayout()
        row3.setSpacing(1) 
        row3.setContentsMargins(1,0, 1, 1) # Standard margins
        row3.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # ADCS section using the new ADCSSection widget - takes half width and full height
        self.adcs_control_widget = ADCSSection() # Instantiate your custom widget
                                                                            
        self.apply_groupbox_style(self.adcs_control_widget, self.COLOR_BOX_BORDER_ADCS)

        # Set size policy to expand vertically and take half width
        self.adcs_control_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.adcs_control_widget.adcs_command_sent.connect(self.handle_adcs_command)
        row3.addWidget(self.adcs_control_widget, 1)  # stretch factor 1 for ADCS controls
        
        parent_layout.addLayout(row3)

##########################################################################################
#info panel
#########################################################################################
   
    def setup_system_info_panel(self):
        """Setup right column system information panel"""
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(2, 2, 2, 2)
        info_container.setStyleSheet(f"background-color: {self.COLOR_BOX_BG_RIGHT};")

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

        # keep a handle to the container so we can walk its QGroupBoxes later
        self.info_container = info_container

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

            # Export each subsystem status group
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
            logging(f"[INFO] Health report exported to: {file_path}")

        except Exception as e:
            self.show_message(
                "Error",
                f"Failed to export health report:\n{e}",
                QMessageBox.Icon.Critical
            )
            logging(f"[ERROR] Health report export failed: {e}")

    def setup_subsystem_status_groups(self, parent_layout):
        """Setup all subsystem status monitoring groups"""
        # Initialize label dictionaries for live data updates
        self.power_labels = {}
        self.thermal_labels = {}
        self.comms_labels = {}
        self.adcs_labels = {}
        self.cdh_labels = {}
        self.error_labels = {}
        self.overall_labels = {}
        
        subsystems = [
            ("Power Subsystem", ["Current: Pending...", "Voltage: Pending...", "Power: Pending...", "Energy: Pending...", "Battery: Pending...", "Status: Pending..."]),
            ("Thermal Subsystem", ["Pi: Pending...", "Power PCB: Pending...", "Battery: Pending...", "Payload: Pending...", "Status: Pending..."]),
            ("Communication Subsystem", ["Downlink Frequency: Pending...", "Uplink Frequency: Pending...", "Server Signal: Pending...", "Client Signal: Pending...", "Data Transmission Rate: Pending...", "Latency: Pending...", "Status: Pending..."]),
            ("ADCS Subsystem", [
                "Gyro X: -- °/s", 
                "Gyro Y: -- °/s", 
                "Gyro Z: -- °/s",
                "Angle X: -- °", 
                "Angle Y: -- °", 
                "Angle Z: -- °",
                "Lux1: -- lux", 
                "Lux2: -- lux", 
                "Lux3: -- lux",
                "Status: Pending..."
            ]),
            ("Payload Subsystem", []),  # Special handling for payload
            ("Command & Data Handling Subsystem", ["CPU Usage: Pending...", "Memory Usage: Pending...", "Uptime: Pending...", "Status: Pending..."]),
            ("Error Log", ["No Critical Errors Detected: Pending..."]),
            ("Overall Status", ["No Anomalies Detected: Pending...", "Recommended Actions: Pending..."])
        ]

        for name, items in subsystems:
            group = QGroupBox(name)
            layout = QVBoxLayout()
            layout.setSpacing(2)
            layout.setContentsMargins(2, 2, 2, 2)

        for name, items in subsystems:
            group = QGroupBox(name)
            layout = QVBoxLayout()
            layout.setSpacing(2)
            layout.setContentsMargins(2, 2, 2, 2)

            if name == "Power Subsystem":
                # Store references to power labels for live updates
                for i, text in enumerate(items):
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    # Store label references to match your power.py data structure
                    if "Current:" in text:
                        self.power_labels["current"] = lbl
                    elif "Voltage:" in text:
                        self.power_labels["voltage"] = lbl
                    elif "Power:" in text:
                        self.power_labels["power"] = lbl
                    elif "Energy:" in text:
                        self.power_labels["energy"] = lbl
                    elif "Battery:" in text:
                        self.power_labels["battery"] = lbl
                    elif "Status:" in text:
                        self.power_labels["status"] = lbl
                        
            elif name == "Thermal Subsystem":
                # Store references to thermal labels for live updates
                for i, text in enumerate(items):
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    # Store label references for your new thermal labels
                    if "Pi:" in text:
                        self.thermal_labels["pi_temp"] = lbl
                    elif "Power PCB:" in text:
                        self.thermal_labels["power_pcb_temp"] = lbl
                    elif "Battery:" in text:
                        self.thermal_labels["battery_temp"] = lbl
                    elif "Payload:" in text:
                        self.thermal_labels["payload_temp"] = lbl
                    elif "Status:" in text:
                        self.thermal_labels["status"] = lbl
                        
            elif name == "ADCS Subsystem":
                # Store references to ADCS labels for live updates
                for i, text in enumerate(items):
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    # Store label references for the individual ADCS components
                    if "Gyro X:" in text:
                        self.adcs_labels["gyro_x"] = lbl
                    elif "Gyro Y:" in text:
                        self.adcs_labels["gyro_y"] = lbl
                    elif "Gyro Z:" in text:
                        self.adcs_labels["gyro_z"] = lbl
                    elif "Angle X:" in text:
                        self.adcs_labels["angle_x"] = lbl
                    elif "Angle Y:" in text:
                        self.adcs_labels["angle_y"] = lbl
                    elif "Angle Z:" in text:
                        self.adcs_labels["angle_z"] = lbl
                    elif "Lux1:" in text:
                        self.adcs_labels["lux1"] = lbl
                    elif "Lux2:" in text:
                        self.adcs_labels["lux2"] = lbl
                    elif "Lux3:" in text:
                        self.adcs_labels["lux3"] = lbl
                    elif "Status:" in text:
                        self.adcs_labels["status"] = lbl
                        
            elif name == "Command & Data Handling Subsystem":
                # Store references to CDH labels for live updates
                for i, text in enumerate(items):
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    # Store label references
                    if "CPU Usage" in text:
                        self.cdh_labels["cpu_usage"] = lbl
                    elif "Memory Usage" in text:
                        self.cdh_labels["memory"] = lbl
                    elif "Uptime" in text:
                        self.cdh_labels["uptime"] = lbl
                    elif "Status" in text:
                        self.cdh_labels["status"] = lbl
                        
            elif name == "Communication Subsystem":
                # Store references to communication labels for live updates
                for i, text in enumerate(items):
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    # Store label references for the new communication labels
                    if "Downlink Frequency:" in text:
                        self.comms_labels["downlink_frequency"] = lbl
                    elif "Uplink Frequency:" in text:
                        self.comms_labels["uplink_frequency"] = lbl
                    elif "Server Signal:" in text:
                        self.comms_labels["server_signal_strength"] = lbl
                    elif "Client Signal:" in text:
                        self.comms_labels["client_signal_strength"] = lbl
                    elif "Data Transmission Rate:" in text:
                        self.comms_labels["data_transmission_rate"] = lbl
                    elif "Latency:" in text:
                        self.comms_labels["latency"] = lbl
                    elif "Status:" in text:
                        self.comms_labels["status"] = lbl
            elif name == "Payload Subsystem":
                # Create payload subsystem labels with combined format
                self.payload_camera_label = QLabel("Camera: Checking...")
                self.payload_camera_label.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.payload_camera_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.payload_camera_label)
                
                self.payload_lidar_label = QLabel("Lidar: Checking...")
                self.payload_lidar_label.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.payload_lidar_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.payload_lidar_label)
                
                self.payload_status_label = QLabel("Status: Not Ready")
                self.payload_status_label.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                self.payload_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(self.payload_status_label)
                
                # Initialize payload status tracking variables
                self.camera_payload_status = "Error"  # Default to Error until we get actual status
                self.lidar_payload_status = "Error"   # Default to Error until we get actual status
            else:
                # Standard subsystem items (Error Log, Overall Status)
                for text in items:
                    lbl = QLabel(text)
                    lbl.setStyleSheet(f"QLabel {{ color: #bbb; margin: 2px 0px; padding: 2px 0px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}")
                    if name != "Error Log" and name != "Overall Status":
                        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    layout.addWidget(lbl)
                    
                    # Store references for Error Log and Overall Status
                    if name == "Error Log":
                        self.error_labels["critical_errors"] = lbl
                    elif name == "Overall Status":
                        if "Anomalies" in text:
                            self.overall_labels["anomalies"] = lbl
                        elif "Recommended" in text:
                            self.overall_labels["recommendations"] = lbl

            group.setLayout(layout)
            self.apply_groupbox_style(
                group,
                self.COLOR_BOX_BORDER_RIGHT,
                self.COLOR_BOX_BG_RIGHT,
                self.COLOR_BOX_TITLE_RIGHT,
                is_part_of_right_column=True # Explicitly flag as right column item
            )
            parent_layout.addWidget(group)

#'########################################################################################

    def update_image(self, frame):
        """Update video display with new frame"""
        try:
            # Only display raw frames if detector is NOT active
            if self.detector_active:
                # Just add to queue, don't display
                if self.frame_queue.qsize() < 5:
                    self.frame_queue.put(frame.copy())
                return
                    # Apply crosshairs AFTER all processing, just before display
            display_frame = frame.copy()
            if self.show_crosshairs:
                display_frame = self.draw_crosshairs(display_frame)
        
            # Display raw frame when detector is off
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(display_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            
            # Scale to fit display
            scaled = q_image.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled)
            self.video_label.setPixmap(pixmap)
                
            # ── patch ──
            self.display_frame_counter += 1
        except Exception as e:
            logging.error(f"Failed to update image: {e}")

    def update_analysed_image(self, frame):
        """Update video display with analyzed frame"""
        try:
            # Only display analyzed frames when detector is active
            if not self.detector_active:
                return

              # Apply crosshairs AFTER all processing, just before display
            display_frame = frame.copy()
            if self.show_crosshairs:
                display_frame = self.draw_crosshairs(display_frame)
            

            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(display_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            
            # Scale to fit display
            scaled = q_image.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled)
            self.video_label.setPixmap(pixmap)
            self.display_frame_counter += 1
        except Exception as e:
            logging.error(f"Failed to update analyzed image: {e}")

    #=========================================================================
    #                          SOCKET COMMUNICATION                          
    #=========================================================================

    def setup_socket_events(self):
        """Configure all socket event handlers"""
        
        @sio.event
        def connect():
            logging.info("Connected to server")
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
            logging.info(f"Disconnected from server: {reason}")
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
            # If you want to display server FPS, move it to a subsystem or widget
            # (removed info_labels["fps_server"])
        # ...existing code...
        @sio.on("camera_payload_broadcast")
        def on_camera_payload_broadcast(data):
            """Handle camera payload status updates from server"""
            try:
                # Server sends: {"camera_status": "Streaming", "camera_connected": true, "camera_streaming": true, "fps": 30, "frame_size": 1024, "status": "OK"}
                camera_status = data.get("camera_status", "Unknown")
                fps = data.get("fps", 0)
                
                # Store the OK/Error status for overall status computation
                self.camera_payload_status = data.get("status", "Error")
                
                # Update payload subsystem labels with combined format
                if hasattr(self, "payload_camera_label"):
                    if camera_status.lower() == "streaming" and fps > 0:
                        self.payload_camera_label.setText(f"Camera: {camera_status} - {fps:.1f} FPS")
                    else:
                        self.payload_camera_label.setText(f"Camera: {camera_status}")
                
                # Update overall payload status based on camera status
                self.update_payload_overall_status()
                
            except Exception as e:
                logging.error(f"Failed to process camera_payload_broadcast: {e}")


        @sio.on("image_captured")
        def on_image_captured(data):
            self.handle_image_capture_response(data)

        @sio.on("image_download")
        def on_image_download(data):
            self.handle_image_download(data)

        @sio.on("lidar_broadcast")
        def on_lidar_broadcast(data):
            """Handles incoming LIDAR data from the server on 'lidar_broadcast'."""
            try:
                if isinstance(data, dict):
                    processed_data = {}
                    # Check if the server is sending the new detailed format
                    if "live_distance_cm" in data:
                        processed_data["live_distance_cm"] = data.get("live_distance_cm")
                        processed_data["average_distance_cm_5s"] = data.get("average_distance_cm_5s") # Will be None if not present
                    # Else, check if the server is sending the simple format {'distance_cm': ...}
                    elif "distance_cm" in data:
                        processed_data["live_distance_cm"] = data.get("distance_cm")
                        # Since server only sent live distance, average is not available from this message
                        processed_data["average_distance_cm_5s"] = None
                    else:
                        # Data is a dictionary, but doesn't contain expected keys
                        logging.warning(f"Received LIDAR data on 'lidar_broadcast' with unrecognized keys: {data}")
                        return # Stop processing if format is unknown

                    # Ensure we have at least live_distance_cm to proceed
                    if "live_distance_cm" not in processed_data or processed_data["live_distance_cm"] is None:
                        logging.warning(f"Could not extract a valid live_distance_cm from LIDAR data: {data}")
                        return

                    if hasattr(self, 'lidar_widget') and self.lidar_widget:
                        self.lidar_widget.set_metrics(processed_data)
                    else:
                        # This case should ideally not happen if lidar_widget is initialized
                        logging.warning("LidarWidget instance not found when trying to set metrics.")
                else:
                    # Data received is not a dictionary
                    logging.warning(f"Received LIDAR data on 'lidar_broadcast' that was not a dictionary: {data}")
            except Exception as e:
                logging.error(f"Failed to process LIDAR data from 'lidar_broadcast': {e}")
                import traceback
                traceback.print_exc()

        @sio.on("lidar_payload_broadcast")
        def on_lidar_payload_broadcast(data):
            """Handle lidar payload status updates from server"""
            try:
                # Server sends: {"lidar_status": "Active", "lidar_connected": true, "lidar_collecting": true, "collection_rate_hz": 10, "status": "OK"}
                lidar_status = data.get("lidar_status", "Unknown")
                collection_rate_hz = data.get("collection_rate_hz", 0)
                
                # Store the OK/Error status for overall status computation
                self.lidar_payload_status = data.get("status", "Error")
                
                # Update payload subsystem labels with combined format
                if hasattr(self, "payload_lidar_label"):
                    if lidar_status.lower() == "active" and collection_rate_hz > 0:
                        self.payload_lidar_label.setText(f"Lidar: {lidar_status} - {collection_rate_hz:.1f} Hz")
                    else:
                        self.payload_lidar_label.setText(f"Lidar: {lidar_status}")
                
                # Update overall payload status based on lidar status
                self.update_payload_overall_status()
                
            except Exception as e:
                logging.error(f"Failed to process lidar_payload_broadcast: {e}")

        @sio.on("adcs_broadcast")
        def on_adcs_data(data):
            """Handle ADCS subsystem data updates"""
            try:
                if hasattr(self, 'adcs_labels'):
                    # Update individual gyroscope rates (X, Y, Z in °/s)
                    if "gyro_x" in self.adcs_labels:
                        gyro_x = data.get('gyro_rate_x', '--')
                        self.adcs_labels["gyro_x"].setText(f"Gyro X: {gyro_x} °/s")
                    if "gyro_y" in self.adcs_labels:
                        gyro_y = data.get('gyro_rate_y', '--')
                        self.adcs_labels["gyro_y"].setText(f"Gyro Y: {gyro_y} °/s")
                    if "gyro_z" in self.adcs_labels:
                        gyro_z = data.get('gyro_rate_z', '--')
                        self.adcs_labels["gyro_z"].setText(f"Gyro Z: {gyro_z} °/s")
                    
                    # Update individual orientation angles (X, Y, Z in degrees)
                    if "angle_x" in self.adcs_labels:
                        angle_x = data.get('angle_x', '--')
                        self.adcs_labels["angle_x"].setText(f"Angle X: {angle_x} °")
                    if "angle_y" in self.adcs_labels:
                        angle_y = data.get('angle_y', '--')
                        self.adcs_labels["angle_y"].setText(f"Angle Y: {angle_y} °")
                    if "angle_z" in self.adcs_labels:
                        angle_z = data.get('angle_z', '--')
                        self.adcs_labels["angle_z"].setText(f"Angle Z: {angle_z} °")
                    
                    # Update individual sun sensors (Lux1, Lux2, Lux3 in lux)
                    if "lux1" in self.adcs_labels:
                        lux1 = data.get('lux1', '--')
                        self.adcs_labels["lux1"].setText(f"Lux1: {lux1} lux")
                    if "lux2" in self.adcs_labels:
                        lux2 = data.get('lux2', '--')
                        self.adcs_labels["lux2"].setText(f"Lux2: {lux2} lux")
                    if "lux3" in self.adcs_labels:
                        lux3 = data.get('lux3', '--')
                        self.adcs_labels["lux3"].setText(f"Lux3: {lux3} lux")
                    
                    # Update status
                    if "status" in self.adcs_labels:
                        status = data.get('status', 'Unknown')
                        self.adcs_labels["status"].setText(f"Status: {status}")
                
                # Forward complete ADCS data to ADCS widget for detailed display
                if hasattr(self, 'adcs_control_widget') and self.adcs_control_widget:
                    # Pass all the detailed MPU and Lux sensor data
                    adcs_detailed_data = {
                        # MPU6050 gyro rates (deg/s)
                        'gyro_rate_x': data.get('gyro_rate_x', '0.00'),
                        'gyro_rate_y': data.get('gyro_rate_y', '0.00'), 
                        'gyro_rate_z': data.get('gyro_rate_z', '0.00'),
                        
                        # MPU6050 angle positions (degrees)
                        'angle_x': data.get('angle_x', '0.0'),
                        'angle_y': data.get('angle_y', '0.0'),
                        'angle_z': data.get('angle_z', '0.0'),
                        
                        # MPU6050 temperature
                        'temperature': data.get('temperature', '0.0°C'),
                        
                        # VEML7700 lux sensors
                        'lux1': data.get('lux1', '0.0'),
                        'lux2': data.get('lux2', '0.0'),
                        'lux3': data.get('lux3', '0.0'),
                        
                        # Motor/Control data
                        'rpm': data.get('rpm', '0.0'),
                        'status': data.get('status', 'Unknown'),
                        
                        # Legacy fields for backward compatibility
                        'gyro': data.get('gyro', '0.0°'),
                        'orientation': data.get('orientation', 'Y:0.0° R:0.0° P:0.0°')
                    }
                    
                    # Update ADCS widget with detailed sensor data
                    if hasattr(self.adcs_control_widget, 'update_sensor_data'):
                        self.adcs_control_widget.update_sensor_data(adcs_detailed_data)
                
                # Update payload temperature in thermal subsystem from ADCS temperature data
                if hasattr(self, 'thermal_labels') and 'payload_temp' in self.thermal_labels:
                    temperature_str = data.get('temperature', '0.0°C')
                    # Extract numeric value from temperature string (e.g., "25.5°C" -> 25.5)
                    try:
                        if '°C' in temperature_str:
                            temp_value = float(temperature_str.replace('°C', ''))
                            self.thermal_labels["payload_temp"].setText(f"Payload: {temp_value:.1f}°C")
                        else:
                            # If no °C suffix, try to parse as float
                            temp_value = float(temperature_str)
                            self.thermal_labels["payload_temp"].setText(f"Payload: {temp_value:.1f}°C")
                    except (ValueError, TypeError):
                        self.thermal_labels["payload_temp"].setText(f"Payload: {temperature_str}")
                
            except Exception as e:
                logging.error(f"Failed to update ADCS data: {e}")

        @sio.on("power_broadcast")
        def on_power_data(data):
            """Handle power subsystem data updates with smart status"""
            try:
                if hasattr(self, 'power_labels'):
                    # Server sends formatted data like: 
                    # {"current": "0.123", "voltage": "5.0", "power": "0.62", "energy": "0.01", 
                    #  "temperature": "25.5", "battery_percentage": 75, "status": "Nominal"}
                    
                    # Handle disconnected state
                    if data.get("status") == "Disconnected":
                        self.power_labels["current"].setText("Current: -- A")
                        self.power_labels["voltage"].setText("Voltage: -- V") 
                        self.power_labels["power"].setText("Power: -- W")
                        self.power_labels["energy"].setText("Energy: -- Wh")
                        self.power_labels["battery"].setText("Battery: --%")
                        self.power_labels["status"].setText("Status: Disconnected")
                        self.power_labels["status"].setStyleSheet(
                            f"QLabel {{ color: #666666; margin: 2px 0px; padding: 2px 0px; "
                            f"font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}"
                        )
                        return
                    
                    # Handle normal data updates
                    if "current" in data:
                        self.power_labels["current"].setText(f"Current: {data['current']} A")
                    if "voltage" in data:
                        self.power_labels["voltage"].setText(f"Voltage: {data['voltage']} V")
                    if "power" in data:
                        self.power_labels["power"].setText(f"Power: {data['power']} W")
                    if "energy" in data:
                        self.power_labels["energy"].setText(f"Energy: {data['energy']} Wh")
                    if "battery_percentage" in data:
                        battery_pct = data['battery_percentage']
                        self.power_labels["battery"].setText(f"Battery: {battery_pct}%")
                    
                    # Handle power PCB temperature from power broadcast and update thermal subsystem
                    if "temperature" in data and hasattr(self, 'thermal_labels') and 'power_pcb_temp' in self.thermal_labels:
                        self.thermal_labels["power_pcb_temp"].setText(f"Power PCB: {data['temperature']}°C")
                    
                    # Update status with appropriate color coding
                    if "status" in data:
                        status = data['status']
                        # Apply color coding based on status
                        if status in ["Battery Critical", "Current Critical", "Overheating"]:
                            status_color = "#ff4444"  # Red for critical
                        elif status in ["Battery Low", "High Current", "High Power", "High Temperature"]:
                            status_color = "#ffaa00"  # Orange for warnings
                        elif status == "Disconnected":
                            status_color = "#666666"  # Gray for disconnected
                        else:  # Nominal, OK
                            status_color = "#00ff00"  # Green for normal
                        
                        self.power_labels["status"].setText(f"Status: {status}")
                        self.power_labels["status"].setStyleSheet(
                            f"QLabel {{ color: {status_color}; margin: 2px 0px; padding: 2px 0px; "
                            f"font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}"
                        )
            except Exception as e:
                logging.error(f"Failed to update power data: {e}")

        @sio.on("thermal_broadcast")
        def on_thermal_data(data):
            """Handle thermal subsystem data updates"""
            try:
                if hasattr(self, 'thermal_labels'):
                    # Server now sends only battery_temp and computed status
                    # Other temperatures come from their respective broadcasts
                    
                    # Update battery temperature if available
                    if "battery_temp" in data and data["battery_temp"] is not None:
                        self.thermal_labels["battery_temp"].setText(f"Battery: {data['battery_temp']:.1f}°C")
                    elif "battery_temp" in data and data["battery_temp"] is None:
                        self.thermal_labels["battery_temp"].setText("Battery: N/A")
                    
                    # Update overall thermal status (computed on server using all available temperatures)
                    if "status" in data:
                        status = data["status"]
                        
                        # Apply color coding based on status
                        if status == "Critical":
                            status_color = "#ff4444"  # Red
                        elif status == "Warning":
                            status_color = "#ffaa00"  # Orange
                        elif status == "Elevated":
                            status_color = "#ffcc00"  # Yellow
                        elif status == "Warm":
                            status_color = "#88ff88"  # Light green
                        elif status == "Normal":
                            status_color = "#00ff00"  # Green
                        elif status == "NoData":
                            status_color = "#666666"  # Gray
                        else:  # Error or unknown
                            status_color = "#ff4444"  # Red
                        
                        self.thermal_labels["status"].setText(f"Status: {status}")
                        self.thermal_labels["status"].setStyleSheet(
                            f"QLabel {{ color: {status_color}; margin: 2px 0px; padding: 2px 0px; "
                            f"font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}"
                        )
                        
            except Exception as e:
                logging.error(f"Failed to update thermal data: {e}")

        @sio.on("communication_broadcast")
        def on_communication_data(data):
            """Handle communication subsystem data updates"""
            try:
                # Server sends: {"downlink_frequency": 0.0, "data_transmission_rate": 0.0, 
                # "server_signal_strength": 0, "latency": 0.0, "status": "Disconnected"}
                
                # Update communication labels
                if hasattr(self, 'comms_labels'):
                    # Update downlink frequency
                    if 'downlink_frequency' in self.comms_labels:
                        freq = data.get('downlink_frequency', 0.0)
                        self.comms_labels['downlink_frequency'].setText(f"Downlink Frequency: {freq:.3f} GHz")
                    
                    # Update server signal strength (from server data)
                    if 'server_signal_strength' in self.comms_labels:
                        signal = data.get('server_signal_strength', 0)
                        self.comms_labels['server_signal_strength'].setText(f"Server Signal: {signal} dBm")
                    
                    # Update data transmission rate
                    if 'data_transmission_rate' in self.comms_labels:
                        rate = data.get('data_transmission_rate', 0.0)
                        self.comms_labels['data_transmission_rate'].setText(f"Data Transmission Rate: {rate:.1f} KB/s")
                    
                    # Update latency
                    if 'latency' in self.comms_labels:
                        latency = data.get('latency', 0.0)
                        self.comms_labels['latency'].setText(f"Latency: {latency:.1f} ms")
                    
                    # Update status with color coding
                    if 'status' in self.comms_labels:
                        status = data.get('status', 'Unknown')
                        # Apply color coding based on status
                        if status == "Disconnected":
                            status_color = "#666666"  # Gray for disconnected
                        elif status == "Poor Connection":
                            status_color = "#ff4444"  # Red for poor
                        elif status == "Fair Connection":
                            status_color = "#ffaa00"  # Orange for fair
                        elif status == "Excellent":
                            status_color = "#00ff00"  # Green for excellent
                        else:  # Good
                            status_color = "#88ff88"  # Light green for good
                        
                        self.comms_labels['status'].setText(f"Status: {status}")
                        self.comms_labels['status'].setStyleSheet(
                            f"QLabel {{ color: {status_color}; margin: 2px 0px; padding: 2px 0px; "
                            f"font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt; }}"
                        )
                        
            except Exception as e:
                logging.error(f"Failed to update communication data: {e}")

        @sio.on("throughput_test")
        def on_throughput_test(data):
            """Handle throughput test request from server and echo data back"""
            try:
                # Record when client received the data
                client_receive_time = time.time()
                
                # Extract test data from server
                test_data = data.get('test_data', b'')
                test_size = data.get('size', 0)
                
                # Send latency measurement first
                sio.emit('latency_response', {
                    'client_receive_time': client_receive_time
                })
                
                # Then echo the data back to server for throughput measurement
                sio.emit('throughput_response', {
                    'response_data': test_data,
                    'size': test_size,
                    'timestamp': time.time()
                })
                
            except Exception as e:
                logging.error(f"Failed to handle throughput test: {e}")

        @sio.on("tachometer_broadcast")
        def on_tachometer_data(data):
            """Handle tachometer data updates"""
            try:
                # Update RPM in ADCS subsystem if available
                if hasattr(self, 'adcs_labels') and "rpm" in self.adcs_labels:
                    rpm = data.get('rpm', 0)
                    self.adcs_labels["rpm"].setText(f"RPM: {rpm:.1f}")
            except Exception as e:
                logging.error(f"Failed to update tachometer data: {e}")

        @sio.on("cdh_broadcast")
        def on_cdh_data(data):
            """Handle Command & Data Handling subsystem data updates"""
            try:
                if hasattr(self, 'cdh_labels'):
                    if "memory_usage" in data:
                        self.cdh_labels["memory"].setText(f"Memory Usage: {data['memory_usage']:.1f}%")
                    if "uptime" in data:
                        self.cdh_labels["uptime"].setText(f"Uptime: {data['uptime']}")
                    if "status" in data:
                        self.cdh_labels["status"].setText(f"Status: {data['status']}")
            except Exception as e:
                logging.error(f"Failed to update CDH data: {e}")
                
    def handle_adcs_command(self, mode_name, command_name, value):
        data = {
            "mode":    mode_name,
            "command": command_name,
            "value":   value
        }
        sio.emit("adcs_command", data)
        print(f"[CLIENT] ADCS command sent: {data}")

    def start_lidar_streaming(self):
        """Start LIDAR data streaming from server"""
        if sio.connected:
            logging.info("Requesting LIDAR streaming start")
            sio.emit("start_lidar")
        else:
            logging.warning("Cannot start LIDAR - not connected to server")

    def stop_lidar_streaming(self):
        """Stop LIDAR data streaming from server"""
        if sio.connected:
            logging.info("Requesting LIDAR streaming stop")
            sio.emit("stop_lidar")
        else:
            logging.warning("Cannot stop LIDAR - not connected to server")

    def delayed_server_setup(self):
        """Called shortly after connect—override if needed."""
        # Initialize payload status on startup
        self.update_payload_overall_status()

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
                logging.warning("Frame decode failed")
        except Exception as e:
            logging.error(f"Frame processing error: {e}")

    def update_sensor_display(self, data):
        """Update sensor information display"""
        try:
            # Handle thermal subsystem data (Pi temperature)
            if hasattr(self, 'thermal_labels') and 'pi_temp' in self.thermal_labels:
                temp = data.get("temperature")
                if temp is not None:
                    self.thermal_labels["pi_temp"].setText(f"Pi: {temp:.1f}°C")
                else:
                    self.thermal_labels["pi_temp"].setText("Pi: N/A")
            
            # Handle CDH subsystem data (CPU, memory, uptime, status)
            if hasattr(self, 'cdh_labels'):
                # CPU Usage
                if 'cpu_usage' in self.cdh_labels:
                    cpu = data.get("cpu_percent")
                    if cpu is not None:
                        self.cdh_labels["cpu_usage"].setText(f"CPU Usage: {cpu:.1f}%")
                    else:
                        self.cdh_labels["cpu_usage"].setText("CPU Usage: N/A")
                
                # Memory Usage (now just percentage)
                if 'memory' in self.cdh_labels:
                    memory_percent = data.get("memory_percent")
                    if memory_percent is not None:
                        self.cdh_labels["memory"].setText(f"Memory Usage: {memory_percent:.1f}%")
                    else:
                        self.cdh_labels["memory"].setText("Memory Usage: N/A")
                
                # Uptime
                if 'uptime' in self.cdh_labels:
                    uptime = data.get("uptime")
                    if uptime:
                        self.cdh_labels["uptime"].setText(f"Uptime: {uptime}")
                    else:
                        self.cdh_labels["uptime"].setText("Uptime: N/A")
                
                # System Status
                if 'status' in self.cdh_labels:
                    status = data.get("status")
                    if status:
                        self.cdh_labels["status"].setText(f"Status: {status}")
                    else:
                        self.cdh_labels["status"].setText("Status: Unknown")
                
        except Exception as e:
            logging.error(f"Failed to update sensor display: {e}")

    def update_client_communication_metrics(self):
        """Update client-side communication metrics (uplink frequency and signal strength)"""
        try:
            # Update uplink frequency and client signal strength
            if platform.system() == "Windows":
                # For Windows - use netsh wlan show interfaces
                try:
                    result = subprocess.run(
                        ['netsh', 'wlan', 'show', 'interfaces'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        output = result.stdout
                        for line in output.split('\n'):
                            line = line.strip()
                            # Extract signal strength (e.g., "Signal: 85%")
                            if 'Signal' in line and '%' in line:
                                try:
                                    signal_percent = int(line.split(':')[1].strip().rstrip('%'))
                                    # Convert percentage to dBm approximation (-30 to -90 dBm range)
                                    self.client_signal_strength = -30 - (100 - signal_percent) * 0.6
                                except (ValueError, IndexError):
                                    self.client_signal_strength = 0
                            # Extract frequency/channel info
                            elif 'Channel' in line:
                                try:
                                    channel_info = line.split(':')[1].strip()
                                    # Extract channel number if available
                                    if any(char.isdigit() for char in channel_info):
                                        channel_num = int(''.join(filter(str.isdigit, channel_info.split()[0])))
                                        # Convert channel to frequency (rough approximation)
                                        if channel_num <= 14:  # 2.4 GHz channels
                                            self.client_uplink_frequency = 2.4 + (channel_num - 1) * 0.005
                                        else:  # 5 GHz channels
                                            self.client_uplink_frequency = 5.0 + (channel_num - 36) * 0.005
                                except (ValueError, IndexError):
                                    self.client_uplink_frequency = 2.4  # Default to 2.4 GHz
                except subprocess.TimeoutExpired:
                    logging.warning("Client communication metrics timeout on Windows")
                except Exception as e:
                    logging.error(f"Windows client metrics error: {e}")
                    
            elif platform.system() == "Linux":
                # For Linux - use iwconfig
                try:
                    result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        output = result.stdout
                        for line in output.split('\n'):
                            # Extract signal strength (e.g., "Signal level=-45 dBm")
                            if 'Signal level' in line:
                                try:
                                    parts = line.split('Signal level=')
                                    if len(parts) > 1:
                                        signal_str = parts[1].split()[0]
                                        self.client_signal_strength = int(signal_str)
                                except (ValueError, IndexError):
                                    self.client_signal_strength = 0
                            # Extract frequency (e.g., "Frequency:2.437 GHz")
                            elif 'Frequency:' in line:
                                try:
                                    parts = line.split('Frequency:')
                                    if len(parts) > 1:
                                        freq_str = parts[1].split()[0]
                                        self.client_uplink_frequency = float(freq_str)
                                except (ValueError, IndexError):
                                    self.client_uplink_frequency = 0.0
                except subprocess.TimeoutExpired:
                    logging.warning("Client communication metrics timeout on Linux")
                except Exception as e:
                    logging.error(f"Linux client metrics error: {e}")
            else:
                # Default values for other systems
                self.client_uplink_frequency = 2.4
                self.client_signal_strength = -50
                
            # Update UI labels if they exist
            if hasattr(self, 'comms_labels'):
                if 'uplink_frequency' in self.comms_labels:
                    self.comms_labels['uplink_frequency'].setText(f"Uplink Frequency: {self.client_uplink_frequency:.3f} GHz")
                if 'client_signal_strength' in self.comms_labels:
                    self.comms_labels['client_signal_strength'].setText(f"Client Signal: {self.client_signal_strength:.0f} dBm")
                    
        except Exception as e:
            logging.error(f"Client communication metrics update error: {e}")
            # Set default values on error
            self.client_uplink_frequency = 0.0
            self.client_signal_strength = 0

    def update_payload_overall_status(self):
        """Update the overall payload subsystem status based on camera and lidar OK/Error states"""
        try:
            if not hasattr(self, "payload_status_label"):
                return
                
            # Get camera and lidar status from the stored OK/Error status values
            camera_status = getattr(self, "camera_payload_status", "Error")
            lidar_status = getattr(self, "lidar_payload_status", "Error")
            
            # Determine overall status: OK only if both are OK, otherwise Error
            if camera_status == "OK" and lidar_status == "OK":
                overall_status = "OK"
            else:
                overall_status = "Error"
            
            self.payload_status_label.setText(f"Status: {overall_status}")
            
        except Exception as e:
            logging.error(f"Payload status update error: {e}")

    # Removed update_camera_status and all legacy payload status update logic
                
        except Exception as e:
            logging.error(f"Camera status update error: {e}")

    def handle_image_capture_response(self, data):
        """Handle server response to image capture request"""
        try:
            if data["success"]:
                logging.info(f"Image captured: {data['path']} ({data['size_mb']} MB)")
                self.download_captured_image(data['path'])
            else:
                logging.error(f"Image capture failed: {data['error']}")
        except Exception as e:
            logging.error(f"Failed to handle capture response: {e}")

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
                
                logging.info(f"Image saved: {local_path} ({data['size']/1024:.1f} KB)")
            else:
                logging.error(f"Image download failed: {data['error']}")
                
        except Exception as e:
            logging.error(f"Failed to save downloaded image: {e}")

    #=========================================================================
    #                        CAMERA AND DETECTION                           
    #=========================================================================

    def toggle_stream(self):
        """Toggle video stream on/off"""
        if not sio.connected:
            return
        self.streaming = not self.streaming
        sio.emit("start_camera" if self.streaming else "stop_camera")

    def apply_config(self):
        """Apply camera configuration changes"""
        logging.info("Apply config pressed. Initiating 0.5s pause for stream and graph before sending config.")
        
        # Capture current streaming state for this specific call
        was_streaming_for_this_call = self.streaming

        # 1. Pause stream immediately if active
        if was_streaming_for_this_call:
            if self.streaming: # Double check, as state might change
                sio.emit("stop_camera")
                self.streaming = False
                # Removed: self.camera_controls.toggle_btn.setText("Start Stream")
                logging.info("Stream paused for config application.")


        # 2. Initiate graph pause immediately
        self.calibration_change_time = time.time()
        # Keep the existing 1-second timer for resuming graphs.
        QTimer.singleShot(1000, self.resume_after_calibration_change)

        # 3. Schedule the actual config sending and detector update after 0.5 seconds
        # Pass the captured streaming state as an argument
        QTimer.singleShot(500, lambda: self._execute_config_application_after_pause(was_streaming_for_this_call))

    def _execute_config_application_after_pause(self, was_streaming_at_call_time):
        """Helper method to get/send config and update detector after the initial 0.5s pause."""
        logging.info(f"0.5s pause complete. Getting/sending configuration (stream was {was_streaming_at_call_time}).")
        
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
                    # Removed: self.camera_controls.toggle_btn.setText("Stop Stream")
                    logging.info("Stream restart scheduled (if it was on before apply_config).")

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
                    logging.info(f"Detector calibration updated: {calibration_path}")
                    # Verify the calibration was actually loaded
                    if hasattr(detector4.detector_instance, 'mtx'):
                        cy = detector4.detector_instance.mtx[1, 2] if detector4.detector_instance.mtx is not None else "None"
                else:
                    logging.info(f"[WARNING] ❌ Failed to update detector calibration")
            else:
                logging.info(f"[WARNING] Detector instance not available for calibration update")
            
        except Exception as e:
            logging.info(f"[ERROR] Calibration update failed: {e}")

    def toggle_detector(self):
        """Toggle object detection on/off"""
        self.detector_active = not self.detector_active

        if self.detector_active:
            logging.info("[INFO] 🚀 Starting detector...")
            threading.Thread(target=self.run_detector, daemon=True).start()
        else:
            logging.info("[INFO] 🛑 Stopping detector...")
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
                    logging.info(f"[ERROR] Failed to load image: {image_path}")
                    self._full_lbl.setText("Failed to load image")
                    self._full_lbl.setStyleSheet(f"background-color: black; color: {TEXT_COLOR}; font-size: 24pt;")
                    self._full_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self._full_lbl.show()
            else:
                logging.info(f"[ERROR] Image file not found: {image_path}")
                self._full_lbl.setText("Image file not found")
                self._full_lbl.setStyleSheet(f"background-color: black; color: {TEXT_COLOR}; font-size: 24pt;")
                self._full_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._full_lbl.show()
            
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
            
            logging.info("[INFO] Full image view activated")
            
        except Exception as e:
            logging.info(f"[ERROR] Failed to show full image: {e}")
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
            
            logging.info("[INFO] Returned to normal view")
            
        except Exception as e:
            logging.info(f"[ERROR] Failed to hide full image: {e}")
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
                        logging.info(f"[WARNING] Invalid crop_factor: {crop_factor}")
                        original_height = current_height 
                
                # Process frame with detector
                try:
                    latency_ms = 0.0  # Default value
                    pose = None       # Default value
                    analysed = frame  # Default to original frame if detection fails early

                    if hasattr(detector4, 'detector_instance') and detector4.detector_instance:
                        analysed, pose, latency_ms = detector4.detector_instance.detect_and_draw(
                            frame,
                            return_pose=True,
                            is_cropped=is_cropped,
                            original_height=original_height
                        )
                    else:
                        # This branch is taken if detector_instance is None or not found.
                        # The global detector4.detect_and_draw will then also find detector_instance to be None
                        # and likely return 2 values: (frame, None).
                        # If detector4.detect_and_draw's return is inconsistent (sometimes 2, sometimes 3 values in this path),
                        # this unpacking needs to be more robust or the global function made consistent.
                        # Assuming 2-value return if hasattr(detector4, 'detector_instance') is false:
                        _result = detector4.detect_and_draw(frame, return_pose=True)
                        if isinstance(_result, tuple) and len(_result) == 2:
                            analysed, pose = _result
                            # latency_ms remains 0.0 as it's not provided by a 2-value return
                        elif isinstance(_result, tuple) and len(_result) == 3: # Handle unexpected 3-value return
                            analysed, pose, latency_ms = _result
                            logging.info("[WARNING] detector4.detect_and_draw returned 3 values in an unexpected path.")
                        else: # Fallback if return is not as expected
                            analysed = frame 
                            pose = None
                            logging.info("[ERROR] Unexpected return type/length from detector4.detect_and_draw in else branch.")
                    self.latencyUpdated.emit(latency_ms)
                    bridge.analysed_frame.emit(analysed)

                    # 1) always update all calculators
                    # Apply your recommended safe check structure here
                    if pose is not None and isinstance(pose, (list, tuple)) and len(pose) == 2:
                        rvec, tvec = pose
                        # Further check rvec and tvec for robustness
                        if (rvec is not None and isinstance(rvec, np.ndarray) and rvec.size > 0 and
                            tvec is not None and isinstance(tvec, np.ndarray) and tvec.size > 0):
                            
                            # All clear to use rvec and tvec
                            self.spin_plotter.update(rvec, tvec) # Pass only rvec, timestamp will default to time.time()
                            self.distance_plotter.update(rvec, tvec)
                            self.angular_plotter.update(rvec, tvec)

                            # 2) update the three small live‐value labels WITH UNITS
                            self.graph_section.live_labels["SPIN MODE"]             \
                                .setText(f"{self.spin_plotter.current_angle:.0f}°")  # Added degree symbol
                            self.graph_section.live_labels["DISTANCE MEASURING MODE"] \
                                .setText(f"{self.distance_plotter.current_distance:.3f}m")  # Added meter unit
                            self.graph_section.live_labels["SCANNING MODE"]         \
                                .setText(f"{self.angular_plotter.current_ang:.1f}°")  # Added degree symbol

                            # 2b) update the big "detail" label for the active graph WITH UNITS
                            detail = getattr(self.graph_section, "current_detail_label", None)
                            mode   = getattr(self.graph_section, "current_graph_mode", None)
                            if detail and mode:
                                if mode == "SPIN MODE":
                                    metrics = self.spin_plotter.get_spin_metrics()
                                    detail.setText(
                                        f"Live: {metrics['current']:.0f}°\n"
                                        f"Avg:  {metrics['average']:.0f}°\n"
                                    )
                                elif mode == "DISTANCE MEASURING MODE":
                                    metrics = self.distance_plotter.get_distance_metrics()
                                    detail.setText(
                                        f"Live: {metrics['current']:.3f}m\n"
                                        f"Avg:  {metrics['average']:.3f}m\n"
                                        f"Live: {metrics['current_velocity']:.3f}m/s\n"
                                        f"Avg:  {metrics['average_velocity']:.3f}m/s"
                                    )
                                else:  # SCANNING MODE (RelativeAnglePlotter)
                                    metrics = self.angular_plotter.get_angle_metrics()
                                    detail.setText(
                                        f"Live: {metrics['current']:.1f}°\n"
                                        f"Avg:  {metrics['average']:.1f}°\n"
                                    )

                                # ── if we're recording, grab that same label value ─────────────────
                                if self.graph_section.is_recording:
                                    ts = time.time()
                                    val = None
                                    try:
                                        if mode == "SPIN MODE":
                                            val = self.spin_plotter.current_angle
                                        elif mode == "DISTANCE MEASURING MODE":
                                            # Assuming you want to record the live distance.
                                            # If you want to record velocity, use self.distance_plotter.current_velocity
                                            val = self.distance_plotter.current_distance
                                        elif mode == "SCANNING MODE": # RelativeAnglePlotter
                                            val = self.angular_plotter.current_ang
                                        
                                        if val is not None:
                                            self.graph_section.add_data_point(ts, float(val))
                                        else:
                                            logging.info(f"[WARNING] No value to record for mode: {mode}")
                                            
                                    except AttributeError as e:
                                        logging.info(f"[ERROR] Could not get value for recording from plotter: {e}")
                                    except ValueError as e:
                                        logging.info(f"[ERROR] Value from plotter could not be converted to float for recording: {val}, Error: {e}")
                                    except Exception as e:
                                        logging.info(f"[ERROR] Unexpected error during data preparation for recording: {e}")
                
                            # 3) continue with your throttled redraw / recording logic…
                            if self.should_update_graphs() and self.graph_section.graph_widget:
                                # Call update on the active graph_widget with appropriate arguments
                                current_mode = self.graph_section.current_graph_mode
                                if current_mode == "SPIN MODE":
                                    # AngularPositionPlotter.update(self, rvec, timestamp=None)
                                    # We want to use the default timestamping within the plotter
                                    self.graph_section.graph_widget.update(rvec, tvec) 
                                elif current_mode == "DISTANCE MEASURING MODE":
                                    # RelativeDistancePlotter.update(self, rvec, tvec, timestamp=None)
                                    self.graph_section.graph_widget.update(rvec, tvec)
                                elif current_mode == "SCANNING MODE":
                                    # RelativeAnglePlotter.update(self, rvec, tvec, timestamp=None)
                                    self.graph_section.graph_widget.update(rvec, tvec)
                                else:
                                    logging.info(f"[WARNING] Unknown graph mode for update: {current_mode}")
                                # … recording code …
                        else:
                            # This case means pose was a 2-element tuple, but rvec/tvec were invalid
                            if rvec is None or not isinstance(rvec, np.ndarray) or not rvec.size > 0:
                                logging.info(f"[WARNING] rvec is invalid after unpacking. Type: {type(rvec)}, Value: {rvec}")
                            if tvec is None or not isinstance(tvec, np.ndarray) or not tvec.size > 0:
                                logging.info(f"[WARNING] tvec is invalid after unpacking. Type: {type(tvec)}, Value: {tvec}")
                    elif pose is not None: # pose was not None, but not a 2-element tuple
                        logging.info(f"[WARNING] Pose is not None but has unexpected structure: {type(pose)}, value: {pose}")
                    # If pose is None, normal operation (no detection), calculations are skipped.

                except Exception as e:
                    logging.info(f"[ERROR] Detector processing error: {e}")
                    import traceback
                    traceback.print_exc() # Add traceback for better debugging
            except queue.Empty:
                continue
            except Exception as e:
                logging.info(f"[ERROR] Detector thread error: {e}")

    def should_update_graphs(self):
        """Check if graphs should be updated (not during calibration pause)"""
        if hasattr(self, 'calibration_change_time'):
            time_since_change = time.time() - self.calibration_change_time
            return time_since_change >= 1.0
        return True

    def capture_image(self):
        """Request image capture from server"""
        if not sio.connected:
            logging.info("[WARNING] Cannot capture image - not connected to server")
            return
        
        try:
            sio.emit("capture_image", {})
            logging.info("[INFO] 📸 Image capture requested")
        except Exception as e:
            logging.info(f"[ERROR] Failed to request image capture: {e}")

    def download_captured_image(self, server_path):
        """Download captured image from server"""
        try:
            filename = os.path.basename(server_path)
            sio.emit("download_image", {"server_path": server_path, "filename": filename})
        except Exception as e:
            logging.info(f"[ERROR] Failed to request image download: {e}")

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

    def timerEvent(self, event):
        """Handle timer events for FPS calculation"""
        # live FPS (incoming)
        self.current_fps = self.frame_counter
        self.frame_counter = 0

        # display FPS
        self.current_display_fps   = self.display_frame_counter
        self.display_frame_counter = 0

        # Update display FPS in detector widget
        if hasattr(self, 'detector_settings') and self.detector_settings:
            self.detector_settings.set_display_fps(self.current_display_fps)
            
    #=========================================================================
    #                          UTILITY METHODS                              
    #=========================================================================

    def handle_adcs_command(self, mode_name, command_name, value):
        data = {
            "mode": mode_name,
            "command": command_name,
            "value": value
        }
        sio.emit("adcs_command", data)
        print(f"[CLIENT] ADCS command sent: {data}")

    def try_reconnect(self):
        """Attempt to reconnect to server"""
        threading.Thread(target=self.reconnect_socket, daemon=True).start()

    def reconnect_socket(self):
        """Handle socket reconnection logic"""
        was_streaming = self.streaming
        try:
            if was_streaming: # if it was streaming, stop it first
                self.streaming = False
                # Removed: self.camera_controls.toggle_btn.setText("Start Stream")
                sio.emit("stop_camera")
                time.sleep(0.5) # give server time to process
            sio.disconnect()
        except Exception as e: # Catch specific socketio errors if possible, or general Exception
            logging.error(f"Error during disconnect phase of reconnect: {e}")
            # pass # Or log the error
        
        try:
            logging.info(f"Attempting to reconnect to {SERVER_URL}...")
            sio.connect(SERVER_URL, wait_timeout=5)
            # If connect is successful, connect() handler should be called by socketio
            # which in turn calls self.apply_config()
            # self.apply_config() # This might be redundant if 'connect' event handler does it.
                                # However, if 'connect' handler isn't reliably called or if
                                # apply_config needs to happen immediately after this specific reconnect, keep it.
            
            if was_streaming: # if it was streaming before, restart it
                # Add a small delay to ensure server is ready after (re)connection and config
                QTimer.singleShot(500, self._restart_stream_after_reconnect)
                
        except socketio.exceptions.ConnectionError as e:
            logging.error(f"Reconnect failed: ConnectionError - {e}")
        except Exception as e:
            logging.exception(f"Reconnect failed with an unexpected error: {e}")

    def _restart_stream_after_reconnect(self):
        """Helper to restart stream after a delay, ensuring it's still desired."""
        if self.streaming == False and hasattr(self, 'camera_controls'): # Check if it wasn't already restarted and if UI is available
            # Check if the original intent was to stream (was_streaming was true)
            # This requires was_streaming to be accessible, e.g. by making it an instance var if needed,
            # or by always attempting to restart if self.streaming is false here.
            # For simplicity, assuming if self.streaming is false now, we try to restart.
            logging.info("Restarting stream after reconnect...")
            sio.emit("start_camera")
            self.streaming = True # Update state
            # Removed: self.camera_controls.toggle_btn.setText("Stop Stream")
        elif self.streaming:
            logging.info("Stream already running after reconnect or restart not needed.")

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
            logging.info("[INFO] Closing application...")
            
            # Remove QtLogHandler from logging FIRST to prevent RuntimeError at exit
            if hasattr(self, 'qt_log_handler') and self.qt_log_handler is not None:
                logging.getLogger().removeHandler(self.qt_log_handler)
                self.qt_log_handler.close() # Good practice, though base Handler.close() is no-op
                self.qt_log_handler = None # Clear reference
            
            if self.detector_active:
               
                self.detector_active = False
    
            self.reset_camera_to_default() # This might log
            time.sleep(0.5)
    
            if self.streaming:
                sio.emit("stop_camera") # This might log
                self.streaming = False
                # Removed: if hasattr(self, 'camera_controls'): self.camera_controls.toggle_btn.setText("Start Stream")
                time.sleep(0.5)
    
            sio.emit("set_camera_idle") # This might log
            time.sleep(0.5)
    
            if sio.connected:
                sio.disconnect() # This might log
                time.sleep(0.2)
            
        except Exception as e:
            logging.info(f"[DEBUG] Cleanup error during closeEvent: {e}")
            traceback.print_exc() # Add traceback for more details on cleanup errors

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
    logging.info("=== Calibration Status ===")
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
                logging.info(f"OLD (Legacy) - {filename}")
            else:
                logging.info(f"{resolution[0]}x{resolution[1]} - {filename}")
            found += 1
        else:
            if resolution == "legacy":
                logging.info(f"❌ OLD (Legacy) - {filename} (MISSING)")
            else:
                               logging.info(f"❌ {resolution[0]}x{resolution[1]} - {filename} (MISSING)")
    
    logging.info(f"\nStatus: {found}/{total} calibrations available")
    
    if found == total:
        logging.info("🎉 All calibrations complete!")
    else:
        logging.info(f"⚠️  Missing {total - found} calibrations")

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
            logging.info(f"[INFO] Attempting to connect to {SERVER_URL}")
            sio.connect(SERVER_URL, wait_timeout=10)
            logging.info("[INFO] Successfully connected to server")
        except Exception as e:
            logging.info(f"[ERROR] Failed to connect to server: {e}")
    
    threading.Thread(target=connect_to_server, daemon=True).start()
    
    sys.exit(app.exec())