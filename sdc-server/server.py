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
from gevent import monkey

monkey.patch_all()

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque):
            return {"__deque__": True, "data": list(obj)}  # Convert deque to a list
        elif isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "data": obj.tolist()}  # Convert ndarray to list
        return super().default(obj)

Payload.max_decode_packets = 500

app = Flask(__name__)
socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*", transports=["websocket", "polling"])

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
    # Send video frame and sensor data
    aprcapobj.capture_frame()

    if aprcapobj.latest_frame_data:
        payload = {
            "image": aprcapobj.latest_frame_data,
            "pose": aprcapobj.pose_data_list[0],
            "tag": aprcapobj.tag_detected,
            "fps": aprcapobj.get_fps(),
            "sensors": imu.read_sensor_data()
        }

        socketio.emit('response_data', json.dumps(payload, cls=CustomEncoder))

@socketio.on('flip')
def flip():
    aprcapobj.flip_state = not aprcapobj.flip_state

@socketio.on('invert')
def invert():
    aprcapobj.invert_state = not aprcapobj.invert_state

# Graceful shutdown to release camera properly when the server stops
def cleanup():
    print("Shutting down server...")
    aprcapobj.cap.release()
    print("Camera released.")

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    finally:
        cleanup()  # Ensure cleanup runs on exit