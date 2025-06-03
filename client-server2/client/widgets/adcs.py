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

    def __init__(self, parent=None):
        super().__init__("ADCS", parent) # Sets the GroupBox title
        self.setObjectName("ADCSSection")

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setSpacing(5)
        self._main_layout.setContentsMargins(5, 5, 5, 5) # Padding inside the GroupBox

        self.stacked_widget = QStackedWidget()

        # Page 1: Initial ADCS Mode Buttons
        mode_page = self._create_mode_selection_page()
        self.stacked_widget.addWidget(mode_page)

        # Page 2: Detail View with Dead Buttons and Back Button
        detail_page = self._create_detail_page()
        self.stacked_widget.addWidget(detail_page)
        
        self._main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0) # Start with the mode selection page

    def _create_mode_selection_page(self):
        """Creates the page with four horizontal ADCS mode selection buttons."""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(0,0,0,0)

        self.adcs_mode_buttons = []
        adcs_mode_names = ["ADCS Mode 1", "ADCS Mode 2", "ADCS Mode 3", "ADCS Mode 4"]
        for i, mode_name in enumerate(adcs_mode_names):
            btn = QPushButton(mode_name)
            btn.setStyleSheet(ADCS_BUTTON_STYLE) 
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            # btn.setMinimumWidth(100) # Optional: set a minimum width if needed
            btn.clicked.connect(lambda checked, idx=i, name=mode_name: self._handle_mode_button_clicked(idx, name))
            layout.addWidget(btn)
            self.adcs_mode_buttons.append(btn)
        
        return page

    def _create_detail_page(self):
        """Creates the detail page with a label, three dead action buttons, and a back button."""
        page = QWidget()
        # Main vertical layout for this page: Label on top, button row below
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(10) 
        page_layout.setContentsMargins(0, 5, 0, 0) # Top margin for the label

        self.detail_label = QLabel("Details for: ADCS Mode X") # Placeholder text
        self.detail_label.setStyleSheet(ADCS_LABEL_STYLE)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(self.detail_label)

        # Horizontal layout for the row of action buttons and the back button
        button_row_layout = QHBoxLayout() 
        button_row_layout.setSpacing(6)
        button_row_layout.setContentsMargins(0,0,0,0)

        self.adcs_detail_action_buttons = []
        dead_button_names = ["Action 1", "Action 2", "Action 3"] # Placeholder action names
        for name in dead_button_names:
            btn = QPushButton(name)
            btn.setStyleSheet(ADCS_BUTTON_STYLE)
            btn.setFixedHeight(ADCS_BUTTON_HEIGHT)
            btn.setEnabled(False) # Make them appear "dead"
            button_row_layout.addWidget(btn)
            self.adcs_detail_action_buttons.append(btn)

        self.back_button = QPushButton("← Back")
        self.back_button.setStyleSheet(ADCS_BUTTON_STYLE)
        self.back_button.setFixedHeight(ADCS_BUTTON_HEIGHT)
        self.back_button.clicked.connect(self.switch_to_mode_selection_view)
        button_row_layout.addWidget(self.back_button)
        
        page_layout.addLayout(button_row_layout) # Add button row to the page's main layout
        return page

    def _handle_mode_button_clicked(self, mode_index, mode_name):
        """Internal handler for mode button clicks. Emits signal and switches view."""
        self.mode_selected.emit(mode_index, mode_name)
        self.switch_to_detail_view(mode_name) # Pass mode_name to update label

    def switch_to_detail_view(self, mode_name):
        """Switches the ADCS view to the detail page and updates the label."""
        print(f"[ADCSSection] Displaying details for: {mode_name}")
        self.detail_label.setText(f"Details for: {mode_name}")
        self.stacked_widget.setCurrentIndex(1)

    def switch_to_mode_selection_view(self):
        """Switches the ADCS view back to the mode selection page."""
        print("[ADCSSection] Returning to ADCS Mode Selection.")
        self.stacked_widget.setCurrentIndex(0)
