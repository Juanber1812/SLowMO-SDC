# -*- coding: utf-8 -*-
from flask import Flask, Response, request, render_template_string, jsonify, send_file
import time, cv2, psutil, threading, io, csv
from picamera2 import Picamera2
from datetime import datetime

app = Flask(__name__)
picam = Picamera2()

# Global config and state
SETTINGS = {
    "fps": 10,
    "jpeg_quality": 70,
    "resolution": (640, 480)
}
lock = threading.Lock()
running = True
latest_frame = b''
fps_display = 0
frame_count = 0
last_fps_time = time.time()
csv_file = "camera_benchmark.csv"

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
            <title>Pi Camera Dashboard</title>
            <style>
                body { font-family: sans-serif; background: #111; color: #eee; }
                input, button { font-size: 1em; margin: 5px; }
                #panel { background: #222; padding: 10px; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>Live Stream</h2>
            <img src="/video_feed" width="640">
            <div id="panel">
                <h3>Controls</h3>
                <form method="POST" action="/settings">
                    FPS: <input type="number" name="fps" min="1" max="120" value="{{ fps }}">
                    JPEG Quality: <input type="number" name="jpeg" min="10" max="100" value="{{ jpeg }}">
                    <button type="submit">Apply</button>
                </form>
                <button onclick="window.location='/snapshot'">📸 Download Snapshot</button>
                <h3>Live System Info</h3>
                <p id="status">...</p>
                <canvas id="fpsChart" width="600" height="200"></canvas>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script>
                let fpsData = [];
                let chart = new Chart(document.getElementById('fpsChart'), {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'FPS',
                            data: [],
                            borderColor: 'lime',
                            borderWidth: 1,
                            fill: false
                        }]
                    },
                    options: { animation: false, scales: { y: { min: 0, max: 120 } } }
                });

                function updateInfo() {
                    fetch('/status').then(r => r.json()).then(data => {
                        document.getElementById('status').innerText =
                            `FPS: ${data.fps} | CPU: ${data.cpu}% | Temp: ${data.temp} °C`;
                        const now = new Date().toLocaleTimeString();
                        if (chart.data.labels.length > 30) {
                            chart.data.labels.shift();
                            chart.data.datasets[0].data.shift();
                        }
                        chart.data.labels.push(now);
                        chart.data.datasets[0].data.push(data.fps);
                        chart.update();
                    });
                }

                setInterval(updateInfo, 1000);
            </script>
        </body>
        </html>
    ''', fps=SETTINGS["fps"], jpeg=SETTINGS["jpeg_quality"])

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({
        "fps": fps_display,
        "cpu": psutil.cpu_percent(),
        "temp": get_temp()
    })

@app.route('/settings', methods=['POST'])
def update_settings():
    with lock:
        SETTINGS["fps"] = int(request.form.get("fps", SETTINGS["fps"]))
        SETTINGS["jpeg_quality"] = int(request.form.get("jpeg", SETTINGS["jpeg_quality"]))
        print(f"[CONFIG] Applied: {SETTINGS}")
    return "Settings updated. <a href='/'>Return</a>"

@app.route('/snapshot')
def snapshot():
    global latest_frame
    return send_file(io.BytesIO(latest_frame), mimetype='image/jpeg', as_attachment=True, download_name='snapshot.jpg')

def write_csv(fps):
    with open(csv_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            SETTINGS["resolution"][0],
            SETTINGS["resolution"][1],
            SETTINGS["fps"],
            SETTINGS["jpeg_quality"],
            round(fps, 2)
        ])

def gen_frames():
    global latest_frame, fps_display, frame_count, last_fps_time

    with lock:
        config = picam.create_preview_configuration(main={"format": "XRGB8888", "size": SETTINGS["resolution"]})
        picam.configure(config)
        picam.start()

    while running:
        try:
            with lock:
                frame = picam.capture_array()
                jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), SETTINGS["jpeg_quality"]])[1]
                latest_frame = jpeg.tobytes()
                frame_count += 1

            now = time.time()
            if now - last_fps_time >= 1.0:
                fps_display = frame_count
                frame_count = 0
                last_fps_time = now
                write_csv(fps_display)

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n'
            )
        except Exception as e:
            print("[ERROR]", e)
            time.sleep(1)

if __name__ == '__main__':
    print("[INFO] Starting at http://0.0.0.0:5001")
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "width", "height", "fps_set", "jpeg", "fps_measured"])
    app.run(host="0.0.0.0", port=5001, threaded=True)
