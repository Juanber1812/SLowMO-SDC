from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget
)
from PyQt6.QtCore import pyqtSignal, Qt

# Attempt to import style constants from theme.py, similar to GraphSection
# Assumes theme.py is in the parent directory 'client' relative to 'widgets'
try:
    from ..theme import (
        BOX_BACKGROUND, BUTTON_TEXT as THEME_BUTTON_TEXT, BUTTON_COLOR as THEME_BUTTON_COLOR,
        BUTTON_HOVER as THEME_BUTTON_HOVER, BORDER_RADIUS as THEME_BORDER_RADIUS,
        BORDER_WIDTH as THEME_BORDER_WIDTH, FONT_FAMILY as THEME_FONT_FAMILY,
        FONT_SIZE_NORMAL as THEME_FONT_SIZE_NORMAL, BUTTON_HEIGHT as THEME_BUTTON_HEIGHT,
        TEXT_COLOR as THEME_TEXT_COLOR, # For label
        BUTTON_DISABLED_BG, BUTTON_DISABLED_TEXT, BUTTON_DISABLED_BORDER # Assuming these exist for disabled state
    )
    # Construct styles dynamically
    ADCS_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {THEME_BUTTON_TEXT};
            border: {THEME_BORDER_WIDTH}px solid {THEME_BUTTON_COLOR};
            border-radius: {THEME_BORDER_RADIUS}px;
            padding: 6px 12px;
            font-family: {THEME_FONT_FAMILY};
            font-size: {THEME_FONT_SIZE_NORMAL}pt;
        }}
        QPushButton:hover {{
            background-color: {THEME_BUTTON_HOVER};
            color: black; /* Or a theme color for hover text */
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED_BG if 'BUTTON_DISABLED_BG' in locals() else '#2c2c2c'};
            color: {BUTTON_DISABLED_TEXT if 'BUTTON_DISABLED_TEXT' in locals() else '#777777'};
            border: {THEME_BORDER_WIDTH}px solid {BUTTON_DISABLED_BORDER if 'BUTTON_DISABLED_BORDER' in locals() else '#444444'};
        }}
    """
    ADCS_BUTTON_HEIGHT = int(THEME_BUTTON_HEIGHT) if THEME_BUTTON_HEIGHT is not None else 30
    ADCS_LABEL_STYLE = f"color: {THEME_TEXT_COLOR}; font-family: {THEME_FONT_FAMILY}; font-size: {THEME_FONT_SIZE_NORMAL}pt;"

except ImportError:
    print("[ADCSSection] Warning: Theme file or specific ADCS style constants not found. Using fallback styles.")
    ADCS_BUTTON_STYLE = """
        QPushButton {
            background-color: #444444; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px;
        }
        QPushButton:hover { background-color: #555555; }
        QPushButton:disabled { background-color: #2c2c2c; color: #777777; border: 1px solid #444444; }
    """
    ADCS_BUTTON_HEIGHT = 30
    ADCS_LABEL_STYLE = "color: white; font-size: 10pt;"


class ADCSSection(QGroupBox):
    """
    A QGroupBox widget to manage ADCS controls using a QStackedWidget
    for different views (mode selection and detail view).
    """
    mode_selected = pyqtSignal(int, str) # Emits mode_index, mode_name when a mode button is clicked
    # You might want to add more specific signals for actions from detail buttons, e.g.:
    # adcs_command_sent = pyqtSignal(str, str) # mode_name, command_name

    def __init__(self, parent=None):
        super().__init__("ADCS", parent)
        self.setObjectName("ADCSSection")

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setSpacing(5)
        self._main_layout.setContentsMargins(5, 5, 5, 5)

        self.stacked_widget = QStackedWidget()

        # Define the main ADCS modes and their respective detail view buttons
        # << YOU CAN CHANGE THE BUTTON NAMES FOR EACH MODE HERE >>
        self.adcs_modes_config = {
            "Environmental Calibration": ["hello"],
            "Manual Orientation": ["Clockwise", "Anticlockwise"],
            "Automatic Orientation": ["Set value"],
            "Detumbling": ["world"]
        }
        # The order of these names will determine the order of the main mode buttons
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
        layout.setContentsMargins(0,0,0,0)

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
        """Clears and populates the detail_button_row_layout with buttons specific to the given mode."""
        
        # 1. Safely remove the persistent back_button from its current parent/layout.
        #    This ensures it's not accidentally deleted by the clearing loop below.
        #    The self.back_button widget instance itself remains.
        if self.back_button:
            self.back_button.setParent(None)

        # 2. Clear all (now only old mode-specific) buttons from the layout and delete their widgets.
        while self.detail_button_row_layout.count() > 0:
            item = self.detail_button_row_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater() # These are the old mode-specific buttons
        
        # Clear the list of references to the old action buttons
        if hasattr(self, 'adcs_detail_action_buttons'):
            self.adcs_detail_action_buttons.clear()
        else:
            self.adcs_detail_action_buttons = []
        
        button_names_for_mode = self.adcs_modes_config.get(mode_name, [])

        # 3. Add new mode-specific buttons for the current mode.
        for name in button_names_for_mode:
            btn = QPushButton(name)
            btn.setStyleSheet(ADCS_BUTTON_STYLE)
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            btn.clicked.connect(lambda checked, cmd=name, m=mode_name: self._handle_detail_action_clicked(m, cmd))
            self.detail_button_row_layout.addWidget(btn)
            self.adcs_detail_action_buttons.append(btn) # Keep track of newly added buttons

        # 4. Add the persistent self.back_button instance back to the layout.
        #    addWidget will correctly re-parent it.
        if self.back_button:
            self.detail_button_row_layout.addWidget(self.back_button)


    def _handle_detail_action_clicked(self, mode_name, command_name):
        """Placeholder for handling clicks on detail action buttons."""
        print(f"[ADCSSection] Action for mode '{mode_name}': Command '{command_name}' clicked.")
        # TODO: Implement actual command sending logic here.
        # For example, you might emit a signal:
        # self.adcs_command_sent.emit(mode_name, command_name)


    def _handle_mode_button_clicked(self, mode_index, mode_name):
        """Internal handler for main mode button clicks. Emits signal and switches view."""
        self.mode_selected.emit(mode_index, mode_name) # Notify client3.py or other listeners
        self.switch_to_detail_view(mode_name)

    def switch_to_detail_view(self, mode_name):
        """Switches the ADCS view to the detail page, updates the label, and populates buttons."""
        print(f"[ADCSSection] Displaying details for: {mode_name}")
        self.detail_label.setText(f"Details for: {mode_name}")
        self._populate_detail_buttons(mode_name) # Populate buttons for the current mode
        self.stacked_widget.setCurrentIndex(1) # Switch to the detail page view

    def switch_to_mode_selection_view(self):
        """Switches the ADCS view back to the mode selection page."""
        print("[ADCSSection] Returning to ADCS Mode Selection.")
        self.stacked_widget.setCurrentIndex(0)
