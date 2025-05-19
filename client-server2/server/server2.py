# server2.py

from gevent import monkey; monkey.patch_all()  # MUST be first

from flask import Flask, request
from flask_socketio import SocketIO, emit
import time
import threading
import camera  # This is your camera module

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
connected_clients = {}

@app.route('/status')
def status():
    return "✅ Server is running"

@socketio.on('connect')
def on_connect():
    sid = request.sid
    connected_clients[sid] = time.time()
    print(f"🟢 Client connected: {sid} | Total: {len(connected_clients)}")
    emit('server_status', {
        'status': 'connected',
        'client_id': sid,
        'connected_count': len(connected_clients)
    }, to=sid)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    connected_clients.pop(sid, None)
    print(f"🔴 Client disconnected: {sid} | Total: {len(connected_clients)}")
    emit('server_status', {
        'status': 'disconnected',
        'client_id': sid,
        'connected_count': len(connected_clients)
    }, broadcast=True)

@socketio.on('frame_data')
def on_frame(data):
    print(f"📷 Frame received ({len(data)} bytes) → broadcasting to {len(connected_clients)} clients")
    emit('frame', data, broadcast=True)

@socketio.on('sensor_data')
def on_sensor(data):
    print(f"🌡️ Sensor update → Temp: {data.get('temperature')} °C | CPU: {data.get('cpu_percent')} %")
    emit('sensor', data, broadcast=True)

@socketio.on('imu_data')
def on_imu(data):
    print("🧭 IMU data received")
    emit('imu', data, broadcast=True)

@socketio.on('control_data')
def on_control(data):
    print(f"🛞 Control data received → Wheel RPM: {data.get('wheel_speed_rpm')}")
    emit('control', data, broadcast=True)

def start_camera_thread():
    cam_thread = threading.Thread(target=camera.start_stream, daemon=True)
    cam_thread.start()
    print("📽️ Camera streaming thread started.")

@socketio.on('start_camera')
def handle_start_camera():
    print("📩 Start camera command received from client.")
    emit('start_camera', {}, broadcast=True)

@socketio.on('stop_camera')
def handle_stop_camera():
    print("📩 Stop camera command received from client.")
    emit('stop_camera', {}, broadcast=True)

if __name__ == "__main__":
    print("🚀 Starting Socket.IO server on http://0.0.0.0:5000")
    start_camera_thread()
    socketio.run(app, host="0.0.0.0", port=5000)
