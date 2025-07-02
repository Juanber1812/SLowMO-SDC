# filepath: c:\Users\juanb\OneDrive\Documents\GitHub\SLowMO-SDC-juan\SLowMO-SDC\client-server2\client\widgets\adcs.py
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QSizePolicy, QButtonGroup, QGridLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
import logging

# --- THEME AND STYLE CONFIGURATION ---


# --- THEME AND STYLE CONFIGURATION ---
try:
    from theme import (
        BUTTON_TEXT, BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED,
        BORDER_RADIUS, BORDER_WIDTH, FONT_FAMILY, FONT_SIZE_NORMAL, TEXT_COLOR, BORDER_COLOR, BOX_BACKGROUND, BOX_TITLE_COLOR,
        PLOT_LINE_PRIMARY, BACKGROUND
    )
    ADCS_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: 2px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 6px 12px;
            min-height: 24px;
            font-size: {FONT_SIZE_NORMAL}pt;
            font-family: {FONT_FAMILY};
        }}
        QPushButton:hover, QPushButton:pressed {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:checked {{
            background-color: {PLOT_LINE_PRIMARY};
            color: black;
        }}
        QPushButton:checked:hover {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
            border: 0px solid #555;
        }}
    """
    ADCS_LABEL_STYLE = f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;"
    ADCS_GROUPBOX_STYLE = f"""
        QGroupBox {{
            border: 0px solid {BORDER_COLOR};
            border-radius: 4px;
            background-color: {BACKGROUND};
            margin-top: 6px;
            color: {BOX_TITLE_COLOR};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 6px;
            padding: 0 2px;
            font-size: {FONT_SIZE_NORMAL}pt;
            font-family: {FONT_FAMILY};
            color: {BOX_TITLE_COLOR};
        }}
    """
except (ImportError, NameError):
    print("[ADCSSection] Warning: Theme file not found or missing variables. Using fallback styles.")
    ADCS_BUTTON_STYLE = """
        QPushButton {
            background-color: #444444; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px;
        }
        QPushButton:hover { background-color: #555555; }
        QPushButton:checked {
            background-color: #00ff88;
            color: black;
        }
        QPushButton:checked:hover {
            background-color: #00dd77;
            color: black;
        }
        QPushButton:disabled { 
            background-color: #444444; color: white; border: 1px solid #555555;
        }
    """
    ADCS_LABEL_STYLE = "color: white; font-size: 10pt;"
    ADCS_GROUPBOX_STYLE = ""

# --- MAIN ADCS WIDGET ---

class ADCSSection(QGroupBox):
    adcs_command_sent = pyqtSignal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ADCSSection")
        self.setFixedSize(850,240)
        self.current_auto_mode = "adcs" # Default auto mode
        # Apply groupbox style to self
        if 'ADCS_GROUPBOX_STYLE' in globals() and ADCS_GROUPBOX_STYLE:
            self.setStyleSheet(ADCS_GROUPBOX_STYLE)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left Column: Mode Selection & Manual Control ---
        left_column = QVBoxLayout()
        left_column.addWidget(self._create_mode_selection_group())
        left_column.addWidget(self._create_manual_controls_group())
        main_layout.addLayout(left_column, 1)

        # --- Right Column: Automatic Control & Parameters ---
        right_column = QVBoxLayout()
        right_column.addWidget(self._create_auto_controls_group())
        right_column.addWidget(self._create_pd_tuning_group())
        main_layout.addLayout(right_column, 2)

    def _create_mode_selection_group(self):
        group = QGroupBox()
        if 'ADCS_GROUPBOX_STYLE' in globals() and ADCS_GROUPBOX_STYLE:
            group.setStyleSheet(ADCS_GROUPBOX_STYLE)
        layout = QHBoxLayout()
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)

        self.raw_btn = QPushButton("Raw")
        self.raw_btn.setCheckable(True)
        self.raw_btn.setChecked(True)
        self.raw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.raw_btn)
        self.mode_button_group.addButton(self.raw_btn)

        self.env_btn = QPushButton("Environmental")
        self.env_btn.setCheckable(True)
        self.env_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.env_btn)
        self.mode_button_group.addButton(self.env_btn)

        self.apriltag_btn = QPushButton("AprilTag")
        self.apriltag_btn.setCheckable(True)
        self.apriltag_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.apriltag_btn)
        self.mode_button_group.addButton(self.apriltag_btn)
        
        group.setLayout(layout)
        return group

    def get_target_yaw(self):
        """Return the current target yaw as a float (from the input box)."""
        try:
            return float(self.value_input.text())
        except Exception:
            return 0.0

    def _create_manual_controls_group(self):
        group = QGroupBox()
        if 'ADCS_GROUPBOX_STYLE' in globals() and ADCS_GROUPBOX_STYLE:
            group.setStyleSheet(ADCS_GROUPBOX_STYLE)
        layout = QVBoxLayout()
        
        cw_ccw_layout = QHBoxLayout()
        # --- Switch order: CCW first (left), CW second (right) ---
        self.manual_ccw_btn = QPushButton("Rotate CCW")
        self.manual_ccw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        # Make buttons 20% smaller in height
        self.manual_ccw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_ccw_btn.setMinimumHeight(int(0.8 * 24))
        cw_ccw_layout.addWidget(self.manual_ccw_btn)
        self.manual_cw_btn = QPushButton("Rotate CW")
        self.manual_cw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_cw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_cw_btn.setMinimumHeight(int(0.8 * 24))
        cw_ccw_layout.addWidget(self.manual_cw_btn)
        layout.addLayout(cw_ccw_layout)

        self.calibrate_btn = QPushButton("Calibrate Sensors")
        self.calibrate_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.calibrate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.calibrate_btn.setMinimumHeight(int(0.8 * 24))
        layout.addWidget(self.calibrate_btn)

        # --- Manual Calibrate Yaw ---
        manual_cal_layout = QHBoxLayout()
        self.manual_cal_input = QLineEdit("0.0")
        self.manual_cal_input.setPlaceholderText("Yaw Offset (deg)")
        self.manual_cal_input.setFixedWidth(80)
        manual_cal_layout.addWidget(self.manual_cal_input)
        self.manual_cal_btn = QPushButton("Manual Calibrate Yaw")
        self.manual_cal_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_cal_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_cal_btn.setMinimumHeight(int(0.8 * 24))
        manual_cal_layout.addWidget(self.manual_cal_btn)
        layout.addLayout(manual_cal_layout)
        # --- End Manual Calibrate Yaw ---

        group.setLayout(layout)
        return group

    def _create_auto_controls_group(self):
        group = QGroupBox()
        if 'ADCS_GROUPBOX_STYLE' in globals() and ADCS_GROUPBOX_STYLE:
            group.setStyleSheet(ADCS_GROUPBOX_STYLE)
        layout = QGridLayout()

        layout.addWidget(QLabel("Target Angle:"), 0, 0)
        self.value_input = QLineEdit("0.0")
        layout.addWidget(self.value_input, 0, 1)
        self.set_value_btn = QPushButton("Set Target")
        self.set_value_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_value_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.set_value_btn, 0, 2)

        self.run_controller_btn = QPushButton("Start Controller")
        self.run_controller_btn.setCheckable(True)
        self.run_controller_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.run_controller_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.run_controller_btn, 1, 0, 1, 2)

        self.set_zero_btn = QPushButton("Zero Yaw Position")
        self.set_zero_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_zero_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.set_zero_btn, 1, 2)

        group.setLayout(layout)
        return group

    def _create_pd_tuning_group(self):
        group = QGroupBox()
        if 'ADCS_GROUPBOX_STYLE' in globals() and ADCS_GROUPBOX_STYLE:
            group.setStyleSheet(ADCS_GROUPBOX_STYLE)
        layout = QGridLayout()

        # Row 0
        layout.addWidget(QLabel("Kp:"), 0, 0)
        self.kp_input = QLineEdit("0.5")
        layout.addWidget(self.kp_input, 0, 1)
        layout.addWidget(QLabel("Kd:"), 0, 2)
        self.kd_input = QLineEdit("0.1")
        layout.addWidget(self.kd_input, 0, 3)
        
        # Row 1
        layout.addWidget(QLabel("Deadband:"), 1, 0)
        self.deadband_input = QLineEdit("1.0")
        layout.addWidget(self.deadband_input, 1, 1)
        layout.addWidget(QLabel("Min Pulse:"), 1, 2)
        self.min_pulse_input = QLineEdit("0.1")
        layout.addWidget(self.min_pulse_input, 1, 3)
        
        # Row 2
        self.set_pd_btn = QPushButton("Set Gains")
        self.set_pd_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_pd_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.set_pd_btn, 0, 4, 2, 1)

        group.setLayout(layout)
        return group

    def _connect_signals(self):
        # Mode selection
        self.raw_btn.clicked.connect(lambda: self._update_current_auto_mode("adcs"))
        self.env_btn.clicked.connect(self._handle_env_mode_selected)
        self.apriltag_btn.clicked.connect(self._handle_apriltag_mode_selected)

        # Manual controls
        self.manual_cw_btn.pressed.connect(lambda: self._handle_action_clicked("adcs", "manual_clockwise_start"))
        self.manual_cw_btn.released.connect(lambda: self._handle_action_clicked("adcs", "manual_stop"))
        self.manual_ccw_btn.pressed.connect(lambda: self._handle_action_clicked("adcs", "manual_counterclockwise_start"))
        self.manual_ccw_btn.released.connect(lambda: self._handle_action_clicked("adcs", "manual_stop"))
        self.calibrate_btn.clicked.connect(lambda: self._handle_action_clicked("adcs", "calibrate"))
        self.manual_cal_btn.clicked.connect(self._handle_manual_cal_clicked)

        # Auto controls
        self.run_controller_btn.clicked.connect(self._handle_run_controller_clicked)
        self.set_zero_btn.clicked.connect(self._handle_set_zero_clicked)
        self.set_value_btn.clicked.connect(self._handle_set_value_clicked)
        self.set_pd_btn.clicked.connect(self._handle_set_pd_clicked)

    def _update_current_auto_mode(self, mode_name):
        prev_mode = getattr(self, "current_auto_mode", "adcs")
        self.current_auto_mode = mode_name
        logging.info(f"[ADCSSection] Auto mode set to: {mode_name}")

        # Stop auto zero if switching away from AprilTag or Environmental
        if prev_mode == "AprilTag" and mode_name != "AprilTag":
            self._handle_action_clicked("adcs", "stop_auto_zero_tag")
        elif prev_mode == "Environmental" and mode_name != "Environmental":
            self._handle_action_clicked("adcs", "stop_auto_zero_lux")

        # If switching to raw, enable both buttons
        if mode_name == "adcs":
            self.set_zero_btn.setDisabled(False)
            self.set_value_btn.setDisabled(False)

    def _handle_run_controller_clicked(self):
        if self.run_controller_btn.isChecked():
            self.run_controller_btn.setText("Stop Controller")
            self._handle_action_clicked(self.current_auto_mode, "start")
        else:
            self.run_controller_btn.setText("Start Controller")
            self._handle_action_clicked(self.current_auto_mode, "stop")

    def _handle_set_pd_clicked(self):
        try:
            pd_values = {
                "kp": float(self.kp_input.text()),
                "kd": float(self.kd_input.text()),
                "deadband": float(self.deadband_input.text()),
                "min_pulse": float(self.min_pulse_input.text())
            }
            self._handle_action_clicked(self.current_auto_mode, "set_pd_values", pd_values)
        except ValueError:
            logging.warning("Invalid PD values entered.")

    def _handle_set_value_clicked(self):
        try:
            value = float(self.value_input.text())
            self._handle_action_clicked(self.current_auto_mode, "set_value", value)
        except ValueError:
            logging.warning(f"Invalid target value: {self.value_input.text()}")

    def _handle_set_zero_clicked(self):
        self._handle_action_clicked(self.current_auto_mode, "set_zero")

    def _handle_action_clicked(self, mode, command, value=None):
        logging.info(f"Sending ADCS command: Mode='{mode}', Command='{command}', Value={value}")
        self.adcs_command_sent.emit(mode, command, value)

    def update_adcs_data(self, data):
        if 'controller' in data:
            controller_data = data['controller']
            self.kp_input.setText(str(controller_data.get('kp', '')))
            self.kd_input.setText(str(controller_data.get('kd', '')))
            self.deadband_input.setText(str(controller_data.get('deadband', '')))
            self.value_input.setText(str(controller_data.get('target_yaw', '')))
            self.min_pulse_input.setText(str(controller_data.get('min_pulse', '')))

    def _handle_env_mode_selected(self):
        self._update_current_auto_mode("adcs")  # Keep mode as adcs
        self._handle_action_clicked("adcs", "auto_zero_lux")
        # Disable only set_zero_btn, enable set_value_btn
        self.set_zero_btn.setDisabled(True)
        self.set_value_btn.setDisabled(False)

    def _handle_apriltag_mode_selected(self):
        self._update_current_auto_mode("adcs")  # Keep mode as adcs
        self._handle_action_clicked("adcs", "auto_zero_tag")
        # Disable both set_zero_btn and set_value_btn
        self.set_zero_btn.setDisabled(True)
        self.set_value_btn.setDisabled(True)

    def _handle_manual_cal_clicked(self):
        try:
            value = float(self.manual_cal_input.text())
            self._handle_action_clicked("adcs", "manual_cal", value)
        except ValueError:
            logging.warning(f"Invalid manual cal value: {self.manual_cal_input.text()}")