from flask import Flask, Response
from picamera2 import Picamera2
import threading, time, cv2

app = Flask(__name__)
picam = Picamera2()
picam_config = picam.create_preview_configuration(main={"format": "XRGB8888", "size": (640, 480)})
picam.configure(picam_config)
picam.start()

current_config = {
    "resolution": (640, 480),
    "fps": 10,
    "jpeg_quality": 70
}

def apply_camera_config():
    try:
        res = current_config["resolution"]
        fps = current_config["fps"]
        config = picam.create_preview_configuration(
            main={"format": "XRGB8888", "size": res},
            controls={"FrameDurationLimits": (
                int(1e6 / fps),
                int(1e6 / fps)
            )}
        )
        picam.stop()
        picam.configure(config)
        picam.start()
        print(f"[CAMERA] Reconfigured: {res[0]}x{res[1]} @ {fps} FPS")
    except Exception as e:
        print("[CAMERA ERROR]", e)

def generate_frames():
    while True:
        frame = picam.capture_array()
        success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), current_config["jpeg_quality"]])
        if not success:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def start_stream():
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False), daemon=True).start()

def update_config(new_config):
    current_config.update(new_config)
    apply_camera_config()
