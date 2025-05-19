# server.py
from flask import Flask
from flask_socketio import SocketIO, emit
from gevent import monkey; monkey.patch_all()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

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
