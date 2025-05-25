from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton, QGroupBox
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE,
    WIDGET_SPACING, WIDGET_MARGIN, BUTTON_HEIGHT
)

class CameraControlsWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Camera Controls", parent)

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Buttons
        self.toggle_btn = QPushButton("Start Stream")
        self.reconnect_btn = QPushButton("Reconnect")
        self.capture_btn = QPushButton("Capture Image")
        self.crop_btn = QPushButton("Crop")

        # Define button style (thinner, same as Start Detector)
        BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 4px 8px;
            min-height: 24px;
            font-size: {FONT_SIZE_NORMAL}pt;
            font-family: {FONT_FAMILY};
        }}
        QPushButton:hover, QPushButton:pressed {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
            border: {BORDER_WIDTH}px solid #555;
        }}
        """

        # Apply the same style to all buttons
        for btn in (self.toggle_btn, self.reconnect_btn, self.capture_btn, self.crop_btn):
            btn.setStyleSheet(BUTTON_STYLE)

        # Default states
        self.toggle_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.crop_btn.setEnabled(True)

        # Add to layout
        self.layout.addWidget(self.toggle_btn, 0, 0)
        self.layout.addWidget(self.reconnect_btn, 0, 1)
        self.layout.addWidget(self.capture_btn, 1, 0)
        self.layout.addWidget(self.crop_btn, 1, 1)


        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {BOX_BACKGROUND};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}
            QGroupBox::title {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_TITLE}pt;
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
        """)

    def apply_style(self, style: str):
        self.setStyleSheet(style)
        # Do NOT set per-button style here!

class MainWindow(QWidget):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme

        # Layout
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Camera controls
        self.camera_controls = CameraControlsWidget(self.theme)
        self.layout.addWidget(self.camera_controls, 0, 0)
