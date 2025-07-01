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
        super().__init__("ADCS", parent)
        self.setObjectName("ADCSSection")

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setSpacing(0)  # Remove spacing to fill completely
        self._main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to fill completely

        self.stacked_widget = QStackedWidget()

        # Page 0: Main mode selection (Manual/Auto + Calibrate)
        main_page = self._create_main_page()
        self.stacked_widget.addWidget(main_page)

        # Page 1: Manual orientation page (Clockwise/Anticlockwise + Back)
        manual_page = self._create_manual_page()
        self.stacked_widget.addWidget(manual_page)

        # Page 2: Auto mode selection (Raw/Env/AprilTag)
        auto_selection_page = self._create_auto_selection_page()
        self.stacked_widget.addWidget(auto_selection_page)

        # Page 3: Raw control page
        raw_page = self._create_raw_page()
        self.stacked_widget.addWidget(raw_page)

        # Page 4: Env control page
        env_page = self._create_env_page()
        self.stacked_widget.addWidget(env_page)

        # Page 5: AprilTag control page
        apriltag_page = self._create_apriltag_page()
        self.stacked_widget.addWidget(apriltag_page)

        # Page 6: Calibration page
        calibration_page = self._create_calibration_page()
        self.stacked_widget.addWidget(calibration_page)

        self._main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0)

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
        page_layout.setSpacing(0)  # Remove spacing to fill completely
        page_layout.setContentsMargins(0, 0, 0, 0)

        # Three rows of buttons
        self.raw_btn = QPushButton("Raw")
        self.raw_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_btn.clicked.connect(lambda: self._go_to_page(3))
        page_layout.addWidget(self.raw_btn)

        self.env_btn = QPushButton("Env")
        self.env_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.env_btn.clicked.connect(lambda: self._go_to_page(4))
        page_layout.addWidget(self.env_btn)

        self.apriltag_btn = QPushButton("AprilTag")
        self.apriltag_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.apriltag_btn.clicked.connect(lambda: self._go_to_page(5))
        page_layout.addWidget(self.apriltag_btn)

        # Back button
        self.auto_back_btn = QPushButton("← Back")
        self.auto_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.auto_back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.auto_back_btn.clicked.connect(lambda: self._go_to_page(0))
        page_layout.addWidget(self.auto_back_btn)
        
        return page

    def _create_raw_page(self):
        """Creates the raw control page with Set Zero, Set Value, Start, Stop buttons."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(0)  # Remove spacing to fill completely
        page_layout.setContentsMargins(0, 0, 0, 0)

        # Set Zero button
        self.raw_set_zero_btn = QPushButton("Set Zero")
        self.raw_set_zero_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_set_zero_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_set_zero_btn.clicked.connect(
            lambda: self._handle_action_clicked("Raw", "set_zero", None)
        )
        page_layout.addWidget(self.raw_set_zero_btn)

        # Set Value input and send button
        value_row = QWidget()
        value_layout = QHBoxLayout(value_row)
        value_layout.setSpacing(0)  # Remove spacing to fill completely
        value_layout.setContentsMargins(0, 0, 0, 0)

        self.raw_value_input = QLineEdit()
        self.raw_value_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_value_input.setPlaceholderText("Enter value")
        value_layout.addWidget(self.raw_value_input)

        self.raw_set_value_btn = QPushButton("Set Value")
        self.raw_set_value_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_set_value_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_set_value_btn.clicked.connect(self._send_raw_value)
        value_layout.addWidget(self.raw_set_value_btn)

        page_layout.addWidget(value_row)

        # Start and Stop buttons
        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setSpacing(0)  # Remove spacing to fill completely
        control_layout.setContentsMargins(0, 0, 0, 0)

        self.raw_start_btn = QPushButton("Start")
        self.raw_start_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_start_btn.clicked.connect(
            lambda: self._handle_action_clicked("Raw", "start", None)
        )
        control_layout.addWidget(self.raw_start_btn)

        self.raw_stop_btn = QPushButton("Stop")
        self.raw_stop_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_stop_btn.clicked.connect(
            lambda: self._handle_action_clicked("Raw", "stop", None)
        )
        control_layout.addWidget(self.raw_stop_btn)

        page_layout.addWidget(control_row)

        # Back button
        self.raw_back_btn = QPushButton("← Back")
        self.raw_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.raw_back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.raw_back_btn.clicked.connect(lambda: self._go_to_page(2))
        page_layout.addWidget(self.raw_back_btn)
        
        return page

    def _create_env_page(self):
        """Creates the env control page with Set Zero, Set Value, Start, Stop buttons."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(6)
        page_layout.setContentsMargins(0, 0, 0, 0)

        # Set Zero button
        self.env_set_zero_btn = QPushButton("Set Zero")
        self.env_set_zero_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_set_zero_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_set_zero_btn.clicked.connect(
            lambda: self._handle_action_clicked("Env", "set_zero", None)
        )
        page_layout.addWidget(self.env_set_zero_btn)

        # Set Value input and send button
        value_row = QWidget()
        value_layout = QHBoxLayout(value_row)
        value_layout.setSpacing(6)
        value_layout.setContentsMargins(0, 0, 0, 0)

        self.env_value_input = QLineEdit()
        self.env_value_input.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_value_input.setPlaceholderText("Enter value")
        value_layout.addWidget(self.env_value_input)

        self.env_set_value_btn = QPushButton("Set Value")
        self.env_set_value_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_set_value_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_set_value_btn.clicked.connect(self._send_env_value)
        value_layout.addWidget(self.env_set_value_btn)

        page_layout.addWidget(value_row)

        # Start and Stop buttons
        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setSpacing(6)
        control_layout.setContentsMargins(0, 0, 0, 0)

        self.env_start_btn = QPushButton("Start")
        self.env_start_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_start_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_start_btn.clicked.connect(
            lambda: self._handle_action_clicked("Env", "start", None)
        )
        control_layout.addWidget(self.env_start_btn)

        self.env_stop_btn = QPushButton("Stop")
        self.env_stop_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_stop_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_stop_btn.clicked.connect(
            lambda: self._handle_action_clicked("Env", "stop", None)
        )
        control_layout.addWidget(self.env_stop_btn)

        page_layout.addWidget(control_row)

        # Back button
        self.env_back_btn = QPushButton("← Back")
        self.env_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.env_back_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.env_back_btn.clicked.connect(lambda: self._go_to_page(2))
        page_layout.addWidget(self.env_back_btn)
        
        return page

    def _create_apriltag_page(self):
        """Creates the AprilTag control page with Set Zero, Set Value, Start, Stop buttons."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(6)
        page_layout.setContentsMargins(0, 0, 0, 0)

        # Set Zero button
        self.apriltag_set_zero_btn = QPushButton("Set Zero")
        self.apriltag_set_zero_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_set_zero_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_set_zero_btn.clicked.connect(
            lambda: self._handle_action_clicked("AprilTag", "set_zero", None)
        )
        page_layout.addWidget(self.apriltag_set_zero_btn)

        # Set Value input and send button
        value_row = QWidget()
        value_layout = QHBoxLayout(value_row)
        value_layout.setSpacing(6)
        value_layout.setContentsMargins(0, 0, 0, 0)

        self.apriltag_value_input = QLineEdit()
        self.apriltag_value_input.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_value_input.setPlaceholderText("Enter value")
        value_layout.addWidget(self.apriltag_value_input)

        self.apriltag_set_value_btn = QPushButton("Set Value")
        self.apriltag_set_value_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_set_value_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_set_value_btn.clicked.connect(self._send_apriltag_value)
        value_layout.addWidget(self.apriltag_set_value_btn)

        page_layout.addWidget(value_row)

        # Start and Stop buttons
        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setSpacing(6)
        control_layout.setContentsMargins(0, 0, 0, 0)

        self.apriltag_start_btn = QPushButton("Start")
        self.apriltag_start_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_start_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_start_btn.clicked.connect(
            lambda: self._handle_action_clicked("AprilTag", "start", None)
        )
        control_layout.addWidget(self.apriltag_start_btn)

        self.apriltag_stop_btn = QPushButton("Stop")
        self.apriltag_stop_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_stop_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_stop_btn.clicked.connect(
            lambda: self._handle_action_clicked("AprilTag", "stop", None)
        )
        control_layout.addWidget(self.apriltag_stop_btn)

        page_layout.addWidget(control_row)

        # Back button
        self.apriltag_back_btn = QPushButton("← Back")
        self.apriltag_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.apriltag_back_btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.apriltag_back_btn.clicked.connect(lambda: self._go_to_page(2))
        page_layout.addWidget(self.apriltag_back_btn)
        
        return page

    def _create_calibration_page(self):
        """Creates the calibration page with live text display and calibrate button."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(0)  # Remove spacing to fill completely
        page_layout.setContentsMargins(0, 0, 0, 0)

        # Live text display
        self.calibration_status_label = QLabel("Calibration Status: Ready")
        self.calibration_status_label.setStyleSheet(ADCS_LABEL_STYLE)
        self.calibration_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibration_status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        page_layout.addWidget(self.calibration_status_label)

        # Calibrate button
        self.calibrate_again_btn = QPushButton("Start Calibration")
        self.calibrate_again_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.calibrate_again_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.calibrate_again_btn.clicked.connect(
            lambda: self._handle_action_clicked("Calibration", "start_calibration", None)
        )
        page_layout.addWidget(self.calibrate_again_btn)

        # Back button
        self.calibration_back_btn = QPushButton("← Back")
        self.calibration_back_btn.setStyleSheet(ADCS_BUTTON_STYLE)
        self.calibration_back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Fill available space
        self.calibration_back_btn.clicked.connect(lambda: self._go_to_page(0))
        page_layout.addWidget(self.calibration_back_btn)
        
        return page

    def _go_to_page(self, page_index):
        """Navigate to a specific page."""
        logging.info(f"[ADCSSection] Navigating to page {page_index}")
        self.stacked_widget.setCurrentIndex(page_index)

    def _send_raw_value(self):
        """Send raw value from input field."""
        try:
            value = int(self.raw_value_input.text() or 0)
            self._handle_action_clicked("Raw", "set_value", value)
            self.raw_value_input.clear()
        except ValueError:
            logging.warning(f"[ADCSSection] Invalid raw value: {self.raw_value_input.text()}")
            self.raw_value_input.selectAll()

    def _send_env_value(self):
        """Send env value from input field."""
        try:
            value = int(self.env_value_input.text() or 0)
            self._handle_action_clicked("Env", "set_value", value)
            self.env_value_input.clear()
        except ValueError:
            logging.warning(f"[ADCSSection] Invalid env value: {self.env_value_input.text()}")
            self.env_value_input.selectAll()

    def _send_apriltag_value(self):
        """Send AprilTag value from input field."""
        try:
            value = int(self.apriltag_value_input.text() or 0)
            self._handle_action_clicked("AprilTag", "set_value", value)
            self.apriltag_value_input.clear()
        except ValueError:
            logging.warning(f"[ADCSSection] Invalid AprilTag value: {self.apriltag_value_input.text()}")
            self.apriltag_value_input.selectAll()

    def _handle_action_clicked(self, mode_name, command_name, value=None):
        """Handle action button clicks and emit signals."""
        logging.info(f"[ADCSSection] Action for mode '{mode_name}': Command '{command_name}', Value: {value}")
        self.adcs_command_sent.emit(mode_name, command_name, value)

    def update_calibration_status(self, status_text):
        """Update the calibration status text (can be called from main application)."""
        if hasattr(self, 'calibration_status_label'):
            self.calibration_status_label.setText(f"Calibration Status: {status_text}")

    # Deprecated methods - keeping for backward compatibility but they now redirect to main page
    def switch_to_mode_selection_view(self):
        """Deprecated: Switches back to main page for backward compatibility."""
        logging.info("[ADCSSection] Returning to main page (deprecated method).")
        self._go_to_page(0)

    def switch_to_detail_view(self, mode_name):
        """Deprecated: For backward compatibility only."""
        logging.warning(f"[ADCSSection] Deprecated method called: switch_to_detail_view({mode_name})")
        self._go_to_page(0)

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
