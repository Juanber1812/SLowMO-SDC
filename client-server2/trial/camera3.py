# camera.py
from picamera2 import Picamera2
import threading
import time
import cv2

class MJPEGCamera:
    def __init__(self):
        self.picam = Picamera2()
        self.streaming = False
        self.jpeg_quality = 80
        self.frame_lock = threading.Lock()
        self.latest_frame = b''
        self.config = {
            "resolution": (640, 480),
            "fps": 30,
            "jpeg_quality": 80
        }

    def configure(self):
        """Apply camera configuration settings."""
        try:
            self.jpeg_quality = self.config["jpeg_quality"]
            frame_interval = int(1e6 / max(self.config["fps"], 1))

            cam_config = self.picam.create_preview_configuration(
                main={"format": "XRGB8888", "size": self.config["resolution"]},
                controls={"FrameDurationLimits": (frame_interval, frame_interval)}
            )
            self.picam.configure(cam_config)
            print(f"[CAMERA] Configured with {self.config}")
        except Exception as e:
            print("[CAMERA ERROR] Configuration failed:", e)

    def start(self):
        if not self.streaming:
            self.configure()
            self.picam.start()
            self.streaming = True
            threading.Thread(target=self._capture_loop, daemon=True).start()
            print("[CAMERA] Started streaming.")

    def stop(self):
        if self.streaming:
            self.streaming = False
            self.picam.stop()
            print("[CAMERA] Stopped streaming.")

    def update_config(self, new_config):
        """Update resolution, fps, jpeg quality. Applies immediately if streaming."""
        self.config.update(new_config)
        print(f"[CAMERA] Updating config: {self.config}")
        if self.streaming:
            self.configure()

    def _capture_loop(self):
        while self.streaming:
            try:
                frame = self.picam.capture_array()
                success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                if success:
                    with self.frame_lock:
                        self.latest_frame = buffer.tobytes()
            except Exception as e:
                print("[CAMERA ERROR] Frame capture failed:", e)
            time.sleep(0.001)  # adjust for performance

    def get_jpeg_frame(self):
        """Get the latest encoded JPEG frame."""
        with self.frame_lock:
            return self.latest_frame
