#!/usr/bin/env python3
import smbus2, time

BUS = 1
ADDR = 0x62

# LiDAR-Lite v4 registers
ACQ_CMD  = 0x00
ACQ_VAL  = 0x04
STATUS   = 0x01
DIST_LO  = 0x10
DIST_HI  = 0x11

def read_distance(bus):
    # 1) Trigger
    bus.write_byte_data(ADDR, ACQ_CMD, ACQ_VAL)
    # 2) Wait for bit0 of STATUS to go low
    while bus.read_byte_data(ADDR, STATUS) & 0x01:
        time.sleep(0.005)
    # 3) Read low/high
    lo = bus.read_byte_data(ADDR, DIST_LO)
    hi = bus.read_byte_data(ADDR, DIST_HI)
    return (hi << 8) | lo

def main():
    bus = smbus2.SMBus(BUS)
    try:
        while True:
            try:
                d = read_distance(bus)
                print(f"Distance: {d} cm")
            except OSError as e:
                print("I2C error:", e)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()

if __name__ == "__main__":
    main()
