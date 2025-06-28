#!/usr/bin/env python3
"""
MPU6050 Gyroscope and Accelerometer Data Reader
Reads data from MPU6050 sensor at I2C address 0x68
Displays live data with periodic logging to avoid spam
"""

import smbus2
import time
import struct
import math
from datetime import datetime
import sys

class MPU6050:
    def __init__(self, bus_number=1, device_address=0x68):
        """Initialize MPU6050 sensor"""
        self.bus = smbus2.SMBus(bus_number)
        self.device_address = device_address
        
        # MPU6050 Register addresses
        self.PWR_MGMT_1 = 0x6B
        self.SMPLRT_DIV = 0x19
        self.CONFIG = 0x1A
        self.GYRO_CONFIG = 0x1B
        self.ACCEL_CONFIG = 0x1C
        self.INT_ENABLE = 0x38
        
        # Data registers
        self.ACCEL_XOUT_H = 0x3B
        self.GYRO_XOUT_H = 0x43
        self.TEMP_OUT_H = 0x41
        
        # Initialize the sensor
        self.initialize_sensor()
        
    def initialize_sensor(self):
        """Initialize MPU6050 with proper configuration"""
        try:
            # Wake up the MPU6050 (it starts in sleep mode)
            self.bus.write_byte_data(self.device_address, self.PWR_MGMT_1, 0)
            
            # Set sample rate to 1000Hz
            self.bus.write_byte_data(self.device_address, self.SMPLRT_DIV, 7)
            
            # Set accelerometer configuration (+/- 2g)
            self.bus.write_byte_data(self.device_address, self.ACCEL_CONFIG, 0)
            
            # Set gyroscope configuration (+/- 250 deg/s)
            self.bus.write_byte_data(self.device_address, self.GYRO_CONFIG, 0)
            
            # Set filter bandwidth to 21Hz
            self.bus.write_byte_data(self.device_address, self.CONFIG, 0)
            
            print("MPU6050 initialized successfully!")
            time.sleep(0.1)  # Give sensor time to stabilize
            
        except Exception as e:
            print(f"Error initializing MPU6050: {e}")
            sys.exit(1)
    
    def read_raw_data(self, addr):
        """Read raw 16-bit data from sensor"""
        high = self.bus.read_byte_data(self.device_address, addr)
        low = self.bus.read_byte_data(self.device_address, addr + 1)
        
        # Combine high and low bytes
        value = (high << 8) + low
        
        # Convert to signed 16-bit
        if value >= 32768:
            value = value - 65536
            
        return value
    
    def read_accelerometer(self):
        """Read accelerometer data (x, y, z) in g"""
        acc_x = self.read_raw_data(self.ACCEL_XOUT_H)
        acc_y = self.read_raw_data(self.ACCEL_XOUT_H + 2)
        acc_z = self.read_raw_data(self.ACCEL_XOUT_H + 4)
        
        # Convert to g (16384 LSB/g for +/- 2g range)
        acc_x = acc_x / 16384.0
        acc_y = acc_y / 16384.0
        acc_z = acc_z / 16384.0
        
        return acc_x, acc_y, acc_z
    
    def read_gyroscope(self):
        """Read gyroscope data (x, y, z) in deg/s"""
        gyro_x = self.read_raw_data(self.GYRO_XOUT_H)
        gyro_y = self.read_raw_data(self.GYRO_XOUT_H + 2)
        gyro_z = self.read_raw_data(self.GYRO_XOUT_H + 4)
        
        # Convert to deg/s (131 LSB/deg/s for +/- 250 deg/s range)
        gyro_x = gyro_x / 131.0
        gyro_y = gyro_y / 131.0
        gyro_z = gyro_z / 131.0
        
        return gyro_x, gyro_y, gyro_z
    
    def read_temperature(self):
        """Read temperature in Celsius"""
        temp_raw = self.read_raw_data(self.TEMP_OUT_H)
        # Temperature in degrees C = (TEMP_OUT Register Value as a signed number)/340 + 36.53
        temperature = (temp_raw / 340.0) + 36.53
        return temperature
    
    def read_all_data(self):
        """Read all sensor data"""
        acc_x, acc_y, acc_z = self.read_accelerometer()
        gyro_x, gyro_y, gyro_z = self.read_gyroscope()
        temperature = self.read_temperature()
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'accel': {'x': acc_x, 'y': acc_y, 'z': acc_z},
            'gyro': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z},
            'temperature': temperature
        }

def main():
    """Main loop to read and display MPU6050 data"""
    print("Starting MPU6050 Data Reader...")
    print("Press Ctrl+C to exit")
    print("-" * 80)
    
    try:
        # Initialize sensor
        mpu = MPU6050()
        
        # Variables for controlled logging
        last_log_time = 0
        log_interval = 2.0  # Log every 2 seconds to avoid spam
        
        while True:
            # Read sensor data
            data = mpu.read_all_data()
            current_time = time.time()
            
            # Live display (overwrite same line)
            accel = data['accel']
            gyro = data['gyro']
            temp = data['temperature']
            
            # Create live display string
            live_display = (
                f"\rAccel: X={accel['x']:+6.2f}g Y={accel['y']:+6.2f}g Z={accel['z']:+6.2f}g | "
                f"Gyro: X={gyro['x']:+7.1f}°/s Y={gyro['y']:+7.1f}°/s Z={gyro['z']:+7.1f}°/s | "
                f"Temp: {temp:5.1f}°C"
            )
            
            # Update live display
            print(live_display, end='', flush=True)
            
            # Periodic logging (to avoid spam)
            if current_time - last_log_time >= log_interval:
                print()  # New line
                print(f"[{data['timestamp']}] "
                      f"Accel(g): X={accel['x']:+6.3f} Y={accel['y']:+6.3f} Z={accel['z']:+6.3f} | "
                      f"Gyro(°/s): X={gyro['x']:+7.2f} Y={gyro['y']:+7.2f} Z={gyro['z']:+7.2f} | "
                      f"Temp: {temp:5.1f}°C")
                last_log_time = current_time
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nExiting MPU6050 reader...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Cleanup complete.")

if __name__ == "__main__":
    main()