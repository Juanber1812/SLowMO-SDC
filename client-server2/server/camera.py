# camera.py (manual resolution and FPS configuration)

from gevent import monkey; monkey.patch_all()
import time, base64, socketio, cv2
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
        jpeg_quality = camera_config["jpeg_quality"]
        fps = camera_config["fps"]
        duration = int(1e6 / max(fps, 1))

        if picam.started:
            picam.stop()

        # Enforce manually selected resolution and FPS
        config = picam.create_video_configuration(
            main={"format": "YUV420", "size": res},
            controls={"FrameDurationLimits": (duration, duration)}
        )

        picam.configure(config)
        picam.start()
        print(f"[INFO] Camera reconfigured to resolution: {res}, JPEG: {jpeg_quality}, FPS: {fps}")
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
        reconfigure_camera()
        print("[INFO] Camera initialized.")
    except Exception as e:
        print("[ERROR] Camera setup failed:", e)
        return

    frame_count = 0
    last_time = time.time()

    while True:
        try:
            if streaming:
                frame = picam.capture_array("main")
                frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
                success, buffer = cv2.imencode(
                    '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]]
                )
                if not success:
                    continue

                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                sio.emit("frame_data", jpg_b64)
                frame_count += 1

                now = time.time()
                if now - last_time >= 1.0:
                    elapsed = now - last_time
                    actual_capture_fps = frame_count / elapsed
                    print(f"[FPS] Processed: {frame_count} fps | Capture-only: {actual_capture_fps:.1f} fps", end='\r')
                    frame_count = 0
                    last_time = now

            time.sleep(1.0 / max(camera_config["fps"], 1))

        except Exception as e:
            print("[ERROR] Streaming failure:", e)
            time.sleep(1)
