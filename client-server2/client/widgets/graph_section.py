from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox, QSizePolicy # Changed QSpinBox to QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter
import time
import threading
import pandas as pd 
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
import csv # Ensure csv is imported if not already

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
    graph_update_frequency_changed = pyqtSignal(float) # Changed to float for QDoubleSpinBox
    payload_recording_started = pyqtSignal(str) # New: Emits current_graph_mode
    payload_recording_stopped = pyqtSignal()    # New: Signals recording has stopped

    def __init__(self, record_btn: QPushButton, duration_dropdown: QComboBox, parent=None): # Or load_graph if style is there
        super().__init__(parent)
        self.setObjectName("GraphSection")

        # ── Store live‐value labels ───────────────────────────────────────
        self.live_labels = {}

        self.graph_display_layout = QVBoxLayout()
        self.setLayout(self.graph_display_layout)

        self.graph_display_placeholder = QWidget()
        self.placeholder_layout = QVBoxLayout(self.graph_display_placeholder)
        self.placeholder_layout.setContentsMargins(10, 10, 10, 10)
        self.placeholder_layout.setSpacing(15)
        # center everything
        self.placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # add a header label
        header = QLabel("Select Payload Mode")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"""
            QLabel {{
                color: {BOX_TITLE_COLOR};
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                padding: 8px 0;
            }}
        """)
        self.placeholder_layout.addWidget(header)

        self.graph_modes = ["DISTANCE MEASURING MODE", "SCANNING MODE", "SPIN MODE"]
        self.select_buttons = {}

        # Recording state tracking
        self.is_recording = False
        self.recorded_data = []
        self.current_graph_mode = None  # Track which graph is currently active
        self.recording_start_time = None

        # ── replace old single‐column button loop with button+label rows ──
        for mode in self.graph_modes:
            row = QHBoxLayout()
            # mode button
            btn = QPushButton(mode)
            color = GRAPH_MODE_COLORS[mode]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BOX_BACKGROUND};
                    color: {TEXT_COLOR};
                    border: {BORDER_WIDTH}px solid {color};
                    border-radius: {BORDER_RADIUS}px;
                    padding: 4px 12px;
                    font-size: {FONT_SIZE_NORMAL}pt;
                    font-family: {FONT_FAMILY};
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: black;
                }}
            """)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(int(BUTTON_HEIGHT * 1.8))
            btn.clicked.connect(lambda _, m=mode: self.load_graph(m))

            # live‐value label, boxed in button‐color border + matching text
            lbl = QLabel("0.0")
            lbl.setFixedWidth(60)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                background-color: {BOX_BACKGROUND};
                border: {BORDER_WIDTH}px solid {color};
                border-radius: {BORDER_RADIUS}px;
                color: {color};
                font-size: {FONT_SIZE_LABEL}pt;
                padding: 2px;
            """)

            # pack them
            row.addWidget(btn)
            row.addWidget(lbl)
            self.placeholder_layout.addLayout(row)

            # keep references
            self.select_buttons[mode] = btn
            self.live_labels[mode]   = lbl

        self.graph_display_layout.addWidget(self.graph_display_placeholder)

        self.record_btn = record_btn
        self.duration_dropdown = duration_dropdown
        self.graph_widget = None
        self.exit_graph_btn = None
        self.shared_start_time = None

        # For frequency control
        self.freq_label = None
        self.freq_spinbox = None

        # Connect the record button to toggle recording
        self.record_btn.clicked.connect(self.toggle_recording)

    def apply_sci_fi_button_style(self, button: QPushButton, color=BOX_BACKGROUND):
        button.setStyleSheet(sci_fi_button_style(color))

    def load_graph(self, mode):
        self.graph_display_placeholder.setParent(None)
        
        # Set the current graph mode
        self.current_graph_mode = mode

        if mode == "DISTANCE MEASURING MODE":
            self.graph_widget = RelativeDistancePlotter()
        elif mode == "SCANNING MODE":
            self.graph_widget = RelativeAnglePlotter()
        elif mode == "SPIN MODE":
            self.graph_widget = AngularPositionPlotter()
        else:
            return

        self.shared_start_time = time.time()
        self.graph_widget.start_time = self.shared_start_time
        self.graph_widget.setFixedSize(500, 300)  # Larger graph size

        # ── hook the frequency‐spinbox to this plotter’s redraw rate ───────────
        self.graph_update_frequency_changed.connect(self.graph_widget.set_redraw_rate)

        # Create a horizontal layout for graph and buttons
        graph_and_btns_layout = QHBoxLayout()
        graph_and_btns_layout.setContentsMargins(0, 0, 0, 0)
        graph_and_btns_layout.setSpacing(18)

        # Add the graph widget (left)
        graph_and_btns_layout.addWidget(self.graph_widget, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Stack buttons vertically, left-aligned and vertically centered
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(2)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ── Detail live‐value label for the selected mode ───────────────
        color = GRAPH_MODE_COLORS[mode]
        detail_label = QLabel("0.0")
        detail_label.setFixedWidth(120)  # Increased from 60 to accommodate more text
        detail_label.setFixedHeight(160)  # Increased height for multiple lines
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_label.setWordWrap(True)   # Enable word wrapping for multi-line text
        detail_label.setStyleSheet(f"""
            background-color: {BOX_BACKGROUND};
            border: {BORDER_WIDTH}px solid {color};
            border-radius: {BORDER_RADIUS}px;
            color: {color};
            font-size: {FONT_SIZE_LABEL}pt;
            font-family: {FONT_FAMILY};
            padding: 4px;
        """)
        # keep for updates
        self.current_detail_label = detail_label
        btn_layout.addWidget(detail_label, alignment=Qt.AlignmentFlag.AlignLeft)

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
        # Style for SpinBox and its Label
        control_style = f"""
            QLabel {{
                color: {LABEL_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_LABEL}pt;
                padding-top: 4px; /* Align better with spinbox */
                /* Add other QLabel specific styles if needed */
            }}
            QDoubleSpinBox {{
                background-color: {BOX_BACKGROUND}; 
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR}; 
                border-radius: {BORDER_RADIUS}px;
                padding: 1px 3px; /* Adjust padding as needed for text alignment */
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
                /* min-height: {int(BUTTON_HEIGHT * 0.9)}px; /* Optional: ensure a minimum height */
                /* padding-right: 20px; /* Only if needed to reserve space for default buttons, usually not required */
            }}

            /* 
            All custom styling for ::up-button, ::down-button, ::up-arrow, ::down-arrow 
            has been removed from here. The QDoubleSpinBox will now use the default 
            system appearance for its buttons and arrows.
            
            If you wish to style the hover/pressed state of these default buttons,
            you might be able to add simple rules like:
            QDoubleSpinBox::up-button:hover {{ background-color: {BUTTON_HOVER}; }}
            QDoubleSpinBox::down-button:hover {{ background-color: {BUTTON_HOVER}; }}
            However, for a truly default look, omit these as well.
            */
        """


        # Reset record button text when loading new graph
        self.record_btn.setText("Record")
        self.is_recording = False
        self.record_btn.setFixedHeight(int(BUTTON_HEIGHT))
        self.record_btn.setFixedWidth(120)  # Increased from default
        self.record_btn.setStyleSheet(button_style)
        btn_layout.addWidget(self.record_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.duration_dropdown.setFixedHeight(int(BUTTON_HEIGHT))
        self.duration_dropdown.setFixedWidth(120)  # Increased from default
        # self.duration_dropdown.setStyleSheet(button_style) # Apply similar style if visible
        btn_layout.addWidget(self.duration_dropdown, alignment=Qt.AlignmentFlag.AlignLeft)

        # Graph Update Frequency Control
        self.freq_spinbox = QDoubleSpinBox() 
        self.freq_spinbox.setRange(1, 50.0)
        self.freq_spinbox.setSingleStep(1)   
        self.freq_spinbox.setDecimals(1)       
        self.freq_spinbox.setValue(30.0)        
        self.freq_spinbox.setSuffix(" Hz")

        # Apply the "modern" spinbox style from camera_settings.py:
        self.freq_spinbox.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 1px 3px;
                min-height: {BUTTON_HEIGHT - 2}px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
            QDoubleSpinBox:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777;
                border: {BORDER_WIDTH}px solid #555;
            }}
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {{
                background-color: {BUTTON_COLOR};
                border: none;
                border-radius: {int(BORDER_RADIUS/2)}px;
                width: 12px;
            }}
            QDoubleSpinBox::up-button {{
                subcontrol-position: top right;
                margin-right: 1px;
                margin-top: 1px;
            }}
            QDoubleSpinBox::down-button {{
                subcontrol-position: bottom right;
                margin-right: 1px;
                margin-bottom: 1px;
            }}
            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {{
                background-color: {BUTTON_HOVER};
            }}
            QDoubleSpinBox::up-arrow {{
                image: url(./client/widgets/icons/arrow_up_light.png);
                width: 4px; height: 6px;
            }}
            QDoubleSpinBox::down-arrow {{
                image: url(./client/widgets/icons/arrow_down_light.png);
                width: 4px; height: 6px;
            }}
        """)

        # Increased width for frequency spinbox
        self.freq_spinbox.setFixedHeight(int(BUTTON_HEIGHT))
        self.freq_spinbox.setFixedWidth(120)  # Increased from 72
        self.freq_spinbox.valueChanged.connect(self.on_frequency_changed)
        btn_layout.addWidget(self.freq_spinbox, alignment=Qt.AlignmentFlag.AlignLeft)

        # emit once to kick off the initial rate on our new widget
        self.on_frequency_changed(self.freq_spinbox.value())

        self.exit_graph_btn = QPushButton("← Back")
        self.exit_graph_btn.setFixedHeight(int(BUTTON_HEIGHT))
        self.exit_graph_btn.setFixedWidth(120)  # Increased from default
        self.exit_graph_btn.setStyleSheet(button_style)
        self.exit_graph_btn.clicked.connect(self.exit_graph)
        btn_layout.addWidget(self.exit_graph_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Add the button layout (right)
        graph_and_btns_layout.addLayout(btn_layout)

        # Add the combined layout to the main graph display layout
        self.graph_display_layout.addLayout(graph_and_btns_layout)

    def on_frequency_changed(self, value_hz: float): # value_hz is now float
        """Emits the new frequency when the spinbox changes."""
        self.graph_update_frequency_changed.emit(value_hz) # Emitting float
        print(f"[GraphSection] Update frequency set to: {value_hz:.1f} Hz via spinbox")

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
            self.payload_recording_started.emit(self.current_graph_mode) # Emit signal
            
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
            self.payload_recording_stopped.emit() # Emit signal
            
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
        # Ensure self.recorded_data exists and is not empty before proceeding
        if not hasattr(self, 'recorded_data') or not self.recorded_data:
            print("[WARNING] No data recorded for payload or 'recorded_data' attribute missing. CSV not saved.")
            return

        # import os, time, csv # Already imported or should be at the top
        rec_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "recordings")
        )
        os.makedirs(rec_dir, exist_ok=True)

        MODE_CODES = {
            "DISTANCE MEASURING MODE":  "distance_01",
            "SCANNING MODE":     "angle_02",
            "SPIN MODE":   "spin_03",
        }
        
        mode_str = str(self.current_graph_mode) if self.current_graph_mode else "unknown_mode"
        code = MODE_CODES.get(
            self.current_graph_mode, 
            mode_str.lower().replace(" ", "_")
        )
        # Recommended: Add seconds to timestr for more unique filenames
        timestr = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()) 
        fname = f"{code}_{timestr}.csv"
        fullpath = os.path.join(rec_dir, fname)

        rows_written = 0
        try:
            with open(fullpath, "w", newline="") as csvf:
                writer = csv.writer(csvf)
                # Determine headers dynamically or use fixed ones
                # For simplicity, using fixed "timestamp", "value" as per original structure
                # If your add_data_point adds more keys, you'd need to adjust headers
                headers = ["timestamp", "value"]
                if self.recorded_data and isinstance(self.recorded_data[0], dict):
                    # Attempt to get more complete headers from the first data point
                    # This assumes all data points have similar structure
                    all_keys = list(self.recorded_data[0].keys())
                    # Ensure 'timestamp' and 'value' are first if they exist
                    if 'timestamp' in all_keys:
                        all_keys.pop(all_keys.index('timestamp'))
                        all_keys.insert(0, 'timestamp')
                    if 'value' in all_keys:
                        all_keys.pop(all_keys.index('value'))
                        # Insert 'value' after 'timestamp' if 'timestamp' is present and first
                        insert_idx = 1 if headers[0] == 'timestamp' and 'timestamp' in all_keys else 0
                        all_keys.insert(insert_idx, 'value')
                    headers = all_keys
                
                writer.writerow(headers)

                for entry in self.recorded_data:
                    if isinstance(entry, dict):
                        # Write row based on header order
                        row_to_write = [entry.get(h) for h in headers]
                        writer.writerow(row_to_write)
                        rows_written +=1
                    elif isinstance(entry, (list, tuple)) and len(entry) >= 2 and headers == ["timestamp", "value"]: # Fallback for old list format
                        ts, val = entry[:2]
                        try:
                            writer.writerow([float(ts), float(val)])
                            rows_written +=1
                        except (ValueError, TypeError):
                            print(f"[DEBUG] Skipping malformed list/tuple entry during CSV save: {entry}")
                            continue
                    else:
                        print(f"[DEBUG] Skipping malformed entry during CSV save: {entry}")
                        continue
            
            if rows_written > 0:
                print(f"[INFO] ✅ Payload recording saved to {fullpath} with {rows_written} data points.")
                self.recording_saved.emit(fullpath)
            else:
                print(f"[WARNING] Payload CSV file created at {fullpath}, but no valid data points were written.")

        except IOError as e:
            print(f"[ERROR] Could not write payload to CSV file {fullpath}: {e}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during payload CSV saving: {e}")

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
            self.exit_graph_btn.setParent(None) # Remove from layout
            # self.exit_graph_btn = None # Optional: clear reference
        
        # Remove frequency controls
        if self.freq_label:
            self.freq_label.setParent(None)
            # self.freq_label = None
        if self.freq_spinbox:
            self.freq_spinbox.setParent(None)
            # self.freq_spinbox = None

        # ── remove the detail live‐value label if present ───────────────
        if hasattr(self, "current_detail_label") and self.current_detail_label:
            self.current_detail_label.setParent(None)
            self.current_detail_label = None

        # Detach record_btn and duration_dropdown from this specific graph view's layout
        # They are managed by client3.py and passed in, so we just remove them from the current dynamic layout
        self.record_btn.setParent(None)
        self.duration_dropdown.setParent(None)

        # Clear the dynamic graph_and_btns_layout
        # Assuming graph_and_btns_layout is the last item added to self.graph_display_layout
        if self.graph_display_layout.count() > 1: 
             item = self.graph_display_layout.takeAt(self.graph_display_layout.count() -1)
             if item is not None:
                 widget = item.widget() or item.layout()
                 if widget:
                     widget.setParent(None)

        # ── re‐insert the placeholder (buttons + small live‐boxes) ─────────
        self.graph_display_layout.addWidget(self.graph_display_placeholder)


