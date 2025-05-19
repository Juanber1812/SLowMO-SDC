# cam_test_server.py

from flask import Flask, Response, request
import time, cv2
from picamera2 import Picamera2

app = Flask(__name__)
picam = Picamera2()

# Manual config
JPEG_QUALITY = 70
FPS = 10
RESOLUTION = (640, 480)

def camera_stream():
    config = picam.create_preview_configuration(main={"format": "XRGB8888", "size": RESOLUTION})
    picam.configure(config)
    picam.start()

    frame_delay = 1.0 / FPS
    frame_count = 0
    last_time = time.time()

    while True:
        frame = picam.capture_array()
        success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if not success:
            continue
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        frame_count += 1
        now = time.time()
        if now - last_time >= 1.0:
            print(f"[FPS] Actual FPS: {frame_count}")
            frame_count = 0
            last_time = now

        time.sleep(frame_delay)


@app.route('/')
def video_feed():
    return Response(camera_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print(f"[INFO] Starting MJPEG test stream: {RESOLUTION} @ {FPS} fps, JPEG {JPEG_QUALITY}")
    app.run(host='0.0.0.0', port=5001, threaded=True)
