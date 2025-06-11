from smbus2 import SMBus
import time

LIDAR_ADDR = 0x62
ACQ_COMMAND = 0x00
MEASURE = 0x04  # Try 0x03 if this doesn't work
DISTANCE_HIGH = 0x0f
DISTANCE_LOW = 0x10

def read_distance(bus):
    try:
        bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, MEASURE)
        time.sleep(0.02)
        high = bus.read_byte_data(LIDAR_ADDR, DISTANCE_HIGH)
        low = bus.read_byte_data(LIDAR_ADDR, DISTANCE_LOW)
        return (high << 8) + low
    except Exception as e:
        print("[ERROR] Reading LIDAR:", e)
        return None

with SMBus(1) as bus:
    print("Starting LIDAR test...\n")
    time.sleep(1)
    for i in range(20):
        dist = read_distance(bus)
        if dist is not None:
            print(f"Distance: {dist} cm")
        else:
            print("Failed to read distance.")
        time.sleep(0.2)
