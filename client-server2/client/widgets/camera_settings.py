from PyQt6.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel, QSlider, QComboBox, QPushButton
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
    BUTTON_HEIGHT
)

RES_PRESETS = [
    ("192x108", (192, 108)),
    ("256x144", (256, 144)),
    ("384x216", (384, 216)),
    ("768x432", (768, 432)),
    ("1024x576", (1024, 576)),
    ("1536x864", (1536, 864)),
]

class CameraSettingsWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Camera Settings", parent)

        self.setObjectName("CameraSettings")
        self.layout = QGridLayout()

        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(1, 100)
        self.jpeg_slider.setValue(70)

        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda val: self.jpeg_label.setText(f"JPEG: {val}"))

        self.res_dropdown = QComboBox()
        for label, _ in RES_PRESETS:
            self.res_dropdown.addItem(label)

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 120)
        self.fps_slider.setValue(10)

        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda val: self.fps_label.setText(f"FPS: {val}"))

        self.apply_btn = QPushButton("Apply Settings")

        self.layout.addWidget(self.jpeg_label, 0, 0)
        self.layout.addWidget(self.jpeg_slider, 0, 1)
        self.layout.addWidget(QLabel("Resolution"), 1, 0)
        self.layout.addWidget(self.res_dropdown, 1, 1)
        self.layout.addWidget(self.fps_label, 2, 0)
        self.layout.addWidget(self.fps_slider, 2, 1)
        self.layout.addWidget(self.apply_btn, 3, 0, 1, 2)

        self.setLayout(self.layout)

        # --- Apply sci-fi theme style ---
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
                color: {BUTTON_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                padding: {PADDING_NORMAL}px {PADDING_LARGE}px;
                border-radius: {BORDER_RADIUS}px;
                min-height: {BUTTON_HEIGHT}px;
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

    def get_config(self):
        res_idx = self.res_dropdown.currentIndex()
        _, resolution = RES_PRESETS[res_idx]
        return {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": resolution
        }

    def apply_style(self, style: str):
        self.setStyleSheet(style)
