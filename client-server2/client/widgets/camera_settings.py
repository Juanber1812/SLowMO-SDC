from PyQt6.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel, QSlider, QComboBox, QPushButton, QHBoxLayout, QButtonGroup
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

RES_PRESETS_LOW = [
    ("OLD", "legacy"),  # Special case for old calibration
    ("768x432", (768, 432)),
    ("1024x576", (1024, 576)),
    ("1536x864", (1536, 864)),
]

RES_PRESETS_MID = [
    ("1920x1080", (1920, 1080)),     # Full HD
    ("2304x1296", (2304, 1296)),     # Base medium resolution
    ("2560x1440", (2560, 1440)),     # 1440p
]

RES_PRESETS_HIGH = [
    ("2880x1620", (2880, 1620)),     # New lower resolution for HIGH
    ("3456x1944", (3456, 1944)),     # 4608/1.33 x 2592/1.33
    ("4608x2592", (4608, 2592)),     # Highest resolution
]

CALIBRATION_FILES = {
    # Special case for OLD preset - uses your original calibration file
    "legacy": "payload/calibration_data.npz",  # Correct filename: calibration_data.npz
    
    # LOW presets
    (768, 432): "calibrations/calibration_768x432.npz",
    (1024, 576): "calibrations/calibration_1024x576.npz", 
    (1536, 864): "calibrations/calibration_1536x864.npz",
    
    # MID presets
    (1920, 1080): "calibrations/calibration_1920x1080.npz",
    (2304, 1296): "calibrations/calibration_2304x1296.npz",
    (2560, 1440): "calibrations/calibration_2560x1440.npz",
    
    # HIGH presets
    (2880, 1620): "calibrations/calibration_2880x1620.npz",
    (3456, 1944): "calibrations/calibration_3456x1944.npz",
    (4608, 2592): "calibrations/calibration_4608x2592.npz",
}



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

        self.cropped = False  # Track cropped state

        # --- Preset selection buttons ---
        self.preset_buttons_layout = QHBoxLayout()
        self.low_btn = QPushButton("Low")
        self.mid_btn = QPushButton("Mid")
        self.high_btn = QPushButton("High")
        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setCheckable(True)
            btn.setMinimumWidth(60)
            btn.setMinimumHeight(BUTTON_HEIGHT)  # Match other buttons' height

        self.low_btn.setChecked(True)  # Default selected

        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        self.preset_group.addButton(self.low_btn, 0)
        self.preset_group.addButton(self.mid_btn, 1)
        self.preset_group.addButton(self.high_btn, 2)
        self.preset_buttons_layout.addWidget(self.low_btn)
        self.preset_buttons_layout.addWidget(self.mid_btn)
        self.preset_buttons_layout.addWidget(self.high_btn)

        self.preset_group.idClicked.connect(self.on_preset_changed)
        self.current_presets = RES_PRESETS_LOW  # Default

        self.res_dropdown = QComboBox()
        self._populate_res_dropdown()

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 120)
        self.fps_slider.setValue(10)

        self.fps_label = QLabel("FPS: 10")
        self.fps_slider.valueChanged.connect(lambda val: self.fps_label.setText(f"FPS: {val}"))

        self.apply_btn = QPushButton("Apply Settings")

        # Add calibration status label
        self.calibration_status_label = QLabel("Calibration: Unknown")
        self.layout.addWidget(self.calibration_status_label, 5, 0, 1, 2)  # Add after apply button

        # Now set the font for the preset buttons to match apply_btn
        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setFont(self.apply_btn.font())

        self.layout.addWidget(self.jpeg_label, 0, 0)
        self.layout.addWidget(self.jpeg_slider, 0, 1)
        self.layout.addLayout(self.preset_buttons_layout, 1, 0, 1, 2)  # Add buttons horizontally
        self.layout.addWidget(QLabel("Resolution"), 2, 0)
        self.layout.addWidget(self.res_dropdown, 2, 1)
        self.layout.addWidget(self.fps_label, 3, 0)
        self.layout.addWidget(self.fps_slider, 3, 1)
        self.layout.addWidget(self.apply_btn, 4, 0, 1, 2)

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
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: {PADDING_NORMAL}px {PADDING_LARGE}px;
                min-height: {BUTTON_HEIGHT}px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
            QPushButton:checked {{
                background-color: {BUTTON_COLOR};
                color: black;
            }}
            QPushButton:checked:hover {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
            QPushButton:pressed {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
            QPushButton:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777;
                border: {BORDER_WIDTH}px solid #555;
            }}
        """)

        # Define the same thinner button style as Camera Controls
        PRESET_BUTTON_STYLE = f"""
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
        QPushButton:checked {{
            background-color: {BUTTON_COLOR};
            color: black;
        }}
        QPushButton:checked:hover {{
            background-color: {BUTTON_HOVER};
            color: black;
        }}
        QPushButton:disabled {{
            background-color: {BUTTON_DISABLED};
            color: #777;
            border: {BORDER_WIDTH}px solid #555;
        }}
        """

        # Apply the thinner style to Low, Mid, High buttons
        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setCheckable(True)
            btn.setMinimumWidth(60)
            btn.setStyleSheet(PRESET_BUTTON_STYLE)  # Apply the thinner style

        # Connect preset and resolution changes to update calibration status
        self.preset_group.idClicked.connect(self.update_calibration_status)
        self.res_dropdown.currentIndexChanged.connect(self.update_calibration_status)

        # Initial status update
        self.update_calibration_status()

    def on_preset_changed(self, id):
        if id == 0:
            self.current_presets = RES_PRESETS_LOW
        elif id == 1:
            self.current_presets = RES_PRESETS_MID
        elif id == 2:
            self.current_presets = RES_PRESETS_HIGH
        self._populate_res_dropdown()

    def _populate_res_dropdown(self):
        """Populate the dropdown with cropped or uncropped labels, preserving selection."""
        current_label = self.get_current_resolution_label()
        self.res_dropdown.clear()
        for label, _ in self.current_presets:
            display_label = f"{label} (Cropped)" if self.cropped else label
            self.res_dropdown.addItem(display_label)
        # Restore selection if possible
        idx = 0
        for i in range(self.res_dropdown.count()):
            if self.res_dropdown.itemText(i).startswith(current_label):
                idx = i
                break
        self.res_dropdown.setCurrentIndex(idx)

    def get_current_resolution_label(self):
        """Get the base label of the current selection (without ' (Cropped)')."""
        label = self.res_dropdown.currentText()
        return label.replace(" (Cropped)", "")

    def get_config(self):
        res_idx = self.res_dropdown.currentIndex()
        label, resolution_data = self.current_presets[res_idx]
        
        # Handle special case for OLD preset
        if resolution_data == "legacy":
            # Use 1536x864 resolution for OLD preset (matches your original calibration)
            actual_resolution = (1536, 864)  # Resolution used for original calibration
            calibration_file = CALIBRATION_FILES["legacy"]
        else:
            width, height = resolution_data
            
            # If cropped, adjust height to 16:3 aspect ratio
            if self.cropped:
                cropped_height = int(width * 3 / 16)
                actual_resolution = (width, cropped_height)
            else:
                actual_resolution = (width, height)
            
            # Get the appropriate calibration file (use original resolution for cropped)
            calibration_resolution = (width, height)
            calibration_file = CALIBRATION_FILES.get(calibration_resolution, "calibrations/calibration_default.npz")
        
        return {
            "jpeg_quality": self.jpeg_slider.value(),
            "fps": self.fps_slider.value(),
            "resolution": actual_resolution,
            "calibration_file": calibration_file,
            "cropped": self.cropped,
            "preset_type": "legacy" if resolution_data == "legacy" else "standard"
        }

    def apply_style(self, style: str):
        self.setStyleSheet(style)
        # Do NOT set style individually on buttons, let the group box stylesheet apply

    def set_cropped_label(self, cropped: bool):
        """Switch all dropdown labels to cropped/uncropped, preserving selection."""
        self.cropped = cropped
        self._populate_res_dropdown()

    def has_calibration(self, resolution):
        """Check if calibration file exists for given resolution."""
        import os
        filename = CALIBRATION_FILES.get(resolution, "calibrations/calibration_default.npz")
        return os.path.exists(filename)

    def get_calibration_status(self):
        """Get status of all calibrations for current preset."""
        import os
        status = {}
        for label, resolution in self.current_presets:
            filename = CALIBRATION_FILES.get(resolution, f"calibrations/calibration_{resolution[0]}x{resolution[1]}.npz")
            status[label] = os.path.exists(filename)
        return status

    def update_calibration_status(self):
        """Update the calibration status display."""
        import os
        config = self.get_config()
        calibration_file = config.get('calibration_file', 'calibrations/calibration_default.npz')
        
        if os.path.exists(calibration_file):
            self.calibration_status_label.setText("Calibration: ✓ Available")
            self.calibration_status_label.setStyleSheet(f"color: {SUCCESS_COLOR};")
        else:
            self.calibration_status_label.setText("Calibration: ❌ Missing")
            self.calibration_status_label.setStyleSheet(f"color: {ERROR_COLOR};")
