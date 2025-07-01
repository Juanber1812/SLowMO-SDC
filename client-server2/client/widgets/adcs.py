from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
import logging
# Initialize with fallback styles in case import fails
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
        background-color: #444444; /* Fallback normal background for disabled */
        color: white; /* Fallback normal text for disabled */
        border: 1px solid #555555; /* Fallback normal border for disabled */
        border-radius: 3px; 
        padding: 5px;
    }
"""
ADCS_BUTTON_HEIGHT = 30
ADCS_LABEL_STYLE = "color: white; font-size: 10pt;"

try:
    # Attempt to import style constants directly from theme.py
    from theme import (
        BUTTON_TEXT,
        BUTTON_COLOR,
        BUTTON_HOVER,
        BORDER_RADIUS,
        BORDER_WIDTH,
        FONT_FAMILY,
        FONT_SIZE_NORMAL,
        BUTTON_HEIGHT as THEME_BUTTON_HEIGHT, # Keep alias if original BUTTON_HEIGHT is different type or for clarity
        TEXT_COLOR,
        BORDER_COLOR
        # Not importing BUTTON_DISABLED, BUTTON_DISABLED_TEXT, BUTTON_DISABLED_BORDER
        # as the disabled state will now use normal button colors.
    )

    # Construct styles dynamically if import was successful
    ADCS_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BUTTON_COLOR};
            color: {BUTTON_TEXT};
            border: {BORDER_WIDTH}px solid {BORDER_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 6px 12px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QPushButton:hover {{
            background-color: {BUTTON_HOVER};
            color: {BUTTON_TEXT};
        }}
        QPushButton:checked {{
            background-color: #00ff88;
            color: black;
        }}
        QPushButton:checked:hover {{
            background-color: #00dd77;
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_COLOR}; /* Use normal button background */
            color: {BUTTON_TEXT}; /* Use normal button text color */
            border: {BORDER_WIDTH}px solid {BORDER_COLOR}; /* Use normal button border */
            border-radius: {BORDER_RADIUS}px;
            padding: 6px 12px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
    """
    # Using THEME_BUTTON_HEIGHT alias for clarity as it's cast to int
    ADCS_BUTTON_HEIGHT = int(THEME_BUTTON_HEIGHT) if THEME_BUTTON_HEIGHT is not None else 30
    ADCS_LABEL_STYLE = f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;"

except ImportError as e:
    print(f"[ADCSSection] Detailed Import Error (using 'from theme import ...'): {e}")
    print("[ADCSSection] Warning: Theme file or specific ADCS style constants not found. Using fallback styles.")

# Fallback theme variables if not imported (for QLineEdit styling example)
TEXT_COLOR = globals().get('TEXT_COLOR', 'white')
BORDER_COLOR = globals().get('BORDER_COLOR', '#555555')
BORDER_RADIUS = globals().get('BORDER_RADIUS', 3)
FONT_FAMILY = globals().get('FONT_FAMILY', 'Segoe UI')
FONT_SIZE_NORMAL = globals().get('FONT_SIZE_NORMAL', 10)
# ADCS_BUTTON_HEIGHT is already defined with a fallback

class ADCSSection(QGroupBox):
    """
    A QGroupBox widget to manage ADCS controls using a QStackedWidget
    for different views (mode selection and detail view).
    """
    # Define signals for mode selection and commands
    mode_selected = pyqtSignal(int, str)  # Emits mode_index, mode_name
    adcs_command_sent = pyqtSignal(str, str, object)  # Emits mode_name, command_name, value (can be None)

    def __init__(self, parent=None):
        super().__init__(parent)  # Removed "ADCS" title
        self.setObjectName("ADCSSection")
        
        # Set fixed size for the widget
        self.setFixedSize(650, 220)  # Width x Height

        self._main_layout = QHBoxLayout(self)  # Changed to horizontal layout
        self._main_layout.setSpacing(4)  # Reduced spacing between columns
        self._main_layout.setContentsMargins(2, 2, 2, 2)  # Reduced padding around the widget

        # Left column: Automatic controls with stacked widget
        self.auto_stacked_widget = QStackedWidget()
        
        # Page 0: Auto mode selection (Raw/Env/AprilTag)
        auto_selection_page = self._create_auto_selection_page()
        self.auto_stacked_widget.addWidget(auto_selection_page)
        
        # Page 1: Control page for Raw/Env/AprilTag (shared layout)
        control_page = self._create_control_page()
        self.auto_stacked_widget.addWidget(control_page)
        
        self.auto_stacked_widget.setCurrentIndex(0)
        
        # Right column: Manual controls (fixed)
        manual_column = self._create_manual_column()
        
        # Add columns to main layout
        self._main_layout.addWidget(self.auto_stacked_widget, 3)  # Auto column takes more space (3/4)
        self._main_layout.addWidget(manual_column, 1)  # Manual column takes less space (1/4)
        
        # Track current auto mode for control page
        self.current_auto_mode = None
        
        # Initialize current values (will be updated when server sends actual values)
        self.current_kp = 0.0
        self.current_kd = 0.0
        self.current_target = 0.0

    def _create_main_page(self):
        """Creates the main page with Manual/Auto buttons and Calibrate button."""
        page = QWidget()
        main_layout = QHBoxLayout(page)
        main_layout.setSpacing(0)  # Remove spacing to fill completely
        main_layout.setContentsMargins(0, 0, 0, 0)

        # First column: Manual and Auto buttons (2 rows)
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setSpacing(0)  # Remove spacing to fill completely
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.manual_btn = QPushButton("Manual")
        self.manual_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.manual_btn.clicked.connect(lambda: self._go_to_page(1))
        left_layout.addWidget(self.manual_btn)

        self.auto_btn = QPushButton("Auto")
        self.auto_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.auto_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.auto_btn.clicked.connect(lambda: self._go_to_page(2))
        left_layout.addWidget(self.auto_btn)

        # Second column: Calibrate button (1 row)
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setSpacing(0)  # Remove spacing to fill completely
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.calibrate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.calibrate_btn.clicked.connect(lambda: self._go_to_page(6))
        right_layout.addWidget(self.calibrate_btn)

        main_layout.addWidget(left_column)
        main_layout.addWidget(right_column)
        
        return page

    def _create_manual_page(self):
        """Creates the manual page with Clockwise/Anticlockwise buttons and Back button."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(0)  # Remove spacing to fill completely
        page_layout.setContentsMargins(0, 0, 0, 0)

        # First row: Clockwise and Anticlockwise buttons
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setSpacing(0)  # Remove spacing to fill completely
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.manual_cw_btn = QPushButton("Clockwise")
        self.manual_cw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_cw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.manual_cw_btn.pressed.connect(
            lambda: self._handle_action_clicked("Manual Orientation", "manual_clockwise_start", None)
        )
        self.manual_cw_btn.released.connect(
            lambda: self._handle_action_clicked("Manual Orientation", "manual_clockwise_stop", None)
        )
        button_layout.addWidget(self.manual_cw_btn)

        self.manual_ccw_btn = QPushButton("Anticlockwise")
        self.manual_ccw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_ccw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.manual_ccw_btn.pressed.connect(
            lambda: self._handle_action_clicked("Manual Orientation", "manual_anticlockwise_start", None)
        )
        self.manual_ccw_btn.released.connect(
            lambda: self._handle_action_clicked("Manual Orientation", "manual_anticlockwise_stop", None)
        )
        button_layout.addWidget(self.manual_ccw_btn)

        # Second row: Back button
        self.manual_back_btn = QPushButton("← Back")
        self.manual_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.manual_back_btn.clicked.connect(lambda: self._go_to_page(0))

        page_layout.addWidget(button_row)
        page_layout.addWidget(self.manual_back_btn)
        
        return page

    def _create_auto_selection_page(self):
        """Creates the auto selection page with Raw/Env/AprilTag buttons."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(2)  # Reduced spacing between buttons
        page_layout.setContentsMargins(2, 2, 2, 2)  # Reduced padding inside the page

        # Three buttons stacked vertically with increased height to fill space
        self.raw_btn = QPushButton("Raw")
        self.raw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.raw_btn.clicked.connect(lambda: self._show_control_page("Raw"))
        page_layout.addWidget(self.raw_btn)

        self.env_btn = QPushButton("Environmental")
        self.env_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.env_btn.clicked.connect(lambda: self._show_control_page("Environmental"))
        page_layout.addWidget(self.env_btn)

        self.apriltag_btn = QPushButton("AprilTag")
        self.apriltag_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.apriltag_btn.clicked.connect(lambda: self._show_control_page("AprilTag"))
        page_layout.addWidget(self.apriltag_btn)
        
        return page

    def _create_control_page(self):
        """Creates the shared control page for Raw/Env/AprilTag modes."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(1)  # Reduced spacing between controls
        page_layout.setContentsMargins(2, 2, 2, 2)  # Reduced padding inside the page

        # Title label to show current mode
        self.control_title_label = QLabel("Control Mode")
        self.control_title_label.setStyleSheet(ADCS_LABEL_STYLE)
        self.control_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.control_title_label.setFixedHeight(25)  # Reduced label height to occupy less vertical space
        page_layout.addWidget(self.control_title_label)

        # Run Controller and Set Zero buttons row
        controller_row = QWidget()
        controller_layout = QHBoxLayout(controller_row)
        controller_layout.setSpacing(2)  # Reduced spacing
        controller_layout.setContentsMargins(0, 0, 0, 0)

        self.run_controller_btn = QPushButton("Run Controller")  # Always show "Run Controller"
        self.run_controller_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.run_controller_btn.setFixedHeight(30)  # Same height as Set Value button
        self.run_controller_btn.setCheckable(True)  # Make it a toggle button
        self.run_controller_btn.clicked.connect(self._handle_run_controller_clicked)
        controller_layout.addWidget(self.run_controller_btn)

        self.set_zero_btn = QPushButton("Set Zero")
        self.set_zero_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_zero_btn.setFixedHeight(30)  # Fixed button height
        self.set_zero_btn.clicked.connect(self._handle_set_zero_clicked)
        controller_layout.addWidget(self.set_zero_btn)

        page_layout.addWidget(controller_row)

        # PD Tuning controls - all in one row
        pd_tuning_row = QWidget()
        pd_tuning_layout = QHBoxLayout(pd_tuning_row)
        pd_tuning_layout.setSpacing(2)  # Reduced spacing
        pd_tuning_layout.setContentsMargins(0, 0, 0, 0)
        
        kp_label = QLabel("Kp:")
        kp_label.setStyleSheet(ADCS_LABEL_STYLE)
        kp_label.setFixedWidth(25)  # Fixed label width
        pd_tuning_layout.addWidget(kp_label)
        
        self.kp_input = QLineEdit()
        self.kp_input.setPlaceholderText("Enter Kp")
        self.kp_input.setFixedHeight(25)  # Fixed input height
        pd_tuning_layout.addWidget(self.kp_input)
        
        kd_label = QLabel("Kd:")
        kd_label.setStyleSheet(ADCS_LABEL_STYLE)
        kd_label.setFixedWidth(25)  # Fixed label width
        pd_tuning_layout.addWidget(kd_label)
        
        self.kd_input = QLineEdit()
        self.kd_input.setPlaceholderText("Enter Kd")
        self.kd_input.setFixedHeight(25)  # Fixed input height
        pd_tuning_layout.addWidget(self.kd_input)

        # Add min_pulse_time
        min_pulse_label = QLabel("Min Pulse:")
        min_pulse_label.setStyleSheet(ADCS_LABEL_STYLE)
        min_pulse_label.setFixedWidth(60)
        pd_tuning_layout.addWidget(min_pulse_label)

        self.min_pulse_input = QLineEdit()
        self.min_pulse_input.setPlaceholderText("s")
        self.min_pulse_input.setFixedHeight(25)
        self.min_pulse_input.setFixedWidth(50)
        pd_tuning_layout.addWidget(self.min_pulse_input)

        # Add deadband
        deadband_label = QLabel("Deadband:")
        deadband_label.setStyleSheet(ADCS_LABEL_STYLE)
        deadband_label.setFixedWidth(60)
        pd_tuning_layout.addWidget(deadband_label)

        self.deadband_input = QLineEdit()
        self.deadband_input.setPlaceholderText("deg")
        self.deadband_input.setFixedHeight(25)
        self.deadband_input.setFixedWidth(50)
        pd_tuning_layout.addWidget(self.deadband_input)
        
        self.set_pd_btn = QPushButton("Set PD")
        self.set_pd_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_pd_btn.setFixedHeight(25)  # Fixed button height
        self.set_pd_btn.clicked.connect(self._handle_set_pd_clicked)
        pd_tuning_layout.addWidget(self.set_pd_btn)
        
        page_layout.addWidget(pd_tuning_row)

        # Set Value input and button row
        set_value_row = QWidget()
        set_value_layout = QHBoxLayout(set_value_row)
        set_value_layout.setSpacing(2)  # Reduced spacing between input and button
        set_value_layout.setContentsMargins(0, 0, 0, 0)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Enter value")
        self.value_input.setFixedHeight(25)  # Fixed input height
        set_value_layout.addWidget(self.value_input)

        self.set_value_btn = QPushButton("Set Target")
        self.set_value_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.set_value_btn.setFixedHeight(25)  # Fixed button height
        self.set_value_btn.clicked.connect(self._handle_set_value_clicked)
        set_value_layout.addWidget(self.set_value_btn)

        page_layout.addWidget(set_value_row)

        # Back button
        self.control_back_btn = QPushButton("← Back")
        self.control_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.control_back_btn.setFixedHeight(30)  # Fixed button height
        self.control_back_btn.clicked.connect(self._show_auto_selection)
        page_layout.addWidget(self.control_back_btn)
        
        return page

    def _create_manual_column(self):
        """Creates the manual control column with 4 fixed buttons."""
        column = QWidget()
        column.setMaximumWidth(120)  # Limit the width of the manual column
        column_layout = QVBoxLayout(column)
        column_layout.setSpacing(2)  # Reduced spacing between buttons
        column_layout.setContentsMargins(3, 3, 3, 3)  # Reduced padding inside the column

        # Clockwise button
        self.manual_cw_btn = QPushButton("CW")  # Shortened text
        self.manual_cw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_cw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_cw_btn.setMaximumWidth(100)  # Limit button width
        self.manual_cw_btn.pressed.connect(
            lambda: self._handle_action_clicked("Manual", "manual_clockwise_start", None)
        )
        self.manual_cw_btn.released.connect(
            lambda: self._handle_action_clicked("Manual", "manual_clockwise_stop", None)
        )
        column_layout.addWidget(self.manual_cw_btn)

        # Anticlockwise button
        self.manual_ccw_btn = QPushButton("CCW")  # Shortened text
        self.manual_ccw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.manual_ccw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.manual_ccw_btn.setMaximumWidth(100)  # Limit button width
        self.manual_ccw_btn.pressed.connect(
            lambda: self._handle_action_clicked("Manual", "manual_anticlockwise_start", None)
        )
        self.manual_ccw_btn.released.connect(
            lambda: self._handle_action_clicked("Manual", "manual_anticlockwise_stop", None)
        )
        column_layout.addWidget(self.manual_ccw_btn)

        # Enable Motor toggle button
        self.enable_motor_btn = QPushButton("Enable")  # Always show "Enable"
        self.enable_motor_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.enable_motor_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.enable_motor_btn.setMaximumWidth(100)  # Limit button width
        self.enable_motor_btn.setCheckable(True)  # Make it a toggle button
        self.enable_motor_btn.clicked.connect(self._handle_enable_motor_clicked)
        column_layout.addWidget(self.enable_motor_btn)

        # Calibrate button
        self.calibrate_btn = QPushButton("Cal")  # Shortened text
        self.calibrate_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.calibrate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.calibrate_btn.setMaximumWidth(100)  # Limit button width
        self.calibrate_btn.clicked.connect(
            lambda: self._handle_action_clicked("Manual", "calibrate", None)
        )
        column_layout.addWidget(self.calibrate_btn)
        
        return column

    def _show_control_page(self, mode_name):
        """Show the control page for the specified mode."""
        self.current_auto_mode = mode_name
        self.control_title_label.setText(f"{mode_name} Control")
        
        # Reset the run controller button state when switching modes
        self.run_controller_btn.setChecked(False)
        # Button text remains "Run Controller" - visual state is shown by checked/unchecked appearance
        
        self.auto_stacked_widget.setCurrentIndex(1)
        logging.info(f"[ADCSSection] Switched to {mode_name} control page")

    def _show_auto_selection(self):
        """Show the auto mode selection page."""
        self.auto_stacked_widget.setCurrentIndex(0)
        self.current_auto_mode = None
        logging.info("[ADCSSection] Switched to auto selection page")

    def _handle_run_controller_clicked(self):
        """Handle run controller toggle button click."""
        if self.current_auto_mode:
            if self.run_controller_btn.isChecked():
                # Button is now pressed/checked - start the controller
                # Text stays "Run Controller" - visual state is shown by checked appearance
                self._handle_action_clicked(self.current_auto_mode, "start", None)
            else:
                # Button is now unpressed/unchecked - stop the controller
                # Text stays "Run Controller" - visual state is shown by unchecked appearance
                self._handle_action_clicked(self.current_auto_mode, "stop", None)

    def _handle_enable_motor_clicked(self):
        """Handle enable motor toggle button click."""
        if self.enable_motor_btn.isChecked():
            # Button is now pressed/checked - enable motor
            # Text stays "Enable" - visual state is shown by checked appearance
            self._handle_action_clicked("Manual", "enable_motor", True)
        else:
            # Button is now unpressed/unchecked - disable motor
            # Text stays "Enable" - visual state is shown by unchecked appearance
            self._handle_action_clicked("Manual", "enable_motor", False)

    def _handle_start_clicked(self):
        """Handle start button click."""
        if self.current_auto_mode:
            self._handle_action_clicked(self.current_auto_mode, "start", None)

    def _handle_stop_clicked(self):
        """Handle stop button click."""
        if self.current_auto_mode:
            self._handle_action_clicked(self.current_auto_mode, "stop", None)

    def _handle_set_pd_clicked(self):
        """Handle set PD values button click."""
        if self.current_auto_mode:
            try:
                kp_value = float(self.kp_input.text() or 0)
                kd_value = float(self.kd_input.text() or 0)
                min_pulse = float(self.min_pulse_input.text() or 0)
                deadband = float(self.deadband_input.text() or 0)
                pd_values = {"kp": kp_value, "kd": kd_value, "min_pulse_time": min_pulse, "deadband": deadband}
                self._handle_action_clicked(self.current_auto_mode, "set_pd_values", pd_values)
                
                self.kp_input.clear()
                self.kd_input.clear()
                self.min_pulse_input.clear()
                self.deadband_input.clear()
            except ValueError:
                logging.warning(f"[ADCSSection] Invalid PD values: Kp={self.kp_input.text()}, Kd={self.kd_input.text()}, MinPulse={self.min_pulse_input.text()}, Deadband={self.deadband_input.text()}")
                # Select all text in both inputs for easy correction
                self.kp_input.selectAll()
                self.kd_input.selectAll()
                self.min_pulse_input.selectAll()
                self.deadband_input.selectAll()

    def _handle_pd_tuning_clicked(self):
        """Handle PD tuning button click."""
        if self.current_auto_mode:
            self._handle_action_clicked(self.current_auto_mode, "pd_tuning", None)

    def _handle_set_value_clicked(self):
        """Handle set value button click."""
        if self.current_auto_mode:
            try:
                value = float(self.value_input.text() or 0)
                self._handle_action_clicked(self.current_auto_mode, "set_value", value)
                
                self.value_input.clear()
            except ValueError:
                logging.warning(f"[ADCSSection] Invalid value: {self.value_input.text()}")
                self.value_input.selectAll()

    def _handle_set_zero_clicked(self):
        """Handle set zero button click."""
        if self.current_auto_mode:
            self._handle_action_clicked(self.current_auto_mode, "set_zero", None)

    def _handle_action_clicked(self, mode_name, command_name, value=None):
        """Handle action button clicks and emit signals."""
        logging.info(f"[ADCSSection] Action for mode '{mode_name}': Command '{command_name}', Value: {value}")
        self.adcs_command_sent.emit(mode_name, command_name, value)

    def populate_inputs_with_current_values(self, kp, kd, min_pulse, deadband, target):
        """Pre-fill input fields with current values for easy editing."""
        if hasattr(self, 'kp_input'):
            self.kp_input.setText(str(kp))
        
        if hasattr(self, 'kd_input'):
            self.kd_input.setText(str(kd))
        
        if hasattr(self, 'min_pulse_input'):
            self.min_pulse_input.setText(str(min_pulse))
        
        if hasattr(self, 'deadband_input'):
            self.deadband_input.setText(str(deadband))
        
        if hasattr(self, 'value_input'):
            self.value_input.setText(str(target))

    def update_sensor_data(self, data):
        """Update sensor data display by populating input fields with current values."""
        # Update input fields with current values from server
        if 'current_kp' in data or 'current_kd' in data or 'current_min_pulse_time' in data or 'current_deadband' in data or 'current_target' in data:
            kp = data.get('current_kp', 0.0)
            kd = data.get('current_kd', 0.0)
            min_pulse = data.get('current_min_pulse_time', 0.0)
            deadband = data.get('current_deadband', 0.0)
            target = data.get('current_target', 0.0)
            
            # Populate input fields with current values
            self.populate_inputs_with_current_values(kp, kd, min_pulse, deadband, target)

    # Deprecated methods - keeping for backward compatibility
    def switch_to_mode_selection_view(self):
        """Deprecated: Switches back to auto selection for backward compatibility."""
        logging.info("[ADCSSection] Returning to auto selection (deprecated method).")
        self._show_auto_selection()

    def switch_to_detail_view(self, mode_name):
        """Deprecated: For backward compatibility only."""
        logging.warning(f"[ADCSSection] Deprecated method called: switch_to_detail_view({mode_name})")
        self._show_auto_selection()


# Example of how to use it (if run standalone, for testing)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    # Dummy theme variables if theme.py is not available for standalone test
    BUTTON_TEXT = "white"
    BUTTON_COLOR = "#444444"
    BUTTON_HOVER = "#555555"
    BORDER_RADIUS = 3
    BORDER_WIDTH = 1
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_NORMAL = 10
    BUTTON_HEIGHT = 30
    TEXT_COLOR = "white"
    BORDER_COLOR = "#555555"
    
    # Re-evaluate styles if in __main__ for testing
    ADCS_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BUTTON_COLOR}; color: {BUTTON_TEXT}; border: {BORDER_WIDTH}px solid {BORDER_COLOR};
            border-radius: {BORDER_RADIUS}px; padding: 5px; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QPushButton:hover {{ background-color: {BUTTON_HOVER}; }}
        QPushButton:disabled {{ background-color: {BUTTON_COLOR}; color: {BUTTON_TEXT}; border: {BORDER_WIDTH}px solid {BORDER_COLOR}; }}
    """
    ADCS_BUTTON_HEIGHT = int(BUTTON_HEIGHT)
    ADCS_LABEL_STYLE = f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;"

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    adcs_widget = ADCSSection()
    main_window.setCentralWidget(adcs_widget)
    
    def on_adcs_command(mode, command, val):
        logging.info(f"MAIN APP RECEIVED ADCS COMMAND: Mode='{mode}', Command='{command}', Value='{val}'")
    adcs_widget.adcs_command_sent.connect(on_adcs_command)
    
    main_window.setGeometry(300, 300, 500, 200)
    main_window.show()
    sys.exit(app.exec())