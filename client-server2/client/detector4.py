import cv2
import numpy as np
import pyapriltags
import os

# Load calibration data with error handling
calib_file = 'calibration_data.npz'
if not os.path.exists(calib_file):
    raise FileNotFoundError(f"Calibration file '{calib_file}' not found.")

try:
    calibration = np.load(calib_file)
    mtx = calibration['mtx']
    dist = calibration['dist']
except Exception as e:
    raise RuntimeError(f"Failed to load calibration data: {e}")

# Set tag size and create detector
tag_size = 0.055  # meters
detector = pyapriltags.Detector(
    families='tag25h9',
    nthreads=4,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
    decode_sharpening=0.25
)

# Define object points (for completeness, though unused in simple drawing)
object_points = np.array([
    [-tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2, -tag_size / 2, 0],
    [ tag_size / 2,  tag_size / 2, 0],
    [-tag_size / 2,  tag_size / 2, 0]
], dtype=np.float32)

def detect_and_draw(frame: np.ndarray) -> np.ndarray:
    """Detect AprilTags and draw green boxes around them."""
    frame = cv2.undistort(frame, mtx, dist)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray)

    for tag in tags:
        corners = tag.corners.astype(int)
        for i in range(4):
            pt1 = tuple(corners[i])
            pt2 = tuple(corners[(i + 1) % 4])
            cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

    return frame
