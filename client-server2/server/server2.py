
from flask_socketio import SocketIO, emit
from gevent import monkey; monkey.patch_all()
from flask import Flask, request

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Keep track of connected clients (optional)
connected_clients = set()

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    connected_clients.add(sid)
    print(f"Client connected: {sid}; total = {len(connected_clients)}")
    # Send an acknowledgment back just to that client:
    emit('server_status', {
        'status': 'connected',
        'client_id': sid,
        'connected_count': len(connected_clients)
    }, to=sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    connected_clients.discard(sid)
    print(f"Client disconnected: {sid}; total = {len(connected_clients)}")
    # Broadcast an update to everyone
    emit('server_status', {
        'status': 'disconnected',
        'client_id': sid,
        'connected_count': len(connected_clients)
    }, broadcast=True)

@app.route('/status')
def status():
    return "Server is up"

@socketio.on('frame_data')
def on_frame(data):
    emit('frame', data, broadcast=True)

@socketio.on('sensor_data')
def on_sensor(data):
    emit('sensor', data, broadcast=True)

@socketio.on('imu_data')
def on_imu(data):
    emit('imu', data, broadcast=True)

@socketio.on('control_data')
def on_control(data):
    emit('control', data, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000)
