# lidar.py

from smbus2 import SMBus
import time
import socketio

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
        time.sleep(0.02)
        high = bus.read_byte_data(LIDAR_ADDR, DISTANCE_HIGH)
        low = bus.read_byte_data(LIDAR_ADDR, DISTANCE_LOW)
        return (high << 8) + low
    except Exception as e:
        print(f"[ERROR] LIDAR read: {e}")
        return None

def start_lidar():
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        print("❌ LIDAR connection failed:", e)
        return

    print("📡 LIDAR monitoring started.")
    with SMBus(1) as bus:
        while True:
            distance = read_distance(bus)
            if distance is not None:
                sio.emit("lidar_data", {"distance_cm": distance})
            time.sleep(0.05)  # Adjust as needed
