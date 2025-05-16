# Install dependencies:
#   pip install opencv-python pyapriltags websockets PyQt6 PyQt6-WebSockets matplotlib

# --- server.py ---
"""
WebSocket server for AprilTag distance detection.
Runs on your laptop, using the local camera (index 0).
Streams JSON messages to connected clients with fields:
  {"type": "distance", "ts": timestamp, "distance": value_in_meters}
Supports control messages from client:
  {"type": "control", "action": "start"|"stop"}
  {"type": "config", "tag_size": float_in_meters}
"""
import asyncio
import json
import time
import cv2
import numpy as np
import pyapriltags
import multiprocessing
import websockets

# Load calibration data (add your calibration_data.npz in working folder)
try:
    calibration = np.load('calibration_data.npz')
    mtx = calibration['mtx']
    dist_coeffs = calibration['dist']
except Exception:
    print("Warning: calibration_data.npz not found, using default intrinsics.")
    # Fallback: assume 800px focal, center at (640,360), no distortion
    mtx = np.array([[800, 0, 640], [0, 800, 360], [0, 0, 1]], dtype=float)
    dist_coeffs = np.zeros(5)

# AprilTag detector setup
num_threads = multiprocessing.cpu_count()
detector = pyapriltags.Detector(
    families='tag25h9',
    nthreads=num_threads,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
    decode_sharpening=0.25
)

# Default parameters
tag_size = 0.055  # meters
detection_enabled = False

# Capture device (global)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

async def handler(websocket, path):
    """
    Handles incoming control/config messages and pushes distance data to clients.
    """
    global tag_size, detection_enabled

    async def consumer():
        """Receive control/config messages from client."""
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get('type') == 'control':
                    action = data.get('action', '').lower()
                    if action == 'start':
                        detection_enabled = True
                        print('Detection enabled')
                    elif action == 'stop':
                        detection_enabled = False
                        print('Detection disabled')
                elif data.get('type') == 'config':
                    new_size = float(data.get('tag_size', tag_size))
                    tag_size = new_size
                    print(f'Tag size set to {tag_size:.3f} m')
            except json.JSONDecodeError:
                continue

    async def producer():
        """Capture frames, detect AprilTag, compute distance, send to client."""
        while True:
            if detection_enabled:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                tags = detector.detect(gray)
                if tags:
                    tag = tags[0]
                    img_pts = np.array(tag.corners, dtype=np.float32)
                    obj_pts = np.array([
                        [-tag_size/2, -tag_size/2, 0],
                        [ tag_size/2, -tag_size/2, 0],
                        [ tag_size/2,  tag_size/2, 0],
                        [-tag_size/2,  tag_size/2, 0]
                    ], dtype=np.float32)
                    success, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, mtx, dist_coeffs)
                    if success:
                        distance = float(np.linalg.norm(tvec))
                        payload = {
                            'type': 'distance',
                            'ts': time.time(),
                            'distance': distance
                        }
                        await websocket.send(json.dumps(payload))
            await asyncio.sleep(0.05)

    # Run consumer and producer concurrently
    await asyncio.gather(consumer(), producer())

async def main():
    print('Starting WebSocket server on ws://localhost:8765')
    async with websockets.serve(handler, '0.0.0.0', 8765):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main())

