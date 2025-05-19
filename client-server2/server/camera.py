# camera.py

from gevent import monkey; monkey.patch_all()

import time, base64, cv2, socketio, numpy as np
from picamera2 import Picamera2

camera_config = {
    "jpeg_quality": 70,
    "fps": 10,
    "resolution": (640, 480)
}
sio = socketio.Client()
streaming = False  # Controlled by client

@sio.on("camera_config")
def on_camera_config(data):
    global camera_config
    camera_config.update(data)
    print(f"🔧 Camera config updated: {camera_config}")

SERVER_URL = "http://localhost:5000"
FRAME_WIDTH, FRAME_HEIGHT = camera_config["resolution"]
JPEG_QUALITY = camera_config["jpeg_quality"]
STREAM_INTERVAL = 1.0 / max(camera_config["fps"], 1)




@sio.event
def connect():
    print("📡 Connected to server from camera.py")

@sio.event
def disconnect():
    print("🔌 Disconnected from server")

@sio.event
def connect_error(data):
    print("❌ Failed to connect to server:", data)

@sio.on("start_camera")
def on_start_camera(data):
    global streaming
    streaming = True
    print("🎥 Camera stream STARTED")

@sio.on("stop_camera")
def on_stop_camera(data):
    global streaming
    streaming = False
    print("🛑 Camera stream STOPPED")

def start_stream():
    global streaming
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print("❌ Socket.IO connection failed:", e)
        return

    try:
        picam = Picamera2()
        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": (FRAME_WIDTH, FRAME_HEIGHT)}
        )
        picam.configure(config)
        picam.start()
        print("✅ Camera is ready.")
    except Exception as e:
        print("❌ Failed to start camera:", e)
        return

    while True:
        try:
            if streaming:
                frame = picam.capture_array()
                success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if not success:
                    continue
                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                sio.emit('frame_data', jpg_b64)
            time.sleep(STREAM_INTERVAL)
        except Exception as e:
            print("❌ Error in capture/send loop:", e)
            time.sleep(1)
