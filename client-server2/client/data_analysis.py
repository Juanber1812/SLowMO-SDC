import os
import time
import traceback
import pandas as pd
import numpy as np
import warnings
import csv

# Crucial Qt Imports:
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QTextEdit, QFileDialog, QStackedWidget, QSizePolicy, QMessageBox,
    QButtonGroup, QCheckBox, QLineEdit
)

from theme import (
    BACKGROUND, BOX_BACKGROUND, PLOT_BACKGROUND, STREAM_BACKGROUND,
    TEXT_COLOR, TEXT_SECONDARY, BOX_TITLE_COLOR, LABEL_COLOR, 
    GRID_COLOR, TICK_COLOR, PLOT_LINE_PRIMARY, PLOT_LINE_SECONDARY, PLOT_LINE_ALT,
    BUTTON_COLOR, BUTTON_HOVER, BUTTON_DISABLED, BUTTON_TEXT,BUTTON_HEIGHT,
    BORDER_COLOR, BORDER_ERROR, BORDER_HIGHLIGHT,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LABEL, FONT_SIZE_TITLE,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR, SECOND_COLUMN,
    BORDER_WIDTH, BORDER_RADIUS, PADDING_NORMAL, PADDING_LARGE
)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor

from scipy.signal import savgol_filter, butter, filtfilt, find_peaks, peak_prominences

# Matplotlib imports for plotting
try:
    import matplotlib
    matplotlib.use('Qt5Agg')  # Use Qt backend
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("[WARNING] Matplotlib not available. Plotting will be disabled.")

# helper
def style_button(btn, color=BUTTON_TEXT):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {color};
            border: 2px solid {color};
            border-radius: 4px;
            padding: 4px 8px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_LABEL}pt;
        }}
        QPushButton:hover {{ background-color: {BUTTON_HOVER}; color: black; }}
        QPushButton:disabled {{ background-color: #333; color: #555; }}
        QPushButton:checked {{ background-color: {BUTTON_COLOR}; color: black; }}
    """)

def style_modern_spinbox(spinbox):
    """Apply modern styling to spinboxes - matching camera_settings crop spinbox style"""
    spinbox.setStyleSheet(f"""
        QSpinBox, QDoubleSpinBox {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 1px 3px;
            min-height: {BUTTON_HEIGHT - 2}px;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_NORMAL}pt;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {BUTTON_COLOR};
        }}
        QSpinBox:disabled, QDoubleSpinBox:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
            border: {BORDER_WIDTH}px solid #555;
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            background-color: {BUTTON_COLOR};
            border: none;
            border-radius: {int(BORDER_RADIUS / 2)}px;
            width: 18px;
            subcontrol-position: top right;
            margin-right: 2px;
            margin-top: 2px;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {BUTTON_COLOR};
            border: none;
            border-radius: {int(BORDER_RADIUS / 2)}px;
            width: 18px;
            subcontrol-position: bottom right;
            margin-right: 2px;
            margin-bottom: 2px;
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {BUTTON_HOVER};
        }}
        QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
        QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled {{
            background-color: {BUTTON_DISABLED};
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            width: 10px;
            height: 10px;
            background-color: transparent;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            width: 10px;
            height: 10px;
            background-color: transparent;
        }}
        QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
        QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
            background-color: #777;
        }}
    """)

class DataAnalysisTab(QWidget):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.full_df = None
        self.metrics = {}
        
        # Filter states - independent for each type
        self.distance_filters = {
            'savgol_enabled': False,
            'butter_enabled': False,
            'kalman_enabled': False
        }
        self.velocity_filters = {
            'savgol_enabled': False,
            'butter_enabled': False,
            'kalman_enabled': False
        }
        
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {BACKGROUND}; color: {TEXT_COLOR};")
        layout = QVBoxLayout(self)
        layout.setSpacing(8); layout.setContentsMargins(8,8,8,8)

        # ── top controls ─────────────────────────────────────────────────
        ctr = QWidget()
        ctr.setStyleSheet(f"background-color: {BOX_BACKGROUND}; border-radius: {BORDER_RADIUS}px;")
        ctr.setFixedHeight(220)  # Increased height for better spacing
        ctr_l = QHBoxLayout(ctr)
        ctr_l.setSpacing(16); ctr_l.setContentsMargins(12,12,12,12)  # Increased spacing
        
        # File loader
        grp = QGroupBox("Load CSV Data")
        grp.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {BOX_BACKGROUND};
                margin-top: 8px;
                color: {TEXT_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                color: {BOX_TITLE_COLOR};
            }}
        """)
        gl = QVBoxLayout(grp); gl.setSpacing(10); gl.setContentsMargins(12,15,12,12)  # Better spacing
        self.load_btn = QPushButton("Browse & Load CSV")
        style_button(self.load_btn)
        self.load_btn.setFixedHeight(32)  # Taller button
        self.load_btn.clicked.connect(self.load_csv)
        self.csv_label = QLabel("No file loaded")
        self.csv_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_NORMAL}pt;
                font-family: {FONT_FAMILY};
                background-color: {BOX_BACKGROUND};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 8px;
                margin: 2px 0px;
            }}
        """)
        self.csv_label.setWordWrap(True)
        self.csv_label.setMaximumHeight(70)  # Increased height

        gl.addWidget(self.load_btn); gl.addWidget(self.csv_label)
        grp.setFixedWidth(220)  # Increased width
        ctr_l.addWidget(grp)

        # Mode selector & Time Range
        mode_time_container = QWidget()
        mode_time_layout = QVBoxLayout(mode_time_container)
        mode_time_layout.setContentsMargins(0,0,0,0)
        mode_time_layout.setSpacing(10)  # Better spacing
        
        mode_selector_layout = QHBoxLayout()
        mode_selector_layout.setSpacing(8)
        lbl_mode = QLabel("Analysis Mode:")
        lbl_mode.setStyleSheet(f"font-size:{FONT_SIZE_LABEL}pt; color: {TEXT_COLOR}; font-family: {FONT_FAMILY};")
        mode_selector_layout.addWidget(lbl_mode)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "DISTANCE MEASURING MODE",
            "SCANNING MODE",
            "SPIN MODE"
        ])
        self.mode_combo.setFixedWidth(200)  # Increased width
        self.mode_combo.setFixedHeight(28)  # Fixed height
        self.mode_combo.setStyleSheet(f"""
            QComboBox {{
                background-color:{BOX_BACKGROUND}; 
                color: {TEXT_COLOR}; 
                border: 1px solid {BORDER_COLOR}; 
                padding: 4px 8px;
                font-size: {FONT_SIZE_NORMAL}pt;
                font-family: {FONT_FAMILY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
        """)
        self.mode_combo.currentIndexChanged.connect(self.update_plots)
        mode_selector_layout.addWidget(self.mode_combo)
        mode_time_layout.addLayout(mode_selector_layout)

        rng = QGroupBox("Time Range")
        rng.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {BOX_BACKGROUND};
                margin-top: 8px;
                color: {TEXT_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                color: {BOX_TITLE_COLOR};
            }}
        """)
        gr = QGridLayout(rng); gr.setSpacing(10); gr.setContentsMargins(12,15,12,12)  # Better spacing
        self.start_spin = QDoubleSpinBox(); self.end_spin = QDoubleSpinBox()
        for w, label_text in ((self.start_spin, "Start (s):"), (self.end_spin, "End (s):")):
            w.setDecimals(1); w.setFixedWidth(100); w.setFixedHeight(32)  # Larger size
            w.setSingleStep(0.1)  # Modern 0.1 steps
            w.valueChanged.connect(self.update_plots)
            style_modern_spinbox(w)
            label_widget = QLabel(label_text)
            label_widget.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
            if label_text == "Start (s):":
                gr.addWidget(label_widget,0,0); gr.addWidget(w,0,1)
            else:
                gr.addWidget(label_widget,1,0); gr.addWidget(w,1,1)
        
        # Initially disable until CSV is loaded
        self.start_spin.setEnabled(False)
        self.end_spin.setEnabled(False)

        mode_time_layout.addWidget(rng)
        ctr_l.addWidget(mode_time_container)

        # --- Distance/Angle Filters ---
        self._create_filter_group(ctr_l, "Distance/Angle Filters", "distance")

        # --- Velocity Filters ---
        self._create_filter_group(ctr_l, "Velocity Filters", "velocity")

        layout.addWidget(ctr)

        # ── plots + metrics ─────────────────────────────────────────────
        content = QHBoxLayout(); content.setSpacing(12)
        
        # plots pane
        self.plots_container = QWidget()
        self.plots_container.setStyleSheet(f"""
            QWidget {{
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                background-color: {BOX_BACKGROUND};
            }}
        """)
        plot_area_layout = QVBoxLayout(self.plots_container)
        plot_area_layout.setSpacing(6)
        plot_area_layout.setContentsMargins(8, 8, 8, 8)
        
        content.addWidget(self.plots_container, stretch=5)
        
        # metrics pane
        metrics_container = QWidget()
        metrics_layout = QVBoxLayout(metrics_container)
        metrics_layout.setSpacing(4)
        metrics_layout.setContentsMargins(6,6,6,6)
        metrics_container.setMinimumWidth(220)
        metrics_container.setMaximumWidth(260)  # Increased width
        metrics_container.setStyleSheet(f"background-color: {BOX_BACKGROUND}; border-radius: {BORDER_RADIUS}px;")

        # Analysis Results Section
        title_label = QLabel("Analysis Results")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {BOX_TITLE_COLOR};
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                padding: 6px 0px;
                border-bottom: 1px solid {BORDER_COLOR};
                margin-bottom: 6px;
            }}
        """)
        metrics_layout.addWidget(title_label)

        # Current Analysis Display
        self.metrics_txt = QTextEdit()
        self.metrics_txt.setReadOnly(True)
        self.metrics_txt.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {FONT_SIZE_NORMAL-1}pt;
                line-height: 1.3;
                padding: 4px;
            }}
        """)
        self.metrics_txt.setFixedHeight(180)  # Reduced height
        self.metrics_txt.setText("Load a CSV file to see analysis...")
        metrics_layout.addWidget(self.metrics_txt)

        # Data Collection Section
        collection_title = QLabel("Data Collection")
        collection_title.setStyleSheet(f"""
            QLabel {{
                color: {BOX_TITLE_COLOR};
                font-size: {FONT_SIZE_TITLE}pt;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                padding: 6px 0px;
                border-bottom: 1px solid {BORDER_COLOR};
                margin: 8px 0px 6px 0px;
            }}
        """)
        metrics_layout.addWidget(collection_title)

        # Record buttons
        record_buttons_widget = QWidget()
        record_layout = QVBoxLayout(record_buttons_widget)
        record_layout.setSpacing(4)
        record_layout.setContentsMargins(0,0,0,0)

        # Sensor type selection
        sensor_layout = QHBoxLayout()
        sensor_label = QLabel("Sensor:")
        sensor_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        sensor_layout.addWidget(sensor_label)
        
        self.sensor_type_combo = QComboBox()
        self.sensor_type_combo.addItems(["Camera", "Lidar"])
        self.sensor_type_combo.setFixedWidth(120)
        self.sensor_type_combo.setStyleSheet(f"""
            QComboBox {{
                background-color:{BOX_BACKGROUND}; 
                color: {TEXT_COLOR}; 
                border: 1px solid {BORDER_COLOR}; 
                padding: 4px 8px;
                font-size: {FONT_SIZE_NORMAL}pt;
                font-family: {FONT_FAMILY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
        """)
        sensor_layout.addWidget(self.sensor_type_combo)
        record_layout.addLayout(sensor_layout)
        
        self.record_distance_btn = QPushButton("Record Distance")
        self.record_distance_btn.setFixedHeight(24)
        self.record_distance_btn.setFixedWidth(120)
        style_button(self.record_distance_btn, SUCCESS_COLOR)
        self.record_distance_btn.clicked.connect(self._record_distance)
        self.record_distance_btn.setEnabled(False)
        record_layout.addWidget(self.record_distance_btn)
        
        self.record_velocity_btn = QPushButton("Record Gradient")
        self.record_velocity_btn.setFixedHeight(24)
        self.record_velocity_btn.setFixedWidth(120)
        style_button(self.record_velocity_btn, WARNING_COLOR)
        self.record_velocity_btn.clicked.connect(self._record_velocity)
        self.record_velocity_btn.setEnabled(False)
        record_layout.addWidget(self.record_velocity_btn)
        
        # Add manual input box and submit button
        manual_input_layout = QHBoxLayout()
        manual_label = QLabel("Manual Input:")
        manual_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        manual_input_layout.addWidget(manual_label)
        
        self.manual_value_input = QLineEdit()
        self.manual_value_input.setPlaceholderText("Enter value")
        self.manual_value_input.setFixedWidth(100)
        self.manual_value_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 4px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
            QLineEdit:focus {{
                border: 2px solid {BUTTON_COLOR};
            }}
        """)
        manual_input_layout.addWidget(self.manual_value_input)
        
        self.manual_submit_btn = QPushButton("Submit Manual")
        style_button(self.manual_submit_btn)
        self.manual_submit_btn.setFixedHeight(28)
        self.manual_submit_btn.clicked.connect(self.manual_submit_manual_value)
        manual_input_layout.addWidget(self.manual_submit_btn)
        record_layout.addLayout(manual_input_layout)
        
        # Rotation speed record button
        self.record_rotation_btn = QPushButton("Record Rotation")
        self.record_rotation_btn.setFixedHeight(24)
        self.record_rotation_btn.setFixedWidth(120)
        style_button(self.record_rotation_btn, ERROR_COLOR)
        self.record_rotation_btn.clicked.connect(self._record_rotation)
        self.record_rotation_btn.setEnabled(False)
        record_layout.addWidget(self.record_rotation_btn)
        
        metrics_layout.addWidget(record_buttons_widget)

        # CSV File Management
        csv_mgmt_widget = QWidget()
        csv_mgmt_layout = QVBoxLayout(csv_mgmt_widget)
        csv_mgmt_layout.setSpacing(4)
        csv_mgmt_layout.setContentsMargins(0,0,0,0)

        # CSV filename input
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(4)
        
        filename_label = QLabel("CSV:")
        filename_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        filename_layout.addWidget(filename_label)
        
        self.csv_filename_input = QLineEdit("test_data.csv")
        self.csv_filename_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 4px;
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
            QLineEdit:focus {{
                border: 2px solid {BUTTON_COLOR};
            }}
        """)
        filename_layout.addWidget(self.csv_filename_input)
        csv_mgmt_layout.addLayout(filename_layout)

        # CSV management buttons
        csv_btn_layout = QHBoxLayout()
        csv_btn_layout.setSpacing(4)
        
        self.new_csv_btn = QPushButton("New")
        style_button(self.new_csv_btn)
        self.new_csv_btn.setFixedHeight(28)
        self.new_csv_btn.clicked.connect(self._new_csv_file)
        csv_btn_layout.addWidget(self.new_csv_btn)
        
        self.save_csv_btn = QPushButton("Save As")
        style_button(self.save_csv_btn)
        self.save_csv_btn.setFixedHeight(28)
        self.save_csv_btn.clicked.connect(self._save_csv_as)
        self.save_csv_btn.setEnabled(False)
        csv_btn_layout.addWidget(self.save_csv_btn)
        
        csv_mgmt_layout.addLayout(csv_btn_layout)
        metrics_layout.addWidget(csv_mgmt_widget)

        # Current CSV Data Display
        csv_data_title = QLabel("Collected Data")
        csv_data_title.setStyleSheet(f"""
            QLabel {{
                color: {BOX_TITLE_COLOR};
                font-size: {FONT_SIZE_LABEL}pt;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                padding: 4px 0px;
                margin: 6px 0px 4px 0px;
            }}
        """)
        metrics_layout.addWidget(csv_data_title)

        self.csv_data_display = QTextEdit()
        self.csv_data_display.setReadOnly(True)
        self.csv_data_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {FONT_SIZE_NORMAL-2}pt;
                padding: 4px;
            }}
        """)
        self.csv_data_display.setMaximumHeight(100)
        self.csv_data_display.setText("No data collected yet...")
        metrics_layout.addWidget(self.csv_data_display)
        
        metrics_layout.addStretch(1)
        content.addWidget(metrics_container, stretch=0)
        layout.addLayout(content)

        # Initialize collection data storage
        self.collection_data = []
        self.current_csv_path = None

    def _create_filter_group(self, parent_layout, title, filter_type):
        """Create a filter group for distance or velocity filters"""
        filter_container = QWidget()
        filter_layout = QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)  # Better spacing

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color:{TEXT_COLOR}; 
            font-size:{FONT_SIZE_LABEL}pt; 
            font-family:{FONT_FAMILY}; 
            font-weight: bold;
            padding: 4px 0px;
        """)
        filter_layout.addWidget(title_label)

        # Filter checkboxes and parameters
        filters_widget = QWidget()
        filters_grid = QGridLayout(filters_widget)
        filters_grid.setSpacing(8)  # Increased spacing
        filters_grid.setContentsMargins(0, 0, 0, 0)

        row = 0

        # SavGol Filter
        savgol_cb = QCheckBox("SavGol")
        savgol_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {BORDER_COLOR};
                border-radius: 3px;
                background-color: {BOX_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {BUTTON_COLOR};
                border-color: {BUTTON_COLOR};
            }}
            QCheckBox::indicator:hover {{
                border-color: {BUTTON_HOVER};
            }}
        """)
        savgol_cb.toggled.connect(lambda checked, ft=filter_type: self._toggle_filter(ft, 'savgol', checked))
        filters_grid.addWidget(savgol_cb, row, 0)

        # SavGol parameters
        savgol_params = QWidget()
        savgol_layout = QHBoxLayout(savgol_params)
        savgol_layout.setContentsMargins(0, 0, 0, 0)
        savgol_layout.setSpacing(6)  # Better spacing

        win_label = QLabel("Win:")
        win_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        savgol_layout.addWidget(win_label)
        sg_win = QSpinBox()
        sg_win.setRange(3, 101)
        sg_win.setSingleStep(2)
        sg_win.setValue(11)
        sg_win.setFixedWidth(65)  # Wider
        sg_win.setFixedHeight(28)  # Taller
        style_modern_spinbox(sg_win)
        sg_win.valueChanged.connect(self.update_plots)
        savgol_layout.addWidget(sg_win)

        poly_label = QLabel("Poly:")
        poly_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        savgol_layout.addWidget(poly_label)
        sg_poly = QSpinBox()
        sg_poly.setRange(1, 5)
        sg_poly.setValue(2)
        sg_poly.setFixedWidth(50)  # Wider
        sg_poly.setFixedHeight(28)  # Taller
        style_modern_spinbox(sg_poly)
        sg_poly.valueChanged.connect(self.update_plots)
        savgol_layout.addWidget(sg_poly)

        filters_grid.addWidget(savgol_params, row, 1)

        # Store references for savgol filter
        setattr(self, f"{filter_type}_savgol_cb", savgol_cb)
        setattr(self, f"{filter_type}_sg_win", sg_win)
        setattr(self, f"{filter_type}_sg_poly", sg_poly)

        row += 1

        # Butterworth Filter
        butter_cb = QCheckBox("Butter")
        butter_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {BORDER_COLOR};
                border-radius: 3px;
                background-color: {BOX_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {BUTTON_COLOR};
                border-color: {BUTTON_COLOR};
            }}
            QCheckBox::indicator:hover {{
                border-color: {BUTTON_HOVER};
            }}
        """)
        butter_cb.toggled.connect(lambda checked, ft=filter_type: self._toggle_filter(ft, 'butter', checked))
        filters_grid.addWidget(butter_cb, row, 0)

        # Butterworth parameters
        butter_params = QWidget()
        butter_layout = QHBoxLayout(butter_params)
        butter_layout.setContentsMargins(0, 0, 0, 0)
        butter_layout.setSpacing(6)  # Better spacing

        bw_type = QComboBox()
        bw_type.addItems(["Low", "High"])
        bw_type.setFixedWidth(65)  # Wider
        bw_type.setFixedHeight(28)  # Taller
        bw_type.setStyleSheet(f"""
            QComboBox {{
                background-color:{BOX_BACKGROUND}; 
                color: {TEXT_COLOR}; 
                border: 1px solid {BORDER_COLOR}; 
                padding: 2px 4px;
                font-size: {FONT_SIZE_NORMAL}pt;
                font-family: {FONT_FAMILY};
            }}
        """)
        bw_type.currentTextChanged.connect(self.update_plots)
        butter_layout.addWidget(bw_type)

        fc_label = QLabel("fc:")
        fc_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        butter_layout.addWidget(fc_label)
        bw_fc = QDoubleSpinBox()
        bw_fc.setRange(0.1, 100.0)
        bw_fc.setSingleStep(0.1)
        bw_fc.setDecimals(1)
        bw_fc.setValue(1.0)
        bw_fc.setFixedWidth(70)  # Wider
        bw_fc.setFixedHeight(28)  # Taller
        style_modern_spinbox(bw_fc)
        bw_fc.valueChanged.connect(self.update_plots)
        butter_layout.addWidget(bw_fc)

        ord_label = QLabel("Ord:")
        ord_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
        butter_layout.addWidget(ord_label)
        bw_ord = QSpinBox()
        bw_ord.setRange(1, 10)
        bw_ord.setValue(2)
        bw_ord.setFixedWidth(50)  # Wider
        bw_ord.setFixedHeight(28)  # Taller
        style_modern_spinbox(bw_ord)
        bw_ord.valueChanged.connect(self.update_plots)
        butter_layout.addWidget(bw_ord)

        filters_grid.addWidget(butter_params, row, 1)

        # Store references for butter filter
        setattr(self, f"{filter_type}_butter_cb", butter_cb)
        setattr(self, f"{filter_type}_bw_type", bw_type)
        setattr(self, f"{filter_type}_bw_fc", bw_fc)
        setattr(self, f"{filter_type}_bw_ord", bw_ord)

        row += 1

        # For velocity filters only, add two spin boxes for min and max velocity filtering
        if filter_type == "velocity":
            y_range_container = QWidget()
            y_range_layout = QHBoxLayout(y_range_container)
            y_range_layout.setContentsMargins(0, 0, 0, 0)
            y_range_layout.setSpacing(4)
            
            # Min velocity spin box
            y_min_label = QLabel("Vel Min:")
            y_min_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
            y_range_layout.addWidget(y_min_label)
            self.velocity_min_spin = QDoubleSpinBox()
            self.velocity_min_spin.setRange(-360.0, 360.0)
            self.velocity_min_spin.setSingleStep(0.1)
            self.velocity_min_spin.setDecimals(1)
            self.velocity_min_spin.setValue(-100.0)  # default minimum threshold
            self.velocity_min_spin.setFixedWidth(70)
            self.velocity_min_spin.setFixedHeight(28)
            style_modern_spinbox(self.velocity_min_spin)
            self.velocity_min_spin.valueChanged.connect(self.update_plots)
            y_range_layout.addWidget(self.velocity_min_spin)
            
            # Max velocity spin box
            y_max_label = QLabel("Vel Max:")
            y_max_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_NORMAL}pt;")
            y_range_layout.addWidget(y_max_label)
            self.velocity_max_spin = QDoubleSpinBox()
            self.velocity_max_spin.setRange(-360.0, 360.0)
            self.velocity_max_spin.setSingleStep(0.1)
            self.velocity_max_spin.setDecimals(1)
            self.velocity_max_spin.setValue(100.0)  # default maximum threshold
            self.velocity_max_spin.setFixedWidth(70)
            self.velocity_max_spin.setFixedHeight(28)
            style_modern_spinbox(self.velocity_max_spin)
            self.velocity_max_spin.valueChanged.connect(self.update_plots)
            y_range_layout.addWidget(self.velocity_max_spin)
            
            filter_layout.addWidget(y_range_container)

        # Line of Best Fit Checkbox
        if filter_type == "distance":
            bestfit_cb = QCheckBox("Line of Best Fit")
            bestfit_cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {TEXT_COLOR};
                    font-family: {FONT_FAMILY};
                    font-size: {FONT_SIZE_NORMAL}pt;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid {BORDER_COLOR};
                    border-radius: 3px;
                    background-color: {BOX_BACKGROUND};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {BUTTON_COLOR};
                    border-color: {BUTTON_COLOR};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {BUTTON_HOVER};
                }}
            """)
            bestfit_cb.toggled.connect(self.update_plots)
            filters_grid.addWidget(bestfit_cb, row, 0)
            setattr(self, f"{filter_type}_bestfit_cb", bestfit_cb)

        # Set column stretches to make better use of space
        filters_grid.setColumnStretch(0, 0)  # Checkbox column: fixed width
        filters_grid.setColumnStretch(1, 1)  # Parameters column: stretch
        
        filter_layout.addWidget(filters_widget)
        filter_layout.addStretch(1)
        parent_layout.addWidget(filter_container, stretch=1)

    def _toggle_filter(self, filter_type, filter_name, enabled):
        """Toggle filter on/off"""
        if filter_type == 'distance':
            self.distance_filters[f'{filter_name}_enabled'] = enabled
        else:  # velocity
            self.velocity_filters[f'{filter_name}_enabled'] = enabled
        self.update_plots()

    def load_csv(self):
        default_dir = os.path.join(os.path.dirname(__file__), "recordings")
        if not os.path.isdir(default_dir):
            default_dir = os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV",
            default_dir,
            "CSV Files (*.csv)"
        )
        if not fn: 
            return
        
        try:
            df = pd.read_csv(fn)
            if not {'timestamp','value'}.issubset(df.columns):
                QMessageBox.warning(self, "Invalid CSV",
                    "CSV must contain 'timestamp' and 'value' columns.")
                return
            
            df['relative_time'] = df['timestamp'] - df['timestamp'].min()
            self.full_df = df
            self.csv_label.setText(os.path.basename(fn))
            
            mn, mx = df.relative_time.min(), df.relative_time.max()
            for spin, val in ((self.start_spin,mn),(self.end_spin,mx)):
                spin.blockSignals(True)
                spin.setRange(mn, mx)
                spin.setValue(val)
                spin.blockSignals(False)
                spin.setEnabled(True)
    
            self._make_canvases()
            
            if hasattr(self.parent(), 'tab_widget'):
                idx = self.parent().tab_widget.indexOf(self)
                self.parent().tab_widget.setCurrentIndex(idx)
        
            self.update_plots()
        
            print(f"[INFO] Loaded CSV: {os.path.basename(fn)} with {len(df)} data points")
        
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load CSV file:\n{e}")
            print(f"[ERROR] Failed to load CSV: {e}")

    def _make_canvases(self):
        """Create matplotlib canvases for plotting"""
        if not MATPLOTLIB_AVAILABLE:
            return
            
        l = self.plots_container.layout() 
        # clear any old widgets
        for i in reversed(range(l.count())):
            w = l.takeAt(i).widget()
            if w: w.deleteLater()
        
        # Create matplotlib figures and canvases
        self.raw_fig = Figure(figsize=(8, 4), facecolor=PLOT_BACKGROUND)
        self.raw_canvas = FigureCanvas(self.raw_fig)
        self.raw_canvas.setStyleSheet(f"background-color: {PLOT_BACKGROUND};")
        
        self.vel_fig = Figure(figsize=(8, 4), facecolor=PLOT_BACKGROUND)
        self.vel_canvas = FigureCanvas(self.vel_fig)
        self.vel_canvas.setStyleSheet(f"background-color: {PLOT_BACKGROUND};")
        
        l.addWidget(self.raw_canvas, 1)
        l.addWidget(self.vel_canvas, 1)

    def apply_savgol(self, data, window_length, poly_order):
        """Apply Savitzky-Golay filter"""
        try:
            if len(data) <= window_length:
                return data.copy()
            # Ensure window_length is odd
            if window_length % 2 == 0:
                window_length += 1
            return savgol_filter(data, window_length, poly_order)
        except Exception as e:
            print(f"[ERROR] SavGol filter failed: {e}")
            return data.copy()

    def apply_butter(self, data, fs, cutoff, order, btype='low'):
        """Apply Butterworth filter with improved error handling"""
        try:
            if len(data) < 10:  # Minimum data points needed
                print(f"[WARNING] Butterworth filter skipped: insufficient data points ({len(data)} < 10)")
                return data.copy()
                
            # Check if we have enough data for the filter order
            min_required = max(2 * order, 6)  # At least 6 points or 2*order
            if len(data) < min_required:
                print(f"[WARNING] Butterworth filter: reducing order from {order} to fit data length {len(data)}")
                order = max(1, len(data) // 4)  # Reduce order
                
            nyquist = 0.5 * fs
            normal_cutoff = cutoff / nyquist
            
            # Ensure cutoff frequency is valid
            if normal_cutoff >= 1.0:
                normal_cutoff = 0.95  # Safer margin
                print(f"[WARNING] Butterworth filter: cutoff frequency too high, reduced to {normal_cutoff * nyquist:.2f} Hz")
            if normal_cutoff <= 0:
                print(f"[WARNING] Butterworth filter: invalid cutoff frequency")
                return data.copy()
                
            b, a = butter(order, normal_cutoff, btype=btype, analog=False)
            
            # Use lfilter instead of filtfilt for shorter data
            if len(data) < 3 * order:
                from scipy.signal import lfilter
                return lfilter(b, a, data)
            else:
                return filtfilt(b, a, data)
                
        except Exception as e:
            print(f"[ERROR] Butterworth filter failed: {e}")
            return data.copy()

    def _apply_filters(self, data, filter_type, fs=None):
        """Apply all enabled filters for a given type"""
        result = data.copy()
        
        filters = getattr(self, f"{filter_type}_filters")
        
        # Apply SavGol if enabled
        if filters['savgol_enabled']:
            window = getattr(self, f"{filter_type}_sg_win").value()
            poly = getattr(self, f"{filter_type}_sg_poly").value()
            result = self.apply_savgol(result, window, poly)
        
        # Apply Butterworth if enabled
        if filters['butter_enabled'] and fs is not None:
            cutoff = getattr(self, f"{filter_type}_bw_fc").value()
            order = getattr(self, f"{filter_type}_bw_ord").value()
            btype_text = getattr(self, f"{filter_type}_bw_type").currentText()
            btype = "low" if btype_text == "Low" else "high"
            result = self.apply_butter(result, fs, cutoff, order, btype)
        
        # Apply Kalman if enabled
        if filters['kalman_enabled']:
            q_noise = getattr(self, f"{filter_type}_kf_q").value()
            r_noise = getattr(self, f"{filter_type}_kf_r").value()
            result = self.apply_kalman(result, q_noise, r_noise)
        
        return result

    def update_plots(self):
        """Update plots with actual matplotlib plotting"""
        if self.full_df is None or not MATPLOTLIB_AVAILABLE or not hasattr(self, 'raw_canvas'):
            return
            
        try:
            self.raw_fig.clear()
            self.vel_fig.clear()

            df = self.full_df
            s, e = self.start_spin.value(), self.end_spin.value()
            if e <= s:
                self.metrics_txt.setText("End time must be after start time.")
                return

            window = df[(df.relative_time >= s) & (df.relative_time <= e)]
            if len(window) < 2:
                self.metrics_txt.setText("Not enough data points in selected range.")
                return

            full_ts, full_v = df.relative_time.values, df.value.values
            ts, raw = window.relative_time.values, window.value.values

            # Apply distance/angle filters
            dt0 = np.diff(ts)
            fs = 1.0/np.mean(dt0) if len(dt0) > 0 and np.mean(dt0) != 0 else 1.0
            vals = self._apply_filters(raw, 'distance', fs)

            # Calculate velocity from filtered distance data
            dts = np.diff(ts)
            dvs = np.diff(vals)
            dts_safe = np.where(dts == 0, 1e-9, dts)
            raw_vel = dvs/dts_safe if len(dvs) > 0 else np.array([])

            # Apply velocity filters
            mean_dt = np.mean(dts) if len(dts) > 0 else 1.0
            fs_vel = 1.0 / mean_dt
            vel = self._apply_filters(raw_vel, 'velocity', fs_vel)

            # Now apply velocity range filtering using the spin box values
            if hasattr(self, "velocity_min_spin") and hasattr(self, "velocity_max_spin") and len(raw_vel) > 0:
                min_val = self.velocity_min_spin.value()
                max_val = self.velocity_max_spin.value()
                vel_ts = ts[1:len(raw_vel)+1]  # timestamps corresponding to velocity data
                mask = (raw_vel >= min_val) & (raw_vel <= max_val)
                raw_vel_masked = raw_vel[mask]
                vel_ts_masked = vel_ts[mask]
                # For the processed velocity (if its length equals raw_vel), mask it too
                if len(vel) == len(raw_vel):
                    vel_masked = vel[mask]
                else:
                    vel_masked = vel
                # Plot filtered velocity
                ax2 = self.vel_fig.add_subplot(111)
                ax2.set_facecolor(PLOT_BACKGROUND)
                ax2.plot(vel_ts_masked, raw_vel_masked, color=PLOT_LINE_SECONDARY, alpha=0.6, label="Raw Velocity", linewidth=1)
                if len(vel_masked) > 0:
                    ax2.plot(vel_ts_masked, vel_masked, color=PLOT_LINE_PRIMARY, linewidth=2, label="Filtered Velocity")
            else:
                # Fallback: plot without additional velocity range filtering
                ax2 = self.vel_fig.add_subplot(111)
                ax2.set_facecolor(PLOT_BACKGROUND)
                if len(ts) > 1 and len(raw_vel) > 0:
                    vel_ts = ts[1:len(raw_vel)+1]
                    ax2.plot(vel_ts, raw_vel, color=PLOT_LINE_SECONDARY, alpha=0.6, label="Raw Velocity", linewidth=1)
                    if len(vel) > 0:
                        ax2.plot(vel_ts[:len(vel)], vel, color=PLOT_LINE_PRIMARY, linewidth=2, label="Filtered Velocity")

            # Plot raw data (distance/angle)
            ax1 = self.raw_fig.add_subplot(111)
            ax1.set_facecolor(PLOT_BACKGROUND)
            ax1.plot(full_ts, full_v, color=PLOT_LINE_ALT, alpha=0.4, label="Full Data", linewidth=1)
            ax1.plot(ts, raw, color=PLOT_LINE_SECONDARY, alpha=0.6, label="Raw", linewidth=1)
            ax1.plot(ts, vals, color=PLOT_LINE_PRIMARY, linewidth=2, label="Filtered")

            # If Butterworth filter is enabled, mark peaks used for rotation calculation
            if self.distance_filters.get('butter_enabled', False):
                _, _, _, extrema_indices = self.calculate_rotation_speed(vals, ts)
                if extrema_indices is not None and len(extrema_indices) > 0:
                    extrema_x = [ts[i] for i in extrema_indices]
                    extrema_y = [vals[i] for i in extrema_indices]
                    
                    # Plot all extrema (both peaks and troughs)
                    ax1.scatter(extrema_x, extrema_y, color='red', marker='o', s=50, 
                               label="Detected Points", zorder=5)
                    
                    # Optionally, you can visualize peaks and troughs differently
                    peaks_mask = np.isin(extrema_indices, find_peaks(vals, distance=3, prominence=0.005)[0])
                    troughs_mask = ~peaks_mask
                    
                    peaks_x = [extrema_x[i] for i, is_peak in enumerate(peaks_mask) if is_peak]
                    peaks_y = [extrema_y[i] for i, is_peak in enumerate(peaks_mask) if is_peak]
                    
                    troughs_x = [extrema_x[i] for i, is_peak in enumerate(peaks_mask) if not is_peak]
                    troughs_y = [extrema_y[i] for i, is_peak in enumerate(peaks_mask) if not is_peak]
                    
                    ax1.scatter(peaks_x, peaks_y, color='red', marker='^', s=50, label="Peaks", zorder=6)
                    ax1.scatter(troughs_x, troughs_y, color='blue', marker='v', s=50, label="Troughs", zorder=6)

            # Line of Best Fit
            show_bestfit = hasattr(self, "distance_bestfit_cb") and self.distance_bestfit_cb.isChecked()
            bestfit_gradient = None
            if show_bestfit and len(ts) > 1:
                # Fit line: y = m*x + b
                m, b = np.polyfit(ts, vals, 1)
                bestfit_line = m * ts + b
                ax1.plot(ts, bestfit_line, color=WARNING_COLOR, linestyle="--", linewidth=2, label="Best Fit")
                bestfit_gradient = m
            ax1.axvline(s, color=SUCCESS_COLOR, linestyle='--', alpha=0.7, label=f"Start: {s:.1f}s")
            ax1.axvline(e, color=ERROR_COLOR, linestyle='--', alpha=0.7, label=f"End: {e:.1f}s")
            ax1.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=FONT_SIZE_LABEL-2)
            # Determine ylabel based on mode
            current_mode_text = self.mode_combo.currentText()
            if current_mode_text == "DISTANCE MEASURING MODE":
                y_raw_label = "Distance (m)"
            elif current_mode_text == "SCANNING MODE":
                y_raw_label = "Relative Angle (°)"
            else:
                y_raw_label = "Angular Pos. (°)"
            ax1.set_ylabel(y_raw_label, color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=FONT_SIZE_LABEL-2)
            ax1.tick_params(axis='both', colors=TICK_COLOR, labelsize=FONT_SIZE_LABEL-3)
            for spine in ax1.spines.values():
                spine.set_edgecolor(TICK_COLOR)
            ax1.grid(True, color=GRID_COLOR, linestyle=':', linewidth=0.5, alpha=0.3)
            ax1.legend(facecolor=BOX_BACKGROUND, labelcolor=TEXT_COLOR, edgecolor=BORDER_COLOR, fontsize=FONT_SIZE_LABEL-3)
            self.raw_fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.15)
            
            # Velocity axes labels based on mode
            if current_mode_text == "DISTANCE MEASURING MODE":
                y_vel_label = "Velocity (m/s)"
            elif current_mode_text == "SCANNING MODE":
                y_vel_label = "Rate of Change (°/s)"
            else:
                y_vel_label = "Spin Rate (°/s)"
            ax2.set_xlabel("Time (s)", color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=FONT_SIZE_LABEL-2)
            ax2.set_ylabel(y_vel_label, color=TEXT_COLOR, fontfamily=FONT_FAMILY, fontsize=FONT_SIZE_LABEL-2)
            ax2.tick_params(axis='both', colors=TICK_COLOR, labelsize=FONT_SIZE_LABEL-3)
            for spine in ax2.spines.values():
                spine.set_edgecolor(TICK_COLOR)
            ax2.grid(True, color=GRID_COLOR, linestyle=':', linewidth=0.5, alpha=0.3)
            ax2.legend(facecolor=BOX_BACKGROUND, labelcolor=TEXT_COLOR, edgecolor=BORDER_COLOR, fontsize=FONT_SIZE_LABEL-3)
            self.raw_canvas.draw()
            self.vel_canvas.draw()

            # Compute metrics from filtered data:
            # For distance: use 'vals'
            # For velocity: use filtered velocity (vel), possibly masked by min/max
            if hasattr(self, "velocity_min_spin") and hasattr(self, "velocity_max_spin") and len(raw_vel) > 0:
                min_val = self.velocity_min_spin.value()
                max_val = self.velocity_max_spin.value()
                # Only mask if lengths match
                if len(vel) == len(raw_vel):
                    mask = (vel >= min_val) & (vel <= max_val)
                    filtered_vel_for_metrics = vel[mask]
                else:
                    # If lengths don't match, use all of vel (and optionally warn)
                    filtered_vel_for_metrics = vel
            else:
                filtered_vel_for_metrics = vel

            self._compute_metrics(vals, filtered_vel_for_metrics, dts, current_mode_text, bestfit_gradient)
            
        except Exception as e:
            print(f"Plot error in DataAnalysisTab.update_plots: {e}\n{traceback.format_exc()}")
            self.metrics_txt.setText(f"Error plotting data: {e}")

    def calculate_rotation_speed(self, filtered_data, timestamps):
        """Calculate rotation speed from filtered data by finding period between peaks AND troughs"""
        if len(filtered_data) < 5:  # Need enough data points
            return None, None, None, None  # Return 4 values
    
        try:
            # 1. Find peaks (local maxima)
            peaks, _ = find_peaks(filtered_data, distance=3, prominence=0.005)
            
            # 2. Find troughs (local minima) by inverting the signal
            troughs, _ = find_peaks(-filtered_data, distance=3, prominence=0.005)
            
            # 3. Combine peaks and troughs as "extrema"
            if len(peaks) == 0 and len(troughs) == 0:
                return None, None, None, None  # No peaks or troughs found
                
            extrema_indices = np.concatenate([peaks, troughs] if len(peaks) > 0 and len(troughs) > 0 
                                             else [peaks] if len(peaks) > 0 
                                             else [troughs])
            
            # Only proceed if we have enough extrema points
            if len(extrema_indices) < 2:
                return None, None, None, None
                
            # 4. Sort by time
            extrema_indices = np.sort(extrema_indices)
            
            # 5. Get timestamps for each extrema
            extrema_times = timestamps[extrema_indices]
            
            # 6. Calculate time between consecutive extrema
            periods = np.diff(extrema_times)
            
            # 7. Calculate rotation metrics
            # If using both peaks and troughs, each full rotation has TWO extrema
            # So we multiply each period by 2 to get the full rotation period
            full_rotation_periods = periods * 2
            avg_period = np.mean(full_rotation_periods)
            avg_period = avg_period*4
            frequency = 1.0 / avg_period if avg_period > 0 else 0
            rpm = frequency * 360  # Convert Hz to RPM
            
            return avg_period, frequency, rpm, extrema_indices
        except Exception as e:
            print(f"[ERROR] Rotation speed calculation failed: {e}")
            return None, None, None, None  # Always return 4 values
    
    def _compute_metrics(self, vals, vel, dts, mode_text, bestfit_gradient=None):
        """Compute and display analysis metrics"""
        try:
            pts = len(vals)
            dur = self.end_spin.value() - self.start_spin.value()
            # Determine labels based on mode_text
            if mode_text == "DISTANCE MEASURING MODE":
                P_label, D_label = "Distance", "Velocity"
            elif mode_text == "SCANNING MODE":
                P_label, D_label = "Rel. Angle", "Rate of Change"
            else:  # SPIN MODE
                P_label, D_label = "Angl. Pos.", "Spin Rate"

            self.metrics = {
                "Data Points": pts,
                "Time Range": dur,
                f"Avg {P_label}": vals.mean() if len(vals) > 0 else 0.0,
                f"Avg {D_label}": vel.mean() if len(vel) > 0 else 0.0,
            }
            
            if bestfit_gradient is not None:
                self.metrics["Best Fit Gradient"] = bestfit_gradient
                
            # Calculate rotation speed if there's enough data and we've applied filters
            if len(vals) > 10 and self.distance_filters.get('butter_enabled', False):
                # Get timestamps from the current window
                window_ts = np.linspace(
                    self.start_spin.value(), 
                    self.end_spin.value(), 
                    len(vals)
                )
                period, freq, rpm, _ = self.calculate_rotation_speed(vals, window_ts)
                
                if period is not None:
                    self.metrics["Rotation Period"] = period
                    self.metrics["Rotation Freq"] = freq
                    self.metrics["Rotation Speed"] = rpm

            lines = []
            primary_metrics = [
                ("Data Points", "{:.0f}"),
                ("Time Range", "{:.1f} s"),
                (f"Avg {P_label}", "{:.4f}"),
                (f"Avg {D_label}", "{:.4f}")
            ]
            for key, fmt_str in primary_metrics:
                if key in self.metrics:
                    value = self.metrics[key]
                    lines.append(f"{key + ':':<18} {fmt_str.format(value)}")
                
            # Show gradient if present
            if "Best Fit Gradient" in self.metrics:
                lines.append(f"{'Best Fit Gradient:':<18} {self.metrics['Best Fit Gradient']:.4f}")
            
            # Show rotation metrics if present
            if "Rotation Period" in self.metrics:
                lines.append(f"{'Rotation Period:':<18} {self.metrics['Rotation Period']:.4f} s")
                lines.append(f"{'Rotation Speed:':<18} {self.metrics['Rotation Speed']:.4f} °/s")
            
            txt = "\n".join(lines)
            self.metrics_txt.setText(txt)
            
            has_valid_data = len(vals) > 0 and not np.isnan(vals.mean())
            self.record_distance_btn.setEnabled(has_valid_data)
            self.record_velocity_btn.setEnabled(has_valid_data and len(vel) > 0)
            
        except Exception as e:
            print(f"[ERROR] Metrics computation failed: {e}")
            self.metrics_txt.setText(f"Error computing metrics: {e}")
            self.record_distance_btn.setEnabled(False)
            self.record_velocity_btn.setEnabled(False)

    def _export(self):
        """Export analysis results to file"""
        if not hasattr(self, 'metrics'):
            QMessageBox.warning(self, "No Data", "No analysis data to export.")
            return
        
        # Dynamic default filename based on mode
        mode_text = self.mode_combo.currentText()
        key = mode_text.replace(" ", "_").lower() if mode_text else "analysis"
        default_name = f"{key}_analysis_report.txt"
        
        # Default to recordings directory
        recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        default_path = os.path.join(recordings_dir, default_name)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis", default_path, 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.metrics_txt.toPlainText())
                QMessageBox.information(
                    self, "Success", 
                    f"Analysis exported to:\n{file_path}"
                )
                print(f"[INFO] Analysis exported to: {file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", 
                    f"Failed to export analysis:\n{e}"
                )
                print(f"[ERROR] Export failed: {e}")

    def _save_plot(self, canvas, default_name):
        """Save matplotlib plot to file"""
        if not hasattr(self, 'metrics'):
            QMessageBox.warning(self, "No Data", "No plot data to save.")
            return
            
        recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        default_path = os.path.join(recordings_dir, default_name)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", default_path, 
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
        )
        
        if file_path:
            try:
                canvas.figure.savefig(file_path, dpi=300, bbox_inches='tight', 
                                    facecolor=PLOT_BACKGROUND, edgecolor='none')
                QMessageBox.information(
                    self, "Saved", 
                    f"Plot saved to:\n{file_path}"
                )
                print(f"[INFO] Plot saved to: {file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Save Failed", 
                    f"Failed to save plot:\n{e}"
                )
                print(f"[ERROR] Plot save failed: {e}")

    def _record_distance(self):
        """Record the current average distance to the collection CSV"""
        if not hasattr(self, 'metrics') or not self.metrics:
            QMessageBox.warning(self, "No Data", "No analysis data available to record.")
            return
        
        # Find the average distance metric
        avg_distance_key = None
        for key in self.metrics.keys():
            if "▶ Avg" in key and ("Distance" in key or "Angl. Pos." in key or "Rel. Angle" in key):
                avg_distance_key = key
                break
        
        if avg_distance_key is None:
            QMessageBox.warning(self, "No Data", "No average distance/angle data found.")
            return
        
        avg_value = self.metrics[avg_distance_key]

        # Add to collection
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get sensor type from dropdown
        sensor_type = self.sensor_type_combo.currentText()
        
        entry = {
            "sensor_type": sensor_type,  # Record sensor type
            "avg_value": avg_value,
        }
        
        self.collection_data.append(entry)
        self._update_csv_display()
        self._auto_save_csv()
        
        print(f"[INFO] Recorded distance: {avg_value:.4f}")

    def _record_velocity(self):
        """Record the current best fit gradient (or avg velocity if not available) to the collection CSV"""
        if not hasattr(self, 'metrics') or not self.metrics:
            QMessageBox.warning(self, "No Data", "No analysis data available to record.")
            return

        # Prefer to record the best fit gradient if available
        if "Best Fit Gradient" in self.metrics:
            value = self.metrics["Best Fit Gradient"]
            label = "Gradient"
        else:
            # Fallback to avg velocity
            avg_velocity_key = None
            for key in self.metrics.keys():
                if "▶ Avg" in key and ("Velocity" in key or "Rate of Change" in key or "Spin Rate" in key):
                    avg_velocity_key = key
                    break
            if avg_velocity_key is None:
                QMessageBox.warning(self, "No Data", "No gradient or average velocity data found.")
                return
            value = self.metrics[avg_velocity_key]
            label = "Avg Velocity"

        sensor_type = self.sensor_type_combo.currentText()
        entry = {
            "sensor_type": sensor_type,
            "value_type": label,
            "value": value,
        }
        self.collection_data.append(entry)
        self._update_csv_display()
        self._auto_save_csv()
        print(f"[INFO] Recorded {label}: {value:.4f}")

    def _record_rotation(self):
        """Record the rotation speed to the collection CSV"""
        if not hasattr(self, 'metrics') or not self.metrics or "Rotation Speed" not in self.metrics:
            QMessageBox.warning(self, "No Data", "No rotation speed data available to record.")
            return
        
        value = self.metrics["Rotation Speed"]
        sensor_type = self.sensor_type_combo.currentText()
        entry = {
            "sensor_type": sensor_type,
            "value_type": "Rotation Speed",
            "value": value,
        }
        self.collection_data.append(entry)
        self._update_csv_display()
        self._auto_save_csv()
        print(f"[INFO] Recorded rotation speed: {value:.2f} RPM")

    def manual_submit_manual_value(self):
        """Submit the manual input from the QLineEdit as a manual record."""
        text = self.manual_value_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter a value.")
            return
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Invalid number format.")
            return
        entry = {
            "sensor_type": "manual",
            "value_type": "Manual",
            "value": value,
        }
        self.collection_data.append(entry)
        self._update_csv_display()
        self._auto_save_csv()
        print(f"[INFO] Recorded manual value: {value}")
        self.manual_value_input.clear()

    def record_manual_input(self):
        """Record a manual input value: sensor type 'manual' and input value as avg value."""
        from PyQt6.QtWidgets import QInputDialog  # Ensure QInputDialog is imported
        value, ok = QInputDialog.getDouble(self, "Manual Input", "Enter value:", decimals=4)
        if not ok:
            return
        
        entry = {
            "sensor_type": "manual",
            "avg_value": value,
        }
        
        self.collection_data.append(entry)
        self._update_csv_display()
        self._auto_save_csv()
        
        print(f"[INFO] Recorded manual value: {value}")

    def _update_csv_display(self):
        """Update the CSV data display"""
        if not self.collection_data:
            self.csv_data_display.setText("No data collected yet...")
            self.save_csv_btn.setEnabled(False)
            return

        lines = [f"Entries: {len(self.collection_data)}"]
        lines.append("─" * 25)

        # Show last 5 entries
        recent_data = self.collection_data[-5:] if len(self.collection_data) > 5 else self.collection_data

        for i, entry in enumerate(recent_data):
            entry_num = len(self.collection_data) - len(recent_data) + i + 1
            sensor = entry.get("sensor_type", "")
            vtype = entry.get("value_type", "")
            value = entry.get("value", entry.get("avg_value", 0.0))
            lines.append(f"{entry_num}. ({sensor}) {vtype}: {value:.4f}")

        if len(self.collection_data) > 5:
            lines.insert(2, f"... (showing last 5 of {len(self.collection_data)})")

        self.csv_data_display.setText("\n".join(lines))
        self.save_csv_btn.setEnabled(True)

    def _new_csv_file(self):
        """Create a new CSV file for data collection"""
        # Prompt the user for a filename
        file_path, _ = QFileDialog.getSaveFileName(
            self, "New CSV File", 
            os.path.join(os.path.dirname(__file__), "recordings", "new_data.csv"),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            # Initialize the CSV with headers
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerow([
                        "sensor_type", 
                        "avg_value"
                    ])
                
                self.collection_data = []  # Clear existing data
                self.current_csv_path = file_path
                self._update_csv_display()
                QMessageBox.information(
                    self, "New File Created", 
                    f"New CSV file created:\n{file_path}"
                )
                print(f"[INFO] New CSV file created: {file_path}")
            
            except Exception as e:
                QMessageBox.critical(
                    self, "Error Creating File", 
                    f"Failed to create new CSV file:\n{e}"
                )
                print(f"[ERROR] Failed to create new CSV: {e}")

    def _save_csv_as(self):
        """Save collected data to a CSV file, prompting for filename"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV As", 
            os.path.join(os.path.dirname(__file__), "recordings", self.csv_filename_input.text()),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self._save_csv(file_path)

    def _save_csv(self, file_path):
        """Save collected data to the specified CSV file"""
        if not self.collection_data:
            QMessageBox.warning(self, "No Data", "No data to save.")
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                csv_writer = csv.writer(csvfile)
                # Write the header row
                header = ["sensor_type", "value_type", "value"]
                csv_writer.writerow(header)
                # Write the data rows
                for entry in self.collection_data:
                    csv_writer.writerow([
                        entry.get("sensor_type", ""),
                        entry.get("value_type", ""),
                        entry.get("value", entry.get("avg_value", 0.0))
                    ])

            self.current_csv_path = file_path
            QMessageBox.information(
                self, "Save Successful",
                f"Data saved to:\n{file_path}"
            )
            print(f"[INFO] Data saved to: {file_path}")

        except Exception as e:
            QMessageBox.critical(
                self, "Save Error",
                f"Failed to save data to CSV:\n{e}"
            )
            print(f"[ERROR] Failed to save data to CSV: {e}")

    def _auto_save_csv(self):
        """Automatically save the CSV data to the current file"""
        if self.current_csv_path:
            self._save_csv(self.current_csv_path)
        else:
            # If no file is currently open, prompt the user to save as.
            self._save_csv_as()