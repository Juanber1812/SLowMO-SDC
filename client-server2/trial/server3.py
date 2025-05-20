# mjpeg_server.py
from flask import Flask, Response, request
from picamera2 import Picamera2
import threading
import time
import cv2

app = Flask(__name__)

# Initialize camera
picam = Picamera2()
streaming = False
jpeg_quality = 80
frame_lock = threading.Lock()
latest_frame = b''

# Default camera config
camera_config = {
    "resolution": (640, 480),
    "fps": 30,
    "jpeg_quality": 80
}

def configure_camera():
    global jpeg_quality
    config = picam.create_preview_configuration(
        main={"format": "XRGB8888", "size": camera_config["resolution"]},
        controls={"FrameDurationLimits": (
            int(1e6 / max(camera_config["fps"], 1)),
            int(1e6 / max(camera_config["fps"], 1))
        )}
    )
    picam.configure(config)
    jpeg_quality = camera_config["jpeg_quality"]

def camera_loop():
    global latest_frame
    while streaming:
        try:
            frame = picam.capture_array()
            success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
            if success:
                with frame_lock:
                    latest_frame = buffer.tobytes()
        except Exception as e:
            print("[ERROR] MJPEG frame capture failed:", e)
        time.sleep(0.001)

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                frame = latest_frame
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.01)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start', methods=['POST'])
def start_stream():
    global streaming
    if not streaming:
        configure_camera()
        picam.start()
        streaming = True
        threading.Thread(target=camera_loop, daemon=True).start()
        print("[INFO] Camera started.")
    return "Stream started", 200

@app.route('/stop', methods=['POST'])
def stop_stream():
    global streaming
    if streaming:
        streaming = False
        picam.stop()
        print("[INFO] Camera stopped.")
    return "Stream stopped", 200

@app.route('/config', methods=['POST'])
def update_config():
    try:
        data = request.json
        if "resolution" in data:
            camera_config["resolution"] = tuple(data["resolution"])
        if "fps" in data:
            camera_config["fps"] = int(data["fps"])
        if "jpeg_quality" in data:
            camera_config["jpeg_quality"] = int(data["jpeg_quality"])
        print("[CONFIG] Updated settings:", camera_config)
        if streaming:
            configure_camera()
        return "Config updated", 200
    except Exception as e:
        print("[ERROR] Config update failed:", e)
        return "Error", 400

@app.route('/')
def index():
    return '''<html>
        <head><title>MJPEG Stream</title></head>
        <body>
            <h2>MJPEG Stream</h2>
            <img src="/video_feed" width="640">
            <form action="/start" method="post"><button>Start Camera</button></form>
            <form action="/stop" method="post"><button>Stop Camera</button></form>
        </body>
    </html>'''

if __name__ == '__main__':
    print("[INFO] MJPEG camera server running at http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, threaded=True)
