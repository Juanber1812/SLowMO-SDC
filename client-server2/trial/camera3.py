# camera_mjpeg.py
from picamera2 import Picamera2
from flask import Flask, Response
import threading, time, cv2

app = Flask(__name__)
picam = Picamera2()
streaming = False
jpeg_quality = 80
frame_lock = threading.Lock()
latest_frame = b''

def mjpeg_stream():
    global latest_frame
    while streaming:
        frame = picam.capture_array()
        success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if success:
            with frame_lock:
                latest_frame = buffer.tobytes()
        time.sleep(0.01)

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                frame = latest_frame
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)  # ~30 FPS
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start')
def start_stream():
    global streaming
    if not streaming:
        config = picam.create_preview_configuration(main={"format": "XRGB8888", "size": (640, 480)})
        picam.configure(config)
        picam.start()
        streaming = True
        threading.Thread(target=mjpeg_stream, daemon=True).start()
    return "Streaming started"

@app.route('/stop')
def stop_stream():
    global streaming
    if streaming:
        streaming = False
        picam.stop()
    return "Streaming stopped"

if __name__ == "__main__":
    print("Starting MJPEG stream at http://0.0.0.0:8080/video_feed")
    app.run(host='0.0.0.0', port=8080, threaded=True)
