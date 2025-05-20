from gevent import monkey; monkey.patch_all()
import time, base64, socketio, cv2, threading, queue
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
frame_queue = queue.Queue(maxsize=5)

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
        res = camera_config["resolution"]
        jpeg_quality = camera_config["jpeg_quality"]
        fps = camera_config["fps"]
        duration = int(1e6 / max(fps, 1))

        if picam.started:
            picam.stop()

        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": res},
            controls={"FrameDurationLimits": (duration, duration)}
        )
        picam.configure(config)
        picam.start()
        print(f"[INFO] Camera reconfigured: {res}, JPEG: {jpeg_quality}, FPS: {fps}")
    except Exception as e:
        print("[ERROR] Reconfigure failed:", e)

def capture_loop():
    while True:
        if streaming:
            try:
                frame = picam.capture_array()
                if not frame_queue.full():
                    frame_queue.put(frame)
            except Exception as e:
                print("[ERROR] Capture failed:", e)
        time.sleep(0.001)

def encode_and_send_loop():
    frame_count = 0
    last_time = time.time()

    while True:
        try:
            frame = frame_queue.get(timeout=1)
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
                print(f"[FPS] {frame_count} fps", end='\r')
                frame_count = 0
                last_time = now

        except queue.Empty:
            continue
        except Exception as e:
            print("[ERROR] Encode/send failed:", e)

def start_stream():
    global picam
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print("[ERROR] Connection failed:", e)
        return

    try:
        picam = Picamera2()

        print("[INFO] Available sensor modes:")
        for i, mode in enumerate(picam.sensor_modes):
            size = mode.get("size", "N/A")
            bit_depth = mode.get("bit_depth", "N/A")
            fmt = mode.get("format", "N/A")
            fps = mode.get("fps", "N/A")
            print(f"  Mode {i}: {size}, {bit_depth}-bit, format={fmt}, max_fps={fps}")

        reconfigure_camera()
        print("[INFO] Camera initialized.")
    except Exception as e:
        print("[ERROR] Camera setup failed:", e)
        return

    # Start processing threads
    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=encode_and_send_loop, daemon=True).start()

    while True:
        time.sleep(1)
