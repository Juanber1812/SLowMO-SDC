import cv2
import base64
import time
from gevent import monkey
from picamera2 import Picamera2

monkey.patch_all()

class AprilTagCaptureObject():
    def __init__(self):
        self.latest_frame_data = None
        self.last_time = time.time()
        self.frame_count = 0

        self.flip_state = False
        self.invert_state = False

        self.camera = Picamera2()
        config = self.camera.create_preview_configuration(
            main={"format": "XRGB8888", "size": (1000, 1000)}
        )
        self.camera.configure(config)
        self.camera.start()

    def capture_frame(self):
        frame = self.camera.capture_array()

        if self.flip_state:
            frame = cv2.flip(frame, 1)
        if self.invert_state:
            frame = cv2.bitwise_not(frame)

        _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        self.latest_frame_data = base64.b64encode(buf).decode('utf-8')

    def get_fps(self):
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_time
        if elapsed >= 1.0:
            fps = self.frame_count / elapsed
            self.last_time, self.frame_count = now, 0
            return fps
