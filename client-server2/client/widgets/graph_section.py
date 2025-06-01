from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
import time
import threading
import pandas as pd  # Add pandas import
import os
from datetime import datetime
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
    # new signal: emits the full path to the CSV just saved
    recording_saved = pyqtSignal(str)

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

        # Recording state tracking
        self.is_recording = False
        self.recorded_data = []
        self.current_graph_mode = None  # Track which graph is currently active
        self.recording_start_time = None

        # Make graph mode buttons smaller and centered
        for mode in self.graph_modes:
            btn = QPushButton(mode)
            color = GRAPH_MODE_COLORS[mode]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BOX_BACKGROUND};
                    color: {TEXT_COLOR};
                    border: {BORDER_WIDTH}px solid {color};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 1px 1px;
                    font-size: 9pt;
                    font-family: {FONT_FAMILY};
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: black;
                    border: {BORDER_WIDTH}px solid {color};
                }}
            """)
            btn.setMinimumHeight(int(BUTTON_HEIGHT *1.5))
            btn.setFixedHeight(int((BUTTON_HEIGHT + 4) *1.5))  # 20% bigger
            btn.setMinimumWidth(int(120 * 1.5))                 # 20% bigger width
            btn.clicked.connect(lambda _, m=mode: self.load_graph(m))
            self.placeholder_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.select_buttons[mode] = btn

        self.graph_display_layout.addWidget(self.graph_display_placeholder)

        self.record_btn = record_btn
        self.duration_dropdown = duration_dropdown
        self.graph_widget = None
        self.exit_graph_btn = None
        self.shared_start_time = None

        # Connect the record button to toggle recording
        self.record_btn.clicked.connect(self.toggle_recording)

    def apply_sci_fi_button_style(self, button: QPushButton, color=BOX_BACKGROUND):
        button.setStyleSheet(sci_fi_button_style(color))

    def load_graph(self, mode):
        self.graph_display_placeholder.setParent(None)
        
        # Set the current graph mode
        self.current_graph_mode = mode

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
        self.graph_widget.setFixedSize(480, 280)  # Larger graph size

        # Create a horizontal layout for graph and buttons
        graph_and_btns_layout = QHBoxLayout()
        graph_and_btns_layout.setContentsMargins(0, 0, 0, 0)
        graph_and_btns_layout.setSpacing(18)

        # Add the graph widget (left)
        graph_and_btns_layout.addWidget(self.graph_widget, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Stack buttons vertically, left-aligned and vertically centered
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        button_style = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
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

        # Reset record button text when loading new graph
        self.record_btn.setText("Record")
        self.is_recording = False
        self.record_btn.setFixedHeight(int(BUTTON_HEIGHT))
        self.record_btn.setStyleSheet(button_style)
        btn_layout.addWidget(self.record_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.duration_dropdown.setFixedHeight(int(BUTTON_HEIGHT))
        btn_layout.addWidget(self.duration_dropdown, alignment=Qt.AlignmentFlag.AlignLeft)

        self.exit_graph_btn = QPushButton("← Back")
        self.exit_graph_btn.setFixedHeight(int(BUTTON_HEIGHT))
        self.exit_graph_btn.setStyleSheet(button_style)
        self.exit_graph_btn.clicked.connect(self.exit_graph)
        btn_layout.addWidget(self.exit_graph_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.exit_graph_btn.setSizePolicy(self.record_btn.sizePolicy())

        # Add the button layout (right)
        graph_and_btns_layout.addLayout(btn_layout)

        # Add the combined layout to the main graph display layout
        self.graph_display_layout.addLayout(graph_and_btns_layout)

    def toggle_recording(self):
        """Toggle recording state and update button text"""
        if not self.current_graph_mode:
            print("[WARNING] No graph mode selected for recording")
            return

        self.is_recording = not self.is_recording

        if self.is_recording:
            # Start recording
            self.record_btn.setText("⏹ Stop")
            self.record_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BOX_BACKGROUND};
                    color: {ERROR_COLOR};
                    border: {BORDER_WIDTH}px solid {ERROR_COLOR};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 6px 12px;
                    font-family: {FONT_FAMILY};
                    font-size: {FONT_SIZE_NORMAL}pt;
                }}
                QPushButton:hover {{
                    background-color: {ERROR_COLOR};
                    color: white;
                }}
            """)
            self.recorded_data = []  # Reset the log
            self.recording_start_time = time.time()
            print(f"[INFO] 🔴 Started recording: {self.current_graph_mode}")
            
            # Start the recording timer if graph widget exists
            if self.graph_widget and hasattr(self.graph_widget, 'start_recording'):
                self.graph_widget.start_recording()
        else:
            # Stop recording
            self.record_btn.setText("Record")
            self.record_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BOX_BACKGROUND};
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
            """)
            print(f"[INFO] ⏹ Recording stopped: {self.current_graph_mode}")
            
            # Stop the recording timer if graph widget exists
            if self.graph_widget and hasattr(self.graph_widget, 'stop_recording'):
                self.graph_widget.stop_recording()
            
            # Save the recorded data
            self.save_recording_to_csv()

    def add_data_point(self, timestamp, value, **kwargs):
        """Add a data point to the recording if recording is active"""
        if self.is_recording:
            data_point = {
                'timestamp': timestamp,
                'value': value,
                'mode': self.current_graph_mode,
                **kwargs  # Additional data like x, y coordinates, etc.
            }
            self.recorded_data.append(data_point)

    def save_recording_to_csv(self):
        """Save out recorded_data → CSV and then emit signal."""
        if not getattr(self, "recorded_data", None):
            return

        import os, time, csv
        rec_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "recordings")
        )
        os.makedirs(rec_dir, exist_ok=True)

        MODE_CODES = {
            "Relative Distance":  "distance_01",
            "Relative Angle":     "angle_02",
            "Angular Position":   "angular_position_03",
        }
        code = MODE_CODES.get(
            self.current_graph_mode,
            self.current_graph_mode.lower().replace(" ", "_")
        )
        timestr = time.strftime("%Y-%m-%d_%H-%M", time.localtime())
        fname = f"{code}_{timestr}.csv"
        fullpath = os.path.join(rec_dir, fname)

        with open(fullpath, "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["timestamp", "value"])
            for entry in self.recorded_data:
                # handle dict entries
                if isinstance(entry, dict):
                    ts = entry.get("timestamp")
                    val = entry.get("value")
                # or sequence entries
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    ts, val = entry[:2]
                else:
                    continue

                try:
                    writer.writerow([float(ts), float(val)])
                except Exception:
                    continue

        print(f"[INFO] ✅ Recording saved to {fullpath}")
        self.recording_saved.emit(fullpath)

    def exit_graph(self):
        # Stop recording if active
        if self.is_recording:
            self.toggle_recording()  # This will save any recorded data
        
        # Reset state
        self.current_graph_mode = None
        
        if self.graph_widget:
            self.graph_widget.setParent(None)
            self.graph_widget = None
        if self.exit_graph_btn:
            self.exit_graph_btn.setParent(None)
        self.record_btn.setParent(None)
        self.duration_dropdown.setParent(None)
        self.graph_display_layout.addWidget(self.graph_display_placeholder)


