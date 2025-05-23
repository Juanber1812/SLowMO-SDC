import cv2
import numpy as np
import pyapriltags
import os

# Load calibration data
calib_file = 'calibration_data.npz'
if not os.path.exists(calib_file):
    raise FileNotFoundError(f"Calibration file '{calib_file}' not found.")

try:
    calibration = np.load(calib_file)
    mtx = calibration['mtx']
    dist = calibration['dist']
except Exception as e:
    raise RuntimeError(f"Failed to load calibration data: {e}")

# AprilTag detector setup
tag_size = 0.0545  # meters
detector = pyapriltags.Detector(
    families='tag25h9',
    nthreads=4,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
    decode_sharpening=0.25
)

line_color = (0, 255, 0)
line_thickness = 8  # <--- Define thickness variable here

def draw_cube_manual(img, rvec, tvec, size, offset, mtx, dist):
    cube_points = np.array([
        [-size / 2, -size / 2, 0],
        [ size / 2, -size / 2, 0],
        [ size / 2,  size / 2, 0],
        [-size / 2,  size / 2, 0],
        [-size / 2, -size / 2, size],
        [ size / 2, -size / 2, size],
        [ size / 2,  size / 2, size],
        [-size / 2,  size / 2, size],
    ], dtype=np.float32)

    cube_points += offset  # Apply Z offset
    img_points, _ = cv2.projectPoints(cube_points, rvec, tvec, mtx, dist)
    pts = img_points.reshape(-1, 2).astype(int)

    # Manually draw all cube edges
    cv2.line(img, tuple(pts[0]), tuple(pts[1]), line_color, line_thickness)
    cv2.line(img, tuple(pts[1]), tuple(pts[2]), line_color, line_thickness)
    cv2.line(img, tuple(pts[2]), tuple(pts[3]), line_color, line_thickness)
    cv2.line(img, tuple(pts[3]), tuple(pts[0]), line_color, line_thickness)

    cv2.line(img, tuple(pts[4]), tuple(pts[5]), line_color, line_thickness)
    cv2.line(img, tuple(pts[5]), tuple(pts[6]), line_color, line_thickness)
    cv2.line(img, tuple(pts[6]), tuple(pts[7]), line_color, line_thickness)
    cv2.line(img, tuple(pts[7]), tuple(pts[4]), line_color, line_thickness)

    cv2.line(img, tuple(pts[0]), tuple(pts[4]), line_color, line_thickness)
    cv2.line(img, tuple(pts[1]), tuple(pts[5]), line_color, line_thickness)
    cv2.line(img, tuple(pts[2]), tuple(pts[6]), line_color, line_thickness)
    cv2.line(img, tuple(pts[3]), tuple(pts[7]), line_color, line_thickness)

def detect_and_draw(frame: np.ndarray, return_pose=False):
    frame = cv2.undistort(frame, mtx, dist)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray, estimate_tag_pose=True,
                           camera_params=(mtx[0, 0], mtx[1, 1], mtx[0, 2], mtx[1, 2]),
                           tag_size=tag_size)

    for tag in tags:
        corners = tag.corners.astype(int)
        for i in range(4):
            pt1 = tuple(corners[i])
            pt2 = tuple(corners[(i + 1) % 4])
            cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

        rvec, _ = cv2.Rodrigues(tag.pose_R)
        tvec = tag.pose_t.reshape(3, 1)
        cube_size = 0.10  # meters

        draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, 0, 0], dtype=np.float32), mtx=mtx, dist=dist)  # Center cube
        draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, -cube_size, 0], dtype=np.float32), mtx=mtx, dist=dist)  # Top cube
        draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, cube_size, 0], dtype=np.float32), mtx=mtx, dist=dist)  # Bottom cube

    if return_pose and tags:
        rvec, _ = cv2.Rodrigues(tags[0].pose_R)
        tvec = tags[0].pose_t.reshape(3, 1)
        return frame, (rvec, tvec)

    return frame, None if return_pose else frame

