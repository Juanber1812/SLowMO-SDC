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
    """Handle camera start request from client"""
    global camera_state
    try:
        print("[INFO] Camera start requested from client")
        
        # Start the camera streaming thread if not already running
        if hasattr(camera, 'start_camera_streaming'):
            camera.start_camera_streaming()
        elif hasattr(camera.streamer, 'start_streaming'):
            camera.streamer.start_streaming()
        else:
            # Fallback - use existing start method
            camera.start_stream()
        
        camera_state = "Streaming"
        
        # Send status update to all clients
        emit('camera_status', {
            'status': camera_state,
            'streaming': True,
            'message': 'Camera streaming started'
        }, broadcast=True)
        
        print("[INFO] ✓ Camera streaming started")
        
    except Exception as e:
        print(f"[ERROR] start_camera handler: {e}")
        camera_state = "Error"
        emit('camera_status', {
            'status': camera_state,
            'streaming': False,
            'error': str(e)
        }, broadcast=True)

@socketio.on('stop_camera')
def handle_stop_camera():
    """Handle camera stop request from client"""
    global camera_state
    try:
        print("[INFO] Camera stop requested from client")
        
        # Stop the camera streaming thread
        if hasattr(camera, 'stop_camera_streaming'):
            camera.stop_camera_streaming()
        elif hasattr(camera.streamer, 'stop_streaming'):
            camera.streamer.stop_streaming()
        else:
            # Fallback - set streaming flag to False
            if hasattr(camera.streamer, 'streaming'):
                camera.streamer.streaming = False
        
        camera_state = "Idle"
        
        # Send status update to all clients
        emit('camera_status', {
            'status': camera_state,
            'streaming': False,
            'message': 'Camera streaming stopped'
        }, broadcast=True)
        
        print("[INFO] ✓ Camera streaming stopped")
        
    except Exception as e:
        print(f"[ERROR] stop_camera handler: {e}")
        camera_state = "Error"
        emit('camera_status', {
            'status': camera_state,
            'streaming': False,
            'error': str(e)
        }, broadcast=True)


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
        # Broadcast the camera status to all connected clients
        emit("camera_status", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] camera_status: {e}")


@socketio.on('get_camera_status')
def handle_get_camera_status():
    """Get current camera status"""
    try:
        # Check if camera is currently streaming
        is_streaming = False
        if hasattr(camera.streamer, 'streaming'):
            is_streaming = camera.streamer.streaming
        elif camera_state == "Streaming":
            is_streaming = True
        
        emit('camera_status', {
            'status': camera_state,
            'streaming': is_streaming
        })
        
    except Exception as e:
        print(f"[ERROR] get_camera_status: {e}")
        emit('camera_status', {
            'status': 'error',
            'streaming': False,
            'error': str(e)
        })


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


@socketio.on('start_lidar')
def handle_start_lidar():
    """Handle LIDAR start request from client"""
    try:
        print("[INFO] LIDAR start requested from client")
        # Start the LIDAR thread if not already running
        if hasattr(lidar, 'start_lidar_streaming'):
            lidar.start_lidar_streaming()
        else:
            # Fallback if different function name
            lidar.start_lidar()
        
        # Send status update to all clients
        emit("lidar_status", {
            "status": "started", 
            "streaming": True,
            "message": "LIDAR streaming started"
        }, broadcast=True)
        
        print("[INFO] ✓ LIDAR streaming started")
        
    except Exception as e:
        print(f"[ERROR] start_lidar handler: {e}")
        emit("lidar_status", {
            "status": "error",
            "streaming": False, 
            "error": str(e)
        }, broadcast=True)

@socketio.on('stop_lidar')
def handle_stop_lidar():
    """Handle LIDAR stop request from client"""
    try:
        print("[INFO] LIDAR stop requested from client")
        # Stop the LIDAR thread
        if hasattr(lidar, 'stop_lidar_streaming'):
            lidar.stop_lidar_streaming()
        else:
            # Fallback if different function name
            lidar.stop_lidar()
        
        # Send status update to all clients
        emit("lidar_status", {
            "status": "stopped",
            "streaming": False,
            "message": "LIDAR streaming stopped"
        }, broadcast=True)
        
        print("[INFO] ✓ LIDAR streaming stopped")
        
    except Exception as e:
        print(f"[ERROR] stop_lidar handler: {e}")
        emit("lidar_status", {
            "status": "error",
            "streaming": False,
            "error": str(e)
        }, broadcast=True)

@socketio.on('get_lidar_status')
def handle_get_lidar_status():
    """Get current LIDAR status"""
    try:
        # Check if LIDAR is currently streaming
        is_streaming = False
        if hasattr(lidar, 'is_streaming'):
            is_streaming = lidar.is_streaming
        elif hasattr(lidar, 'streaming'):
            is_streaming = lidar.streaming
        
        emit("lidar_status", {
            "status": "streaming" if is_streaming else "idle",
            "streaming": is_streaming
        })
        
    except Exception as e:
        print(f"[ERROR] get_lidar_status: {e}")
        emit("lidar_status", {
            "status": "error",
            "streaming": False,
            "error": str(e)
        })

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
