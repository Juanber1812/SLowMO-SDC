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
    print("📡 Connected to server from lidar.py")

@sio.event
def disconnect():
    print("🔌 LIDAR disconnected")

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
        self.error_count = 0
        self.start_time = None
        self.last_status_time = time.time()
        self.connected = False
        
    def connect_to_server(self):
        """Connect to the SocketIO server"""
        if not self.connected:
            try:
                sio.connect(SERVER_URL)
                self.connected = True
                print("📡 LIDAR connected to server")
            except Exception as e:
                print(f"❌ LIDAR connection failed: {e}")
                self.connected = False
        
    def start_collection(self):
        """Start LIDAR data collection"""
        if self.is_collecting:
            print("⚠️ LIDAR collection already running")
            return
            
        self.connect_to_server()
        if not self.connected:
            return
            
        self.is_collecting = True
        self.data_count = 0
        self.error_count = 0
        self.start_time = time.time()
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        print("� LIDAR collection started")
        
    def stop_collection(self):
        """Stop LIDAR data collection"""
        if not self.is_collecting:
            print("⚠️ LIDAR collection not running")
            return
            
        self.is_collecting = False
        if self.collection_thread:
            self.collection_thread.join(timeout=1.0)
        print("🔴 LIDAR collection stopped")
        
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
                    else:
                        self.error_count += 1
                    
                    # Send status update every 5 seconds
                    current_time = time.time()
                    if current_time - self.last_status_time >= 5.0:
                        self._send_status_update()
                        self.last_status_time = current_time
                    
                    time.sleep(0.05)  # 20 Hz collection rate
                    
        except Exception as e:
            print(f"❌ LIDAR collection error: {e}")
            self.error_count += 1
            self.is_collecting = False
            
    def _send_status_update(self):
        """Send status update to server"""
        if not self.connected:
            return
            
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        collection_rate = self.data_count / elapsed_time if elapsed_time > 0 else 0
        
        status_data = {
            "status": "collecting" if self.is_collecting else "stopped",
            "is_collecting": self.is_collecting,
            "is_active": self.is_collecting,  # For compatibility with client
            "collection_rate_hz": round(collection_rate, 2),
            "data_count": self.data_count,
            "error_count": self.error_count,
            "uptime_seconds": round(elapsed_time, 1),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        try:
            sio.emit("lidar_status", status_data)
        except Exception as e:
            print(f"❌ Failed to send LIDAR status: {e}")

# Create global controller instance
lidar_controller = LidarController()

def start_lidar():
    """Legacy function for backward compatibility - just connects to server"""
    lidar_controller.connect_to_server()
