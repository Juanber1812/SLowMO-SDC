# -*- coding: utf-8 -*-
from flask import Flask, Response, request, render_template_string, jsonify
import time, cv2, psutil, threading, csv
from picamera2 import Picamera2

app = Flask(__name__)
picam = Picamera2()

RES_OPTIONS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
    "2592x1944": (2592, 1944)
}

SETTINGS = {
    "resolution": (640, 480),
    "fps": 10,
    "jpeg_quality": 70,
    "camera_running": False
}

latest_frame = b''
frame_count = 0
fps_measured = 0
csv_file = "camera_benchmark.csv"
points = []  # List of dicts: {"fps_set": ..., "fps_measured": ..., "jpeg": ...}

def get_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000.0
    except:
        return None

def get_res_label(res):
    for label, val in RES_OPTIONS.items():
        if val == res:
            return label
    return "640x480"

def camera_thread():
    global latest_frame, frame_count, fps_measured
    last_time = time.time()
    while True:
        if SETTINGS["camera_running"]:
            try:
                frame = picam.capture_array()
                success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), SETTINGS["jpeg_quality"]])
                if not success:
                    continue
                latest_frame = buffer.tobytes()
                frame_count += 1

                now = time.time()
                if now - last_time >= 1.0:
                    fps_measured = frame_count
                    frame_count = 0
                    last_time = now
            except Exception as e:
                print("[ERROR] Camera capture:", e)
                time.sleep(0.5)
        else:
            time.sleep(0.2)

@app.route('/')
def index():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pi Camera Dashboard</title>
            <style>
                body { font-family: sans-serif; background: #111; color: #eee; }
                input, select, button { font-size: 1em; margin: 5px; }
                #panel { background: #222; padding: 10px; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>Live Stream</h2>
            <img src="/video_feed" width="640" id="liveimg">
            <div id="panel">
                <h3>Controls</h3>
                <form id="settingsForm">
                    Resolution:
                    <select name="res" id="res">
                        {% for label in res_labels %}
                            <option value="{{ label }}" {% if current_res == label %}selected{% endif %}>{{ label }}</option>
                        {% endfor %}
                    </select><br>
                    FPS: <input type="number" name="fps" min="1" max="120" value="{{ fps }}" id="fps">
                    JPEG Quality: <input type="number" name="jpeg" min="10" max="100" value="{{ jpeg }}" id="jpeg">
                    <button type="submit">Apply Settings</button>
                </form>
                <button onclick="startCamera()">Start Camera</button>
                <button onclick="stopCamera()">Stop Camera</button>
                <button onclick="recordPoint()">Record Point</button>
                <h3>Live Info</h3>
                <p id="info">Loading...</p>
                <canvas id="fpsChart" width="600" height="300"></canvas>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script>
                let chart = new Chart(document.getElementById('fpsChart'), {
                    type: 'scatter',
                    data: {
                        datasets: []
                    },
                    options: {
                        plugins: {
                            legend: { display: true }
                        },
                        scales: {
                            x: { title: { display: true, text: 'Set FPS' }, min: 0, max: 130 },
                            y: { title: { display: true, text: 'Measured FPS' }, min: 0, max: 130 }
                        }
                    }
                });

                function updateStatus() {
                    fetch('/status').then(r => r.json()).then(data => {
                        document.getElementById('info').innerText =
                            `Measured FPS: ${data.fps} | CPU: ${data.cpu}% | Temp: ${data.temp} °C`;
                    });
                }
                setInterval(updateStatus, 1000);

                function updateChart() {
                    fetch('/points').then r => r.json()).then(points => {
                        // Group by JPEG quality
                        let groups = {};
                        points.forEach(pt => {
                            let key = "JPEG " + pt.jpeg;
                            if (!groups[key]) groups[key] = [];
                            groups[key].push({x: pt.fps_set, y: pt.fps_measured});
                        });
                        chart.data.datasets = Object.entries(groups).map(([label, data], i) => ({
                            label,
                            data,
                            backgroundColor: `hsl(${(i*60)%360},80%,60%)`
                        }));
                        chart.update();
                    });
                }
                setInterval(updateChart, 2000);

                function recordPoint() {
                    fetch('/record', {method: 'POST'})
                        .then(() => updateChart());
                }

                function startCamera() {
                    fetch('/start', {method: 'POST'});
                }
                function stopCamera() {
                    fetch('/stop', {method: 'POST'});
                }

                document.getElementById('settingsForm').onsubmit = function(e) {
                    e.preventDefault();
                    let form = new FormData(this);
                    fetch('/settings', {method: 'POST', body: form})
                        .then(() => setTimeout(updateStatus, 500));
                };
            </script>
        </body>
        </html>
    ''', fps=SETTINGS["fps"], jpeg=SETTINGS["jpeg_quality"],
       res_labels=RES_OPTIONS.keys(),
       current_res=get_res_label(SETTINGS["resolution"]))

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            if latest_frame:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n'
                )
            else:
                time.sleep(0.1)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/settings', methods=['POST'])
def update_settings():
    SETTINGS["fps"] = int(request.form.get("fps", SETTINGS["fps"]))
    SETTINGS["jpeg_quality"] = int(request.form.get("jpeg", SETTINGS["jpeg_quality"]))
    label = request.form.get("res")
    if label in RES_OPTIONS:
        SETTINGS["resolution"] = RES_OPTIONS[label]
    if SETTINGS["camera_running"]:
        try:
            config = picam.create_preview_configuration(
                main={"format": "XRGB8888", "size": SETTINGS["resolution"]},
                controls={"FrameDurationLimits": (
                    int(1e6 / max(SETTINGS["fps"], 1)),
                    int(1e6 / max(SETTINGS["fps"], 1))
                )}
            )
            picam.configure(config)
            picam.start()
        except Exception as e:
            print("[ERROR] Reconfiguring camera:", e)
    print(f"[CONFIG] New Settings: {SETTINGS}")
    return ('', 204)

@app.route('/start', methods=['POST'])
def start_camera():
    if not SETTINGS["camera_running"]:
        try:
            config = picam.create_preview_configuration(
                main={"format": "XRGB8888", "size": SETTINGS["resolution"]},
                controls={"FrameDurationLimits": (
                    int(1e6 / max(SETTINGS["fps"], 1)),
                    int(1e6 / max(SETTINGS["fps"], 1))
                )}
            )
            picam.configure(config)
            picam.start()
            SETTINGS["camera_running"] = True
            print("[INFO] Camera started.")
        except Exception as e:
            print("[ERROR] Starting camera:", e)
    return ('', 204)

@app.route('/stop', methods=['POST'])
def stop_camera():
    if SETTINGS["camera_running"]:
        try:
            picam.stop()
            SETTINGS["camera_running"] = False
            print("[INFO] Camera stopped.")
        except Exception as e:
            print("[ERROR] Stopping camera:", e)
    return ('', 204)

@app.route('/status')
def status():
    return jsonify({
        "fps": fps_measured,
        "cpu": psutil.cpu_percent(),
        "temp": get_temp()
    })

@app.route('/record', methods=['POST'])
def record_point():
    width, height = SETTINGS["resolution"]
    row = {
        "width": width,
        "height": height,
        "fps_set": SETTINGS["fps"],
        "jpeg": SETTINGS["jpeg_quality"],
        "fps_measured": round(fps_measured, 2)
    }
    points.append(row)
    with open(csv_file, "a", newline="") as f:
        csv.writer(f).writerow([row["width"], row["height"], row["fps_set"], row["jpeg"], row["fps_measured"]])
    print(f"[RECORD] {row}")
    return ('', 204)

@app.route('/points')
def get_points():
    return jsonify(points)

if __name__ == '__main__':
    with open(csv_file, "w", newline="") as f:
        csv.writer(f).writerow(["width", "height", "fps_set", "jpeg", "fps_measured"])
    threading.Thread(target=camera_thread, daemon=True).start()
    print("[INFO] Access camera dashboard at http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, threaded=True)
