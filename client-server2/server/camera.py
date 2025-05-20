# camera.py (manual resolution and FPS configuration)

from gevent import monkey; monkey.patch_all()
import time, base64, cv2, threading
from picamera2 import Picamera2
import socketio

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

picam = Picamera2()
streaming = False

# Default config
camera_config = {
    "resolution": (640, 480),
    "fps": 30,
    "jpeg_quality": 70
}

def find_sensor_mode(requested_res, requested_fps):
    # Find the closest supported mode
    best_mode = None
    min_diff = float('inf')
    for mode in picam.sensor_modes:
        size = mode.get('size')
        fps = mode.get('fps')
        diff = abs(size[0] - requested_res[0]) + abs(size[1] - requested_res[1]) + abs(fps - requested_fps)
        if diff < min_diff:
            min_diff = diff
            best_mode = mode
    return best_mode

def reconfigure_camera():
    global camera_config
    mode = find_sensor_mode(camera_config["resolution"], camera_config["fps"])
    if mode is None:
        print("[ERROR] No matching sensor mode found, using default.")
        mode = picam.sensor_modes[0]
    size = mode['size']
    fps = mode['fps']
    print(f"[INFO] Using sensor mode: {size} @ {fps}fps")
    config = picam.create_preview_configuration(
        main={"format": "YUV420", "size": size},
        controls={"FrameDurationLimits": (
            int(1e6 / max(camera_config["fps"], 1)),
            int(1e6 / max(camera_config["fps"], 1))
        )}
    )
    try:
        picam.stop()
    except Exception:
        pass
    picam.configure(config)
    picam.start()
    print(f"[INFO] Camera reconfigured to resolution: {size}, JPEG: {camera_config['jpeg_quality']}, FPS: {camera_config['fps']}")

@sio.event
def connect():
    print("[INFO] Connected to server.")

@sio.event
def disconnect():
    print("[INFO] Disconnected from server.")

@sio.on("start_camera")
def on_start_camera():
    global streaming
    print("[INFO] Stream started.")
    streaming = True

@sio.on("stop_camera")
def on_stop_camera():
    global streaming
    print("[INFO] Stream stopped.")
    streaming = False

@sio.on("camera_config")
def on_camera_config(data):
    global camera_config
    print("[INFO] Config received:", data)
    camera_config.update(data)
    reconfigure_camera()

@sio.on("get_sensor_modes")
def on_get_sensor_modes():
    modes = []
    for mode in picam.sensor_modes:
        size = mode.get('size')
        fps = mode.get('fps')
        label = f"{size[0]}x{size[1]} @ {fps:.0f}fps"
        modes.append({"label": label, "size": size, "fps": fps})
    sio.emit("sensor_modes", modes)

def stream_loop():
    global streaming
    while True:
        if streaming:
            try:
                frame = picam.capture_array("main")
                frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
                success, buffer = cv2.imencode(
                    '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]]
                )
                if not success:
                    continue
                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                sio.emit("frame", jpg_b64)
                time.sleep(1.0 / max(camera_config["fps"], 1))
            except Exception as e:
                print("[ERROR] Frame capture failed:", e)
                time.sleep(0.05)
        else:
            time.sleep(0.1)

if __name__ == "__main__":
    sio.connect(SERVER_URL)
    reconfigure_camera()
    threading.Thread(target=stream_loop, daemon=True).start()
    sio.wait()
