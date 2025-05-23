import sys
import cv2
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

RTSP_URL = "rtsp://192.168.65.89:8554/mystream"  # <-- Replace <PI_IP> with your Pi’s IP

class VideoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RTSP Stream Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.label = QLabel("Connecting to stream...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.cap = cv2.VideoCapture(RTSP_URL)
        if not self.cap.isOpened():
            self.label.setText("Failed to connect to RTSP stream.")
            return

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~33ms = 30 FPS

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self.label.setPixmap(pixmap)
        else:
            self.label.setText("Lost connection to stream.")

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = VideoWindow()
    viewer.show()
    sys.exit(app.exec())
