from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

camera_state = "Idle"
background_threads_started = False  # ✅ Flag to avoid starting threads multiple times


def print_server_status(status):
    print(f"[SERVER STATUS] {status}".ljust(80), end='\r', flush=True)


def start_background_tasks():
    print("[DEBUG] Starting background threads for camera and sensors")
    threading.Thread(target=camera.start_stream, daemon=True).start()
    threading.Thread(target=sensors.start_sensors, daemon=True).start()


@socketio.on('connect')
def handle_connect():
    global background_threads_started
    print(f"[INFO] Client connected: {request.sid}")

    if not background_threads_started:
        start_background_tasks()
        background_threads_started = True


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
    global camera_state
    try:
        emit('start_camera', {}, broadcast=True)
        camera_state = "Streaming"
        socketio.emit('camera_status', {'status': camera_state})
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")


@socketio.on('stop_camera')
def handle_stop_camera():
    global camera_state
    try:
        emit('stop_camera', {}, broadcast=True)
        camera_state = "Idle"
        socketio.emit('camera_status', {'status': camera_state})
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


@socketio.on("camera_status")
def handle_camera_status(data):
    try:
        emit("camera_status", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] camera_status: {e}")


@socketio.on('get_camera_status')
def handle_get_camera_status():
    emit('camera_status', {'status': camera_state})


@socketio.on("camera_info")
def on_camera_info(data):
    try:
        emit("camera_info", data, broadcast=True)
    except Exception as e:
        print("Camera info error:", e)


@socketio.on('set_camera_idle')
def handle_set_camera_idle():
    global camera_state
    try:
        camera_state = "Idle"
        socketio.emit('camera_status', {'status': camera_state})
        print("[INFO] Camera set to idle by client request.")
    except Exception as e:
        print(f"[ERROR] set_camera_idle: {e}")


@socketio.on('capture_image')
def handle_capture_image(data):
    try:
        print("[INFO] Image capture requested from client")
        custom_path = data.get("path") if data else None
        result = camera.streamer.capture_image(custom_path)
        emit("image_captured", result, broadcast=True)

        if result["success"]:
            print(f"[INFO] ✓ Image captured: {result['path']} ({result['size_mb']} MB)")
        else:
            print(f"[ERROR] ❌ Image capture failed: {result['error']}")
    except Exception as e:
        print(f"[ERROR] capture_image handler: {e}")
        emit("image_captured", {
            "success": False,
            "error": f"Server error: {str(e)}"
        }, broadcast=True)


@socketio.on('download_image')
def handle_download_image(data):
    try:
        import os
        import base64

        server_path = data.get("server_path")
        filename = data.get("filename")
        print(f"[INFO] Image download requested: {filename}")

        if os.path.exists(server_path):
            with open(server_path, 'rb') as f:
                image_data = f.read()

            encoded_image = base64.b64encode(image_data).decode('utf-8')
            emit("image_download", {
                "success": True,
                "filename": filename,
                "data": encoded_image,
                "size": len(image_data)
            })
            print(f"[INFO] 📤 Sent image to client: {filename} ({len(image_data)/1024:.1f} KB)")
        else:
            emit("image_download", {
                "success": False,
                "error": f"Image not found: {server_path}"
            })
            print(f"[ERROR] Image file not found: {server_path}")
    except Exception as e:
        print(f"[ERROR] download_image handler: {e}")
        emit("image_download", {
            "success": False,
            "error": str(e)
        })


def set_camera_state(new_state):
    global camera_state
    camera_state = new_state
    socketio.emit('camera_status', {'status': camera_state})


if __name__ == "__main__":
    print("🚀 Server running at http://0.0.0.0:5000")
    print("Press Ctrl+C to stop the server and clean up resources.")
    try:
        socketio.run(app, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down server...")
        try:
            camera.streamer.streaming = False
            if hasattr(camera.streamer, "picam") and getattr(camera.streamer.picam, "started", False):
                camera.streamer.picam.stop()
                print("[INFO] Camera stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop camera: {e}")

        try:
            sensors.stop_sensors()
            print("[INFO] Sensors stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop sensors: {e}")

        print("[INFO] Server exited cleanly.")
        exit(0)
