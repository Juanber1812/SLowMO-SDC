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

CHESSBOARD_SIZE = (9, 6)
SQUARE_SIZE = 0.025  # meters
SAVE_FILE = "calibration_data.npz"
SERVER_URL = "http://192.168.1.146:5000"  # Change if needed

sio = socketio.Client()

class FrameSignal(QObject):
    frame_received = pyqtSignal(np.ndarray)

frame_signal = FrameSignal()

class CalibrationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Calibration Tool")

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
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
        layout.addWidget(self.chessboard_info_label)  # Add this line
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
        self.timer.start(30)

        frame_signal.frame_received.connect(self.on_new_frame)

        # Connect to the server
        try:
            sio.connect(SERVER_URL)
        except Exception as e:
            self.status_label.setText(f"Failed to connect to server: {e}")

    def update_display(self):
        if self.last_frame is not None:
            display_frame = self.last_frame.copy()
            if self.last_found and self.last_corners is not None:
                cv2.drawChessboardCorners(display_frame, CHESSBOARD_SIZE, self.last_corners, self.last_found)
            rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self.image_label.setPixmap(pixmap)
            self.capture_btn.setEnabled(self.last_found)
        else:
            self.capture_btn.setEnabled(False)

    def on_new_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE)
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
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self.objpoints, self.imgpoints, img_shape, None, None
        )
        if ret:
            self.status_label.setText("Calibration successful.")
            self.calibration = {"mtx": mtx, "dist": dist}
            self.save_btn.setEnabled(True)
        else:
            self.status_label.setText("Calibration failed.")

    def save_calibration(self):
        if hasattr(self, "calibration"):
            np.savez(SAVE_FILE, mtx=self.calibration["mtx"], dist=self.calibration["dist"])
            self.status_label.setText(f"Saved to {SAVE_FILE}")
        else:
            QMessageBox.warning(self, "No Data", "No calibration data to save.")

    def closeEvent(self, event):
        sio.disconnect()
        event.accept()

# SocketIO event for receiving frames
@sio.on("frame")
def on_frame(data):
    arr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is not None:
        frame_signal.frame_received.emit(frame)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CalibrationApp()
    win.show()
    sys.exit(app.exec())
