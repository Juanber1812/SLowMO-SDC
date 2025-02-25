import graph_windows

import sys
import atexit
import socketio
import base64
import json
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton
from multiprocessing import Process, Queue
import cv2
import numpy as np
from collections import deque

# Create a socketio client instance
sio = socketio.Client()
queue = Queue()
graph_process = None

frame = None
fps = None
sensor = None

class CameraWindow(QMainWindow):
    def __init__(self, updateFreq):
        super().__init__()
        self.setWindowTitle("Camera Feed")
        self.setGeometry(100, 100, 750, 530)

        self.image_label = QLabel(self)
        self.image_label.setGeometry(10, 10, 620, 460)

        self.fps_label = QLabel("FPS: -1", self)
        self.fps_label.setGeometry(15, 0, 140, 40)
        self.fps_label.setStyleSheet("color: white;")

        self.sensor_text = QLabel('Temperature: -1\nHumidity: -1', self)
        self.sensor_text.setGeometry(640, 20, 140, 40)
        
        self.flip_button = QPushButton('Flip', self) # Create a "Flip" button
        self.flip_button.setGeometry(150, 480, 140, 40)
        self.flip_button.clicked.connect(self.flip_video)  # Connect to the flip function on click

        self.invert_button = QPushButton('Invert', self) # Create an "Invert" button
        self.invert_button.setGeometry(350, 480, 140, 40)
        self.invert_button.clicked.connect(self.invert_video)  # Connect to the invert function on click

        # THINK ABOUT SWITCHING TO THIS LAYOUT
        #self.layout = QVBoxLayout()
        #self.layout.addWidget(self.image_label)
        #self.layout.addWidget(self.fps_label)
        #self.setLayout(self.layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.request_data)  # Request data
        self.timer.start(updateFreq)  # Update every time_interval ms

    def request_data(self):
        """Request a new frame from the server"""
        sio.emit('request_data')  # Send request to the server for a new frame

    def update_data(self):
        self.update_frame()  # Update frame
        self.update_fps_data()   # Update fps data
        self.update_sensor_data()   # Update sensor data

    def update_frame(self):
        global frame
        if frame is not None:
            # Convert the frame to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create QImage from the frame
            height, width, channels = rgb_frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(rgb_frame.data, width, height, width * channels, QImage.Format.Format_RGB888)

            # Display the image in the QLabel
            self.image_label.setPixmap(QPixmap.fromImage(q_img))

    def update_fps_data(self):
        if fps is not None:
            self.fps_label.setText(f"FPS: {fps:.2f}")

    def update_sensor_data(self):
        if sensor is not None:
            self.sensor_text.setText('Temperature: {temperature}\nHumidity: {humidity}'.format(**sensor))

    def flip_video(self): # Send signal to server to toggle the flip state.
        print(f"Client: Image is flipped")
        sio.emit('flip')

    def invert_video(self): # Send signal to server to toggle the invert state.
        print(f"Client: Image is inverted")
        sio.emit('invert')

    def closeEvent(self, event):
        event.accept()



# Socket.IO events
@sio.event
def connect():
    print("Connected to server.")

@sio.event
def disconnect():
    print("Disconnected from server.")

@sio.event
def response_data(data): # Receive frames from the server
    global frame, fps, sensor

    # Parse the incoming JSON data
    json_data = json.loads(data, object_hook=custom_decoder)  # Decode the JSON string

    # Retrieve 'image' (frame_data) and 'sensors' from the parsed JSON
    frame_data = json_data.get('image')
    pose_data = json_data.get('pose')
    tag_detected_data = json_data.get('tag')
    fps_data = json_data.get('fps')
    sensor_data = json_data.get('sensors')

    update_graphs(pose_data, tag_detected_data)
    fps = fps_data
    sensor = sensor_data

    try:
        nparr = np.frombuffer(base64.b64decode(frame_data), np.uint8)  # Decode the base64 data to NumPy array
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # Decode the frame

        window.update_data()  # Update window data
    except Exception as e:
        print(f"Error decoding frame: {e}")
        frame = None  # If an error occurs, set frame to None


def custom_decoder(obj):
    if "__deque__" in obj:
        return deque(obj["data"])  # Convert list back to deque
    elif "__ndarray__" in obj:
        return np.array(obj["data"])  # Convert list back to ndarray
    return obj

def update_graphs(pose_data, tag_detected):
    if tag_detected:
        queue.put(pose_data)
    else:
        queue.put(None)



# Cleanup function to ensure a proper shutdown
def cleanup():
    global graph_process
    print("Cleaning up before exit...")

    if sio.connected:
        sio.disconnect()
        print("SocketIO disconnected.")

    if graph_process.is_alive():
        graph_process.terminate()
        graph_process.join()
        print("Graph process terminated.")

    QApplication.quit()
    sys.exit(0) 

# Register cleanup on exit
atexit.register(cleanup)

if __name__ == "__main__":
    # Set time interval bewteen frames and graph update rate
    time_interval = 50 #milliseconds
    graphing_rate = 0.01 #seconds

    # Queue graph windows
    queue = Queue()
    graph_process = Process(target=graph_windows.graph_updater, args=(queue,graphing_rate,))
    graph_process.start()

    # Setup PyQt6 and run
    app = QApplication(sys.argv)
    window = CameraWindow(time_interval)

    # Connect to the server
    try:
        sio.connect('http://127.0.0.1:5000', wait_timeout=5)
        print("Connected to server.")
    except Exception as e:
        print(f"Connection error: {e}")

    # Connect the cleanup function to the aboutToQuit signal
    app.aboutToQuit.connect(cleanup)

    # Show the main window and run the event loop
    window.show()
    sys.exit(app.exec())
