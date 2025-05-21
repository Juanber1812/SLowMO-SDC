# camera.py (refactored)

from gevent import monkey; monkey.patch_all()
import time, base64, socketio, cv2
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()


class CameraStreamer:
    def __init__(self):
        self.config = {
            "jpeg_quality": 70,
            "fps": 10,
            "resolution": (640, 480)
        }
        self.streaming = False
        self.picam = Picamera2()
        self.connected = False

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

                    # Update FPS display every second
                    now = time.time()
                    if now - last_time >= 1.0:
                        print(f"[FPS] {frame_count} fps", end='\r')
                        frame_count = 0
                        last_time = now

                else:
                    sio.sleep(0.1)  # prevent busy waiting when not streaming

            except Exception as e:
                print("[ERROR] Stream loop exception:", e)
                sio.sleep(1)



streamer = CameraStreamer()


@sio.event
def connect():
    print("[INFO] Connected to server.")
    streamer.connected = True


@sio.event
def disconnect():
    print("[INFO] Disconnected from server.")
    streamer.connected = False
    streamer.streaming = False
    if hasattr(streamer, "picam") and getattr(streamer.picam, "started", False):
        streamer.picam.stop()
        print("[INFO] Camera stopped due to disconnect.")


@sio.on("start_camera")@sio.on("start_camera")
def on_start_camera(_):
    streamer.streaming = True= True
    if not streamer.picam.started:rted:
        streamer.picam.start()
    print("[INFO] Streaming started.")arted.")


@sio.on("stop_camera")@sio.on("stop_camera")
def on_stop_camera(_):
    streamer.streaming = False = False
    if streamer.picam.started:
        streamer.picam.stop()
    print("[INFO] Streaming stopped.")topped.")


@sio.on("camera_config")@sio.on("camera_config")
def on_camera_config(data):a):
    print(f"[INFO] New camera config: {data}")ra config: {data}")
    streamer.config.update(data)
    if not streamer.streaming:
        streamer.apply_config())
    else:
        print("[WARN] Can't apply config while streaming.")rint("[WARN] Can't apply config while streaming.")


def start_stream():def start_stream():
    streamer.connect_socket()t_socket()
    streamer.apply_config()
    print("[INFO] Camera ready.")ady."
    streamer.stream_loop()
