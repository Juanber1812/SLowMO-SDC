from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QLineEdit
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
        self._main_layout.setSpacing(5)
        self._main_layout.setContentsMargins(5, 5, 5, 5)

        self.stacked_widget = QStackedWidget()

        # Define the main ADCS modes and their respective detail view buttons
        self.adcs_modes_config = {
            "Environmental Calibration": ["hello"],
            "Manual Orientation": ["Clockwise", "Anticlockwise"],  # These will be press/hold
            "Automatic Orientation": ["Set Value"],  # This will trigger special widget creation
            "Detumbling": ["world"]
        }
        self.adcs_mode_names = list(self.adcs_modes_config.keys())

        # Page 1: Initial ADCS Mode Buttons
        mode_page = self._create_mode_selection_page()
        self.stacked_widget.addWidget(mode_page)

        # Page 2: Detail View (structure created, content populated dynamically)
        detail_page_widget = self._create_detail_page_structure()
        self.stacked_widget.addWidget(detail_page_widget)

        self._main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0)

    def _create_mode_selection_page(self):
        """Creates the page with four horizontal ADCS mode selection buttons."""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        self.adcs_mode_buttons = []
        # Use self.adcs_mode_names defined in __init__
        for i, mode_name in enumerate(self.adcs_mode_names):
            btn = QPushButton(mode_name)
            btn.setStyleSheet(ADCS_BUTTON_STYLE) 
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            btn.clicked.connect(lambda checked, idx=i, name=mode_name: self._handle_mode_button_clicked(idx, name))
            layout.addWidget(btn)
            self.adcs_mode_buttons.append(btn)
        
        return page

    def _create_detail_page_structure(self):
        """Creates the static structure of the detail page: label, a layout for dynamic buttons, and the back button."""
        page = QWidget()
        page_layout = QVBoxLayout(page) # Main vertical layout for this page
        page_layout.setSpacing(10) 
        page_layout.setContentsMargins(0, 5, 0, 0) # Top margin for the label

        self.detail_label = QLabel("Details for: ADCS Mode X") # Placeholder text
        self.detail_label.setStyleSheet(ADCS_LABEL_STYLE)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(self.detail_label)

        # This QHBoxLayout will hold the dynamically generated action buttons
        self.detail_button_row_layout = QHBoxLayout() 
        self.detail_button_row_layout.setSpacing(6)
        self.detail_button_row_layout.setContentsMargins(0,0,0,0)
        
        page_layout.addLayout(self.detail_button_row_layout) # Add this (currently empty) layout to the page
        
        # Create the back button ONCE. It will be re-parented as needed.
        self.back_button = QPushButton("← Back")
        self.back_button.setStyleSheet(ADCS_BUTTON_STYLE)
        self.back_button.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.back_button.clicked.connect(self.switch_to_mode_selection_view)

        return page

    def _populate_detail_buttons(self, mode_name):
        """Clears and populates the detail_button_row_layout with buttons for the given mode."""
        
        # Remove the persistent back_button from its current parent
        if self.back_button:
            self.back_button.setParent(None)
        
        # Clear existing buttons from the layout
        while self.detail_button_row_layout.count() > 0:
            item = self.detail_button_row_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if hasattr(self, 'adcs_detail_action_buttons'):
            self.adcs_detail_action_buttons.clear()
        else:
            self.adcs_detail_action_buttons = []
        
        # Create independent buttons/signals based on the current mode
        if mode_name == "Environmental Calibration":
            btn = QPushButton("Environmental Calibration")
            btn.setStyleSheet(ADCS_BUTTON_STYLE)
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            btn.clicked.connect(lambda: self._handle_detail_action_clicked(mode_name, "environmental", None))
            self.detail_button_row_layout.addWidget(btn)
        
        elif mode_name == "Manual Orientation":
            # Create 'Clockwise' and 'Anticlockwise' buttons with press/release events
            for name in ["Clockwise", "Anticlockwise"]:
                btn = QPushButton(name)
                btn.setStyleSheet(ADCS_BUTTON_STYLE)
                btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
                if name == "Clockwise":
                    btn.pressed.connect(lambda m=mode_name, cmd_start="manual_clockwise_start": self._handle_detail_action_clicked(m, cmd_start, None))
                    btn.released.connect(lambda m=mode_name, cmd_stop="manual_clockwise_stop": self._handle_detail_action_clicked(m, cmd_stop, None))
                else:
                    btn.pressed.connect(lambda m=mode_name, cmd_start="manual_anticlockwise_start": self._handle_detail_action_clicked(m, cmd_start, None))
                    btn.released.connect(lambda m=mode_name, cmd_stop="manual_anticlockwise_stop": self._handle_detail_action_clicked(m, cmd_stop, None))
                self.detail_button_row_layout.addWidget(btn)
                self.adcs_detail_action_buttons.append(btn)
        
        elif mode_name == "Automatic Orientation":
            # Create container for setting a value
            input_container = QWidget()
            input_layout = QHBoxLayout(input_container)
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.setSpacing(5)
            
            value_label = QLabel("Desired Value:")
            value_label.setStyleSheet(ADCS_LABEL_STYLE)
            input_layout.addWidget(value_label)
            
            self.orientation_input_field = QLineEdit()
            self.orientation_input_field.setPlaceholderText("Enter integer")
            self.orientation_input_field.setStyleSheet(f"""
                QLineEdit {{
                    color: {TEXT_COLOR};
                    background-color: #2D2D2D;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 5px;
                    font-family: {FONT_FAMILY};
                    font-size: {FONT_SIZE_NORMAL}pt;
                }}
            """)
            self.orientation_input_field.setFixedHeight(ADCS_BUTTON_HEIGHT)
            self.orientation_input_field.returnPressed.connect(self._handle_send_automatic_orientation_value)
            input_layout.addWidget(self.orientation_input_field)
            
            self.orientation_send_button = QPushButton("Send")
            self.orientation_send_button.setStyleSheet(ADCS_BUTTON_STYLE)
            self.orientation_send_button.setFixedHeight(ADCS_BUTTON_HEIGHT)
            self.orientation_send_button.clicked.connect(self._handle_send_automatic_orientation_value)
            input_layout.addWidget(self.orientation_send_button)
            
            self.detail_button_row_layout.addWidget(input_container)
        
        elif mode_name == "Detumbling":
            btn = QPushButton("Detumbling")
            btn.setStyleSheet(ADCS_BUTTON_STYLE)
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            btn.clicked.connect(lambda: self._handle_detail_action_clicked(mode_name, "detumbling", None))
            self.detail_button_row_layout.addWidget(btn)
        
        # Re-add the persistent back button
        if self.back_button:
            self.detail_button_row_layout.addWidget(self.back_button)


    def _handle_send_automatic_orientation_value(self):
        """Handles sending the value from the QLineEdit for Automatic Orientation."""
        if self.orientation_input_field:
            value_text = self.orientation_input_field.text()
            try:
                value_int = int(value_text)
                # Use a specific command name, e.g., "set_target_orientation"
                self._handle_detail_action_clicked("Automatic Orientation", "set_target_orientation", value_int)
                self.orientation_input_field.clear()  # Clear input after sending
            except ValueError:
                logging.info(f"[ADCSSection] Invalid input: '{value_text}' is not an integer.")
                # Optionally, provide visual feedback to the user (e.g., QToolTip or status label)
                self.orientation_input_field.selectAll() # Make it easy for user to correct

    def _handle_detail_action_clicked(self, mode_name, command_name, value=None):
        """Placeholder for handling clicks on detail action buttons. Emits a signal."""
        logging.info(f"[ADCSSection] Action for mode '{mode_name}': Command '{command_name}', Value: {value}")
        # Emit the signal so that MainWindow (client3.py) can pick it up and send it via sio.emit
        self.adcs_command_sent.emit(mode_name, command_name, value)


    def _handle_mode_button_clicked(self, mode_index, mode_name):
        """Internal handler for main mode button clicks. Emits signal and switches view."""
        self.mode_selected.emit(mode_index, mode_name) # Notify client3.py or other listeners
        self.switch_to_detail_view(mode_name)

    def switch_to_detail_view(self, mode_name):
        """Switches the ADCS view to the detail page, updates the label, and populates buttons."""
        logging.info(f"[ADCSSection] Displaying details for: {mode_name}")
        self.detail_label.setText(f"Details for: {mode_name}")
        self._populate_detail_buttons(mode_name) # Populate buttons for the current mode
        self.stacked_widget.setCurrentIndex(1) # Switch to the detail page view

    def switch_to_mode_selection_view(self):
        """Switches the ADCS view back to the mode selection page."""
        logging.info("[ADCSSection] Returning to ADCS Mode Selection.")
        self.stacked_widget.setCurrentIndex(0)

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
