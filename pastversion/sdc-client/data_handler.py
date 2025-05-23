import time
import socketio
import base64
import json
import cv2
import numpy as np
from collections import deque
from multiprocessing import Queue
import pyapriltags

# Load calibration (used for undistortion and pose estimation)
calib = np.load('calibration_data.npz')
mtx = calib['mtx']
dist = calib['dist']

# AprilTag setup
tag_size = 0.055  # meters
object_points = np.array([
    [-tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2,  tag_size / 2, 0],
    [-tag_size / 2,  tag_size / 2, 0]
], dtype=np.float32)

detector = pyapriltags.Detector(
    families='tag25h9', nthreads=2,
    quad_decimate=1.0, quad_sigma=0.0,
    refine_edges=1, decode_sharpening=0.25
)

# Socket.IO setup
sio = socketio.Client()
queue = Queue()
window = None

frame = None
fps = None
sensor = None

@sio.event
def connect():
    print("Connected to server.")

@sio.event
def disconnect():
    print("Disconnected from server.")

@sio.event
def response_data(data):
    global frame, fps, sensor

    json_data = json.loads(data)
    frame_data = json_data.get('image')
    fps_data = json_data.get('fps')
    sensor_data = json_data.get('sensors')

    fps = fps_data
    sensor = sensor_data

    try:
        nparr = np.frombuffer(base64.b64decode(frame_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Optional: undistort frame before detection
        #frame = cv2.undistort(frame, mtx, dist)

        pose = detect_apriltag(frame)
        queue.put(pose if pose is not None else None)

        window.update_data()
    except Exception as e:
        print(f"Error decoding or processing frame: {e}")
        frame = None

def detect_apriltag(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray)

    if not tags:
        return None

    tag = tags[0]
    success, rvec, tvec = cv2.solvePnP(
        object_points,
        tag.corners.astype(np.float32),
        mtx, dist
    )
    if not success:
        return None

    timestamp = time.time()
    return (rvec, tvec, timestamp)
