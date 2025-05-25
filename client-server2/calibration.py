import sys
import cv2
import numpy as np
import socketio
import threading
import time
import queue
import os

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QMessageBox, QComboBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap

SERVER_URL = "http://192.168.1.146:5000"
CHESSBOARD_SIZE = (15,8)
SQUARE_SIZE = 0.016  # in meters

sio = socketio.Client()

class FrameBridge(QObject):
    new_frame = pyqtSignal(np.ndarray)

bridge = FrameBridge()
frame_queue = queue.Queue(maxsize=2)

# Resolution mapping
RESOLUTION_LIST = [
    ("768x432", (768, 432)),
    ("1024x576", (1024, 576)), 
    ("1536x864", (1536, 864)),
    ("1920x1080", (1920, 1080)),
    ("2304x1296", (2304, 1296)),
    ("2560x1440", (2560, 1440)),
    ("2880x1620", (2880, 1620)),
    ("3456x1944", (3456, 1944)),
    ("4608x2592", (4608, 2592)),
]

RESOLUTION_FILES = {
    (768, 432): "calibrations/calibration_768x432.npz",
    (1024, 576): "calibrations/calibration_1024x576.npz", 
    (1536, 864): "calibrations/calibration_1536x864.npz",
    (1920, 1080): "calibrations/calibration_1920x1080.npz",
    (2304, 1296): "calibrations/calibration_2304x1296.npz",
    (2560, 1440): "calibrations/calibration_2560x1440.npz",
    (2880, 1620): "calibrations/calibration_2880x1620.npz",
    (3456, 1944): "calibrations/calibration_3456x1944.npz",
    (4608, 2592): "calibrations/calibration_4608x2592.npz",
}

class CalibrationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calibration Tool")
        self.setMinimumSize(1200, 700)

        # Main layout
        main_layout = QHBoxLayout()
        
        # Left side - Controls
        controls_layout = QVBoxLayout()
        
        # Resolution Control Group
        res_group = QGroupBox("Resolution Control")
        res_layout = QVBoxLayout()
        
        self.resolution_combo = QComboBox()
        for label, _ in RESOLUTION_LIST:
            self.resolution_combo.addItem(label)
        
        self.set_resolution_btn = QPushButton("Set Resolution")
        self.set_resolution_btn.clicked.connect(self.set_resolution)
        
        self.current_res_label = QLabel("Current: Unknown")
        
        self.start_stream_btn = QPushButton("Start Camera Stream")
        self.stop_stream_btn = QPushButton("Stop Camera Stream")
        self.start_stream_btn.clicked.connect(lambda: sio.emit("start_camera"))
        self.stop_stream_btn.clicked.connect(lambda: sio.emit("stop_camera"))
        
        res_layout.addWidget(QLabel("Select Resolution:"))
        res_layout.addWidget(self.resolution_combo)
        res_layout.addWidget(self.set_resolution_btn)
        res_layout.addWidget(self.current_res_label)
        res_layout.addWidget(self.start_stream_btn)
        res_layout.addWidget(self.stop_stream_btn)
        res_group.setLayout(res_layout)
        
        # Calibration Control Group
        calib_group = QGroupBox("Calibration Controls")
        calib_layout = QVBoxLayout()
        
        self.capture_btn = QPushButton("Capture Frame")
        self.calibrate_btn = QPushButton("Calibrate")
        self.save_btn = QPushButton("Save Calibration")
        self.reset_btn = QPushButton("Reset/New Calibration")
        
        self.capture_btn.clicked.connect(self.capture_frame)
        self.calibrate_btn.clicked.connect(self.run_calibration)
        self.save_btn.clicked.connect(self.save_calibration)
        self.reset_btn.clicked.connect(self.reset_calibration)
        
        # Initially disable calibration buttons
        self.capture_btn.setEnabled(False)
        self.calibrate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        calib_layout.addWidget(self.capture_btn)
        calib_layout.addWidget(self.calibrate_btn)
        calib_layout.addWidget(self.save_btn)
        calib_layout.addWidget(self.reset_btn)
        calib_group.setLayout(calib_layout)
        
        # Status Group
        status_group = QGroupBox("Status & Progress")
        status_layout = QVBoxLayout()
        
        self.count_label = QLabel("Captured: 0")
        self.status_label = QLabel("Status: Waiting for stream...")
        self.info_label = QLabel(f"Chessboard: {CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]} | Square: {SQUARE_SIZE}m")
        self.progress_label = QLabel("")
        
        status_layout.addWidget(self.count_label)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.info_label)
        status_layout.addWidget(self.progress_label)
        status_group.setLayout(status_layout)
        
        # Add groups to controls
        controls_layout.addWidget(res_group)
        controls_layout.addWidget(calib_group)
        controls_layout.addWidget(status_group)
        controls_layout.addStretch()  # Push everything to top
        
        # Right side - Video display
        video_layout = QVBoxLayout()
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(800, 450)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        video_layout.addWidget(self.image_label)
        
        # Add to main layout
        main_layout.addLayout(controls_layout, 1)  # 1/3 width
        main_layout.addLayout(video_layout, 2)     # 2/3 width
        self.setLayout(main_layout)

        # Initialize variables
        self.current_resolution = None
        self.last_frame = None
        self.last_found = False
        self.last_corners = None
        self.objpoints = []
        self.imgpoints = []
        self.frames = []

        bridge.new_frame.connect(self.handle_frame)

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.process_frame_queue)
        self.frame_timer.start(30)
        
        # Update progress on startup
        self.update_progress_display()

    def set_resolution(self):
        """Send resolution change command to server"""
        idx = self.resolution_combo.currentIndex()
        if idx >= 0:
            label, (width, height) = RESOLUTION_LIST[idx]
            
            try:
                # Send the same format as your main client
                config = {
                    "jpeg_quality": 70,
                    "fps": 1,
                    "resolution": (width, height),
                    "cropped": False  # Add this to match your main client
                }
                sio.emit("camera_config", config)
                self.status_label.setText(f"Setting resolution to {label}...")
                
                # Disable controls temporarily while camera adjusts
                self.set_resolution_btn.setEnabled(False)
                QTimer.singleShot(3000, lambda: self.set_resolution_btn.setEnabled(True))
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to set resolution: {e}")
                print(f"[ERROR] Resolution change failed: {e}")

    def reset_calibration(self):
        """Reset calibration data for new calibration"""
        self.objpoints = []
        self.imgpoints = []
        self.frames = []
        self.count_label.setText("Captured: 0")
        self.calibrate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Ready for new calibration")
        if hasattr(self, 'calibration'):
            delattr(self, 'calibration')

    def handle_frame(self, frame):
        # Detect resolution from frame
        h, w = frame.shape[:2]
        self.current_resolution = (w, h)
        self.current_res_label.setText(f"Current: {w}x{h}")

        self.last_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, flags)

        if found:
            self.last_found = True
            self.last_corners = corners
            self.capture_btn.setEnabled(True)
            cv2.drawChessboardCorners(frame, CHESSBOARD_SIZE, corners, found)
            self.status_label.setText("✓ Chessboard detected - Ready to capture")
        else:
            self.last_found = False
            self.last_corners = None
            self.capture_btn.setEnabled(False)
            self.status_label.setText("❌ No chessboard found")

        # Display frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        label_w = self.image_label.width()
        label_h = self.image_label.height()

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

            count = len(self.frames)
            self.count_label.setText(f"Captured: {count}")
            self.status_label.setText(f"✓ Frame {count} captured")
            
            if count >= 5:
                self.calibrate_btn.setEnabled(True)
                self.status_label.setText(f"✓ {count} frames captured - Ready to calibrate")

    def run_calibration(self):
        if len(self.objpoints) < 5:
            QMessageBox.warning(self, "Not Enough Frames", "Capture at least 5 chessboard frames.")
            return

        self.status_label.setText("🔄 Running calibration...")
        
        img_shape = self.frames[0].shape[1::-1]
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self.objpoints, self.imgpoints, img_shape, None, None
        )

        if ret:
            self.calibration = {"mtx": mtx, "dist": dist}
            self.status_label.setText("✓ Calibration successful! Ready to save.")
            self.save_btn.setEnabled(True)
        else:
            self.status_label.setText("❌ Calibration failed - try capturing more frames")

    def save_calibration(self):
        if hasattr(self, "calibration") and self.current_resolution:
            os.makedirs("calibrations", exist_ok=True)
            
            filename = RESOLUTION_FILES.get(self.current_resolution, 
                                          f"calibrations/calibration_{self.current_resolution[0]}x{self.current_resolution[1]}.npz")
            
            np.savez(filename, mtx=self.calibration["mtx"], dist=self.calibration["dist"])
            self.status_label.setText(f"✅ Saved: {filename}")
            
            # Update progress display
            self.update_progress_display()
            
            # Show success message with option to continue
            remaining = self.get_remaining_resolutions()
            if remaining:
                msg = f"Calibration saved!\n\nRemaining resolutions: {len(remaining)}\n"
                msg += "\n".join([f"• {r[0]}x{r[1]}" for r in remaining[:5]])
                if len(remaining) > 5:
                    msg += f"\n... and {len(remaining)-5} more"
                
                reply = QMessageBox.question(self, "Continue?", 
                                           msg + "\n\nContinue with next resolution?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.reset_calibration()
            else:
                QMessageBox.information(self, "Complete!", "🎉 All calibrations complete!")
        else:
            QMessageBox.warning(self, "No Data", "No calibration data to save.")

    def get_remaining_resolutions(self):
        """Get list of resolutions that still need calibration"""
        remaining = []
        for res, filename in RESOLUTION_FILES.items():
            if not os.path.exists(filename):
                remaining.append(res)
        return remaining

    def update_progress_display(self):
        """Update the progress display showing completed calibrations"""
        total = len(RESOLUTION_FILES)
        completed = total - len(self.get_remaining_resolutions())
        
        progress_text = f"Progress: {completed}/{total} calibrations complete\n"
        
        # Show status for each resolution
        status_lines = []
        for res, filename in RESOLUTION_FILES.items():
            status = "✓" if os.path.exists(filename) else "❌"
            status_lines.append(f"{status} {res[0]}x{res[1]}")
        
        self.progress_label.setText(progress_text + "\n".join(status_lines))

    def closeEvent(self, event):
        try:
            if sio.connected:
                sio.emit("stop_camera")  # Stop camera before disconnecting
                sio.disconnect()
        except:
            pass
        event.accept()

    def process_frame_queue(self):
        try:
            frame = frame_queue.get_nowait()
            self.handle_frame(frame)
        except queue.Empty:
            pass

# === SocketIO Events ===

@sio.on("frame")
def on_frame(data):
    try:
        arr = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass
    except Exception as e:
        print(f"[ERROR] Frame decode failed: {e}")

# Add this SocketIO event to automatically start the camera when connected
@sio.on("connect")
def on_connect():
    print("[DEBUG] Connected to server - starting camera stream")
    sio.emit("start_camera")

# Add disconnect cleanup to stop camera
@sio.on("disconnect")
def on_disconnect():
    print("[DEBUG] Disconnected from server")

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
