# camera.py (refactored)

from gevent import monkey; monkey.patch_all()
import time
import socketio
import cv2
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()


def print_status_line(status, resolution=None, jpeg_quality=None, fps=None, fps_value=None):
    msg = f"[CAMERA STATUS] {status}"
    if resolution is not None:
        msg += f" | Res: {resolution}"
    if jpeg_quality is not None:
        msg += f" | JPEG: {jpeg_quality}"
    if fps is not None:
        msg += f" | FPS: {fps}"
    if fps_value is not None:
        msg += f" | Streaming: {fps_value} fps"
    print(msg.ljust(100), end='\r', flush=True)

class CameraStreamer:
    def __init__(self):
        self.streaming = False
        self.connected = False
        self.config = {
            "jpeg_quality": 70,
            "fps": 10,
            "resolution": [640, 480]
        }
        self.picam = Picamera2()

    def connect_socket(self):
        try:
            sio.connect(SERVER_URL)
            self.connected = True
        except Exception as e:
            print("[ERROR] Socket connection failed:", e)

    def apply_config(self):
        try:
            res = self.config["resolution"]
            jpeg_quality = self.config["jpeg_quality"]
            fps = self.config["fps"]
            duration = int(1e6 / max(fps, 1))

            if self.picam.started:
                self.picam.stop()

            stream_cfg = self.picam.create_preview_configuration(
                main={"format": "XRGB8888", "size": res},
                controls={"FrameDurationLimits": (duration, duration)}
            )
            self.picam.configure(stream_cfg)
            self.picam.start()
            print(f"[INFO] Camera configured: {res}, JPEG: {jpeg_quality}, FPS: {fps}")
        except Exception as e:
            print("[ERROR] Failed to configure camera:", e)

    def stream_loop(self):
        frame_count = 0
        last_time = time.time()

        while True:
            try:
                if self.streaming:
                    start_time = time.time()

                    frame = self.picam.capture_array()
                    ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.config["jpeg_quality"]])
                    if not ok:
                        continue

                    sio.emit("frame", buf.tobytes())
                    frame_count += 1
                    now = time.time()
                    if now - last_time >= 1.0:
                        # Use current config for display
                        cfg = self.config
                        print_status_line(
                            "Streaming",
                            cfg.get("resolution"),
                            cfg.get("jpeg_quality"),
                            cfg.get("fps"),
                            fps_value=frame_count
                        )
                        frame_count = 0
                        last_time = now
                else:
                    print_status_line(
                        "Idle",
                        self.config.get("resolution"),
                        self.config.get("jpeg_quality"),
                        self.config.get("fps"),
                        fps_value=0
                    )
                    time.sleep(0.5)
            except Exception as e:
                print("[ERROR] Stream loop exception:", e)
                time.sleep(1)

streamer = CameraStreamer()


@sio.event
def connect():
    streamer.connected = True
    print_status_line("Connected to server")

@sio.event
def disconnect():
    streamer.connected = False
    streamer.streaming = False
    if hasattr(streamer, "picam") and getattr(streamer.picam, "started", False):
        streamer.picam.stop()
    print_status_line("Disconnected from server")


@sio.on("start_camera")
def on_start_camera(_):
    streamer.streaming = True
    if not streamer.picam.started:
        streamer.picam.start()
    print_status_line("Streaming started", streamer.config.get("resolution"), streamer.config.get("jpeg_quality"), streamer.config.get("fps"))


@sio.on("stop_camera")
def on_stop_camera(_):
    streamer.streaming = False
    if streamer.picam.started:
        streamer.picam.stop()
    print_status_line("Streaming stopped", streamer.config.get("resolution"), streamer.config.get("jpeg_quality"), streamer.config.get("fps"))


@sio.on("camera_config")
def on_camera_config(data):
    streamer.config.update(data)
    if not streamer.streaming:
        streamer.apply_config()
        print_status_line("Configured", streamer.config.get("resolution"), streamer.config.get("jpeg_quality"), streamer.config.get("fps"))
    else:
        print_status_line("Can't apply config while streaming", streamer.config.get("resolution"), streamer.config.get("jpeg_quality"), streamer.config.get("fps"))


def start_stream():
    streamer.connect_socket()
    streamer.apply_config()
    print("[INFO] Camera ready.")
    streamer.stream_loop()

if __name__ == "__main__":
    sio.connect("http://localhost:5000")  # Change to your server address
    streamer.stream_loop()
