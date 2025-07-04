# server3.py

from gevent import monkey; monkey.patch_all()
from flask import Flask, request

from flask_socketio import SocketIO, emit
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
    logging.info(f"Client connected.")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[INFO] Client disconnected: {request.sid}")
    logging.info(f"Client disconnected.")



def start_background_tasks():
    def delayed_start():
        time.sleep(2)
        print("\n[INFO] Starting background tasks...")
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
            if adcs_controller:
                adcs_controller.shutdown()
                print("[INFO] ADCS controller stopped.")
        except Exception as e:
            print(f"[WARN] Could not stop ADCS controller: {e}")
        print("[INFO] Server exited cleanly.")
        exit(0)
