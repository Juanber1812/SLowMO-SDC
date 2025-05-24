from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox
)
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
import time
from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR,
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    GRAPH_MODE_COLORS,
    BUTTON_HEIGHT, BORDER_WIDTH, BORDER_RADIUS
)

def sci_fi_button_style(color):
    return f"""
    QPushButton {{
        background-color: {BOX_BACKGROUND};
        color: {color};
        border: 2px solid {color};
        border-radius: 2px;
        padding: 8px 14px;
        font-size: 10pt;
        font-family: 'Orbitron', 'Segoe UI', sans-serif;
    }}
    QPushButton:hover {{
        background-color: {color};
        color: black;
    }}
    QPushButton:disabled {{
        background-color: #222;
        color: #444;
        border: 2px solid #333;
    }}
    """

class GraphSection(QGroupBox):
    def __init__(self, record_btn: QPushButton, duration_dropdown: QComboBox, parent=None):
        super().__init__("Graph Display", parent)
        self.setObjectName("GraphSection")

        self.graph_display_layout = QVBoxLayout()
        self.setLayout(self.graph_display_layout)

        self.graph_display_placeholder = QWidget()
        self.placeholder_layout = QVBoxLayout(self.graph_display_placeholder)
        self.placeholder_layout.setContentsMargins(10, 10, 10, 10)
        self.placeholder_layout.setSpacing(15)

        self.graph_modes = ["Relative Distance", "Relative Angle", "Angular Position"]
        self.select_buttons = {}

        for mode in self.graph_modes:
            btn = QPushButton(mode)
            color = GRAPH_MODE_COLORS[mode]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BOX_BACKGROUND};
                    color: {TEXT_COLOR};
                    border: {BORDER_WIDTH}px solid {color};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 8px 14px;
                    font-size: 10pt;
                    font-family: 'Segoe UI', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: {BUTTON_HOVER};
                    color: black;
                    border: {BORDER_WIDTH}px solid {color};
                }}
            """)
            btn.setMinimumHeight(BUTTON_HEIGHT)
            btn.setFixedHeight(BUTTON_HEIGHT + 32)
            btn.clicked.connect(lambda _, m=mode: self.load_graph(m))
            self.placeholder_layout.addWidget(btn)
            self.select_buttons[mode] = btn

        self.graph_display_layout.addWidget(self.graph_display_placeholder)

        self.record_btn = record_btn
        self.duration_dropdown = duration_dropdown
        self.graph_widget = None
        self.exit_graph_btn = None
        self.shared_start_time = None

    def apply_sci_fi_button_style(self, button: QPushButton, color=BOX_BACKGROUND):
        button.setStyleSheet(sci_fi_button_style(color))

    def load_graph(self, mode):
        self.graph_display_placeholder.setParent(None)

        if mode == "Relative Distance":
            self.graph_widget = RelativeDistancePlotter()
        elif mode == "Relative Angle":
            self.graph_widget = RelativeAnglePlotter()
        elif mode == "Angular Position":
            self.graph_widget = AngularPositionPlotter()
        else:
            return

        self.shared_start_time = time.time()
        self.graph_widget.start_time = self.shared_start_time
        self.graph_widget.setFixedSize(384, 216)
        self.graph_display_layout.addWidget(self.graph_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        button_style = f"""
        QPushButton {{
            background-color: #252525;
            color: {BUTTON_TEXT};
            border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 6px 12px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QPushButton:hover {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
        }}
        """

        self.record_btn.setFixedHeight(BUTTON_HEIGHT)
        self.record_btn.setStyleSheet(button_style)
        btn_layout.addWidget(self.record_btn)

        self.duration_dropdown.setFixedHeight(BUTTON_HEIGHT)
        btn_layout.addWidget(self.duration_dropdown)

        self.exit_graph_btn = QPushButton("← Back")
        self.exit_graph_btn.setFixedHeight(BUTTON_HEIGHT)
        self.exit_graph_btn.setStyleSheet(button_style)
        self.exit_graph_btn.clicked.connect(self.exit_graph)
        btn_layout.addWidget(self.exit_graph_btn)

        self.exit_graph_btn.setSizePolicy(self.record_btn.sizePolicy())
        self.graph_display_layout.addLayout(btn_layout)

    def exit_graph(self):
        if self.graph_widget:
            self.graph_widget.setParent(None)
            self.graph_widget = None
        if self.exit_graph_btn:
            self.exit_graph_btn.setParent(None)
        self.record_btn.setParent(None)
        self.duration_dropdown.setParent(None)
        self.graph_display_layout.addWidget(self.graph_display_placeholder)
