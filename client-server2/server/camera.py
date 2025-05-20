
from gevent import monkey; monkey.patch_all()
import time, base64, socketio
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

camera_config = {
    "jpeg_quality": 70,
    "fps": 10,
    "resolution": (640, 480)
}

streaming = False
picam = None

@sio.event
def connect():
    print("[INFO] Connected to server.")

@sio.event
def disconnect():
    print("[INFO] Disconnected from server.")

@sio.on("start_camera")
def on_start_camera(data):
    global streaming
    streaming = True
    print("[INFO] Stream started.")

@sio.on("stop_camera")
def on_stop_camera(data):
    global streaming
    streaming = False
    print("[INFO] Stream stopped.")

@sio.on("camera_config")
def on_camera_config(data):
    global camera_config
    print(f"[INFO] Config received: {data}")
    camera_config.update(data)
    if not streaming:
        reconfigure_camera()
    else:
        print("[WARN] Config ignored while streaming.")


def reconfigure_camera():
    global picam
    try:
        res = tuple(camera_config["resolution"])
        fps = camera_config["fps"]
        duration = int(1e6 / max(fps, 1))

        if picam.started:
            picam.stop()

        # Use hardware MJPEG pipeline for video
        config = picam.create_video_configuration(
            encode={"format": "MJPEG", "size": res},
            controls={"FrameDurationLimits": (duration, duration)},
            buffer_count=6,
            queue=False
        )
        picam.configure(config)

        print("[DEBUG] Camera configuration:", picam.camera_configuration())
        print("[DEBUG] Camera controls:", picam.camera_controls())

        picam.start()
        print(f"[INFO] Camera reconfigured: {res}, FPS: {fps}")
    except Exception as e:
        print("[ERROR] Reconfigure failed:", e)


def start_stream():
    global streaming, picam
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print("[ERROR] Connection failed:", e)
        return

    try:
        picam = Picamera2()
        print("[INFO] Available sensor modes:")
        for i, mode in enumerate(picam.sensor_modes):
            print(f"  Mode {i}: {mode['size']}, max_fps={mode['fps']}")

        reconfigure_camera()
        print("[INFO] Camera initialized.")
    except Exception as e:
        print("[ERROR] Camera setup failed:", e)
        return

    while True:
        try:
            if streaming:
                # Capture an MJPEG buffer (hardware encoded)
                t0 = time.perf_counter()
                jpeg = picam.capture_buffer("encode")
                dt = time.perf_counter() - t0
                print(f"[DEBUG] Capture-only FPS: {1/dt:.1f}", end='\r')

                jpg_b64 = base64.b64encode(jpeg).decode('utf-8')
                sio.emit("frame_data", jpg_b64)
        except Exception as e:
            print("[ERROR] Streaming failure:", e)
            time.sleep(1)

if __name__ == "__main__":
    start_stream()
