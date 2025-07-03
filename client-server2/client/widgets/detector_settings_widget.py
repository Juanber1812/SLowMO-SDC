from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QComboBox, QDoubleSpinBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

class DetectorSettingsWidget(QGroupBox):
    """
    PyQt6 widget to tweak AprilTag detector params on-the-fly.
    Emits settingsChanged(dict) on any change.
    """
    settingsChanged = pyqtSignal(dict)
    tagSizeUpdated = pyqtSignal(float)  # Move this to class level

    FAMILIES = [
        'tag25h9','tag36h11',  'tag16h5', 'tagStandard41h12'
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── 1) Create controls ────────────────────────────────────────
        self.family_combo = QComboBox()
        self.family_combo.addItems(self.FAMILIES)
        self.family_combo.currentTextChanged.connect(self._emit_settings)

        # Threads
        self.threads_slider = QSlider(Qt.Orientation.Horizontal)
        self.threads_slider.setRange(1, 16)
        self.threads_slider.setValue(4)
        self.threads_slider.setSingleStep(1)
        self.threads_label = QLabel(str(self.threads_slider.value()))
        self.threads_slider.valueChanged.connect(
            lambda v: (self.threads_label.setText(str(v)), self._emit_settings())
        )

      
        self.decimate_slider = QSlider(Qt.Orientation.Horizontal)
        self.decimate_slider.setRange(1, 100)
        self.decimate_slider.setValue(5)
        self.decimate_slider.setSingleStep(1)  # corresponds to 1.0
        self.decimate_label = QLabel(f"{self.decimate_slider.value()*0.1:.1f}")
        self.decimate_slider.valueChanged.connect(
            lambda v: (self.decimate_label.setText(f"{v*0.1:.1f}"), self._emit_settings())
        )

        # Blur (quad_sigma 0.0–2.0, step 0.1 → slider 0–20)
        self.sigma_slider = QSlider(Qt.Orientation.Horizontal)
        self.sigma_slider.setRange(0, 20)
        self.sigma_slider.setValue(0)
        self.sigma_slider.setSingleStep(1)
        self.sigma_label = QLabel(f"{self.sigma_slider.value()*0.1:.1f}")
        self.sigma_slider.valueChanged.connect(
            lambda v: (self.sigma_label.setText(f"{v*0.1:.1f}"), self._emit_settings())
        )

        # Refine edges
        self.refine_slider = QSlider(Qt.Orientation.Horizontal)
        self.refine_slider.setRange(0, 10)
        self.refine_slider.setValue(10)
        self.refine_slider.setSingleStep(1)
        self.refine_label = QLabel(str(self.refine_slider.value()))
        self.refine_slider.valueChanged.connect(
            lambda v: (self.refine_label.setText(str(v)), self._emit_settings())
        )

        # Decode sharpening (0.0–1.0, step 0.05 → slider 0–20)
        self.decode_slider = QSlider(Qt.Orientation.Horizontal)
        self.decode_slider.setRange(0, 20)
        self.decode_slider.setValue(20)
        self.decode_slider.setSingleStep(1)
        self.decode_label = QLabel(f"{self.decode_slider.value()*0.05:.2f}")
        self.decode_slider.valueChanged.connect(
            lambda v: (self.decode_label.setText(f"{v*0.05:.2f}"), self._emit_settings())
        )

        # Tag size control - auto-update on value change
        tag_size_layout = QHBoxLayout()
        tag_size_layout.addWidget(QLabel("Tag Size (cm):"))
        self.tag_size_input = QDoubleSpinBox()
        self.tag_size_input.setRange(0.1, 100.0)  # 0.1cm to 100cm range
        self.tag_size_input.setDecimals(2)
        self.tag_size_input.setValue(5.5)  # Default 5.5cm (0.055m)
        self.tag_size_input.setSingleStep(0.1)

        # Connect to update immediately when value changes - convert cm to meters
        self.tag_size_input.valueChanged.connect(
            lambda value: self.tagSizeUpdated.emit(value / 100.0)  # Convert cm to meters
        )
        
        tag_size_layout.addWidget(self.tag_size_input)
        # No update button needed!

        # ── 2) Layout ────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        def add_row(label_text, widget, extra=None):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            row.addWidget(widget)
            if extra:
                row.addWidget(extra)
            layout.addLayout(row)

        add_row("Family:", self.family_combo)
        add_row("Threads:", self.threads_slider, self.threads_label)
        add_row("Decimate:", self.decimate_slider, self.decimate_label)
        add_row("Blur:", self.sigma_slider, self.sigma_label)
        add_row("Refine Edges:", self.refine_slider, self.refine_label)
        add_row("Decode Sharpening:", self.decode_slider, self.decode_label)
        layout.addLayout(tag_size_layout)

        # ── 3) Latency and Display FPS display ──────────────────────
        self.latency_label = QLabel("Latency: 0.0 ms")
        layout.addWidget(self.latency_label)
        
        self.display_fps_label = QLabel("Display FPS: --")
        layout.addWidget(self.display_fps_label)

        self.setLayout(layout)
        self._emit_settings()


    def _emit_settings(self):
        cfg = {
            'families':          self.family_combo.currentText(),
            'nthreads':          self.threads_slider.value(),
            'quad_decimate':     self.decimate_slider.value() * 0.1,
            'quad_sigma':        self.sigma_slider.value() * 0.1,
            'refine_edges':      self.refine_slider.value(),
            'decode_sharpening': self.decode_slider.value() * 0.05,
        }
        self.settingsChanged.emit(cfg)

    def set_latency(self, ms: float):
        """Update the latency display (in milliseconds)."""
        self.latency_label.setText(f"Latency: {ms:.1f} ms")

    def set_display_fps(self, fps: float):
        """Update the display FPS."""
        self.display_fps_label.setText(f"Display FPS: {fps:.1f}")

    def get_settings(self) -> dict:
        return {
            'families':          self.family_combo.currentText(),
            'nthreads':          self.threads_slider.value(),
            'quad_decimate':     self.decimate_slider.value() * 0.1,
            'quad_sigma':        self.sigma_slider.value() * 0.1,
            'refine_edges':      self.refine_slider.value(),
            'decode_sharpening': self.decode_slider.value() * 0.05,
        }