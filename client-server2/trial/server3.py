from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera3

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

camera3.start_stream()

@socketio.on('connect')
def on_connect():
    emit('server_status', {'status': 'connected'}, to=request.sid)

@socketio.on('disconnect')
def on_disconnect():
    emit('server_status', {'status': 'disconnected'}, to=request.sid)

@socketio.on('camera_config')
def handle_camera_config(data):
    print("[CONFIG] Received:", data)
    camera3.update_config(data)

@socketio.on("sensor_data")
def handle_sensor_data(data):
    socketio.emit("sensor_broadcast", data)

if __name__ == "__main__":
    print("🚀 Server running at http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000)
