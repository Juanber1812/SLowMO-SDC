from flask import Flask, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def on_connect():
    print(f"[SERVER] Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"[SERVER] Client disconnected: {request.sid}")

@socketio.on('frame_data')
def on_frame_data(data):
    emit('frame_data', data, broadcast=True)

@socketio.on('camera_config')
def on_camera_config(data):
    emit('camera_config', data, broadcast=True)

if __name__ == "__main__":
    print("[SERVER] Running at http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000)
