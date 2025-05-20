# server3.py
from flask import Flask, Response, request
from camera3 import MJPEGCamera

app = Flask(__name__)
camera = MJPEGCamera()

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            frame = camera.get_jpeg_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start', methods=['POST'])
def start_stream():
    try:
        camera.start()
        return "Stream started", 200
    except Exception as e:
        return f"Start error: {e}", 500

@app.route('/stop', methods=['POST'])
def stop_stream():
    try:
        camera.stop()
        return "Stream stopped", 200
    except Exception as e:
        return f"Stop error: {e}", 500

@app.route('/config', methods=['POST'])
def update_config():
    try:
        data = request.get_json()
        if not data:
            return "No config received", 400
        camera.update_config(data)
        return "Config updated", 200
    except Exception as e:
        return f"Config error: {e}", 500

@app.route('/')
def index():
    return '''
    <html>
      <head><title>MJPEG Stream</title></head>
      <body>
        <h2>MJPEG Stream</h2>
        <img src="/video_feed" width="640"><br>
        <form action="/start" method="post"><button>Start Camera</button></form>
        <form action="/stop" method="post"><button>Stop Camera</button></form>
      </body>
    </html>
    '''

if __name__ == "__main__":
    print("[SERVER] MJPEG camera server running at http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, threaded=True)
