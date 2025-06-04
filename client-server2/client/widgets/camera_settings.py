from PyQt6.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QLabel, QSlider, QComboBox, QPushButton, QHBoxLayout, QButtonGroup, QDoubleSpinBox
from PyQt6.QtCore import Qt, pyqtSignal # Added pyqtSignal
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
import os
# Crop Factor Constants
DEFAULT_CROP_FACTOR = 3
MIN_CROP_FACTOR = 1.0
MAX_CROP_FACTOR = 10 
CROP_FACTOR_STEP = 0.5

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
    crop_config_requested = pyqtSignal() # New signal

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("CameraSettings")
        self.layout = QVBoxLayout()

        # --- Initialize all widgets first ---
        self.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_slider.setRange(1, 100)
        self.jpeg_slider.setValue(70)
        self.jpeg_label = QLabel("JPEG: 70")
        self.jpeg_slider.valueChanged.connect(lambda val: self.jpeg_label.setText(f"JPEG: {val}"))

        self.cropped = False # Initial crop state

        self.preset_buttons_layout = QHBoxLayout()
        self.low_btn = QPushButton("Low")
        self.mid_btn = QPushButton("Mid")
        self.high_btn = QPushButton("High")
        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setCheckable(True)
            btn.setMinimumWidth(60)
            btn.setMinimumHeight(BUTTON_HEIGHT)
        self.low_btn.setChecked(True)

        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        self.preset_group.addButton(self.low_btn, 0)
        self.preset_group.addButton(self.mid_btn, 1)
        self.preset_group.addButton(self.high_btn, 2)
        self.preset_buttons_layout.addWidget(self.low_btn)
        self.preset_buttons_layout.addWidget(self.mid_btn)
        self.preset_buttons_layout.addWidget(self.high_btn)
        self.preset_group.idClicked.connect(self.on_preset_changed)
        self.current_presets = RES_PRESETS_LOW

        self.res_dropdown = QComboBox()



        self.apply_btn = QPushButton("Apply Settings")
        
        # Crop Controls (NEW - Button and SpinBox)
        self.crop_btn = QPushButton("Crop") # Set static text "Crop"
        self.crop_btn.setCheckable(True) # Make the crop button checkable
        self.crop_factor_spinbox = QDoubleSpinBox()
        self.crop_factor_spinbox.setRange(MIN_CROP_FACTOR, MAX_CROP_FACTOR)
        self.crop_factor_spinbox.setValue(DEFAULT_CROP_FACTOR)
        self.crop_factor_spinbox.setSingleStep(CROP_FACTOR_STEP)
        self.crop_factor_spinbox.setDecimals(1)

        self.crop_controls_layout = QHBoxLayout()
        self.crop_controls_layout.addWidget(self.crop_btn)
        self.crop_controls_layout.addWidget(self.crop_factor_spinbox)
        # Allow spinbox to take some space, but not excessively
        self.crop_controls_layout.setStretchFactor(self.crop_btn, 1)
        self.crop_controls_layout.setStretchFactor(self.crop_factor_spinbox, 0) 


        # create a label to show calibration status
        self.calibration_status_label = QLabel("Calibration: Pending…")
        self.layout.addWidget(self.calibration_status_label)

        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setFont(self.apply_btn.font())

        # --- Add widgets to QVBoxLayout ---
        self.layout.addStretch(1)

        # JPEG Controls
        self.layout.addWidget(self.jpeg_label, 0, Qt.AlignmentFlag.AlignCenter) 
        self.layout.addWidget(self.jpeg_slider) 
        self.layout.addStretch(1)

        # Preset selection buttons (QHBoxLayout)
        self.layout.addLayout(self.preset_buttons_layout)
        self.layout.addStretch(1)

        # Resolution Controls
        resolution_actual_label = QLabel("Resolution")
        self.layout.addWidget(resolution_actual_label, 0, Qt.AlignmentFlag.AlignCenter) 
        self.layout.addWidget(self.res_dropdown) 
        self.layout.addStretch(1)

        # FPS Controls (show numeric value inline)
        # Initialize slider before label so we can read its value
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 120)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel(f"FPS Setting: {self.fps_slider.value()}")
        # Update label text when slider moves
        self.fps_slider.valueChanged.connect(
            lambda val: self.fps_label.setText(f"FPS Setting: {val}")
        )
        self.layout.addWidget(self.fps_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.fps_slider)
        self.layout.addStretch(1)
        
        # Brightness Controls (NEW)
        self.brightness_label = QLabel(f"Brightness: {50}")
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(70)
        self.brightness_slider.valueChanged.connect(
            lambda val: self.brightness_label.setText(f"Brightness: {val}")
        )
        self.layout.addWidget(self.brightness_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.brightness_slider)
        self.layout.addStretch(1)

        # Exposure Controls (percentage → 100µs–200000µs)
        self.exposure_label = QLabel("Exposure: 30%")
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(1, 100)      # 1%–100%
        self.exposure_slider.setValue(30)          # default 30%
        self.exposure_slider.valueChanged.connect(
            lambda pct: self.exposure_label.setText(f"Exposure: {pct}%")
        )
        self.layout.addWidget(self.exposure_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.exposure_slider)
        self.layout.addStretch(1)
        
        # Crop Controls (NEW - PLACEMENT of QHBoxLayout)
        # Create a container widget for the crop_controls_layout to center it
        crop_controls_container = QWidget()
        crop_controls_container.setLayout(self.crop_controls_layout)
        self.layout.addWidget(crop_controls_container, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch(1)

        # ── move Apply Settings button to very bottom ──
        self.layout.addWidget(self.apply_btn, 0, Qt.AlignmentFlag.AlignCenter)
        # Calibration Status Label at very bottom
        self.layout.addWidget(self.calibration_status_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch(1)

        self.setLayout(self.layout)

        # --- Styling and Signal Connections ---
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
                font-family: {FONT_FAMILY}; /* Added font family */
                font-size: {FONT_SIZE_NORMAL}pt; /* Added font size */
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
                color: black;
            }}
            QPushButton:checked {{ /* For preset buttons */
                background-color: {BUTTON_COLOR};
                color: black;
            }}
            QPushButton:checked:hover {{ /* For preset buttons */
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
            QSlider::groove:horizontal {{
                border: 1px solid #bbb;
                background: white;
                height: 8px; 
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {BUTTON_COLOR};
                border: 1px solid {BUTTON_COLOR};
                width: 18px; 
                margin: -5px 0; 
                border-radius: 9px; 
            }}
            QSlider::handle:horizontal:hover {{
                background: {BUTTON_HOVER};
                border: 1px solid {BUTTON_HOVER};
            }}
            QDoubleSpinBox {{
                background-color: {BOX_BACKGROUND};
                color: {TEXT_COLOR};
                border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 1px 3px; /* Adjusted padding */
                min-height: {BUTTON_HEIGHT - 2}px; /* Align height with buttons */
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_NORMAL}pt;
            }}
            QDoubleSpinBox:disabled {{
                background-color: {BUTTON_DISABLED};
                color: #777;
                border: {BORDER_WIDTH}px solid #555;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: {BUTTON_COLOR};
                border: none; 
                border-radius: {int(BORDER_RADIUS / 2)}px; /* Smaller radius */
                width: 18px; /* Adjust width */
                /* Height will be managed by Qt to fit */
            }}
            QDoubleSpinBox::up-button {{
                subcontrol-position: top right;
                margin-right: 2px; /* Space from border */
                margin-top: 2px;
            }}
            QDoubleSpinBox::down-button {{
                subcontrol-position: bottom right;
                margin-right: 2px; /* Space from border */
                margin-bottom: 2px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {BUTTON_HOVER};
            }}
             QDoubleSpinBox::up-arrow {{
                image: url(./client/widgets/icons/arrow_up_light.png); /* Replace with your icon path */
                width: 10px;
                height: 10px;
            }}
            QDoubleSpinBox::down-arrow {{
                image: url(./client/widgets/icons/arrow_down_light.png); /* Replace with your icon path */
                width: 10px;
                height: 10px;
            }}
            QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off {{
               image: url(./client/widgets/icons/arrow_up_grey.png); /* Disabled state icon */
            }}
            QDoubleSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off {{
               image: url(./client/widgets/icons/arrow_down_grey.png); /* Disabled state icon */
            }}
        """)

        PRESET_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: {BOX_BACKGROUND};
            color: {TEXT_COLOR};
            border: {BORDER_WIDTH}px solid {BUTTON_COLOR};
            border-radius: {BORDER_RADIUS}px;
            padding: 4px 8px; /* Thinner padding */
            min-height: 24px; /* Thinner height */
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
        for btn in (self.low_btn, self.mid_btn, self.high_btn):
            btn.setStyleSheet(PRESET_BUTTON_STYLE)
        self.crop_btn.setStyleSheet(PRESET_BUTTON_STYLE) # Apply preset style to crop_btn

        self.preset_group.idClicked.connect(self.update_calibration_status)
        self.res_dropdown.currentIndexChanged.connect(self.update_calibration_status)
        
        self.crop_btn.clicked.connect(self._on_crop_btn_clicked)
        # self.crop_factor_spinbox.valueChanged.connect(self.update_calibration_status) # Optional: update status on factor change

        self.on_preset_changed(self.preset_group.checkedId()) 
        self._update_crop_ui()

    def _update_crop_ui(self):
        """Updates UI elements related to the crop state: button text/state, dropdown, and calibration status."""
        # Text is now static ("Crop"), only update checked state
        self.crop_btn.setChecked(self.cropped)
        
        # Ensure spinbox is always enabled, regardless of crop state
        self.crop_factor_spinbox.setEnabled(True)

        self._populate_res_dropdown() 
        self.update_calibration_status() 

    def _on_crop_btn_clicked(self):
        """Handles the crop button click event. Updates UI state only."""
        self.cropped = self.crop_btn.isChecked() # Update internal state from button's check state
        self._update_crop_ui() # Update text and other dependent UI
        # Debug print to show the UI state change
        print(f"[DEBUG] Crop button clicked. UI crop state set to: {self.cropped}. Current Factor in UI: {self.crop_factor_spinbox.value()}.")
        # self.crop_config_requested.emit() # DO NOT emit here. Config is applied by the main "Apply Settings" button.

    def on_preset_changed(self, id):
        if id == 0:
            self.current_presets = RES_PRESETS_LOW
        elif id == 1:
            self.current_presets = RES_PRESETS_MID
        elif id == 2:
            self.current_presets = RES_PRESETS_HIGH
        self._populate_res_dropdown()

    def _populate_res_dropdown(self, add_custom_cropped_item=False): # add_custom_cropped_item is not actively used by this simplified version
        self.res_dropdown.blockSignals(True)
        
        current_selected_text = self.res_dropdown.currentText() # Store current selection before clearing

        self.res_dropdown.clear()
        
        items_to_add = []

        if not self.current_presets:
            print("[WARNING] _populate_res_dropdown: self.current_presets was None or empty. Attempting to default to RES_PRESETS_LOW.")
            active_preset_button = self.preset_group.checkedButton()
            if active_preset_button == self.low_btn:
                self.current_presets = RES_PRESETS_LOW
            elif active_preset_button == self.mid_btn:
                self.current_presets = RES_PRESETS_MID
            elif active_preset_button == self.high_btn:
                self.current_presets = RES_PRESETS_HIGH
            else: 
                self.current_presets = RES_PRESETS_LOW
                if self.low_btn: 
                    self.low_btn.setChecked(True) 

        if self.current_presets: 
            for label, data in self.current_presets:
                if data == "legacy":
                    items_to_add.append(f"{label} (Legacy)")
                else:
                    items_to_add.append(f"{label} ({data[0]}x{data[1]})")
        
        if items_to_add:
            self.res_dropdown.addItems(items_to_add)
            
            # Try to restore previous selection
            if current_selected_text:
                new_index = self.res_dropdown.findText(current_selected_text)
                if new_index != -1:
                    self.res_dropdown.setCurrentIndex(new_index)
                elif self.res_dropdown.count() > 0: # Fallback to first item if previous not found
                    self.res_dropdown.setCurrentIndex(0)
            elif self.res_dropdown.count() > 0: # Default to first item if there was no previous selection
                 self.res_dropdown.setCurrentIndex(0)
        else:
            print(f"[ERROR] _populate_res_dropdown: No items to add to res_dropdown. self.current_presets: {self.current_presets}. Dropdown will be empty.")

        self.res_dropdown.blockSignals(False)

    def get_current_resolution_label(self):
        """Get the base label of the current selection (without ' (Cropped)')."""
        label = self.res_dropdown.currentText()
        return label.replace(" (Cropped)", "")

    def get_config(self):
        # Add debug prints to understand the state when get_config is called
        # print(f"[DEBUG] get_config: res_dropdown count: {self.res_dropdown.count()}, currentIndex: {self.res_dropdown.currentIndex()}, currentText: '{self.res_dropdown.currentText()}'")
        # if self.current_presets:
        #     print(f"[DEBUG] get_config: self.current_presets has {len(self.current_presets)} items. First is: {self.current_presets[0]}")
        # else:
        #     print(f"[DEBUG] get_config: self.current_presets is None or empty.")

        res_idx = self.res_dropdown.currentIndex()
        
        base_resolution_data = None
        preset_label_for_config = ""

        if res_idx != -1 and self.current_presets and res_idx < len(self.current_presets):
            preset_label_for_config, base_resolution_data = self.current_presets[res_idx]
        elif self.current_presets: 
            if res_idx == -1: 
                print(f"[WARNING] Invalid res_idx {res_idx} from dropdown. Falling back to first preset in current_presets list.")
            preset_label_for_config, base_resolution_data = self.current_presets[0]
        else:
            print("[ERROR] get_config: No resolution presets available (self.current_presets is empty/None). Using hardcoded default.")
            return {
                "jpeg_quality": self.jpeg_slider.value(),
                "fps": self.fps_slider.value(),
                "resolution": (640, 480), 
                "calibration_file": CALIBRATION_FILES.get("legacy") or "calibrations/calibration_default.npz",
                "cropped": False,
                "crop_factor": None,
                "preset_type": "fallback_critical"
            }

        current_crop_factor = self.crop_factor_spinbox.value() # Always read the current factor
        is_cropped = getattr(self, 'cropped', False)
        
        original_width, original_height = (0,0) 
        calibration_file = "calibrations/calibration_default.npz" # Default calibration
        preset_type = "unknown"

        if base_resolution_data == "legacy":
            original_width, original_height = 1536, 864 
            calibration_file = CALIBRATION_FILES.get("legacy", "calibrations/calibration_default.npz")
            preset_type = "legacy"
        elif isinstance(base_resolution_data, tuple) and len(base_resolution_data) == 2:
            original_width, original_height = base_resolution_data
            preset_type = "standard"
            calibration_resolution_key = (original_width, original_height)
            calibration_file = CALIBRATION_FILES.get(calibration_resolution_key, "calibrations/calibration_default.npz")
        else:
            print(f"[ERROR] get_config: Invalid base_resolution_data: {base_resolution_data}. Using hardcoded default.")
            return {
                "jpeg_quality": self.jpeg_slider.value(),
                "fps": self.fps_slider.value(),
                "resolution": (640, 480),
                "calibration_file": "calibrations/calibration_default.npz",
                "cropped": False,
                "crop_factor": None,
                "preset_type": "fallback_data_error"
            }

        actual_resolution = (original_width, original_height)
        if is_cropped and current_crop_factor > 0 and original_height > 0:
            cropped_height = int(original_height / current_crop_factor)
            cropped_height = max(1, cropped_height)
            actual_resolution = (original_width, cropped_height)
        
        cfg = {
             "jpeg_quality": self.jpeg_slider.value(),
             "fps": self.fps_slider.value(),
             "resolution": actual_resolution,
             "calibration_file": calibration_file,
             "cropped": is_cropped,
             "crop_factor": current_crop_factor if is_cropped else None,
             "preset_type": preset_type,
             "preset_label": preset_label_for_config
        }
        # ── include new sliders ──
        cfg["brightness"] = self.brightness_slider.value()
        # map 1–100% slider to 100µs–200000µs exposure
        pct = self.exposure_slider.value() / 100.0
        min_us, max_us = 100, 200_000
        cfg["exposure"] = int(min_us + pct * (max_us - min_us))

    def update_calibration_status(self):
        """Slot: update the calibration_status_label based on current selection."""
        # figure out which resolution key is selected
        idx = self.res_dropdown.currentIndex()
        status = "Unknown"
        try:
            _, base = self.current_presets[idx]
            cal_path = CALIBRATION_FILES.get(base, "")
            status = "Found" if os.path.exists(cal_path) else "Missing"
        except Exception:
            pass
        self.calibration_status_label.setText(f"Calibration: {status}")
