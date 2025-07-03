#!/usr/bin/env python3
"""
LiDAR-Lite v4 I2C Test Script with TCA9548A I2C Multiplexer

This script initializes the Garmin LiDAR-Lite v4 over I2C (default address 0x62)
behind a TCA9548A I2C multiplexer (default address 0x70, channel 2) and continuously
reads distance measurements, printing them in centimeters.

Requirements:
  - python3
  - smbus2 (install via `pip install smbus2`)
  - I2C bus enabled on Raspberry Pi (use `raspi-config` to enable I2C)

Wiring:
  - TCA9548A SDA → Pi SDA (GPIO 2)
  - TCA9548A SCL → Pi SCL (GPIO 3)
  - LiDAR SDA → TCA9548A SDA channel 2 output
  - LiDAR SCL → TCA9548A SCL channel 2 output
  - Multiplexer VCC → 3.3V, GND → GND
  - LiDAR VCC → 3.3V, GND → GND

Usage:
  chmod +x lidar_test.py
  ./lidar_test.py
  or
  python3 lidar_test.py
"""
import smbus2
import time
import sys

# I2C configuration
I2C_BUS = 1            # Raspberry Pi I2C bus number
MUX_ADDR = 0x70        # TCA9548A multiplexer address
MUX_CHANNEL = 2        # Multiplexer channel where LiDAR is connected
LIDAR_ADDR = 0x62      # LiDAR-Lite v4 default I2C address

# LiDAR registers
ACQ_COMMAND   = 0x00   # Register to write to initiate measurement
ACQUIRE_VAL   = 0x04   # Value to trigger distance acquisition
DIST_HIGH_REG = 0x0f   # High byte of distance
DIST_LOW_REG  = 0x10   # Low byte of distance

# Delay after triggering measurement (in seconds)
MEASUREMENT_DELAY = 0.02


def select_mux_channel(bus, channel):
    """
    Select a channel on the TCA9548A multiplexer.
    """
    if not (0 <= channel <= 7):
        raise ValueError("Multiplexer channel must be between 0 and 7")
    bus.write_byte_data(MUX_ADDR, 0, 1 << channel)


def read_distance(bus):
    """
    Trigger a LiDAR measurement and read the result.
    Returns distance in centimeters (int).
    """
    # Trigger acquisition
    bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, ACQUIRE_VAL)
    time.sleep(MEASUREMENT_DELAY)
    # Read high and low bytes
    high = bus.read_byte_data(LIDAR_ADDR, DIST_HIGH_REG)
    low = bus.read_byte_data(LIDAR_ADDR, DIST_LOW_REG)
    return (high << 8) | low


def main():
    print("LiDAR-Lite v4 I2C Test with Multiplexer")
    print(f"I2C bus: {I2C_BUS}, MUX at 0x{MUX_ADDR:02X}, channel: {MUX_CHANNEL}")
    print(f"LiDAR at address 0x{LIDAR_ADDR:02X}")

    try:
        bus = smbus2.SMBus(I2C_BUS)
    except FileNotFoundError:
        print(f"Error: I2C bus {I2C_BUS} not found. Is I2C enabled?")
        sys.exit(1)

    try:
        select_mux_channel(bus, MUX_CHANNEL)
        print(f"Selected multiplexer channel {MUX_CHANNEL}")
    except Exception as e:
        print(f"Multiplexer select error: {e}")
        bus.close()
        sys.exit(1)

    try:
        while True:
            try:
                dist = read_distance(bus)
                print(f"Distance: {dist} cm")
            except Exception as e:
                print(f"Read error: {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting LiDAR test.")
    finally:
        bus.close()


if __name__ == '__main__':
    main()
