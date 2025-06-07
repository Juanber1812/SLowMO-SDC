##############################################################################
#                              SLowMO CLIENT                                #
#                         Satellite Control Interface                       #
##############################################################################

import sys, base64, socketio, cv2, numpy as np, logging, threading, time, queue, os # Ensure logging is imported
import pandas as pd
import traceback
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSlider, QGroupBox, QGridLayout, QMessageBox, QSizePolicy, QScrollArea,
    QTabWidget, QFileDialog, QTextEdit # <<< Added QTextEdit here
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
    level=logging.INFO, # You can set the desired default level here
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

# logging.basicConfig(filename='client_log.txt', level=logging.DEBUG) # <<< This line is redundant if the above config is used.
SERVER_URL = "http://192.168.1.146:5000"

##############################################################################
#                        SOCKETIO AND BRIDGE SETUP                         #
##############################################################################

sio = socketio.Client()

# <<< Step 2: Define QtLogHandler >>>
class QtLogHandler(logging.Handler, QObject):
    """
    Custom logging handler that emits a signal for each log record.
    """
    new_log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        logging.Handler.__init__(self)
        QObject.__init__(self, parent)
        # Set a default formatter, can be customized
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        if record:
            msg = self.format(record)
            self.new_log_message.emit(msg)

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    analysed_frame = pyqtSignal(np.ndarray)

bridge = Bridge()

##############################################################################
#                            MAIN WINDOW CLASS                              #
##############################################################################

class MainWindow(QWidget):
    # ... (your existing signals and theme configuration) ...
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
        self.show_crosshairs = False
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BACKGROUND};
                color: {TEXT_COLOR};
                font-family: {self.FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
        """)
        self.smooth_mode = None
        self.setWindowTitle("SLowMO Client")
        
        self.streaming = False
        self.detector_active = False
        self.frame_queue = queue.Queue()
        self.last_frame = None
        self.shared_start_time = None
        self.calibration_change_time = None

        self.last_frame_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        self.current_frame_size = 0

        self.display_frame_counter = 0
        self.current_display_fps   = 0
        
        self._last_graph_draw = 0.0
        self._graph_update_interval = 1.0 / 2.0 
        
        self.spin_plotter     = AngularPositionPlotter()
        self.distance_plotter = RelativeDistancePlotter()
        self.angular_plotter  = RelativeAnglePlotter()

        # <<< Step 3: Initialize Log Display and Handler >>>
        self.log_display_widget = QTextEdit()
        self.log_display_widget.setReadOnly(True)
        # Use theme variables for styling if available, otherwise fallbacks
        log_text_color = getattr(self, 'TEXT_COLOR', 'white')
        log_border_color = getattr(self, 'BORDER_COLOR', '#333333')
        log_font_family = getattr(self, 'FONT_FAMILY', 'Consolas, "Courier New", monospace')
        
        self.log_display_widget.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1A1A1A; 
                color: {log_text_color};
                font-family: {log_font_family};
                font-size: 9pt;
                border: 1px solid {log_border_color};
                border-radius: {getattr(self, 'BORDER_RADIUS', 3)}px;
            }}
        """)

        self.qt_log_handler = QtLogHandler(self) # Pass self as parent
        self.qt_log_handler.new_log_message.connect(self.append_log_message)
        logging.getLogger().addHandler(self.qt_log_handler)
        # Optional: Set a specific level for the GUI log handler if different from root
        # self.qt_log_handler.setLevel(logging.DEBUG)


        self.setup_ui() 

        if hasattr(self, 'graph_section') and self.graph_section:
            self.graph_section.graph_update_frequency_changed.connect(self.spin_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.distance_plotter.set_redraw_rate)
            self.graph_section.graph_update_frequency_changed.connect(self.angular_plotter.set_redraw_rate)
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

        if hasattr(self, 'camera_settings') and self.camera_settings is not None:
             self.active_config_for_detector = self.camera_settings.get_config()
        else:
             self.active_config_for_detector = None
             logging.warning("[MainWindow.__init__] camera_settings not available for initial active_config_for_detector.")

        self.setup_socket_events()
        self.setup_signals()
        self.setup_timers()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.graph_window = None

    # <<< Step 4: Add append_log_message method >>>
    # @pyqtSignal(str) # Decorator not strictly needed here as it's a direct connection
    def append_log_message(self, message: str):
        """Appends a message to the log display widget and auto-scrolls."""
        self.log_display_widget.append(message)
        scrollbar = self.log_display_widget.verticalScrollBar()
        if scrollbar: # Check if scrollbar exists
            scrollbar.setValue(scrollbar.maximum())

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
        """Setup graph display section, LIDAR section, and Log Display"""
        row2 = QHBoxLayout()
        row2.setSpacing(2) 
        row2.setContentsMargins(2, 2, 2, 2)
        row2.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Graph section
        self.record_btn = QPushButton("Record")
        self.duration_dropdown = QComboBox()
        self.duration_dropdown.setVisible(False)
        self.graph_section = GraphSection(self.record_btn, self.duration_dropdown)
        self.graph_section.setFixedSize(620, 280)
        self.graph_section.graph_display_layout.setSpacing(1)
        self.graph_section.graph_display_layout.setContentsMargins(1, 1, 1, 1)
        self.apply_groupbox_style(self.graph_section, self.COLOR_BOX_BORDER_GRAPH)
        row2.addWidget(self.graph_section)

        # LIDAR section
        self.lidar_widget = LidarWidget()
        self.lidar_widget.back_button_clicked.connect(self.handle_lidar_back_button)
        if hasattr(self.lidar_widget, 'lidar_start_requested'):
            self.lidar_widget.lidar_start_requested.connect(self.start_lidar_streaming)
        if hasattr(self.lidar_widget, 'lidar_stop_requested'):
            self.lidar_widget.lidar_stop_requested.connect(self.stop_lidar_streaming)
        self.lidar_widget.setFixedHeight(self.graph_section.height()) 
        self.lidar_widget.setFixedWidth(250) 
        # Note: LidarWidget is a QGroupBox, so apply_groupbox_style might be called within its __init__
        # or you can call it here if it's not styled internally and needs the standard group box look.
        # For now, assuming it handles its own title and basic group box styling.
        # If it needs the standard border/title from MainWindow's theme:
        # self.apply_groupbox_style(self.lidar_widget, self.COLOR_BOX_BORDER_LIDAR, bg_color=self.COLOR_BOX_BG_LIDAR, title_color=self.COLOR_BOX_TEXT_LIDAR)
        row2.addWidget(self.lidar_widget)
        
        # <<< Step 5: Add Log Display GroupBox to row2 >>>
        log_display_group = QGroupBox("Console Log")
        log_display_layout = QVBoxLayout() # Use a different name if 'log_display_layout' is used elsewhere
        log_display_layout.setContentsMargins(5, 5, 5, 5)
        log_display_layout.setSpacing(2)
        
        # self.log_display_widget was created in __init__
        log_display_layout.addWidget(self.log_display_widget)
        log_display_group.setLayout(log_display_layout)

        # Use theme variables for styling the log group box
        log_group_border_color = getattr(self, 'COLOR_BOX_BORDER_RIGHT', self.BORDER_COLOR)
        log_group_bg_color = getattr(self, 'COLOR_BOX_BG_RIGHT', self.BOX_BACKGROUND) # Or a specific log bg
        log_group_title_color = getattr(self, 'COLOR_BOX_TITLE_RIGHT', self.BOX_TITLE_COLOR)

        self.apply_groupbox_style(
            log_display_group, 
            log_group_border_color, 
            bg_color=log_group_bg_color, 
            title_color=log_group_title_color,
            is_part_of_right_column=True # Assuming it's styled like other right column items
        )
        log_display_group.setFixedHeight(self.graph_section.height()) # Match row height
        log_display_group.setFixedWidth(350) # Adjust width as needed, or use stretch factor

        row2.addWidget(log_display_group)
        # Optional: Add stretch factor if you want other widgets to take precedence in width
        # row2.setStretchFactor(self.graph_section, 2)
        # row2.setStretchFactor(self.lidar_widget, 1)
        # row2.setStretchFactor(log_display_group, 1)
        
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
            print(f"[ERROR] Failed to update image: {e}")

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
                        print(f"[WARNING] Received LIDAR data on 'lidar_broadcast' with unrecognized keys: {data}")
                        return # Stop processing if format is unknown

                    # Ensure we have at least live_distance_cm to proceed
                    if "live_distance_cm" not in processed_data or processed_data["live_distance_cm"] is None:
                        print(f"[WARNING] Could not extract a valid live_distance_cm from LIDAR data: {data}")
                        return

                    if hasattr(self, 'lidar_widget') and self.lidar_widget:
                        self.lidar_widget.set_metrics(processed_data)
                    else:
                        # This case should ideally not happen if lidar_widget is initialized
                        print("[WARNING] LidarWidget instance not found when trying to set metrics.")
                else:
                    # Data received is not a dictionary
                    print(f"[WARNING] Received LIDAR data on 'lidar_broadcast' that was not a dictionary: {data}")
            except Exception as e:
                print(f"[ERROR] Failed to process LIDAR data from 'lidar_broadcast': {e}")
                import traceback
                traceback.print_exc()

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
        else:
            print("[WARNING] Cannot start LIDAR - not connected to server")

    def stop_lidar_streaming(self):
        """Stop LIDAR data streaming from server"""
        if sio.connected:
            print("[INFO] Requesting LIDAR streaming stop")
            sio.emit("stop_lidar")
        else:
            print("[WARNING] Cannot stop LIDAR - not connected to server")

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
                            print("[WARNING] detector4.detect_and_draw returned 3 values in an unexpected path.")
                        else: # Fallback if return is not as expected
                            analysed = frame 
                            pose = None
                            print("[ERROR] Unexpected return type/length from detector4.detect_and_draw in else branch.")
                
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
                                    metrics = self.spin_plotter.get_spin_metrics()
                                    detail.setText(
                                        f"Live: {metrics['current']:.3f}°\n"
                                        f"Avg:  {metrics['average']:.3f}°\n"
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
                                        f"Live: {metrics['current']:.3f}°\n"
                                        f"Avg:  {metrics['average']:.3f}°\n"
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
                                            print(f"[WARNING] No value to record for mode: {mode}")
                                            
                                    except AttributeError as e:
                                        print(f"[ERROR] Could not get value for recording from plotter: {e}")
                                    except ValueError as e:
                                        print(f"[ERROR] Value from plotter could not be converted to float for recording: {val}, Error: {e}")
                                    except Exception as e:
                                        print(f"[ERROR] Unexpected error during data preparation for recording: {e}")
                
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
                                    print(f"[WARNING] Unknown graph mode for update: {current_mode}")
                                # … recording code …
                        else:
                            # This case means pose was a 2-element tuple, but rvec/tvec were invalid
                            if rvec is None or not isinstance(rvec, np.ndarray) or not rvec.size > 0:
                                print(f"[WARNING] rvec is invalid after unpacking. Type: {type(rvec)}, Value: {rvec}")
                            if tvec is None or not isinstance(tvec, np.ndarray) or not tvec.size > 0:
                                print(f"[WARNING] tvec is invalid after unpacking. Type: {type(tvec)}, Value: {tvec}")
                    elif pose is not None: # pose was not None, but not a 2-element tuple
                        print(f"[WARNING] Pose is not None but has unexpected structure: {type(pose)}, value: {pose}")
                    # If pose is None, normal operation (no detection), calculations are skipped.

                except Exception as e:
                    print(f"[ERROR] Detector processing error: {e}")
                    import traceback
                    traceback.print_exc() # Add traceback for better debugging
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
            if was_streaming: # if it was streaming, stop it first
                self.streaming = False
                self.camera_controls.toggle_btn.setText("Start Stream")
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
            logging.info("Restarting stream after reconnect...")
            sio.emit("start_camera")
            self.streaming = True # Update state
            self.camera_controls.toggle_btn.setText("Stop Stream")
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
