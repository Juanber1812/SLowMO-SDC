# camera.py (dual stream version)

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
def on_start_camera(_):
    global streaming
    streaming = True
    print("[INFO] Streaming started.")

@sio.on("stop_camera")
def on_stop_camera(_):
    global streaming
    streaming = False
    print("[INFO] Streaming stopped.")

@sio.on("camera_config")
def on_camera_config(data):
    global camera_config
    print(f"[INFO] Config received: {data}")
    camera_config.update(data)
    if not streaming:
        reconfigure_camera()
    else:
        print("[WARN] Can't reconfigure while streaming.")

def reconfigure_camera():
    global picam
    try:
        res = camera_config["resolution"]
        jpeg_quality = camera_config["jpeg_quality"]
        fps = camera_config["fps"]
        duration = int(1e6 / max(fps, 1))

        if picam.started:
            picam.stop()

        config = picam.create_video_configuration(
            main={"format": "XRGB8888", "size": res},
            lores={"format": "YUV420", "size": (640, 480)},
            encode="lores",
            controls={"FrameDurationLimits": (duration, duration)}
        )
        picam.configure(config)
        picam.start()
        print(f"[INFO] Camera configured: MAIN={res}, LORES=(640, 480), JPEG: {jpeg_quality}, FPS: {fps}")
    except Exception as e:
        print("[ERROR] Failed to configure camera:", e)

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
                frame = picam.capture_array("lores")
                success, buffer = cv2.imencode(
                    '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]]
                )
                if not success:
                    continue

                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                sio.emit("frame", jpg_b64)
                frame_count += 1

                now = time.time()
                if now - last_time >= 1.0:
                    elapsed = now - last_time
                    actual_fps = frame_count / elapsed
                    print(f"[FPS] Sent: {frame_count} fps", end='\r')
                    frame_count = 0
                    last_time = now

            sio.sleep(1.0 / max(camera_config["fps"], 1))

        except Exception as e:
            print("[ERROR] Streaming error:", e)
            sio.sleep(1)

# Optional: capture full-res still from main stream
def capture_high_res_image(filename="capture.jpg"):
    try:
        frame = picam.capture_array("main")
        cv2.imwrite(filename, frame)
        print(f"[INFO] Saved full-res image to {filename}")
    except Exception as e:
        print("[ERROR] Full-res capture failed:", e)
