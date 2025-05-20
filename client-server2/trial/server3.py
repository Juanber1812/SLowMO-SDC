from flask import Flask, request
from flask_socketio import SocketIO, emit
import threading
import camera3  # ensure camera3.py is in same folder

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Start MJPEG video server
def start_camera_http_server():
    threading.Thread(target=camera3.run_flask_video_server, daemon=True).start()

@socketio.on('connect')
def on_connect():
    print(f"[SERVER] Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"[SERVER] Client disconnected: {request.sid}")

@socketio.on('camera_config')
def handle_camera_config(data):
    print("[CONFIG] Received:", data)
    camera3.update_camera_settings(data)
    emit('camera_config', data, broadcast=True)

@socketio.on('start_camera')
def handle_start():
    camera3.start_camera()

@socketio.on('stop_camera')
def handle_stop():
    camera3.stop_camera()

@socketio.on("sensor_data")
def handle_sensor_data(data):
    socketio.emit("sensor_broadcast", data)

if __name__ == "__main__":
    print("🚀 Socket.IO Server running at http://0.0.0.0:5000")
    start_camera_http_server()
    socketio.run(app, host="0.0.0.0", port=5000)
