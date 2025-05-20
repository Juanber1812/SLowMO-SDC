
from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors

# Initialize Flask and Socket.IO with gevent
app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='gevent',
    logger=True,
    engineio_logger=True
)

@socketio.on('connect')
def on_connect():
    print(f"[INFO] Client connected: {request.sid}")
    emit('server_status', {'status': 'connected'})

@socketio.on('disconnect')
def on_disconnect():
    print(f"[INFO] Client disconnected: {request.sid}")
    emit('server_status', {'status': 'disconnected'})

@socketio.on('frame_data')
def handle_frame_data(data):
    # Broadcast incoming frame_data to all clients as 'frame'
    socketio.emit('frame', data, broadcast=True)

@socketio.on('start_camera')
def handle_start_camera():
    print("[INFO] Received start_camera command")
    socketio.emit('start_camera', {}, broadcast=True)

@socketio.on('stop_camera')
def handle_stop_camera():
    print("[INFO] Received stop_camera command")
    socketio.emit('stop_camera', {}, broadcast=True)

@socketio.on('camera_config')
def handle_camera_config(data):
    print(f"[INFO] Received camera_config: {data}")
    socketio.emit('camera_config', data, broadcast=True)

@socketio.on('sensor_data')
def handle_sensor_data(data):
    # Relay sensor data under a separate namespace
    socketio.emit('sensor_broadcast', data, broadcast=True)

if __name__ == "__main__":
    print("[INFO] Server running at http://0.0.0.0:5000")
    # Start camera and sensor clients as background tasks once server is up
    socketio.start_background_task(camera.start_stream)
    socketio.start_background_task(sensors.start_sensors)
    # Run the Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5000)
