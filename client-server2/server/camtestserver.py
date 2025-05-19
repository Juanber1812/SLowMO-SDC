# -*- coding: utf-8 -*-
from flask import Flask, Response, request, render_template_string, jsonify
import time, cv2, psutil, threading
from picamera2 import Picamera2

app = Flask(__name__)
picam = Picamera2()

# Configuration
RESOLUTION = (640, 480)
SETTINGS = {
    "fps": 10,
    "jpeg_quality": 70,
    "resolution": RESOLUTION,
    "restart_camera": False
}

# State
frame_lock = threading.Lock()
latest_frame = b''
frame_count = 0
fps_display = 0

def get_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000.0
    except:
        return None

@app.route('/')
def index():
    return render_template_string('''
        <html>
        <head>
            <title>Pi Camera Test</title>
            <style>
                body { font-family: sans-serif; background: #111; color: #eee; }
                input, button { font-size: 1em; margin: 5px; }
                #panel { background: #222; padding: 10px; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>Live Camera Stream</h2>
            <img src="/video_feed" width="640">
            <div id="panel">
                <h3>Controls</h3>
                <form method="POST" action="/settings">
                    FPS: <input type="number" name="fps" min="1" max="120" value="{{ fps }}">
                    JPEG Quality: <input type="number" name="jpeg" min="10" max="100" value="{{ jpeg }}">
                    <button type="submit">Apply</button>
                </form>
                <h3>System Status</h3>
                <p id="status">Loading...</p>
            </div>
            <script>
                function updateStatus() {
                    fetch('/status').then(r => r.json()).then(data => {
                        document.getElementById('status').innerText =
                            `FPS: ${data.fps} | CPU: ${data.cpu}% | Temp: ${data.temp} °C`;
                    });
                }
                setInterval(updateStatus, 1000);
                updateStatus();
            </script>
        </body>
        </html>
    ''', fps=SETTINGS["fps"], jpeg=SETTINGS["jpeg_quality"])

@app.route('/video_feed')
def video_feed():
    return Response(stream_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/settings', methods=['POST'])
def update_settings():
    try:
        SETTINGS["fps"] = int(request.form.get("fps", SETTINGS["fps"]))
        SETTINGS["jpeg_quality"] = int(request.form.get("jpeg", SETTINGS["jpeg_quality"]))
        SETTINGS["restart_camera"] = True
        return "Settings updated. <a href='/'>Go back</a>"
    except:
        return "Invalid input", 400

@app.route('/status')
def status():
    temp = get_temp()
    cpu = psutil.cpu_percent()
    return jsonify({
        "fps": fps_display,
        "cpu": cpu,
        "temp": temp
    })

def stream_frames():
    global latest_frame, frame_count, fps_display

    config = picam.create_preview_configuration(main={"format": "XRGB8888", "size": SETTINGS["resolution"]})
    picam.configure(config)
    picam.start()
    print("[INFO] Camera started")

    last_time = time.time()

    while True:
        if SETTINGS["restart_camera"]:
            try:
                picam.stop()
                config = picam.create_preview_configuration(
                    main={"format": "XRGB8888", "size": SETTINGS["resolution"]},
                    controls={
                        "FrameDurationLimits": (
                            int(1e6 / max(SETTINGS["fps"], 1)),
                            int(1e6 / max(SETTINGS["fps"], 1))
                        )
                    }
                )
                picam.configure(config)
                picam.start()
                print(f"[INFO] Camera restarted: FPS={SETTINGS['fps']}, JPEG={SETTINGS['jpeg_quality']}")
                SETTINGS["restart_camera"] = False
            except Exception as e:
                print("[ERROR] Camera restart failed:", e)
                time.sleep(1)
                continue

        frame = picam.capture_array()
        success, buffer = cv2.imencode(
            '.jpg',
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), SETTINGS["jpeg_quality"]]
        )
        if not success:
            continue

        frame_bytes = buffer.tobytes()

        with frame_lock:
            latest_frame = frame_bytes
            frame_count += 1

        now = time.time()
        if now - last_time >= 1.0:
            fps_display = frame_count
            frame_count = 0
            last_time = now

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            latest_frame +
            b"\r\n"
        )

if __name__ == '__main__':
    print("[INFO] Starting MJPEG test server on http://0.0.0.0:5001")
    app.run(host='0.0.0.0', port=5001, threaded=True)
