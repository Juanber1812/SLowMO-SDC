# lidar.py

from smbus2 import SMBus
import time
import socketio
import threading
from datetime import datetime

SERVER_URL = "http://localhost:5000"
LIDAR_ADDR = 0x62
ACQ_COMMAND = 0x00
DISTANCE_HIGH = 0x0f
DISTANCE_LOW = 0x10
MEASURE = 0x04

sio = socketio.Client()

@sio.event
def connect():
    print("📡 LIDAR connected to server")
    if 'lidar_controller' in globals():
        lidar_controller.connected = True
        # Send status update immediately to show connected state in client
        lidar_controller._send_status_update()

@sio.event
def disconnect():
    print("🔌 LIDAR disconnected from server")
    if 'lidar_controller' in globals():
        lidar_controller.connected = False
        # Note: Can't send status update here since we're disconnected

@sio.on("lidar_update")
def on_lidar_update(_):
    """Handle request for lidar status update"""
    try:
        if 'lidar_controller' in globals():
            lidar_controller._send_status_update()
            print("[INFO] Lidar status update sent")
    except Exception as e:
        print(f"[ERROR] lidar_update handler: {e}")

def read_distance(bus):
    try:
        bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, MEASURE)
        time.sleep(0.01)
        high = bus.read_byte_data(LIDAR_ADDR, DISTANCE_HIGH)
        low = bus.read_byte_data(LIDAR_ADDR, DISTANCE_LOW)
        return (high << 8) + low
    except Exception as e:
        return None

class LidarController:
    def __init__(self):
        self.is_collecting = False
        self.collection_thread = None
        self.data_count = 0
        self.start_time = None
        self.last_status_time = time.time()
        self.connected = False
        
    def connect_to_server(self):
        """Connect to the SocketIO server"""
        if not self.connected:
            try:
                sio.connect(SERVER_URL)
                self.connected = True
            except Exception as e:
                print(f"❌ LIDAR connection failed: {e}")
                self.connected = False
        
    def start_collection(self):
        """Start LIDAR data collection"""
        if self.is_collecting:
            return  # Already running, no need to spam logs
            
        self.connect_to_server()
        if not self.connected:
            return
            
        self.is_collecting = True
        self.data_count = 0
        self.start_time = time.time()
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        
        # Send immediate status update to show we're now active
        self._send_status_update()
        
    def stop_collection(self):
        """Stop LIDAR data collection"""
        if not self.is_collecting:
            return  # Not running, no need to spam logs
            
        self.is_collecting = False
        if self.collection_thread:
            self.collection_thread.join(timeout=1.0)
        
        # Send status update to show we're now connected but not collecting
        self._send_status_update()
        
    def _collection_loop(self):
        """Main data collection loop"""
        try:
            with SMBus(1) as bus:
                while self.is_collecting:
                    # Read distance
                    distance = read_distance(bus)
                    if distance is not None:
                        sio.emit("lidar_data", {"distance_cm": distance})
                        self.data_count += 1
                    
                    # Send status update every second
                    current_time = time.time()
                    if current_time - self.last_status_time >= 1.0:
                        self._send_status_update()
                        self.last_status_time = current_time
                    

                    
        except Exception as e:
            print(f"❌ LIDAR collection error: {e}")
            self.is_collecting = False
            self.connected = False  # Assume disconnection on error
            
    def _send_status_update(self):
        """Send status update to server"""
        if not self.connected:
            return
            
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        collection_rate = self.data_count / elapsed_time if elapsed_time > 0 and self.start_time else 0
        
        # Determine lidar status based on connection and collection state
        if not self.connected:
            lidar_status = "disconnected"
        elif self.is_collecting:
            lidar_status = "active"
        else:
            lidar_status = "connected"
        
        # Determine overall status (OK if lidar is connected/active, Error if disconnected)
        status = "OK" if self.connected else "Error"
        
        status_data = {
            "collection_rate_hz": round(collection_rate, 2),
            "lidar_status": lidar_status,
            "status": status
        }
        
        try:
            sio.emit("lidar_info", status_data)
        except Exception as e:
            # Silently handle status update failures to avoid log spam
            pass

# Create global controller instance
lidar_controller = LidarController()

def start_lidar():
    """Legacy function for backward compatibility - just connects to server"""
    lidar_controller.connect_to_server()
