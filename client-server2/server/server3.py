# server3.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import threading
import logging
import time

# Import ADCS controller
try:
    from ADCS_PD import ADCSController
    ADCS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"ADCS controller not available: {e}")
    ADCSController = None
    ADCS_AVAILABLE = False

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize ADCS controller
adcs_controller = None
if ADCS_AVAILABLE:
    adcs_controller = ADCSController()

def print_server_status(status):
    print(f"[SERVER STATUS] {status}".ljust(80), end='\r', flush=True)

connected_clients = set()

# ===================== CAMERA/LIVE STREAM/IMAGE SECTION =====================

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
        print("[INFO] Start camera command relayed to camera.py")
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")

@socketio.on('stop_camera')
def handle_stop_camera():
    try:
        emit('stop_camera', {}, broadcast=True)
        print("[INFO] Stop camera command relayed to camera.py")
    except Exception as e:
        print(f"[ERROR] stop_camera: {e}")

@socketio.on('camera_config')
def handle_camera_config(data):
    try:
        emit('camera_config', data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] camera_config: {e}")

@socketio.on("camera_info")
def on_camera_info(data):
    try:
        camera_status_from_info = data.get("status", "Error")
        camera_connected = camera_status_from_info == "OK"
        if not camera_connected:
            display_status = "Disconnected"
        elif data.get("fps", 0) > 0:
            display_status = "Streaming"
        else:
            display_status = "Connected"
        payload_data = {
            "camera_status": display_status,
            "camera_connected": camera_connected,
            "camera_streaming": display_status == "Streaming",
            "fps": data.get("fps", 0),
            "frame_size": data.get("frame_size", 0),
            "status": camera_status_from_info
        }
        emit("camera_payload_broadcast", payload_data, broadcast=True)
    except Exception as e:
        print("Camera info error:", e)

@socketio.on('set_camera_idle')
def handle_set_camera_idle():
    try:
        emit('set_camera_idle', {}, broadcast=True)
        print("[INFO] Set camera idle command relayed to camera.py")
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
            print(f"[INFO] ✓ Image captured successfully: {result['path']} ({result['size_mb']} MB)")
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

# ===================== END CAMERA/LIVE STREAM/IMAGE SECTION =====================

# ===================== ADCS SECTION =====================

@socketio.on("adcs_command")
def handle_adcs_command(data):
    try:
        print(f"[SERVER] Received ADCS command: {data}")
        if not adcs_controller:
            print("[ERROR] ADCS controller not available")
            emit("adcs_command_ack", {"status": "ERROR", "message": "ADCS controller not available"}, broadcast=True)
            return
        mode = data.get("mode", "Unknown")
        command = data.get("command", "unknown")
        value = data.get("value")
        result = adcs_controller.handle_adcs_command(mode, command, value)
        emit("adcs_command_ack", {
            "status": result.get("status", "error").upper(),
            "message": result.get("message", "Command processed"),
            "mode": mode,
            "command": command
        }, broadcast=True)
        print(f"[SERVER] ADCS command result: {result}")
    except Exception as e:
        print(f"[ERROR] ADCS command handling: {e}")
        emit("adcs_command_ack", {
            "status": "ERROR", 
            "message": f"Command failed: {str(e)}"
        }, broadcast=True)

def adcs_data_broadcast():
    if not adcs_controller:
        return
    try:
        adcs_data = adcs_controller.get_adcs_data_for_server()
        socketio.emit("adcs_broadcast", adcs_data)
    except Exception as e:
        logging.error(f"Error in ADCS data broadcast: {e}")
        socketio.emit("adcs_broadcast", {
            "gyro": "0.0°",
            "orientation": "Y:0.0° R:0.0° P:0.0°",
            "gyro_rate_x": "0.00", "gyro_rate_y": "0.00", "gyro_rate_z": "0.00",
            "angle_x": "0.0", "angle_y": "0.0", "angle_z": "0.0",
            "lux1": "0.0", "lux2": "0.0", "lux3": "0.0",
            "temperature": "0.0°C",
            "rpm": "0.0",
            "status": "Error"
        })

def start_adcs_broadcast():
    if not adcs_controller:
        return
    def adcs_broadcast_loop():
        while True:
            try:
                adcs_data_broadcast()
                time.sleep(0.05)  # 20Hz = 50ms interval
            except Exception as e:
                logging.error(f"Error in ADCS broadcast loop: {e}")
                time.sleep(1)
    threading.Thread(target=adcs_broadcast_loop, daemon=True).start()
    logging.info("ADCS data broadcasting started at 20Hz")

# ===================== END ADCS SECTION =====================

@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")
    connected_clients.add(request.sid)
    emit('camera_update', {}, broadcast=True)
    print("[INFO] Status update request sent to camera subsystem")
    logging.info(f"Client connected. Total clients: {len(connected_clients)}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[INFO] Client disconnected: {request.sid}")
    connected_clients.discard(request.sid)
    logging.info(f"Client disconnected. Remaining clients: {len(connected_clients)}")

@socketio.on('request_camera_update')
def handle_request_camera_update():
    try:
        emit('camera_update', {}, broadcast=True)
        print("[INFO] Camera status update requested manually")
    except Exception as e:
        print(f"[ERROR] request_camera_update: {e}")

def start_background_tasks():
    def delayed_start():
        time.sleep(2)
        print("\n[INFO] Starting background tasks...")
        threading.Thread(target=camera.start_stream, daemon=True).start()
        if adcs_controller:
            start_adcs_broadcast()
            logging.info("ADCS controller initialized and broadcasting started")
    threading.Thread(target=delayed_start, daemon=True).start()

if __name__ == "__main__":
    print("🚀 Server starting at http://0.0.0.0:5000")
    print("Background tasks will start after server initialization.")
    print("Press Ctrl+C to stop the server and clean up resources.")
    start_background_tasks()
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
            if adcs_controller:
                adcs_controller.shutdown()
                print("[INFO] ADCS controller stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop ADCS controller: {e}")
        print("[INFO] Server exited cleanly.")
        exit(0)
