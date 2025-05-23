import cv2
import numpy as np
import pyapriltags
import time
import data_handler
from collections import deque

# Load calibration
calibration = np.load('calibration_data.npz')
mtx = calibration['mtx']
dist = calibration['dist']

tag_size = 0.055  # meters
object_points = np.array([
    [-tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2,  tag_size / 2, 0],
    [-tag_size / 2,  tag_size / 2, 0]
], dtype=np.float32)

detector = pyapriltags.Detector(
    families='tag25h9', nthreads=4,
    quad_decimate=1.0, quad_sigma=0.0,
    refine_edges=1, decode_sharpening=0.25
)

prev_pose_data = None


def detect_apriltag():
    global prev_pose_data

    frame = data_handler.frame
    if frame is None:
        return

    undist = cv2.undistort(frame, mtx, dist)
    gray = cv2.cvtColor(undist, cv2.COLOR_BGR2GRAY)

    tags = detector.detect(gray)
    if not tags:
        data_handler.queue.put(None)
        return

    for tag in tags:
        # Estimate pose
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            tag.corners.astype(np.float32),
            mtx, dist
        )
        if not success:
            continue

        timestamp = time.time()
        pose_data = (rvec, tvec, timestamp)

        # Update the queue for graphing
        data_handler.queue.put(pose_data)
        prev_pose_data = pose_data
        break  # Only use the first detected tag


# Optional: Run this periodically if used standalone
if __name__ == '__main__':
    while True:
        detect_apriltag()
        time.sleep(0.03)  # match 30 FPS
