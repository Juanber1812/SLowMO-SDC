# lidar.py

import time
import socketio
import threading
from collections import deque
import statistics

try:
    from smbus2 import SMBus
    HAS_HARDWARE = True
except ImportError:
    print("⚠️  SMBus not available - running in simulation mode")
    HAS_HARDWARE = False
    
    # Mock SMBus for development/testing
    class MockSMBus:
        def __init__(self, bus_number):
            self.bus_number = bus_number
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
        def write_byte_data(self, addr, command, value):
            pass  # Simulated write
            
        def read_byte_data(self, addr, register):
            # Simulate random distance readings between 10-200 cm
            import random
            if register == DISTANCE_HIGH:
                return random.randint(0, 2)  # High byte
            elif register == DISTANCE_LOW:
                return random.randint(10, 255)  # Low byte
            return 0
    
    SMBus = MockSMBus

SERVER_URL = "http://localhost:5000"
LIDAR_ADDR = 0x62
ACQ_COMMAND = 0x00
DISTANCE_HIGH = 0x0f
DISTANCE_LOW = 0x10
MEASURE = 0x04

sio = socketio.Client()

class LidarController:
    def __init__(self):
        self.is_active = False
        self.is_connected = False
        self.collection_rate = 0.0  # Hz
        self.error_count = 0
        self.total_measurements = 0
        self.last_distance = None
        self.status = "Disconnected"
        self.recent_distances = deque(maxlen=100)  # Keep last 100 readings
        self.last_rate_check = time.time()
        self.rate_counter = 0
        self.bus = None
        
    def connect_to_server(self):
        """Connect to the main server"""
        try:
            if not sio.connected:
                sio.connect(SERVER_URL)
            self.is_connected = True
            self.status = "Connected - Idle"
            self.send_status_update()
        except Exception as e:
            print(f"❌ LIDAR server connection failed: {e}")
            self.is_connected = False
            self.status = f"Connection Error: {str(e)[:50]}"
            
    def start_collection(self):
        """Start LIDAR data collection"""
        if not self.is_connected:
            self.connect_to_server()
            
        self.is_active = True
        self.status = "Active - Collecting"
        self.error_count = 0
        self.total_measurements = 0
        self.recent_distances.clear()
        print("📡 LIDAR data collection started")
        self.send_status_update()
        
    def stop_collection(self):
        """Stop LIDAR data collection"""
        self.is_active = False
        self.status = "Connected - Idle" if self.is_connected else "Disconnected"
        print("� LIDAR data collection stopped")
        self.send_status_update()
        
    def read_distance(self):
        """Read distance from LIDAR sensor"""
        if not self.bus:
            return None
            
        try:
            self.bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, MEASURE)
            time.sleep(0.01)
            high = self.bus.read_byte_data(LIDAR_ADDR, DISTANCE_HIGH)
            low = self.bus.read_byte_data(LIDAR_ADDR, DISTANCE_LOW)
            distance = (high << 8) + low
            
            # Update statistics
            self.last_distance = distance
            self.recent_distances.append(distance)
            self.total_measurements += 1
            self.rate_counter += 1
            
            return distance
        except Exception as e:
            self.error_count += 1
            return None
            
    def calculate_collection_rate(self):
        """Calculate current data collection rate"""
        current_time = time.time()
        if current_time - self.last_rate_check >= 1.0:  # Update every second
            self.collection_rate = self.rate_counter / (current_time - self.last_rate_check)
            self.rate_counter = 0
            self.last_rate_check = current_time
            
    def get_statistics(self):
        """Get statistical information about recent measurements"""
        if not self.recent_distances:
            return None
            
        return {
            "min_distance": min(self.recent_distances),
            "max_distance": max(self.recent_distances),
            "avg_distance": statistics.mean(self.recent_distances),
            "median_distance": statistics.median(self.recent_distances)
        }
        
    def send_status_update(self):
        """Send comprehensive status update to server"""
        if not sio.connected:
            return
            
        stats = self.get_statistics()
        status_data = {
            "status": self.status,
            "is_active": self.is_active,
            "collection_rate_hz": round(self.collection_rate, 2),
            "total_measurements": self.total_measurements,
            "error_count": self.error_count,
            "last_distance_cm": self.last_distance,
            "statistics": stats,
            "timestamp": time.time()
        }
        
        sio.emit("lidar_status", status_data)
        
    def run_collection_loop(self):
        """Main collection loop that runs when active"""
        print("📡 LIDAR monitoring thread started")
        
        try:
            with SMBus(1) as bus:
                self.bus = bus
                self.connect_to_server()
                
                while True:
                    if self.is_active:
                        distance = self.read_distance()
                        if distance is not None:
                            # Send minimal data during collection
                            sio.emit("lidar_data", {"distance_cm": distance})
                            
                        # Calculate and send status updates periodically
                        self.calculate_collection_rate()
                        
                        # Send status update every 5 seconds during active collection
                        if self.total_measurements % (int(self.collection_rate * 5) or 50) == 0:
                            self.send_status_update()
                            
                        time.sleep(0.05)  # 20 Hz collection rate
                    else:
                        # When inactive, just send status updates occasionally
                        time.sleep(2.0)
                        if self.is_connected:
                            self.send_status_update()
                            
        except Exception as e:
            print(f"❌ LIDAR collection loop error: {e}")
            self.status = f"Hardware Error: {str(e)[:50]}"
            self.send_status_update()

# Global LIDAR controller instance
lidar_controller = LidarController()

@sio.event
def connect():
    print("📡 Connected to server from lidar.py")
    lidar_controller.is_connected = True
    lidar_controller.status = "Connected - Idle"
    lidar_controller.send_status_update()

@sio.event
def disconnect():
    print("🔌 LIDAR disconnected")
    lidar_controller.is_connected = False
    lidar_controller.status = "Disconnected"

@sio.on("start_lidar_collection")
def handle_start_collection():
    """Handle start collection command from server"""
    lidar_controller.start_collection()

@sio.on("stop_lidar_collection")
def handle_stop_collection():
    """Handle stop collection command from server"""
    lidar_controller.stop_collection()

def start_lidar():
    """Start the LIDAR monitoring system"""
    lidar_controller.run_collection_loop()
