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

# Import temperature monitoring
try:
    from temperature import start_thermal_subprocess
    TEMPERATURE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Temperature monitoring not available: {e}")
    start_thermal_subprocess = None
    TEMPERATURE_AVAILABLE = False

# Import communication monitoring
try:
    from communication import CommunicationMonitor
    COMMUNICATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Communication monitoring not available: {e}")
    CommunicationMonitor = None
    COMMUNICATION_AVAILABLE = False

# Import ADCS controller
try:
    from ADCS_final2 import ADCSController
    ADCS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"ADCS controller not available: {e}")
    ADCSController = None
    ADCS_AVAILABLE = False

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Camera state is now managed entirely by camera.py via camera_info events
# No need for server-side state tracking

# Initialize power monitor
power_monitor = None
if POWER_AVAILABLE:
    power_monitor = PowerMonitor(update_interval=2.0)  # Will try to connect to real hardware

# Initialize temperature monitor
thermal_queue = None
if TEMPERATURE_AVAILABLE:
    thermal_queue = start_thermal_subprocess()

# Initialize communication monitor
communication_monitor = None
if COMMUNICATION_AVAILABLE:
    communication_monitor = CommunicationMonitor()

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
        # Note: Frame data no longer tracked for communication monitoring
        # as true channel throughput is now measured via dedicated tests
    except Exception as e:
        print(f"[ERROR] frame broadcast: {e}")

@socketio.on('start_camera')
def handle_start_camera():
    try:
        # Simply relay the command to camera.py
        emit('start_camera', {}, broadcast=True)
        print("[INFO] Start camera command relayed to camera.py")
    except Exception as e:
        print(f"[ERROR] start_camera: {e}")

@socketio.on('stop_camera')
def handle_stop_camera():
    try:
        # Simply relay the command to camera.py  
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


# --- CAMERA-ONLY PAYLOAD BROADCAST ---
@socketio.on("camera_info")
def on_camera_info(data):
    """Handle camera-only payload: status, fps, frame size"""
    try:
        # Camera.py is now the single source of truth for all camera state
        # We simply forward the information from camera.py to clients
        
        camera_status_from_info = data.get("status", "Error")
        camera_connected = camera_status_from_info == "OK"
        
        # Determine display status based on actual camera state from camera.py
        if not camera_connected:
            display_status = "Disconnected"
        elif data.get("fps", 0) > 0:  # If we're getting frames, we're streaming
            display_status = "Streaming"
        else:
            display_status = "Connected"  # Connected but not streaming
            
        payload_data = {
            "camera_status": display_status,
            "camera_connected": camera_connected,
            "camera_streaming": display_status == "Streaming",
            "fps": data.get("fps", 0),
            "frame_size": data.get("frame_size", 0),
            "status": camera_status_from_info  # Include the OK/Error status
        }
        emit("camera_payload_broadcast", payload_data, broadcast=True)
    except Exception as e:
        print("Camera info error:", e)

# --- LIDAR-ONLY PAYLOAD BROADCAST ---
@socketio.on("lidar_info")
def on_lidar_info(data):
    """Handle lidar-only payload: status and frequency"""
    try:
        # Lidar.py is now the single source of truth for all lidar state
        # We simply forward the information from lidar.py to clients
        
        lidar_status_from_info = data.get("status", "Error")
        lidar_connected = lidar_status_from_info == "OK"
        
        # Use the lidar_status directly from lidar.py
        display_status = data.get("lidar_status", "disconnected")
        lidar_collecting = display_status == "active"
        
        payload_data = {
            "lidar_status": display_status.title(),  # Convert to title case for display
            "lidar_connected": lidar_connected,
            "lidar_collecting": lidar_collecting,
            "collection_rate_hz": data.get("collection_rate_hz", 0),
            "status": lidar_status_from_info  # Include the OK/Error status
        }
        emit("lidar_payload_broadcast", payload_data, broadcast=True)
    except Exception as e:
        print("Lidar info error:", e)

@socketio.on('set_camera_idle')
def handle_set_camera_idle():
    try:
        # Simply relay the command to camera.py
        emit('set_camera_idle', {}, broadcast=True)
        print("[INFO] Set camera idle command relayed to camera.py")
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
        
        # Start ADCS data broadcasting
        if adcs_controller:
            start_adcs_broadcast()
            logging.info("ADCS controller initialized and broadcasting started")
        
        # Start thermal data broadcasting
        if TEMPERATURE_AVAILABLE or ADCS_AVAILABLE:  # Start if we have any temperature source
            start_thermal_broadcast()
            logging.info("Thermal data broadcasting started")
        
        # Do NOT start communication monitoring here; start on client connect
    # Start the delayed initialization in a separate thread
    threading.Thread(target=delayed_start, daemon=True).start()


@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")
    connected_clients.add(request.sid)
    
    # Request current status from camera and lidar subsystems
    emit('camera_update', {}, broadcast=True)
    emit('lidar_update', {}, broadcast=True)
    print("[INFO] Status update requests sent to camera and lidar subsystems")
    
    # Start communication monitoring if not already running
    if communication_monitor and not communication_monitor.is_monitoring:
        communication_monitor.set_update_callback(communication_data_callback)
        communication_monitor.set_throughput_test_callback(throughput_test_callback)
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
        
        if not adcs_controller:
            print("[ERROR] ADCS controller not available")
            emit("adcs_command_ack", {"status": "ERROR", "message": "ADCS controller not available"}, broadcast=True)
            return
        
        # Extract command parameters
        mode = data.get("mode", "Unknown")
        command = data.get("command", "unknown")
        value = data.get("value")
        
        # Use the new ADCS controller command handler
        result = adcs_controller.handle_adcs_command(mode, command, value)
        
        # Send response back to client
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

@socketio.on("sensor_data")
def handle_sensor_data(data):
    global latest_pi_temp
    try:
        # Enhanced sensor data now includes memory usage, uptime, and smart status
        # Format: {
        #   "temperature": 45.2,
        #   "cpu_percent": 25.4,
        #   "memory": {"percent": 68.5, "used_gb": 2.74, "total_gb": 4.0, "available_gb": 1.26},
        #   "uptime": "2h 34m 12s",
        #   "status": "Moderate Load"
        # }
        
        # Store Pi temperature for thermal broadcast
        latest_pi_temp = data.get("temperature")
        
        # Prepare enhanced sensor data for broadcast
        memory_info = data.get("memory", {})
        memory_percent = memory_info.get("percent") if memory_info else None
        
        enhanced_data = {
            "temperature": data.get("temperature"),
            "cpu_percent": data.get("cpu_percent"),
            "memory_percent": memory_percent,  # Only memory percentage
            "uptime": data.get("uptime"),
            "status": data.get("status")   # Smart system status
        }
        
        emit("sensor_broadcast", enhanced_data, broadcast=True)
        
        # Log sensor data periodically (every 60 seconds)
        if not hasattr(handle_sensor_data, 'last_log') or time.time() - handle_sensor_data.last_log > 60:
            temp = enhanced_data.get("temperature", "N/A")
            cpu = enhanced_data.get("cpu_percent", "N/A")
            memory_percent = enhanced_data.get("memory_percent", "N/A")
            uptime = enhanced_data.get("uptime", "N/A")
            status = enhanced_data.get("status", "N/A")
            
            handle_sensor_data.last_log = time.time()
            
    except Exception as e:
        print(f"[ERROR] sensor_data: {e}")
        # Send basic data on error to maintain connectivity
        emit("sensor_broadcast", {
            "temperature": data.get("temperature", 0),
            "cpu_percent": data.get("cpu_percent", 0),
            "memory_percent": None,
            "uptime": "Error",
            "status": "Unknown"
        }, broadcast=True)

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
        if power_data.get('status') in ['Disconnected', 'Error - Disconnected', 'Error']:
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
            # Map power.py status to client-friendly status
            status_mapping = {
                "OK": "Nominal",
                "Battery Low": "Battery Low", 
                "Battery Critical": "Battery Critical",
                "High Current": "High Current",
                "Current Critical": "Current Critical", 
                "High Power": "High Power",
                "High Temperature": "High Temperature",
                "Overheating": "Overheating",
                "Operational": "Nominal"  # Legacy fallback
            }
            
            client_status = status_mapping.get(power_data['status'], power_data['status'])
            
            formatted_data = {
                "current": f"{power_data['current_ma'] / 1000:.3f}",
                "voltage": f"{power_data['voltage_v']:.1f}",
                "power": f"{power_data['power_mw'] / 1000:.2f}",
                "energy": f"{power_data['energy_j'] / 3600:.2f}",
                "temperature": f"{power_data['temperature_c']:.1f}",
                "battery_percentage": power_data['battery_percentage'],
                "status": client_status
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
    """Handle communication data updates and broadcast to clients"""
    try:
        # Format data to match the simplified structure (no WiFi speeds)
        formatted_data = {
            "downlink_frequency": comm_data.get('downlink_frequency', 0.0),
            "data_transmission_rate": comm_data.get('data_transmission_rate', 0.0),
            "server_signal_strength": comm_data.get('server_signal_strength', 0),
            "latency": comm_data.get('latency', 0.0),
            "status": comm_data.get('status', 'Disconnected')
        }
        
        socketio.emit("communication_broadcast", formatted_data)
        
        # Log communication status periodically (every 30 seconds)
        if not hasattr(communication_data_callback, 'last_log') or time.time() - communication_data_callback.last_log > 30:
            communication_data_callback.last_log = time.time()
            
    except Exception as e:
        logging.error(f"Error in communication data callback: {e}")
        # Send error state to clients
        socketio.emit("communication_broadcast", {
            "downlink_frequency": 0.0,
            "data_transmission_rate": 0.0,
            "server_signal_strength": 0,
            "latency": 0.0,
            "status": "Error"
        })

def throughput_test_callback(event_type, data):
    """Handle throughput test requests from communication monitor"""
    try:
        if event_type == 'throughput_test':
            # Send throughput test to all connected clients
            socketio.emit('throughput_test', data)
            logging.info(f"Throughput test initiated: {data['size']} bytes")
    except Exception as e:
        logging.error(f"Error in throughput test callback: {e}")

def adcs_data_broadcast():
    """Broadcast ADCS data at 20Hz"""
    global latest_payload_temp
    
    if not adcs_controller:
        return
    
    try:
        adcs_data = adcs_controller.get_adcs_data_for_server()
        
        # Extract payload temperature from ADCS data
        temp_str = adcs_data.get('temperature', '0.0°C')
        try:
            # Remove the °C suffix and convert to float
            latest_payload_temp = float(temp_str.replace('°C', ''))
        except:
            latest_payload_temp = None
        
        socketio.emit("adcs_broadcast", adcs_data)
        
        # Log ADCS data periodically (every 10 seconds)
        if not hasattr(adcs_data_broadcast, 'last_log') or time.time() - adcs_data_broadcast.last_log > 10:
            yaw = adcs_data.get('angle_z', '0.0')
            roll = adcs_data.get('angle_y', '0.0') 
            pitch = adcs_data.get('angle_x', '0.0')
            temp = adcs_data.get('temperature', '0.0°C')
            status = adcs_data.get('status', 'Unknown')
            
            adcs_data_broadcast.last_log = time.time()
            
    except Exception as e:
        logging.error(f"Error in ADCS data broadcast: {e}")
        # Send error state to clients
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
    """Start ADCS data broadcasting at 20Hz"""
    if not adcs_controller:
        return
    
    def adcs_broadcast_loop():
        while True:
            try:
                adcs_data_broadcast()
                time.sleep(0.05)  # 20Hz = 50ms interval
            except Exception as e:
                logging.error(f"Error in ADCS broadcast loop: {e}")
                time.sleep(1)  # Wait 1 second on error before retrying
    
    threading.Thread(target=adcs_broadcast_loop, daemon=True).start()
    logging.info("ADCS data broadcasting started at 20Hz")

# Global variables to store latest temperature data
latest_battery_temp = None
latest_pi_temp = None
latest_payload_temp = None

def determine_thermal_status(battery_temp, pi_temp, payload_temp):
    """Determine overall thermal status based on temperature thresholds"""
    statuses = []
    
    # Battery temperature thresholds (°C)
    if battery_temp is not None:
        if battery_temp >= 60:
            statuses.append("Battery Critical")
        elif battery_temp >= 50:
            statuses.append("Battery Hot")
        elif battery_temp >= 40:
            statuses.append("Battery Warm")
    
    # Pi temperature thresholds (°C)
    if pi_temp is not None:
        if pi_temp >= 80:
            statuses.append("Pi Critical")
        elif pi_temp >= 70:
            statuses.append("Pi Hot")
        elif pi_temp >= 60:
            statuses.append("Pi Warm")
    
    # Payload/ADCS temperature thresholds (°C)
    if payload_temp is not None:
        if payload_temp >= 70:
            statuses.append("Payload Critical")
        elif payload_temp >= 60:
            statuses.append("Payload Hot")
        elif payload_temp >= 50:
            statuses.append("Payload Warm")
    
    # Determine overall status
    if any("Critical" in status for status in statuses):
        return "Critical"
    elif any("Hot" in status for status in statuses):
        return "Hot"
    elif any("Warm" in status for status in statuses):
        return "Warm"
    else:
        return "Nominal"

def thermal_data_broadcast():
    """Broadcast thermal data combining all temperature sources"""
    global latest_battery_temp, latest_pi_temp, latest_payload_temp
    
    try:
        # Get battery temperature from thermal queue
        if thermal_queue and not thermal_queue.empty():
            try:
                while not thermal_queue.empty():  # Get the most recent reading
                    thermal_data = thermal_queue.get_nowait()
                    latest_battery_temp = thermal_data.get('battery_temp')
            except:
                pass  # Queue was empty
        
        # Get Pi temperature from sensor data (stored globally when sensor_data is received)
        # We'll update this in the sensor_data handler
        
        # Get payload temperature from ADCS data (stored globally when ADCS data is received)
        # We'll update this in the ADCS data handler
        
        # Determine overall status
        status = determine_thermal_status(latest_battery_temp, latest_pi_temp, latest_payload_temp)
        
        # Prepare thermal broadcast data
        thermal_data = {
            "battery_temp": f"{latest_battery_temp:.1f}" if latest_battery_temp is not None else "N/A",
            "pi_temp": f"{latest_pi_temp:.1f}" if latest_pi_temp is not None else "N/A",
            "payload_temp": f"{latest_payload_temp:.1f}" if latest_payload_temp is not None else "N/A",
            "status": status
        }
        
        socketio.emit("thermal_broadcast", thermal_data)
        
        # Log thermal data periodically (every 30 seconds)
        if not hasattr(thermal_data_broadcast, 'last_log') or time.time() - thermal_data_broadcast.last_log > 30:
            thermal_data_broadcast.last_log = time.time()
            logging.info(f"Thermal broadcast: Battery={thermal_data['battery_temp']}°C, Pi={thermal_data['pi_temp']}°C, Payload={thermal_data['payload_temp']}°C, Status={status}")
            
    except Exception as e:
        logging.error(f"Error in thermal data broadcast: {e}")
        # Send error state to clients
        socketio.emit("thermal_broadcast", {
            "battery_temp": "Error",
            "pi_temp": "Error", 
            "payload_temp": "Error",
            "status": "Error"
        })

def start_thermal_broadcast():
    """Start thermal data broadcasting at 2Hz"""
    def thermal_broadcast_loop():
        while True:
            try:
                thermal_data_broadcast()
                time.sleep(0.5)  # 2Hz = 500ms interval
            except Exception as e:
                logging.error(f"Error in thermal broadcast loop: {e}")
                time.sleep(1)  # Wait 1 second on error before retrying
    
    threading.Thread(target=thermal_broadcast_loop, daemon=True).start()
    logging.info("Thermal data broadcasting started at 2Hz")

@socketio.on('latency_response')
def handle_latency_response(data):
    """Handle latency measurement response from client"""
    try:
        if communication_monitor:
            client_receive_time = data.get('client_receive_time', 0.0)
            communication_monitor.handle_latency_response(client_receive_time)
            logging.info(f"Latency measurement received")
    except Exception as e:
        logging.error(f"Error handling latency response: {e}")

@socketio.on('throughput_response')
def handle_throughput_response(data):
    """Handle throughput test response from client"""
    try:
        if communication_monitor:
            response_data = data.get('response_data', b'')
            response_size = data.get('size', 0)
            communication_monitor.handle_throughput_response(response_data, response_size)
            logging.info(f"Throughput response received: {response_size} bytes")
    except Exception as e:
        logging.error(f"Error handling throughput response: {e}")

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

@socketio.on("get_thermal_status")
def handle_get_thermal_status():
    """Handle request for current thermal status"""
    try:
        # Force an immediate thermal broadcast
        thermal_data_broadcast()
        emit("thermal_status_response", {
            "success": True,
            "message": "Thermal status updated"
        })
    except Exception as e:
        emit("thermal_status_response", {
            "success": False,
            "error": str(e)
        })
        logging.error(f"Error getting thermal status: {e}")

@socketio.on("power_data")
def handle_power_data(data):
    try:
        logging.debug(f"Received power data from client: {data}")
    except Exception as e:
        logging.error(f"Error handling power data: {e}")

# ===================== END OTHER LIVE DATA UPDATES SECTION =====================

@socketio.on('request_camera_update')
def handle_request_camera_update():
    """Manual request for camera status update"""
    try:
        emit('camera_update', {}, broadcast=True)
        print("[INFO] Camera status update requested manually")
    except Exception as e:
        print(f"[ERROR] request_camera_update: {e}")

@socketio.on('request_lidar_update')
def handle_request_lidar_update():
    """Manual request for lidar status update"""
    try:
        emit('lidar_update', {}, broadcast=True)
        print("[INFO] Lidar status update requested manually")
    except Exception as e:
        print(f"[ERROR] request_lidar_update: {e}")

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
        try:
            if adcs_controller:
                adcs_controller.shutdown()
                print("[INFO] ADCS controller stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop ADCS controller: {e}")
        print("[INFO] Server exited cleanly.")
        exit(0)
