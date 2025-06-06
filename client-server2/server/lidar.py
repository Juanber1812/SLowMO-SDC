# lidar.py

from smbus2 import SMBus
import time
import socketio
import threading

SERVER_URL = "http://localhost:5000"
LIDAR_ADDR = 0x62
ACQ_COMMAND = 0x00
DISTANCE_HIGH = 0x0f
DISTANCE_LOW = 0x10
MEASURE = 0x04

# Global variables for thread control
lidar_thread = None
is_streaming = False
stop_event = threading.Event()

sio = socketio.Client()

@sio.event
def connect():
    print("📡 Connected to server from lidar.py")

@sio.event
def disconnect():
    print("🔌 LIDAR disconnected")

@sio.on('start_lidar')
def handle_start_lidar():
    """Handle start LIDAR command from server"""
    global lidar_thread, is_streaming
    
    if not is_streaming:
        print("🚀 Starting LIDAR streaming...")
        is_streaming = True
        stop_event.clear()
        
        # Start LIDAR reading thread
        lidar_thread = threading.Thread(target=lidar_worker, daemon=True)
        lidar_thread.start()
        
        # Send confirmation back to server
        sio.emit("lidar_status", {
            "status": "started",
            "streaming": True,
            "message": "LIDAR streaming started"
        })
        print("✅ LIDAR streaming started")
    else:
        print("⚠️ LIDAR already streaming")

@sio.on('stop_lidar')
def handle_stop_lidar():
    """Handle stop LIDAR command from server"""
    global is_streaming
    
    if is_streaming:
        print("🛑 Stopping LIDAR streaming...")
        is_streaming = False
        stop_event.set()
        
        # Send confirmation back to server
        sio.emit("lidar_status", {
            "status": "stopped",
            "streaming": False,
            "message": "LIDAR streaming stopped"
        })
        print("✅ LIDAR streaming stopped")
    else:
        print("⚠️ LIDAR already stopped")

@sio.on('get_lidar_status')
def handle_get_lidar_status():
    """Send current LIDAR status to server"""
    sio.emit("lidar_status", {
        "status": "streaming" if is_streaming else "idle",
        "streaming": is_streaming
    })

def read_distance(bus):
    """Read distance from LIDAR sensor"""
    try:
        bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, MEASURE)
        time.sleep(0.02)
        high = bus.read_byte_data(LIDAR_ADDR, DISTANCE_HIGH)
        low = bus.read_byte_data(LIDAR_ADDR, DISTANCE_LOW)
        return (high << 8) + low
    except Exception as e:
        print(f"[ERROR] LIDAR read: {e}")
        return None

def lidar_worker():
    """Main LIDAR worker thread function"""
    print("🔄 LIDAR worker thread started")
    
    try:
        with SMBus(1) as bus:
            while is_streaming and not stop_event.is_set():
                distance = read_distance(bus)
                if distance is not None:
                    print(f"[DEBUG] LIDAR distance: {distance} cm")
                    # Send data to server
                    sio.emit("lidar_data", {"distance_cm": distance})
                
                # Check for stop signal with timeout
                if stop_event.wait(timeout=0.05):  # 50ms delay between readings
                    break
                    
    except Exception as e:
        print(f"[ERROR] LIDAR worker thread: {e}")
    finally:
        print("🔄 LIDAR worker thread stopped")

def start_lidar_connection():
    """Initialize connection to server and wait for commands"""
    try:
        print("🔗 Connecting LIDAR to server...")
        sio.connect(SERVER_URL)
        print("📡 LIDAR connected to server, waiting for commands...")
        
        # Keep the connection alive
        try:
            sio.wait()
        except KeyboardInterrupt:
            print("\n🛑 LIDAR shutting down...")
            if is_streaming:
                handle_stop_lidar()
            
    except Exception as e:
        print(f"❌ LIDAR connection failed: {e}")
        return

def start_lidar():
    """Legacy function for backward compatibility"""
    start_lidar_connection()

if __name__ == "__main__":
    start_lidar_connection()
