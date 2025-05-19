import sys
import json
import base64
import socketio
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QTimer, Qt

import detector  # <-- this is our detection module

sio = socketio.Client()
latest_frame = None

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AprilTag Viewer")

        self.detection_enabled = False
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.toggle_button = QPushButton("Enable Detection")
        self.toggle_button.clicked.connect(self.toggle_detection)

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.toggle_button)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_image)
        self.timer.start(30)

    def toggle_detection(self):
        self.detection_enabled = not self.detection_enabled
        self.toggle_button.setText(
            "Disable Detection" if self.detection_enabled else "Enable Detection"
        )

    def update_image(self):
        global latest_frame
        if latest_frame is None:
            return

        frame = detection.process_frame(latest_frame.copy(), self.detection_enabled)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(q_img))

@sio.event
def connect():
    print("Connected to server.")

@sio.event
def disconnect():
    print("Disconnected from server.")

@sio.on('response_data')
def on_response(data):
    global latest_frame
    try:
        payload = json.loads(data)
        image_b64 = payload.get('image')
        if image_b64:
            nparr = np.frombuffer(base64.b64decode(image_b64), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            latest_frame = frame
    except Exception as e:
        print(f"Error decoding image: {e}")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1000, 1000)
    win.show()

    try:
        sio.connect("http://192.168.65.89:5000")
    except Exception as e:
        print(f"Could not connect to server: {e}")

    def request_data():
        if sio.connected:
            sio.emit("request_data")

    timer = QTimer()
    timer.timeout.connect(request_data)
    timer.start(100)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
