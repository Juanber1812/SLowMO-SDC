
# server2.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request
from flask_socketio import SocketIO, emit
import camera
import sensors
import lidar
import threading
import logging
import time

# Import power monitoring
try:
    from power import PowerMonitor
    POWER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Power monitoring not available: {e}")
    PowerMonitor = None
    POWER_AVAILABLE = False

# Import communication monitoring
try:
    from communication import CommunicationMonitor
    COMMUNICATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Communication monitoring not available: {e}")
    CommunicationMonitor = None
    COMMUNICATION_AVAILABLE = False

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

camera_state = "Idle"  # Default camera state

# Initialize power monitor
power_monitor = None
if POWER_AVAILABLE:
    power_monitor = PowerMonitor(update_interval=2.0)  # Will try to connect to real hardware

# Initialize communication monitor
communication_monitor = None
if COMMUNICATION_AVAILABLE:
    communication_monitor = CommunicationMonitor()

def print_server_status(status):
    print(f"[SERVER STATUS] {status}".ljust(80), end='\r', flush=True)

connected_clients = set()

# ===================== CAMERA/LIVE STREAM/IMAGE SECTION =====================

@socketio.on('frame')
def handle_frame(data):
    try:
        emit('frame', data, broadcast=True)
        # Track upload data for communication monitoring
        if communication_monitor and isinstance(data, (bytes, bytearray)):
            communication_monitor.record_upload_data(len(data))
            communication_monitor.record_data_transmission(len(data))
        elif communication_monitor and isinstance(data, str):
            data_bytes = len(data.encode('utf-8'))
            communication_monitor.record_upload_data(data_bytes)
            communication_monitor.record_data_transmission(data_bytes)
    except Exception as e:
        print(f"[ERROR] frame broadcast: {e}")

@socketio.on('start_camera')
def handle_start_camera():
    global camera_state
    try:
        emit('start_camera', {}, broadcast=True)
        camera_state = "Streaming"
        # send_payload_status_update() removed; handled by camera_info event
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")

@socketio.on('stop_camera')
def handle_stop_camera():
    global camera_state
    try:
        emit('stop_camera', {}, broadcast=True)
        camera_state = "Idle"
        # send_payload_status_update() removed; handled by camera_info event
    except Exception as e:
        print(f"[ERROR] stop_camera: {e}")

@socketio.on('camera_config')
def handle_camera_config(data):
    try:
        emit('camera_config', data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] camera_config: {e}")


# --- CAMERA-ONLY PAYLOAD BROADCAST ---
@socketio.on("camera_info")
def on_camera_info(data):
    """Handle camera-only payload: status, fps, frame size"""
    try:
        camera_connected = True  # Assume connected if server is running
        camera_streaming = camera_state == "Streaming"
        payload_data = {
            "camera_status": camera_state,
            "camera_connected": camera_connected,
            "camera_streaming": camera_streaming,
            "fps": data.get("fps", 0),
            "frame_size": data.get("frame_size", 0)
        }
        emit("camera_payload_broadcast", payload_data, broadcast=True)
    except Exception as e:
        print("Camera info error:", e)

# --- LIDAR-ONLY PAYLOAD BROADCAST ---
@socketio.on("lidar_info")
def on_lidar_info(data):
    """Handle lidar-only payload: status and frequency"""
    try:
        lidar_status = "Disconnected"
        lidar_collecting = False
        if hasattr(lidar, 'lidar_controller'):
            if lidar.lidar_controller.connected:
                if lidar.lidar_controller.is_collecting:
                    lidar_status = "Active"
                    lidar_collecting = True
                else:
                    lidar_status = "Connected"
            else:
                lidar_status = "Disconnected"
        payload_data = {
            "lidar_status": lidar_status,
            "lidar_connected": lidar_status != "Disconnected",
            "lidar_collecting": lidar_collecting,
            "collection_rate_hz": data.get("collection_rate_hz", 0)
        }
        emit("lidar_payload_broadcast", payload_data, broadcast=True)
    except Exception as e:
        print("Lidar info error:", e)

@socketio.on('set_camera_idle')
def handle_set_camera_idle():
    global camera_state
    try:
        camera_state = "Idle"
        # Do not send payload_status_update; camera status will be sent only via camera_info
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


# Removed all other payload update handlers. Only camera_info and lidar_info are used for payload updates.

# ===================== END CAMERA/LIVE STREAM/IMAGE SECTION =====================

# ===================== OTHER LIVE DATA UPDATES SECTION =====================

def start_background_tasks():
    """Start background tasks with a delay to ensure server is ready"""
    def delayed_start():
        time.sleep(2)  # Give the server time to start
        print("\n[INFO] Starting background tasks...")
        threading.Thread(target=camera.start_stream, daemon=True).start()
        threading.Thread(target=sensors.start_sensors, daemon=True).start()
        threading.Thread(target=lidar.start_lidar, daemon=True).start()
        # Start power monitoring
        if power_monitor:
            power_monitor.set_update_callback(power_data_callback)
            if power_monitor.start_monitoring():
                logging.info("Power monitoring started successfully")
            else:
                logging.error("Failed to start power monitoring")
        # Do NOT start communication monitoring here; start on client connect
    # Start the delayed initialization in a separate thread
    threading.Thread(target=delayed_start, daemon=True).start()


@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")
    connected_clients.add(request.sid)
    # No longer send initial payload status; handled by camera_info/lidar_info events
    # Start communication monitoring if not already running
    if communication_monitor and not communication_monitor.is_monitoring:
        communication_monitor.set_update_callback(communication_data_callback)
        if communication_monitor.start_monitoring():
            logging.info("Communication monitoring started (on client connect)")
        else:
            logging.error("Failed to start communication monitoring (on client connect)")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[INFO] Client disconnected: {request.sid}")
    connected_clients.discard(request.sid)
    # Stop communication monitoring if no clients remain
    if communication_monitor and len(connected_clients) == 0:
        communication_monitor.stop_monitoring()
        logging.info("Communication monitoring stopped (no clients connected)")

@socketio.on("adcs_command")
def handle_adcs_command(data):
    try:
        print(f"[SERVER] Received ADCS command: {data}")
        command = data.get("command")
        if command == "environmental":
            from adcs_functions import environmental_calibration_mode
            environmental_calibration_mode()
        elif command == "manual_clockwise_start":
            from motor_test import rotate_clockwise_dc
            rotate_clockwise_dc()
        elif command == "manual_clockwise_stop":
            from motor_test import stop_motor_dc
            stop_motor_dc()
        elif command == "manual_anticlockwise_start":
            from motor_test import rotate_counterclockwise_dc
            rotate_counterclockwise_dc()
        elif command == "manual_anticlockwise_stop":
            from motor_test import stop_motor_dc
            stop_motor_dc()
        elif command == "set_target_orientation":
            target = data.get("value")
            print(f"[SERVER] Setting target orientation to: {target}")
        elif command == "detumbling":
            print("[SERVER] Running detumbling procedure")
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

@socketio.on("lidar_data")
def handle_lidar_data(data):
    try:
        if "distance_cm" in data and data["distance_cm"] is not None:
            emit("lidar_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] lidar_data: {e}")


@socketio.on("tachometer_data")
def handle_tachometer_data(data):
    try:
        emit("tachometer_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] tachometer_data: {e}")

@socketio.on("start_lidar")
def handle_start_lidar():
    try:
        lidar.lidar_controller.start_collection()
        print("🟢 LIDAR collection start requested")
        emit("lidar_command_response", {"success": True, "message": "LIDAR collection started"})
        # No longer send payload status update here; handled by lidar_info event
    except Exception as e:
        print(f"[ERROR] start_lidar: {e}")
        emit("lidar_command_response", {"success": False, "message": str(e)})

@socketio.on("stop_lidar")
def handle_stop_lidar():
    try:
        lidar.lidar_controller.stop_collection()
        print("🔴 LIDAR collection stop requested")
        emit("lidar_command_response", {"success": True, "message": "LIDAR collection stopped"})
        # No longer send payload status update here; handled by lidar_info event
    except Exception as e:
        print(f"[ERROR] stop_lidar: {e}")
        emit("lidar_command_response", {"success": False, "message": str(e)})




def power_data_callback(power_data):
    try:
        if power_data.get('status') in ['Disconnected', 'Error - Disconnected']:
            formatted_data = {
                "current": "0.000",
                "voltage": "0.0", 
                "power": "0.00",
                "energy": "0.00",
                "temperature": "0.0",
                "battery_percentage": 0,
                "status": "Disconnected"
            }
        else:
            formatted_data = {
                "current": f"{power_data['current_ma'] / 1000:.3f}",
                "voltage": f"{power_data['voltage_v']:.1f}",
                "power": f"{power_data['power_mw'] / 1000:.2f}",
                "energy": f"{power_data['energy_j'] / 3600:.2f}",
                "temperature": f"{power_data['temperature_c']:.1f}",
                "battery_percentage": power_data['battery_percentage'],
                "status": "Nominal" if power_data['status'] == "Operational" else power_data['status']
            }
        socketio.emit("power_broadcast", formatted_data)
        import time
        if not hasattr(power_data_callback, 'last_log') or time.time() - power_data_callback.last_log > 10:
            if power_data.get('status') == 'Disconnected':
                logging.debug("Power broadcast: Disconnected")
            else:
                logging.debug(f"Power broadcast: {power_data['power_mw']:.1f}mW, {power_data['voltage_v']:.2f}V, {power_data['current_ma']:.1f}mA")
            power_data_callback.last_log = time.time()
    except Exception as e:
        logging.error(f"Error in power data callback: {e}")

def communication_data_callback(comm_data):
    try:
        formatted_data = {
            "wifi_download_speed": comm_data.get('wifi_download_speed', 0.0),
            "wifi_upload_speed": comm_data.get('wifi_upload_speed', 0.0),
            "data_upload_speed": comm_data.get('data_upload_speed', 0.0),
            "data_transmission_rate": comm_data.get('data_transmission_rate', 0.0),
            "uplink_frequency": comm_data.get('uplink_frequency', 0.0),
            "downlink_frequency": comm_data.get('downlink_frequency', 0.0),
            "server_signal_strength": comm_data.get('server_signal_strength', 0),
            "connection_quality": comm_data.get('connection_quality', 'Unknown'),
            "network_latency": comm_data.get('network_latency', 0.0),
            "status": comm_data.get('status', 'Disconnected')
        }
        socketio.emit("communication_broadcast", formatted_data)
        if not hasattr(communication_data_callback, 'last_log') or time.time() - communication_data_callback.last_log > 30:
            print(f"\n[COMM] WiFi: {formatted_data['wifi_download_speed']:.1f}↓/{formatted_data['wifi_upload_speed']:.1f}↑ Mbps, "
                  f"Upload: {formatted_data['data_upload_speed']:.1f} KB/s, "
                  f"Data Rate: {formatted_data['data_transmission_rate']:.1f} KB/s, "
                  f"Freq: {formatted_data['uplink_frequency']:.1f} GHz, "
                  f"Signal: {formatted_data['server_signal_strength']} dBm, "
                  f"Latency: {formatted_data['network_latency']:.1f} ms, "
                  f"Quality: {formatted_data['connection_quality']}, "
                  f"Status: {formatted_data['status']}")
            communication_data_callback.last_log = time.time()
    except Exception as e:
        logging.error(f"Error in communication data callback: {e}")
        socketio.emit("communication_broadcast", {
            "wifi_speed": "0.0",
            "upload_speed": "0.0",
            "transmission_rate": "0.0",
            "uplink_frequency": "0.0",
            "downlink_frequency": "0.0",
            "server_signal_strength": 0,
            "connection_quality": "Error",
            "network_latency": "0.0",
            "status": "Error"
        })

@socketio.on("get_power_status")
def handle_get_power_status():
    try:
        if power_monitor:
            status = power_monitor.get_status()
            latest_data = power_monitor.get_latest_data()
            response = {
                "success": True,
                "status": status,
                "latest_data": latest_data
            }
        else:
            response = {
                "success": False,
                "error": "Power monitoring not available"
            }
        emit("power_status_response", response)
    except Exception as e:
        emit("power_status_response", {
            "success": False,
            "error": str(e)
        })
        logging.error(f"Error getting power status: {e}")

@socketio.on("power_data")
def handle_power_data(data):
    try:
        logging.debug(f"Received power data from client: {data}")
    except Exception as e:
        logging.error(f"Error handling power data: {e}")

# ===================== END OTHER LIVE DATA UPDATES SECTION =====================

if __name__ == "__main__":
    print("🚀 Server starting at http://0.0.0.0:5000")
    print("Background tasks will start after server initialization.")
    print("Press Ctrl+C to stop the server and clean up resources.")
    # Start background tasks with delay
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
            sensors.stop_sensors()  # If you have a stop_sensors function
            print("[INFO] Sensors stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop sensors: {e}")
        try:
            if power_monitor:
                power_monitor.stop_monitoring()
                print("[INFO] Power monitoring stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop power monitoring: {e}")
        print("[INFO] Server exited cleanly.")
        exit(0)
