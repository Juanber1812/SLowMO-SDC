from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE,
    WIDGET_SPACING, WIDGET_MARGIN
)


class DetectorControlWidget(QGroupBox):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.detector_btn = QPushButton("Start Detector")
        self.detector_btn.setEnabled(False)
        self.layout.addWidget(self.detector_btn)

        # Apply sci-fi theme style using theme variables
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
            QPushButton {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                padding: {PADDING_NORMAL}px {PADDING_LARGE}px;
                border-radius: {BORDER_RADIUS}px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_COLOR};
                color: black;
            }}
            QPushButton:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777;
                border: {BORDER_WIDTH}px solid #555;
            }}
        """)

    def apply_style(self, style: str):
        self.setStyleSheet(style)
        for child in self.findChildren(QPushButton):
            child.setStyleSheet(style)
