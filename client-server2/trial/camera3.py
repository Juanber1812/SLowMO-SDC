from picamera2 import Picamera2
import time, socketio, cv2, base64, threading

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

camera_config = {
    "resolution": (640, 480),
    "fps": 10,
    "jpeg_quality": 70
}

picam = Picamera2()
streaming = False

def reconfigure_camera():
    try:
        res = camera_config["resolution"]
        fps = camera_config["fps"]
        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": res},
            controls={"FrameDurationLimits": (
                int(1e6 / max(fps, 1)),
                int(1e6 / max(fps, 1))
            )}
        )
        picam.stop()
        picam.configure(config)
        picam.start()
        print(f"[CAMERA] Reconfigured: {res} at {fps} FPS")
    except Exception as e:
        print("[CAMERA ERROR]", e)

@sio.event
def connect():
    print("📡 Camera connected to server")
    reconfigure_camera()

@sio.event
def disconnect():
    print("🔌 Camera disconnected")

@sio.on("camera_config")
def on_camera_config(data):
    camera_config.update(data)
    reconfigure_camera()

@sio.on("start_camera")
def on_start_camera():
    global streaming
    print("[CAMERA] Start streaming")
    streaming = True

@sio.on("stop_camera")
def on_stop_camera():
    global streaming
    print("[CAMERA] Stop streaming")
    streaming = False

def stream_loop():
    while True:
        if streaming:
            frame = picam.capture_array()
            success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]])
            if not success:
                continue
            jpg_b64 = base64.b64encode(buffer).decode('utf-8')
            sio.emit("frame_data", jpg_b64)
            time.sleep(1.0 / max(camera_config["fps"], 1))
        else:
            time.sleep(0.1)

if __name__ == "__main__":
    sio.connect(SERVER_URL)
    threading.Thread(target=stream_loop, daemon=True).start()
    sio.wait()
