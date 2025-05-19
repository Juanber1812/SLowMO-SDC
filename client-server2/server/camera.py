# camera.py

from gevent import monkey; monkey.patch_all()

import time
import base64
import cv2
import socketio
import numpy as np
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

# Default config
camera_config = {
    "jpeg_quality": 70,
    "fps": 10,
    "resolution": (640, 480)
}

streaming = False
picam = None

@sio.event
def connect():
    print("📡 Camera connected to server")

@sio.event
def disconnect():
    print("🔌 Camera disconnected")

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

@sio.on("camera_config")
def on_camera_config(data):
    global camera_config
    print("⚙️ Received camera config:", data)
    camera_config.update(data)
    reconfigure_camera()

def reconfigure_camera():
    global picam
    try:
        res = camera_config.get("resolution", (640, 480))
        width, height = int(res[0]), int(res[1])
        if width < 100 or width > 2592:
            width = 640
        if height < 100 or height > 1944:
            height = 480

        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": (width, height)}
        )

        if picam.is_running():
            picam.stop()

        picam.configure(config)
        picam.start()
        print(f"✅ Camera reconfigured: {width}x{height}")

    except Exception as e:
        print("❌ Reconfigure failed:", e)

    global picam
    res = camera_config["resolution"]
    try:
        if picam:
            picam.stop()
        picam = Picamera2()
        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": res}
        )
        picam.configure(config)
        picam.start()
        print(f"✅ Camera reconfigured: {res[0]}x{res[1]}")
    except Exception as e:
        print("❌ Reconfigure failed:", e)

def start_stream():
    global streaming, picam

    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print("❌ Could not connect to server:", e)
        return

    try:
        picam = Picamera2()
        reconfigure_camera()  # initial configuration
        print("✅ Camera ready, waiting for stream command...")
    except Exception as e:
        print("❌ Initial camera setup failed:", e)
        return

    while True:
        try:
            if streaming:
                frame = picam.capture_array()
                success, buffer = cv2.imencode(
                    '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]]
                )
                if not success:
                    continue
                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                sio.emit("frame_data", jpg_b64)
            time.sleep(1.0 / max(camera_config["fps"], 1))
        except Exception as e:
            print("❌ Stream error:", e)
            time.sleep(1)


    reconfigure_camera()
    print("✅ Camera ready and waiting...")

    while True:
        try:
            if streaming:
                frame = picam.capture_array()
                success, buffer = cv2.imencode(
                    '.jpg',
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), camera_config["jpeg_quality"]]
                )
                if not success:
                    continue
                jpg_b64 = base64.b64encode(buffer).decode('utf-8')
                
                if len(jpg_b64) > 300000:
                    print("⚠️ Skipping oversized frame.")
                    continue

                sio.emit("frame_data", jpg_b64)
            time.sleep(1.0 / max(camera_config["fps"], 1))
        except Exception as e:
            print("❌ Stream error:", e)
            time.sleep(1)
