import cv2
import base64
import numpy as np
import pyapriltags
import time
from collections import deque
from gevent import monkey

# Try to import Picamera2; fall back to OpenCV if unavailable
try:
    from picamera2 import Picamera2
    USE_PICAMERA2 = True
except ImportError:
    USE_PICAMERA2 = False

monkey.patch_all()

class AprilTagCaptureObject():
    def __init__(self):
        self.latest_frame_data = None

        self.last_time = time.time()
        self.frame_count = 0
        self.pose_data = deque(maxlen=100)
        self.prev_pose_data = None
        self.tag_detected = False
        self.pose_data_list = [self.pose_data, self.prev_pose_data, self.tag_detected]

        # Load camera calibration
        self.calibration_data = np.load('calibration_data.npz')
        self.mtx = self.calibration_data['mtx']
        self.dist = self.calibration_data['dist']

        self.flip_state = False
        self.invert_state = False

        # Initialize capture based on environment
        if USE_PICAMERA2:
            self.camera = Picamera2()
            config = self.camera.create_preview_configuration(
                main={"format": "XRGB8888", "size": (1000, 1000)}
            )
            self.camera.configure(config)
            self.camera.start()
        else:
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1000)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1000)
            if not self.cap.isOpened():
                print("Error: Could not open video capture on camera index 0. Please check your camera connection.")
                exit()

        # Prepare AprilTag detector
        self.detector = pyapriltags.Detector(
            families='tag25h9', nthreads=4,
            quad_decimate=1.0, quad_sigma=0.0,
            refine_edges=1, decode_sharpening=0.25
        )
        self.tag_size = 0.055  # meters
        self.object_points = np.array([
            [-self.tag_size/2, -self.tag_size/2, 0],
            [ self.tag_size/2, -self.tag_size/2, 0],
            [ self.tag_size/2,  self.tag_size/2, 0],
            [-self.tag_size/2,  self.tag_size/2, 0]
        ], dtype=np.float32)
        self.line_color = (0, 255, 0)

    def process_pose_data(self, rvec, tvec, timestamp):
        # Convert rotation vector to rotation matrix
        self.rotation_matrix, _ = cv2.Rodrigues(rvec)

    def capture_frame(self):
        # Grab frame from Pi Camera or webcam
        if USE_PICAMERA2:
            frame = self.camera.capture_array()
            ret = True
        else:
            ret, frame = self.cap.read()

        if not ret:
            return

        # Undistort and convert to grayscale
        undist = cv2.undistort(frame, self.mtx, self.dist)
        gray = cv2.cvtColor(undist, cv2.COLOR_BGR2GRAY)

        # Detect AprilTags
        tags = self.detector.detect(gray)
        self.tag_detected = bool(tags)

        for tag in tags:
            corners = tag.corners.astype(int)
            for i in range(4):
                cv2.line(undist,
                         tuple(corners[i]),
                         tuple(corners[(i+1)%4]),
                         self.line_color, 2)

            # Estimate pose
            success, rvec, tvec = cv2.solvePnP(
                self.object_points,
                tag.corners.astype(np.float32),
                self.mtx, self.dist
            )
            if not success:
                continue

            ts = time.time()
            # Store and process pose
            self.pose_data.append((rvec, tvec, ts))
            self.process_pose_data(rvec, tvec, ts)
            if self.prev_pose_data is not None:
                self.pose_data_list = [(rvec, tvec, ts), self.prev_pose_data]
            self.prev_pose_data = (rvec, tvec, ts)

            # Draw coordinate axes
            axes = np.float32([[0,0,0],[0.1,0,0],[0,0.1,0],[0,0,0.1]])
            imgpts, _ = cv2.projectPoints(axes, rvec, tvec, self.mtx, self.dist)
            o, x, y, z = [tuple(pt.ravel().astype(int)) for pt in imgpts]
            cv2.arrowedLine(undist, o, x, (0,0,255), 2); cv2.putText(undist, 'X', x, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.arrowedLine(undist, o, y, (0,255,0), 2); cv2.putText(undist, 'Y', y, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
            cv2.arrowedLine(undist, o, z, (255,0,0), 2); cv2.putText(undist, 'Z', z, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)

        # Apply user flip/invert
        if self.flip_state:
            undist = cv2.flip(undist, 1)
        if self.invert_state:
            undist = cv2.bitwise_not(undist)

        # Encode and store frame
        _, buf = cv2.imencode('.jpg', undist, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        self.latest_frame_data = base64.b64encode(buf).decode('utf-8')

    def get_fps(self):
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_time
        if elapsed >= 1.0:
            fps = self.frame_count / elapsed
            self.last_time, self.frame_count = now, 0
            return fps
