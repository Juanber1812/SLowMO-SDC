# stereo cam ref: https://learnopencv.com/depth-perception-using-stereo-camera-python-c/
# marker det ref: https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html

# graph for distance measurements from lidar

import capture, imu

import json
from flask import Flask
from flask_socketio import SocketIO
from engineio.payload import Payload

from collections import deque
import numpy as np

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque):
            return {"__deque__": True, "data": list(obj)}  # Convert deque to a list
        elif isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "data": obj.tolist()}  # Convert ndarray to list
        return super().default(obj)

Payload.max_decode_packets = 500

app = Flask(__name__)
socketio = SocketIO(app, async_mode="gevent", ping_timeout=1000, ping_interval=0, cors_allowed_origins="*", transports=["websocket", "polling"])

aprcapobj = capture.AprilTagCaptureObject()

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
    aprcapobj.capture_frame()
    frame_data = aprcapobj.latest_frame_data
    if frame_data:
        pose_data = aprcapobj.pose_data_list[0]
        tag_detected_data = aprcapobj.tag_detected
        fps_data = aprcapobj.get_fps()
        sensor_data = imu.read_sensor_data()
        socketio.emit('response_data', json.dumps({
            "image": frame_data,
            "pose": pose_data,
            "tag": tag_detected_data,
            "fps": fps_data,
            "sensors": sensor_data
        }, cls=CustomEncoder))

@socketio.on('flip')
def flip():
    aprcapobj.flip_state = not aprcapobj.flip_state

@socketio.on('invert')
def invert():
    aprcapobj.invert_state = not aprcapobj.invert_state

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

    # Release the camera when the server stops
    aprcapobj.cap.release()