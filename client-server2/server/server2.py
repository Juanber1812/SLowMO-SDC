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

def start_background_tasks():
    """Start background tasks with a delay to ensure server is ready"""
    def delayed_start():
        time.sleep(2)  # Give the server time to start
        print("\n[INFO] Starting background tasks...")
        threading.Thread(target=camera.start_stream, daemon=True).start()
        threading.Thread(target=sensors.start_sensors, daemon=True).start()
        threading.Thread(target=lidar.start_lidar, daemon=True).start()
        # Start periodic payload status updates
        threading.Thread(target=periodic_payload_status_updates, daemon=True).start()
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

    # Tachometer task
#    from tachometer import run_tachometer
#
#    # helper that prints & pushes via SocketIO
#    def report_rpm(rpm):
#        print(f"[TACHO] RPM: {rpm:.1f}")
#        socketio.emit("tachometer_data", {"rpm": rpm})
#
#    # launch the tachometer loop in its own thread
#    threading.Thread(
#        target=lambda: run_tachometer(report_rpm),
#        daemon=True
#    ).start()

def periodic_payload_status_updates():
    """Send payload status updates every 5 seconds"""
    import time
    while True:
        try:
            time.sleep(5)
            send_payload_status_update()
        except Exception as e:
            print(f"[ERROR] periodic_payload_status_updates: {e}")
            time.sleep(5)



@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")
    connected_clients.add(request.sid)
    # Send initial camera and LIDAR status to newly connected client
    socketio.emit('camera_status', {'status': camera_state}, room=request.sid)
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
        socketio.emit('camera_status', {'status': camera_state})
        send_payload_status_update()
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")


@socketio.on('stop_camera')
def handle_stop_camera():
    global camera_state
    try:
        emit('stop_camera', {}, broadcast=True)
        camera_state = "Idle"
        socketio.emit('camera_status', {'status': camera_state})
        send_payload_status_update()
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
        send_payload_status_update()
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
    """Handle LIDAR distance data and broadcast to clients"""
    try:
        # Only broadcast if we have valid data
        if "distance_cm" in data and data["distance_cm"] is not None:
            emit("lidar_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] lidar_data: {e}")


@socketio.on("payload_data")
def handle_payload_data(data):
    try:
        emit("payload_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] payload_data: {e}")


@socketio.on("tachometer_data")
def handle_tachometer_data(data):
    try:
        emit("tachometer_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] tachometer_data: {e}")


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

@socketio.on("start_lidar")
def handle_start_lidar():
    """Handle client request to start LIDAR data collection"""
    try:
        # Direct function call to LIDAR controller instead of socketio
        lidar.lidar_controller.start_collection()
        print("🟢 LIDAR collection start requested")
        emit("lidar_command_response", {"success": True, "message": "LIDAR collection started"})
        send_payload_status_update()
    except Exception as e:
        print(f"[ERROR] start_lidar: {e}")
        emit("lidar_command_response", {"success": False, "message": str(e)})

@socketio.on("stop_lidar")
def handle_stop_lidar():
    """Handle client request to stop LIDAR data collection"""
    try:
        # Direct function call to LIDAR controller instead of socketio
        lidar.lidar_controller.stop_collection()
        print("🔴 LIDAR collection stop requested")
        emit("lidar_command_response", {"success": True, "message": "LIDAR collection stopped"})
        send_payload_status_update()
    except Exception as e:
        print(f"[ERROR] stop_lidar: {e}")
        emit("lidar_command_response", {"success": False, "message": str(e)})

@socketio.on("lidar_status")
def handle_lidar_status(data):
    """Handle comprehensive LIDAR status updates and broadcast to clients"""
    try:
        # Broadcast enhanced status to all clients
        emit("lidar_status_broadcast", data, broadcast=True)
    except Exception as e:
        print(f"[ERROR] lidar_status: {e}")

def set_camera_state(new_state):
    global camera_state
    camera_state = new_state
    socketio.emit('camera_status', {'status': camera_state})
    # Also send payload status update
    send_payload_status_update()

def send_payload_status_update():
    """Send comprehensive payload subsystem status update"""
    try:
        # Get LIDAR status
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
        
        # Get camera status
        camera_connected = True  # Assume connected if server is running
        camera_streaming = camera_state == "Streaming"
        
        payload_data = {
            "camera_status": camera_state,
            "camera_connected": camera_connected,
            "camera_streaming": camera_streaming,
            "lidar_status": lidar_status, 
            "lidar_connected": lidar_status != "Disconnected",
            "lidar_collecting": lidar_collecting,
            "overall_status": "OK" if camera_connected else "ERROR"
        }
        
        socketio.emit('payload_broadcast', payload_data)
        
    except Exception as e:
        print(f"[ERROR] send_payload_status_update: {e}")

def power_data_callback(power_data):
    """Callback function to handle power data updates and broadcast to clients"""
    try:
        # Check if power monitor is disconnected
        if power_data.get('status') in ['Disconnected', 'Error - Disconnected']:
            # Send disconnected status with no data values
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
            # Format data for client consumption (matching expected format)
            formatted_data = {
                "current": f"{power_data['current_ma'] / 1000:.3f}",  # Convert mA to A 
                "voltage": f"{power_data['voltage_v']:.1f}",
                "power": f"{power_data['power_mw'] / 1000:.2f}",  # Convert mW to W
                "energy": f"{power_data['energy_j'] / 3600:.2f}",  # Convert J to Wh
                "temperature": f"{power_data['temperature_c']:.1f}",
                "battery_percentage": power_data['battery_percentage'],
                "status": "Nominal" if power_data['status'] == "Operational" else power_data['status']
            }
        
        # Broadcast to all connected clients
        socketio.emit("power_broadcast", formatted_data)
        
        # Debug logging (reduced frequency)
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
    """Callback function to handle communication data updates and broadcast to clients"""
    try:
        # Send the raw communication data to clients (they will format it)
        formatted_data = {
            "wifi_download_speed": comm_data.get('wifi_download_speed', 0.0),  # Mbps
            "wifi_upload_speed": comm_data.get('wifi_upload_speed', 0.0),  # Mbps
            "data_upload_speed": comm_data.get('data_upload_speed', 0.0),  # KB/s
            "data_transmission_rate": comm_data.get('data_transmission_rate', 0.0),  # KB/s
            "uplink_frequency": comm_data.get('uplink_frequency', 0.0),  # GHz
            "downlink_frequency": comm_data.get('downlink_frequency', 0.0),  # GHz
            "server_signal_strength": comm_data.get('server_signal_strength', 0),  # dBm
            "connection_quality": comm_data.get('connection_quality', 'Unknown'),
            "network_latency": comm_data.get('network_latency', 0.0),  # ms
            "status": comm_data.get('status', 'Disconnected')
        }
        
        # Broadcast to all connected clients
        socketio.emit("communication_broadcast", formatted_data)
        
        # Log periodically (every 30 seconds)
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
        # Send error state
        socketio.emit("communication_broadcast", {
            "wifi_speed": "0.0",
            "upload_speed": "0.0",
            "transmission_rate": "0.0",
            "uplink_frequency": "0.0",
            "downlink_frequency": "0.0",
            "server_signal_strength": 0,
            "client_signal_strength": 0,
            "connection_quality": "Error",
            "network_latency": "0.0",
            "packet_loss": "0.0",
            "status": "Error"
        })

# Power monitoring socket events
@socketio.on("get_power_status")
def handle_get_power_status():
    """Get current power monitoring status"""
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
    """Handle power data from client (if needed)"""
    try:
        # Currently not used, but could be for manual power data input
        # or for testing purposes
        logging.debug(f"Received power data from client: {data}")
    except Exception as e:
        logging.error(f"Error handling power data: {e}")

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

        # Stop power monitoring
        try:
            if power_monitor:
                power_monitor.stop_monitoring()
                print("[INFO] Power monitoring stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop power monitoring: {e}")

        print("[INFO] Server exited cleanly.")
        exit(0)
