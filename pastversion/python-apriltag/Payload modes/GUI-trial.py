# --- client.py ---
"""
PyQt6 client for distance detection UI.
Connects to the server at ws://localhost:8765, receives JSON messages,
allows Start/Stop and Tag Size config, shows live distance & graph.
"""
import sys
import json
import time
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox
)
from PyQt6.QtWebSockets import QWebSocket
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import cv2
from PyQt6.QtGui import QImage, QPixmap

class DistanceGraph(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.ax.set_title('Distance (m)')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Distance')
        self.times, self.values = [], []
        self.start_time = None

    def update_plot(self, ts, value):
        if self.start_time is None:
            self.start_time = ts
        self.times.append(ts - self.start_time)
        self.values.append(value)
        # Keep last 100 points
        self.times = self.times[-100:]
        self.values = self.values[-100:]
        self.ax.clear()
        self.ax.set_title('Distance (m)')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Distance')
        self.ax.plot(self.times, self.values, linewidth=1)
        self.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Distance Detection Client')
        self.ws = QWebSocket()
        self.ws.textMessageReceived.connect(self.on_message)
        self.ws.errorOccurred.connect(lambda err: print('WS error:', err))
        self.connected = False

        # Controls
        self.connect_btn = QPushButton('Connect')
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.start_btn = QPushButton('Start')
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.toggle_detection)
        self.tag_size_spin = QDoubleSpinBox()
        self.tag_size_spin.setRange(0.01, 0.2)
        self.tag_size_spin.setSingleStep(0.005)
        self.tag_size_spin.setValue(0.055)
        self.tag_size_spin.valueChanged.connect(self.send_config)

        # Display
        self.distance_label = QLabel('Distance: ---')
        self.distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.graph = DistanceGraph(self)

        # Video feed
        self.video_label = QLabel()
        self.video_label.setFixedSize(320, 240)

        # Layout
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(self.connect_btn)
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(QLabel('Tag Size (m):'))
        ctrl_layout.addWidget(self.tag_size_spin)

        main_layout = QVBoxLayout()
        main_layout.addLayout(ctrl_layout)
        main_layout.addWidget(self.distance_label)
        main_layout.addWidget(self.graph)
        main_layout.addWidget(self.video_label)  # Add after self.graph

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~30 FPS

    def toggle_connection(self):
        if not self.connected:
            self.ws.open(QUrl('ws://localhost:8765'))
            self.ws.connected.connect(self.on_connected)
            self.ws.disconnected.connect(self.on_disconnected)
        else:
            self.ws.close()

    def on_connected(self):
        self.connected = True
        self.connect_btn.setText('Disconnect')
        self.start_btn.setEnabled(True)
        print('Connected to server')

    def on_disconnected(self):
        self.connected = False
        self.connect_btn.setText('Connect')
        self.start_btn.setEnabled(False)
        print('Disconnected from server')

    def toggle_detection(self):
        msg_type = 'start' if self.start_btn.text() == 'Start' else 'stop'
        self.ws.sendTextMessage(json.dumps({'type':'control','action':msg_type}))
        self.start_btn.setText('Stop' if msg_type=='start' else 'Start')

    def send_config(self, value):
        if self.connected:
            self.ws.sendTextMessage(json.dumps({'type':'config','tag_size': value}))

    def on_message(self, message):
        try:
            data = json.loads(message)
            if data.get('type') == 'distance':
                dist = data['distance']
                ts = data['ts']
                self.distance_label.setText(f'Distance: {dist:.3f} m')
                self.graph.update_plot(ts, dist)
        except Exception:
            pass

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_img))

    def closeEvent(self, event):
        self.cap.release()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())