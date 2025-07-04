from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGroupBox
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
    def __init__(self, parent_window=None):
        super().__init__(parent_window)  # Changed title to include both camera and detector

        self.parent_window = parent_window  # Store reference to parent
        # Changed from QGridLayout to QVBoxLayout for vertical stacking
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Camera Control Buttons
        self.toggle_btn = QPushButton("Run Stream")
        self.reconnect_btn = QPushButton("Reconnect")
        self.capture_btn = QPushButton("Capture Image")

        # New: Get Battery Temp Button
        self.get_batt_temp_btn = QPushButton("Get Battery Temp")
        
        # Detector Control Button
        self.detector_btn = QPushButton("Run Detector")
        
        # Manual Orientation Button
        self.orientation_btn = QPushButton("Show Crosshairs")
        self.show_crosshairs = True  # Track crosshair state - default ON

        # Define button style (thinner, same as Start Detector)
        self.BUTTON_STYLE = f"""
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
            background-color: {PLOT_LINE_PRIMARY};
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

        # Apply the same style to all buttons
        for btn in (self.toggle_btn, self.reconnect_btn, self.capture_btn, self.detector_btn, self.orientation_btn, self.get_batt_temp_btn):
            btn.setStyleSheet(self.BUTTON_STYLE)
            
        # Make the Start Detector button checkable and set it to stay pressed when toggled
        self.detector_btn.setCheckable(True)
        self.toggle_btn.setCheckable(True)
        self.orientation_btn.setCheckable(True)

        # Replace check_btn1, check_btn2, etc. with descriptive names
        #self.run_lidar_btn = QPushButton("Run LiDAR")
        #self.run_camera_btn = QPushButton("Run Camera")
        #self.run_something_btn = QPushButton("Run Something")
        #self.extra_option_btn = QPushButton("Extra Option")
        #for btn in (self.run_lidar_btn, self.run_camera_btn, self.run_something_btn, self.extra_option_btn):
        #    btn.setCheckable(True)
        #    btn.setStyleSheet(self.BUTTON_STYLE)
            
        # Connect camera buttons to parent window methods if they exist
        if self.parent_window:
            if hasattr(self.parent_window, 'toggle_stream'):
                self.toggle_btn.clicked.connect(self.parent_window.toggle_stream)
            if hasattr(self.parent_window, 'try_reconnect'):
                self.reconnect_btn.clicked.connect(self.parent_window.try_reconnect)
            if hasattr(self.parent_window, 'capture_image'):
                self.capture_btn.clicked.connect(self.parent_window.capture_image)
            if hasattr(self.parent_window, 'toggle_detector'):
                self.detector_btn.clicked.connect(self.parent_window.toggle_detector)
            if hasattr(self.parent_window, 'toggle_orientation'):
                self.orientation_btn.clicked.connect(self.parent_window.toggle_orientation)
            # Optionally connect Get Battery Temp button if handler exists
            if hasattr(self.parent_window, 'get_battery_temp'):
                self.get_batt_temp_btn.clicked.connect(self.parent_window.get_battery_temp)

        # Default states
        self.toggle_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)  # Will be enabled when connected
        self.detector_btn.setEnabled(False)  # Will be enabled when connected
        
        # Set crosshairs button to be checked by default
        self.orientation_btn.setChecked(False)

        # Add to layout vertically (all buttons stacked)
        #self.layout.addWidget(self.run_camera_btn)
        #self.layout.addWidget(self.run_lidar_btn)
        self.layout.addWidget(self.detector_btn)
        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.reconnect_btn)
        self.layout.addWidget(self.capture_btn)
        self.layout.addWidget(self.get_batt_temp_btn)
        self.layout.addWidget(self.orientation_btn)

        #self.layout.addWidget(self.run_something_btn)
        #self.layout.addWidget(self.extra_option_btn)
        # Add the new checkable buttons

        
        # Set layout spacing
        self.layout.setSpacing(WIDGET_SPACING)
        self.layout.setContentsMargins(WIDGET_MARGIN, WIDGET_MARGIN, WIDGET_MARGIN, WIDGET_MARGIN)

        # GroupBox styling
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {BOX_BACKGROUND};
                border: {BORDER_WIDTH}px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {BOX_TITLE_COLOR};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_TITLE}pt;
            }}
        """)

    def apply_style(self, style: str):
        """Apply external style while preserving button styles"""
        # Store current button styles
        button_styles = {}
        for btn_name in ['toggle_btn', 'reconnect_btn', 'capture_btn', 'detector_btn']:
            btn = getattr(self, btn_name)
            button_styles[btn_name] = btn.styleSheet()
        
        # Apply the new style
        self.setStyleSheet(style)
        
        # Restore button styles
        for btn_name, btn_style in button_styles.items():
            btn = getattr(self, btn_name)
            btn.setStyleSheet(btn_style)
