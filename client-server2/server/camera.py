# camera_stream.py
import time, base64
import cv2
import socketio
from picamera2 import Picamera2
from gevent import monkey; monkey.patch_all()

# Point this at your server’s IP
SERVER_URL = "http://0.0.0.0:5000"

sio = socketio.Client()
sio.connect(SERVER_URL)

def main():
    camera = Picamera2()
    cfg = camera.create_preview_configuration(
        main={"format": "XRGB8888", "size": (640, 480)}
    )
    camera.configure(cfg)
    camera.start()

    while True:
        frame = camera.capture_array()
        # JPEG compress
        _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        b64 = base64.b64encode(buf).decode('utf-8')
        sio.emit('frame_data', b64)
        time.sleep(0.1)  # 10 Hz

if __name__ == "__main__":
    main()
