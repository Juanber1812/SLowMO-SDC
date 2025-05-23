# ui/ui_main.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from bridge import bridge
from detector_worker import DetectorWorker
import socket_handler
from ui.ui_stream import create_stream_section
from ui.ui_graphs import create_graph_section
from ui.ui_info import create_info_section
from ui.ui_styles import apply_group_styles
from config import GRAPH_MODES

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SLowMO Client")

        self.streaming = False
        self.detector_worker = DetectorWorker()

        self.graph_widget = None
        self.shared_start_time = None

        # Placeholders for required widgets
        self.toggle_btn = None
        self.detector_btn = None
        self.apply_btn = None
        self.comms_status_label = None
        self.info_labels = {}
        self.camera_status_label = None
        self.camera_ready_label = None
        self.image_label = None
        self.analysed_label = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # The following functions must assign the required widgets to self
        # e.g., self.toggle_btn, self.detector_btn, self.apply_btn, etc.
        self.left_column = create_stream_section(self)
        self.right_column = create_graph_section(self, GRAPH_MODES)
        self.info_column = create_info_section(self)

        layout.addLayout(self.left_column)
        layout.addLayout(self.right_column)
        layout.addLayout(self.info_column)

        apply_group_styles(self)

    def _connect_signals(self):
        bridge.frame_received.connect(self.on_frame_received)
        bridge.analysed_frame.connect(self.on_analysed_frame)
        bridge.update_system_info.connect(self.update_system_info)
        bridge.update_camera_status.connect(self.update_camera_status)

    def update_system_info(self, temp, cpu):
        if "temp" in self.info_labels:
            self.info_labels["temp"].setText(f"Temp: {temp:.1f} °C")
        if "cpu" in self.info_labels:
            self.info_labels["cpu"].setText(f"CPU: {cpu:.1f} %")

    def update_camera_status(self, status):
        if self.camera_status_label:
            self.camera_status_label.setText(f"Camera: {status}")
            if status.lower() == "streaming":
                self.camera_status_label.setStyleSheet("color: #0f0;")
            elif status.lower() == "idle":
                self.camera_status_label.setStyleSheet("color: #ff0;")
            else:
                self.camera_status_label.setStyleSheet("color: #bbb;")

    def on_frame_received(self, frame):
        self.last_frame = frame
        if self.streaming and self.image_label:
            self.image_label.setPixmap(self._convert_frame_to_pixmap(frame))
        if self.detector_worker.active:
            self.detector_worker.feed_frame(frame)

    def on_analysed_frame(self, frame):
        if self.analysed_label:
            self.analysed_label.setPixmap(self._convert_frame_to_pixmap(frame))

    def _convert_frame_to_pixmap(self, frame):
        import cv2
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtCore import Qt

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        return pixmap.scaled(384, 216, Qt.AspectRatioMode.KeepAspectRatio)

    def toggle_detector(self):
        if self.detector_worker.active:
            self.detector_worker.stop()
            if self.detector_btn:
                self.detector_btn.setText("Start Detector")
        else:
            self.detector_worker.graph_widget = self.graph_widget
            self.detector_worker.start()
            if self.detector_btn:
                self.detector_btn.setText("Stop Detector")
