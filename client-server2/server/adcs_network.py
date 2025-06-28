#!/usr/bin/env python3
"""
ADCS Network Interface
Integrates the ADCS system with the existing Flask-SocketIO server
for remote control and monitoring via the PyQt client.
"""

import time
import json
from flask import request
from adcs_integrated import adcs, start_adcs_control, stop_adcs_control, set_target, tune_adcs, get_adcs_status, cleanup

class ADCSNetworkInterface:
    def __init__(self):
        self.last_status_update = 0
        self.status_update_interval = 0.5  # Send status updates every 500ms
        
    def handle_adcs_command(self, command_data):
        """
        Handle ADCS commands from network clients
        
        Expected command format:
        {
            "command": "start|stop|set_target|tune|get_status",
            "parameters": {...}
        }
        """
        try:
            command = command_data.get("command", "")
            params = command_data.get("parameters", {})
            
            if command == "start":
                yaw = params.get("yaw", 0.0)
                start_adcs_control(yaw)
                return {"status": "success", "message": f"ADCS started, target yaw: {yaw}°"}
                
            elif command == "stop":
                stop_adcs_control()
                return {"status": "success", "message": "ADCS stopped"}
                
            elif command == "set_target":
                yaw = params.get("yaw", 0.0)
                set_target(yaw)
                return {"status": "success", "message": f"Target set to yaw: {yaw}°"}
                
            elif command == "tune":
                kp = params.get("kp", 2.0)
                kd = params.get("kd", 0.5)
                deadband = params.get("deadband")
                tune_adcs(kp, kd, deadband)
                return {"status": "success", "message": f"Controller tuned: Kp={kp}, Kd={kd}"}
                
            elif command == "get_status":
                status = get_adcs_status()
                return {"status": "success", "data": status}
                
            elif command == "save_log":
                filename = params.get("filename")
                saved_file = adcs.save_log(filename)
                if saved_file:
                    return {"status": "success", "message": f"Log saved to {saved_file}"}
                else:
                    return {"status": "error", "message": "Failed to save log"}
                    
            else:
                return {"status": "error", "message": f"Unknown command: {command}"}
                
        except Exception as e:
            return {"status": "error", "message": f"Command execution error: {str(e)}"}
            
    def get_periodic_status(self):
        """Get status data for periodic updates to clients"""
        current_time = time.time()
        
        if current_time - self.last_status_update >= self.status_update_interval:
            self.last_status_update = current_time
            
            status = get_adcs_status()
            
            # Format for client display
            return {
                "type": "adcs_status",
                "data": {
                    "running": status["running"],
                    "target_yaw": round(status["target_yaw"], 1),
                    "current_yaw": round(status["current_yaw"], 1),
                    "yaw_error": round(status["yaw_error"], 1),
                    "accelerometer": {
                        "x": round(status["sensor_data"].get("ax", 0), 3),
                        "y": round(status["sensor_data"].get("ay", 0), 3),
                        "z": round(status["sensor_data"].get("az", 0), 3)
                    },
                    "gyroscope": {
                        "x": round(status["sensor_data"].get("gx", 0), 1),
                        "y": round(status["sensor_data"].get("gy", 0), 1),
                        "z": round(status["sensor_data"].get("gz", 0), 1)
                    },
                    "lux": round(status["sensor_data"].get("lux", 0), 1),
                    "controller": {
                        "kp": status["kp"],
                        "kd": status["kd"],
                        "deadband": status["deadband"]
                    },
                    "timestamp": status["sensor_data"].get("timestamp", current_time)
                }
            }
        return None

# Global interface instance
adcs_interface = ADCSNetworkInterface()

# Integration functions for server2.py
def setup_adcs_routes(app, socketio):
    """
    Add ADCS routes to the Flask-SocketIO server
    Call this function from server2.py to integrate ADCS control
    """
    
    @socketio.on('adcs_command')
    def handle_adcs_command(data):
        """Handle ADCS command from client"""
        print(f"[ADCS] Received command: {data}")
        response = adcs_interface.handle_adcs_command(data)
        socketio.emit('adcs_response', response)
        
    @app.route('/adcs/status', methods=['GET'])
    def adcs_status():
        """HTTP endpoint for ADCS status"""
        status = get_adcs_status()
        return json.dumps(status, indent=2)
        
    @app.route('/adcs/start', methods=['POST'])
    def adcs_start():
        """HTTP endpoint to start ADCS"""
        try:
            data = request.get_json() or {}
            yaw = data.get('yaw', 0.0)
            start_adcs_control(yaw)
            return {"status": "success", "message": "ADCS started"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
            
    @app.route('/adcs/stop', methods=['POST'])
    def adcs_stop():
        """HTTP endpoint to stop ADCS"""
        try:
            stop_adcs_control()
            return {"status": "success", "message": "ADCS stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

def start_adcs_status_broadcast(socketio):
    """
    Start broadcasting ADCS status updates to connected clients
    Call this from server2.py main loop or in a separate thread
    """
    import threading
    
    def broadcast_loop():
        while True:
            try:
                status_update = adcs_interface.get_periodic_status()
                if status_update:
                    socketio.emit('adcs_data', status_update)
                time.sleep(0.1)  # Check every 100ms, but only send every 500ms
            except Exception as e:
                print(f"[ADCS] Broadcast error: {e}")
                time.sleep(1)
    
    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast_thread.start()
    print("[ADCS] Status broadcast started")

# Cleanup function
def adcs_cleanup():
    """Call this when shutting down the server"""
    cleanup()

# Example integration with server2.py:
"""
In server2.py, add these imports:
from adcs_network import setup_adcs_routes, start_adcs_status_broadcast, adcs_cleanup

Then in the main server setup:
# After creating app and socketio
setup_adcs_routes(app, socketio)

# After starting the server
start_adcs_status_broadcast(socketio)

# In signal handler or cleanup
adcs_cleanup()
"""
