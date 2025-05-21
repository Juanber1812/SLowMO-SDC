import sys
import cv2
import numpy as np
import os
import socketio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap
import time

CHESSBOARD_SIZE = (16, 9)
SQUARE_SIZE = 0.025
SAVE_FILE = "calibration_data.npz"
SERVER_URL = "http://192.168.1.146:5000"

sio = socketio.Client()

class FrameSignal(QObject):
    frame_received = pyqtSignal(np.ndarray)

frame_signal = FrameSignal()

class CalibrationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Calibration Tool")

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(1024, 576)
        self.image_label.setMaximumSize(1536, 864)
        self.capture_btn = QPushButton("Capture Frame")
        self.calibrate_btn = QPushButton("Calibrate")
        self.save_btn = QPushButton("Save Calibration")
        self.status_label = QLabel("Status: Waiting for stream...")
        self.image_count_label = QLabel("Captured: 0")
        self.chessboard_info_label = QLabel(
            f"Chessboard: {CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]}, Square Size: {SQUARE_SIZE} m",
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.capture_btn.clicked.connect(self.capture_frame)
        self.calibrate_btn.clicked.connect(self.calibrate_camera)
        self.save_btn.clicked.connect(self.save_calibration)

        self.calibrate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.chessboard_info_label)
        layout.addWidget(self.image_label)
        btns = QHBoxLayout()
        btns.addWidget(self.capture_btn)
        btns.addWidget(self.calibrate_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)
        layout.addWidget(self.image_count_label)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.last_frame = None
        self.last_found = False
        self.last_corners = None
        self.captured_frames = []
        self.objpoints = []
        self.imgpoints = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)

        frame_signal.frame_received.connect(self.on_new_frame)

    def update_display(self):
        if self.last_frame is not None:
            display_frame = self.last_frame.copy()
            rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
            self.capture_btn.setEnabled(self.last_found)
        else:
            self.capture_btn.setEnabled(False)

    def on_new_frame(self, frame):
        if frame is None or frame.size == 0:
            self.status_label.setText("Received empty frame.")
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Improve detection stability for large boards
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, flags)

        if found:
            criteria = (cv2.TermCriteria_EPS + cv2.TermCriteria_MAX_ITER, 30, 0.001)
            cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)

        self.last_frame = frame
        self.last_found = found
        self.last_corners = corners if found else None

        if found:
            self.status_label.setText("Chessboard detected.")
        else:
            self.status_label.setText("Show chessboard to camera.")

    def capture_frame(self):
        if self.last_frame is not None and self.last_found and self.last_corners is not None:
            frame = self.last_frame.copy()
            self.captured_frames.append(frame)

            if len(self.captured_frames) > 30:
                self.captured_frames.pop(0)
                self.objpoints.pop(0)
                self.imgpoints.pop(0)

            objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
            objp *= SQUARE_SIZE
            self.objpoints.append(objp)
            self.imgpoints.append(self.last_corners)

            self.image_count_label.setText(f"Captured: {len(self.captured_frames)}")
            self.status_label.setText("Captured frame with chessboard.")
            self.calibrate_btn.setEnabled(True)
        else:
            self.status_label.setText("No chessboard detected.")

    def calibrate_camera(self):
        if len(self.objpoints) < 5:
            QMessageBox.warning(self, "Not Enough Frames", "Capture at least 5 frames with detected chessboards.")
            return

        img_shape = self.captured_frames[0].shape[1::-1]
        try:
            ret, mtx, dist, _, _ = cv2.calibrateCamera(
                self.objpoints, self.imgpoints, img_shape, None, None
            )
            if ret:
                self.status_label.setText("Calibration successful.")
                self.calibration = {"mtx": mtx, "dist": dist, "img_shape": img_shape}
                self.save_btn.setEnabled(True)
            else:
                self.status_label.setText("Calibration failed.")
        except Exception as e:
            self.status_label.setText(f"Calibration error: {e}")

    def save_calibration(self):
        if hasattr(self, "calibration"):
            try:
                np.savez(SAVE_FILE, mtx=self.calibration["mtx"], dist=self.calibration["dist"], img_shape=self.calibration["img_shape"])
                self.status_label.setText(f"Saved to {SAVE_FILE}")
            except Exception as e:
                self.status_label.setText(f"Save error: {e}")
        else:
            QMessageBox.warning(self, "No Data", "No calibration data to save.")

    def closeEvent(self, event):
        try:
            sio.disconnect()
        except Exception:
            pass
        event.accept()


@sio.on("frame")
def on_frame(data):
    arr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is not None:
        frame_signal.frame_received.emit(frame)



if __name__ == "__main__":
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print(f"Socket connection failed: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    win = CalibrationApp()
    win.show()
    sys.exit(app.exec())
