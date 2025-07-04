from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QLabel, QPushButton,
    QSizePolicy, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from theme import (
    BOX_BACKGROUND, SECOND_COLUMN, BORDER_COLOR, BOX_TITLE_COLOR,
    TEXT_COLOR, FONT_FAMILY, FONT_SIZE_NORMAL, BORDER_WIDTH, BORDER_RADIUS
)
import os


class HealthPanelWidget(QScrollArea):
    speedtest_result = pyqtSignal(float, float)

    def __init__(self, parent=None, sio_client=None):
        super().__init__(parent)
        self.sio = sio_client               # <<< store the socket client
        self._build_ui()
        self.speedtest_result.connect(self._update_speed_labels)
        self._setup_socket_handlers()

    def _build_ui(self):
        # Container inside scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

        # --- Health Report Button ---
        self.print_report_btn = QPushButton("Print Health Check Report")
        self.print_report_btn.setEnabled(False)
        self.print_report_btn.clicked.connect(self._export_health_report)
        layout.addWidget(self.print_report_btn)

        # --- System Performance Group ---
        perf_group = QGroupBox("System Info")
        perf_layout = QVBoxLayout()

        lbl_style = f"""
            QLabel {{ color: {TEXT_COLOR}; font-size: {FONT_SIZE_NORMAL}pt;
                     font-family: {FONT_FAMILY}; margin:2px 0; padding:2px 0; }}
        """

        # add a comms status label
        self.comms_status_label = QLabel("Comm: Disconnected")
        self.comms_status_label.setStyleSheet(lbl_style)
        perf_layout.addWidget(self.comms_status_label)

        self.info_labels = {
            "temp":      QLabel("Temp: -- °C"),
            "cpu":       QLabel("CPU: --%"),
            "speed":     QLabel("Upload: -- Mbps"),
            "max_frame": QLabel("Max Frame: -- KB"),
            "fps":       QLabel("Live FPS: --"),
            "disp_fps":  QLabel("Display FPS: --"),
            "frame_size":QLabel("Frame Size: -- KB"),
        }
        for lbl in self.info_labels.values():
            lbl.setStyleSheet(lbl_style)
            perf_layout.addWidget(lbl)

        perf_group.setLayout(perf_layout)
        self._apply_groupbox_style(perf_group)
        layout.addWidget(perf_group)

        # --- Subsystem Status Groups ---
        subsystems = [
            ("Power Subsystem", [
                "Battery Voltage: Pending...",
                "Battery Current: Pending...",
                "Battery Temp: Pending...",
                "Status: Pending..."
            ]),
            ("Thermal Subsystem", [
                "Internal Temp: Pending...",
                "Status: Pending..."
            ]),
            ("Communication Subsystem", [
                "Downlink Frequency: Pending...",
                "Uplink Frequency: Pending...",
                "Signal Strength: Pending...",
                "Data Rate: Pending..."
            ]),
            ("ADCS Subsystem", [
                "Gyro: Pending...",
                "Orientation: Pending...",
                "Sun Sensor: Pending...",
                "Wheel Rpm: Pending...",
                "Status: Pending..."
            ]),
            ("Payload Subsystem", []),
            ("Command & Data Handling Subsystem", [
                "Memory Usage: Pending...",
                "Last Command: Pending...",
                "Uptime: Pending...",
                "Status: Pending..."
            ]),
            ("Error Log", [
                "No Critical Errors Detected: Pending..."
            ]),
            ("Overall Status", [
                "No Anomalies Detected: Pending...",
                "Recommended Actions: Pending..."
            ]),
        ]
        for name, items in subsystems:
            grp = QGroupBox(name)
            sublay = QVBoxLayout()
            if name == "Payload Subsystem":
                # add the two labels you need
                self.camera_status_label = QLabel("Camera: Pending...")
                self.camera_ready_label  = QLabel("Status: Not Ready")
                for lbl in (self.camera_status_label, self.camera_ready_label):
                    lbl.setStyleSheet(f"QLabel {{ color:#bbb; margin:2px 0; padding:2px 0; "
                                      f"font-family:{FONT_FAMILY}; font-size:{FONT_SIZE_NORMAL}pt; }}")
                    sublay.addWidget(lbl)
            else:
                for t in items:
                    lbl = QLabel(t)
                    lbl.setStyleSheet(f"QLabel {{ color:#bbb; margin:2px 0; padding:2px 0; "
                                      f"font-family:{FONT_FAMILY}; font-size:{FONT_SIZE_NORMAL}pt; }}")
                    sublay.addWidget(lbl)
            grp.setLayout(sublay)
            self._apply_groupbox_style(grp)
            layout.addWidget(grp)

        layout.addStretch()
        container.setLayout(layout)

        # set up scroll area
        self.setWidget(container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(f"background-color: {SECOND_COLUMN};")

    def _apply_groupbox_style(self, grp: QGroupBox):
        grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ss = f"""
            QGroupBox {{ border:{BORDER_WIDTH}px solid {BORDER_COLOR};
                        border-radius:{BORDER_RADIUS}px;
                        background-color:{BOX_BACKGROUND};
                        margin-top:6px; color:{BOX_TITLE_COLOR}; }}
            QGroupBox::title {{ subcontrol-origin:margin;
                               left:6px; padding:0 2px;
                               font-size:{FONT_SIZE_NORMAL+2}pt;
                               font-family:{FONT_FAMILY}; color:{BOX_TITLE_COLOR};}}
        """
        grp.setStyleSheet(ss)

    def _export_health_report(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Health Check Report", "health_report.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return
        try:
            lines = []
            # performance
            for lbl in self.info_labels.values():
                lines.append(lbl.text())
            # subsystem groups
            container = self.widget()
            for grp in container.findChildren(QGroupBox):
                lines.append(f"\n=== {grp.title()} ===")
                for lbl in grp.findChildren(QLabel):
                    if lbl not in self.info_labels.values():
                        lines.append(lbl.text())
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            QMessageBox.information(self, "Success", f"Health report exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

    def _update_speed_labels(self, upload_mbps, max_frame_kb):
        if upload_mbps < 0:
            self.info_labels["speed"].setText("Upload: Error")
            self.info_labels["max_frame"].setText("Max Frame: -- KB")
        else:
            self.info_labels["speed"].setText(f"Upload: {upload_mbps:.2f} Mbps")
            self.info_labels["max_frame"].setText(f"Max Frame: {max_frame_kb:.1f} KB")

    def _setup_socket_handlers(self):
        if not self.sio:
            return

        @self.sio.on("sensor_broadcast")
        def on_sensor_data(data):
            temp = data.get("temperature", 0.0)
            cpu  = data.get("cpu_percent", 0.0)
            self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
            self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
            if "fps" in data:
                self.info_labels["fps"].setText(f"Server FPS: {data['fps']:.1f}")

        @self.sio.event
        def connect():
            self.print_report_btn.setEnabled(True)
            self.comms_status_label.setText("Comm: Connected")

        @self.sio.event
        def disconnect(reason=None):
            self.comms_status_label.setText("Comm: Disconnected")

    # ── New public API methods ──

    def update_comm_status(self, connected: bool):
        text = "Comm: Connected" if connected else "Comm: Disconnected"
        self.comms_status_label.setText(text)

    def update_sensor_display(self, data):
        """Update sensor information display"""
        try:
            temp = data.get("temperature", 0)
            cpu = data.get("cpu_percent", 0)
            self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
            self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")
        except Exception as e:
            print(f"[ERROR] Sensor update error: {e}")

    def update_sensor_data(self, temperature: float, cpu_pct: float):
        self.info_labels["temp"].setText(f"Temp: {temperature:.1f} °C")
        self.info_labels["cpu"].setText(f"CPU: {cpu_pct:.1f} %")

    def update_fps(self, fps: float):
        self.info_labels["fps"].setText(f"Live FPS: {fps:.1f}")

    def update_display_fps(self, disp_fps: float):
        self.info_labels["disp_fps"].setText(f"Display FPS: {disp_fps:.1f}")

    def update_frame_size(self, size_kb: float):
        self.info_labels["frame_size"].setText(f"Frame Size: {size_kb:.1f} KB")

    def update_camera_status(self, status: str, ready: bool):
        # status text
        self.camera_status_label.setText(f"Camera: {status}")
        # ready text + color
        ready_text = "Ready" if ready else "Not Ready"
        self.camera_ready_label.setText(f"Status: {ready_text}")
        color = "#0f0" if ready else "#f00"
        self.camera_ready_label.setStyleSheet(f"QLabel {{ color: {color}; }}")