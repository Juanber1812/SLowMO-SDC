# server2.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors
import lidar
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

camera_state = "Idle"  # Default camera state


def print_server_status(status):
    print(f"[SERVER STATUS] {status}".ljust(80), end='\r', flush=True)


def start_background_tasks():
    threading.Thread(target=camera.start_stream, daemon=True).start()
    threading.Thread(target=sensors.start_sensors, daemon=True).start()
    threading.Thread(target=lidar.start_lidar, daemon=True).start()

    # Tachometer task
#    from tachometer import run_tachometer
#
 #   # helper that prints & pushes via SocketIO
  #  def report_rpm(rpm):
   #     print(f"[TACHO] RPM: {rpm:.1f}")                             # <-- print
    #    # remove the old `broadcast` arg
     #   socketio.emit("tachometer_data", {"rpm": rpm})

    # launch the tachometer loop in its own thread
 #   threading.Thread(
  #      target=lambda: run_tachometer(report_rpm),
   #     daemon=True
    #).start()


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

@socketio.on("adcs_command")
def handle_adcs_command(data):
    try:
        print(f"[SERVER] Received ADCS command: {data}")
        command = data.get("command")
        
        if command == "environmental":
            # Call environmental calibration mode.
            from adcs_functions import environmental_calibration_mode
            environmental_calibration_mode()
        
        elif command == "manual_clockwise_start":
            # Start clockwise motor action (e.g., acceleration).
            from motor_test import rotate_clockwise_dc
            rotate_clockwise_dc()  # Adjust with parameters if needed.
        
        elif command == "manual_clockwise_stop":
            # Stop the clockwise action. Replace with an appropriate stop function.
            from motor_test import stop_motor_dc
            stop_motor_dc()
        
        elif command == "manual_anticlockwise_start":
            # Start anticlockwise action (e.g., deceleration or reverse logic).
            from motor_test import rotate_counterclockwise_dc
            rotate_counterclockwise_dc()  # Adjust with parameters if needed.
        
        elif command == "manual_anticlockwise_stop":
            # Stop anticlockwise action, using a stop routine.
            from motor_test import stop_motor_dc
            stop_motor_dc()
        
        elif command == "set_target_orientation":
            target = data.get("value")
            # If you have a function to set the orientation, call it here.
            print(f"[SERVER] Setting target orientation to: {target}")
            # For example:
            # from adcs_functions import set_target_orientation
            # set_target_orientation(target)
        
        elif command == "detumbling":
            # Call your detumbling routine if it exists.
            print("[SERVER] Running detumbling procedure")
            # For example:
            # from adcs_functions import detumbling
            # detumbling()
        else:
            print("[SERVER] Unknown ADCS command received.")
        
        emit("adcs_command_ack", {"status": "OK", "command": command}, broadcast=True)
    except Exception as e:
        print(f"[ERROR] ADCS command handling: {e}")

@socketio.on("sensor_data")
def handle_sensor_data(data):
    try:
        emit("sensor_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] sensor_data: {e}")


@socketio.on("camera_status")
def handle_camera_status(data):
    try:
        # Broadcast the camera status to all connected clients
        emit("camera_status", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] camera_status: {e}")


@socketio.on('get_camera_status')
def handle_get_camera_status():
    # Send the current camera state to the requesting client
    emit('camera_status', {'status': camera_state})


@socketio.on("camera_info")
def on_camera_info(data):
    try:
        # Broadcast the camera info to all connected clients
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
    """Handle image capture request from client"""
    try:
        print("[INFO] Image capture requested from client")
        
        # Get custom path if provided in the request data
        custom_path = data.get("path") if data else None
        
        # Use the existing camera streamer instance to capture image
        result = camera.streamer.capture_image(custom_path)
        
        # Broadcast the result to all connected clients
        emit("image_captured", result, broadcast=True)
        
        if result["success"]:
            print(f"[INFO] ✓ Image captured successfully: {result['path']} ({result['size_mb']} MB)")
        else:
            print(f"[ERROR] ❌ Image capture failed: {result['error']}")
            
    except Exception as e:
        print(f"[ERROR] capture_image handler: {e}")
        # Send error response to client
        emit("image_captured", {
            "success": False, 
            "error": f"Server error: {str(e)}"
        }, broadcast=True)

@socketio.on("lidar_data")
def handle_lidar_data(data):
    try:
        emit("lidar_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] lidar_data: {e}")


@socketio.on('download_image')
def handle_download_image(data):
    """Send captured image to client for local storage"""
    try:
        import os
        import base64
        
        server_path = data.get("server_path")
        filename = data.get("filename")
        
        print(f"[INFO] Image download requested: {filename}")
        
        if os.path.exists(server_path):
            # Read the image file
            with open(server_path, 'rb') as f:
                image_data = f.read()
            
            # Encode as base64 for transmission
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Send to client
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
