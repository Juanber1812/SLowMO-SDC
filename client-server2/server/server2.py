# server2.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


def print_server_status(status):
    print(f"[SERVER STATUS] {status}".ljust(80), end='\r', flush=True)


def start_background_tasks():
    threading.Thread(target=camera.start_stream, daemon=True).start()
    threading.Thread(target=sensors.start_sensors, daemon=True).start()


@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
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
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")


@socketio.on('stop_camera')
def handle_stop_camera():
    try:
        emit('stop_camera', {}, broadcast=True)
    except Exception as e:
        print(f"[ERROR] stop_camera: {e}")


@socketio.on('camera_config')
def handle_camera_config(data):
    try:
        emit('camera_config', data, broadcast=True)
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
