# server2.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

connected_clients = set()
CAMERA_SID = None  # Store the camera's session id


def start_background_tasks():
    threading.Thread(target=camera.start_stream, daemon=True).start()
    threading.Thread(target=sensors.start_sensors, daemon=True).start()


@socketio.on('connect')
def handle_connect():
    global CAMERA_SID
    sid = request.sid
    # Identify the camera by a special handshake or first connection
    if CAMERA_SID is None:
        CAMERA_SID = sid
        print("[SERVER STATUS] Camera connected".ljust(80), end='\r', flush=True)
    else:
        connected_clients.add(sid)
        print(f"[INFO] Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    global CAMERA_SID
    sid = request.sid
    if sid == CAMERA_SID:
        print("[SERVER STATUS] Camera disconnected".ljust(80), end='\r', flush=True)
        CAMERA_SID = None
    else:
        connected_clients.discard(sid)
        if not connected_clients:
            # No more clients, stop the camera
            socketio.emit('stop_camera', {}, broadcast=True)
        print(f"[INFO] Client disconnected: {request.sid}")


@socketio.on('frame')
def handle_frame(data):
    try:
        emit('frame', data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] frame broadcast: {e}")


@socketio.on('start_camera')
def handle_start_camera():
    try:
        emit('start_camera', {}, broadcast=True)
        # print("[INFO] start_camera triggered")  # Commented to reduce log spam
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")


@socketio.on('stop_camera')
def handle_stop_camera():
    try:
        emit('stop_camera', {}, broadcast=True)
        # print("[INFO] stop_camera triggered")  # Commented to reduce log spam
    except Exception as e:
        print(f"[ERROR] stop_camera: {e}")


@socketio.on('camera_config')
def handle_camera_config(data):
    try:
        emit('camera_config', data, broadcast=True)
        # print(f"[INFO] camera_config updated: {data}")  # Commented to reduce log spam
    except Exception as e:
        print(f"[ERROR] camera_config: {e}")


@socketio.on("sensor_data")
def handle_sensor_data(data):
    try:
        emit("sensor_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] sensor_data: {e}")


if __name__ == "__main__":
    print("🚀 Server running at http://0.0.0.0:5000")
    print("Press Ctrl+C to stop the server and clean up resources.")
    start_background_tasks()
    try:
        socketio.run(app, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down server...")

        # Attempt to stop camera and sensors gracefully
        try:
            camera.streamer.streaming = False
            if hasattr(camera.streamer, "picam") and getattr(camera.streamer.picam, "started", False):
                camera.streamer.picam.stop()
                print("[INFO] Camera stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop camera: {e}")

        try:
            sensors.stop_sensors()  # If you have a stop_sensors function
            print("[INFO] Sensors stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop sensors: {e}")

        print("[INFO] Server exited cleanly.")
        exit(0)
