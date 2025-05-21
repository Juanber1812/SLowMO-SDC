import sys
import cv2
import numpy as np
import socketio
import threading
import time  # <-- Add this line
import queue

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap

SERVER_URL = "http://192.168.1.146:5000"
CHESSBOARD_SIZE = (15,8)
SQUARE_SIZE = 0.016  # in meters
SAVE_FILE = "calibration_data.npz"

sio = socketio.Client()

class FrameBridge(QObject):
    new_frame = pyqtSignal(np.ndarray)

bridge = FrameBridge()

frame_queue = queue.Queue(maxsize=2)  # <-- Add this line at the top, after imports

class CalibrationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calibration Tool")
        self.setMinimumSize(1024, 600)

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 360)

        self.capture_btn = QPushButton("Capture")
        self.calibrate_btn = QPushButton("Calibrate")
        self.save_btn = QPushButton("Save")
        self.status_label = QLabel("Status: Waiting for stream...")
        self.count_label = QLabel("Captured: 0")
        self.info_label = QLabel(f"Chessboard: {CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]} | Square: {SQUARE_SIZE}m")

        self.capture_btn.clicked.connect(self.capture_frame)
        self.calibrate_btn.clicked.connect(self.run_calibration)
        self.save_btn.clicked.connect(self.save_calibration)

        self.capture_btn.setEnabled(False)
        self.calibrate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.count_label)
        layout.addWidget(self.status_label)
        btns = QHBoxLayout()
        btns.addWidget(self.capture_btn)
        btns.addWidget(self.calibrate_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)
        self.setLayout(layout)

        self.last_frame = None
        self.last_found = False
        self.last_corners = None
        self.objpoints = []
        self.imgpoints = []
        self.frames = []

        bridge.new_frame.connect(self.handle_frame)

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.process_frame_queue)
        self.frame_timer.start(30)  # ~33 FPS

    def handle_frame(self, frame):
        self.last_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, flags)
        print("Chessboard found:", found)  # Add this line for debugging

        if found:
            self.last_found = True
            self.last_corners = corners
            self.capture_btn.setEnabled(True)
            cv2.drawChessboardCorners(frame, CHESSBOARD_SIZE, corners, found)
            self.status_label.setText("Chessboard detected.")
        else:
            self.last_found = False
            self.last_corners = None
            self.capture_btn.setEnabled(False)
            self.status_label.setText("No chessboard found.")

        # --- Improved resizing for QLabel ---
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        label_w = self.image_label.width()
        label_h = self.image_label.height()

        # Compute new size keeping aspect ratio
        scale = min(label_w / w, label_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        qimg = QImage(resized.data, new_w, new_h, new_w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.image_label.setPixmap(pixmap)

    def capture_frame(self):
        if self.last_frame is not None and self.last_found and self.last_corners is not None:
            self.frames.append(self.last_frame.copy())

            objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
            objp *= SQUARE_SIZE

            self.objpoints.append(objp)
            self.imgpoints.append(self.last_corners)

            self.count_label.setText(f"Captured: {len(self.frames)}")
            self.status_label.setText("Captured frame.")
            self.calibrate_btn.setEnabled(len(self.frames) >= 5)

    def run_calibration(self):
        if len(self.objpoints) < 5:
            QMessageBox.warning(self, "Not Enough Frames", "Capture at least 5 chessboard frames.")
            return

        img_shape = self.frames[0].shape[1::-1]
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self.objpoints, self.imgpoints, img_shape, None, None
        )

        if ret:
            self.calibration = {"mtx": mtx, "dist": dist}
            self.status_label.setText("Calibration successful.")
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
        try:
            sio.disconnect()
        except:
            pass
        event.accept()

    def process_frame_queue(self):
        try:
            frame = frame_queue.get_nowait()  # Use the global frame_queue
            self.handle_frame(frame)
        except queue.Empty:
            pass

# === SocketIO Events ===

last_emit_time = 0

@sio.on("frame")
def on_frame(data):
    try:
        arr = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            try:
                frame_queue.put_nowait(frame)  # Use the global frame_queue
            except queue.Full:
                pass  # Drop frame if queue is full
    except Exception as e:
        print(f"[ERROR] Frame decode failed: {e}")

# === SocketIO Connection Thread ===

def socket_thread():
    while True:
        try:
            sio.connect(SERVER_URL, wait_timeout=5)
            sio.wait()
        except Exception as e:
            print(f"[SocketIO ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CalibrationApp()
    win.show()

    threading.Thread(target=socket_thread, daemon=True).start()
    sys.exit(app.exec())
