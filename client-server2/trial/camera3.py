from flask import Flask, Response
from picamera2 import Picamera2
import threading, time, cv2

app = Flask(__name__)

picam = Picamera2()
settings = {
    "resolution": (640, 480),
    "fps": 10,
    "jpeg_quality": 70,
    "camera_running": False
}

frame_buffer = b''
lock = threading.Lock()

def apply_settings():
    try:
        width, height = settings["resolution"]
        fps = settings["fps"]
        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": (width, height)},
            controls={"FrameDurationLimits": (
                int(1e6 / max(fps, 1)),
                int(1e6 / max(fps, 1))
            )}
        )
        picam.stop()
        picam.configure(config)
        picam.start()
        print(f"[CAMERA] Started {width}x{height} @ {fps}fps")
    except Exception as e:
        print("[ERROR] Could not start camera:", e)

def camera_loop():
    global frame_buffer
    while True:
        if settings["camera_running"]:
            try:
                frame = picam.capture_array()
                ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), settings["jpeg_quality"]])
                if ret:
                    with lock:
                        frame_buffer = buf.tobytes()
            except Exception as e:
                print("[ERROR] Frame capture failed:", e)
                time.sleep(0.01)
        else:
            time.sleep(0.1)

@app.route('/video')
def video_feed():
    def gen():
        while True:
            with lock:
                frame = frame_buffer
            if frame:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(1.0 / max(settings["fps"], 1))
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask_video_server():
    threading.Thread(target=app.run, kwargs={
        "host": "0.0.0.0", "port": 8000, "debug": False, "use_reloader": False
    }, daemon=True).start()
    threading.Thread(target=camera_loop, daemon=True).start()

def update_camera_settings(data):
    settings["resolution"] = tuple(data.get("resolution", settings["resolution"]))
    settings["fps"] = int(data.get("fps", settings["fps"]))
    settings["jpeg_quality"] = int(data.get("jpeg_quality", settings["jpeg_quality"]))
    if settings["camera_running"]:
        apply_settings()

def start_camera():
    if not settings["camera_running"]:
        settings["camera_running"] = True
        apply_settings()

def stop_camera():
    if settings["camera_running"]:
        picam.stop()
        settings["camera_running"] = False
        print("[CAMERA] Stopped")
