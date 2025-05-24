from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE,
    WIDGET_SPACING, WIDGET_MARGIN, STREAM_WIDTH, STREAM_HEIGHT
)

SCI_FI_GROUPBOX_STYLE = f"""
QGroupBox {{
    border: {BORDER_WIDTH}px solid {BORDER_COLOR};
    border-radius: {BORDER_RADIUS}px;
    background-color: {BOX_BACKGROUND};
    margin-top: {WIDGET_MARGIN}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {WIDGET_MARGIN - 2}px;
    padding: 0 {PADDING_NORMAL}px;
    font-size: {FONT_SIZE_TITLE}pt;
    font-family: {FONT_FAMILY};
    color: {BOX_TITLE_COLOR};
}}
QGroupBox QLabel {{
    color: {TEXT_COLOR};
    font-size: {FONT_SIZE_NORMAL}pt;
    font-family: {FONT_FAMILY};
}}
"""


class DetectorOutputWidget(QGroupBox):
    def __init__(self):
        super().__init__("Detector Output")
        self.setStyleSheet(SCI_FI_GROUPBOX_STYLE)
        self.layout = QVBoxLayout()
        self.layout.setSpacing(WIDGET_SPACING)
        self.layout.setContentsMargins(WIDGET_MARGIN, WIDGET_MARGIN, WIDGET_MARGIN, WIDGET_MARGIN)
        self.setLayout(self.layout)
        self.label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedSize(STREAM_WIDTH, STREAM_HEIGHT)
        self.layout.addWidget(self.label)
