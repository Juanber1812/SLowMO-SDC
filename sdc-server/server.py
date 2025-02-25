# stereo cam ref: https://learnopencv.com/depth-perception-using-stereo-camera-python-c/
# marker det ref: https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html

# graph for distance measurements from lidar

import capture, imu
import json
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def home():
    return "Server is running"

@socketio.on('connect')  
def handle_connect():
    print("Client connected successfully!")

@socketio.on('disconnect')  
def handle_connect():
    print("Client disconnected.")

@socketio.on('request_data')
def send_data():
    """ Send video frame and sensor data """
    frame_data = capture.capture_frame()
    if frame_data:
        sensor_data = imu.read_sensor_data()
        socketio.emit('response_data', json.dumps({
            "image": frame_data,
            "sensors": sensor_data
        }))

@socketio.on('flip')
def flip():
    capture.flip_state = not capture.flip_state

@socketio.on('invert')
def invert():
    capture.invert_state = not capture.invert_state

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

    # Release the camera when the server stops
    capture.cap.release()