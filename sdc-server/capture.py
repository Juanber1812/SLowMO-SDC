import cv2
import base64
import numpy as np
import time
from gevent import monkey
from picamera2 import Picamera2

monkey.patch_all()

class AprilTagCaptureObject():
    def __init__(self):
        self.latest_frame_data = None
        self.last_time = time.time()
        self.frame_count = 0

        # Load camera calibration
        self.calibration_data = np.load('calibration_data.npz')
        self.mtx = self.calibration_data['mtx']
        self.dist = self.calibration_data['dist']

        self.flip_state = False
        self.invert_state = False

        # Initialize Pi Camera via Picamera2
        self.camera = Picamera2()
        config = self.camera.create_preview_configuration(
            main={"format": "XRGB8888", "size": (1000, 1000)}
        )
        self.camera.configure(config)
        self.camera.start()

    def capture_frame(self):
        # Grab frame from Pi Camera
        frame = self.camera.capture_array()

        # Undistort and convert to grayscale
        undist = cv2.undistort(frame, self.mtx, self.dist)

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
