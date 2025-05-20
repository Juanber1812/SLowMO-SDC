# server2.py

from gevent import monkey; monkey.patch_all()

from flask import Flask, request
from flask_socketio import SocketIO, emit
import sensors
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

def start_sensor_thread():
    sensor_thread = threading.Thread(target=sensors.start_sensors, daemon=True)
    sensor_thread.start()

@socketio.on('connect')
def on_connect():
    emit('server_status', {'status': 'connected'}, to=request.sid)

@socketio.on('disconnect')
def on_disconnect():
    emit('server_status', {'status': 'disconnected'}, to=request.sid)

@socketio.on('frame')
def on_frame(data):
    emit('frame', data, broadcast=True)

@socketio.on('start_camera')
def handle_start_camera():
    emit('start_camera', {}, broadcast=True)

@socketio.on('stop_camera')
def handle_stop_camera():
    emit('stop_camera', {}, broadcast=True)

@socketio.on('camera_config')
def update_camera_config(data):
    emit('camera_config', data, broadcast=True)

@socketio.on("sensor_data")
def handle_sensor_data(data):
    socketio.emit("sensor_broadcast", data)

if __name__ == "__main__":
    print("🚀 Server running at http://0.0.0.0:5000")
    start_sensor_thread()
    socketio.run(app, host="0.0.0.0", port=5000)
