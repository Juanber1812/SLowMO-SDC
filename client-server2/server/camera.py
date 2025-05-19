# camera.py

from gevent import monkey; monkey.patch_all()  # MUST be first

import time, base64, cv2, socketio, numpy as np
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
FRAME_WIDTH, FRAME_HEIGHT = 640, 480
JPEG_QUALITY = 70
STREAM_INTERVAL = 0.1  # 10 FPS

sio = socketio.Client()

@sio.event
def connect():
    print("📡 Connected to server from camera.py")

@sio.event
def disconnect():
    print("🔌 Disconnected from server")

@sio.event
def connect_error(data):
    print("❌ Failed to connect to server:", data)

def start_stream():
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
        print("📷 Camera started successfully.")
    except Exception as e:
        print("❌ Failed to start camera:", e)
        return

    while True:
        try:
            frame = picam.capture_array()
            print(f"🖼️ Captured frame: {frame.shape}")

            success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if not success:
                print("⚠️ JPEG encoding failed.")
                continue

            jpg_b64 = base64.b64encode(buffer).decode('utf-8')
            sio.emit('frame_data', jpg_b64)
            print(f"📤 Frame sent, JPEG size: {len(jpg_b64)} bytes")

            time.sleep(STREAM_INTERVAL)

        except Exception as e:
            print("❌ Error in capture/send loop:", e)
            time.sleep(1)

# Prevent it from running unless called
if __name__ == "__main__":
    start_stream()
