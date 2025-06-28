#!/usr/bin/env python3
"""
MPU-6050 Live Data Logger
Displays live data for all 6 MPU values (accelerometer + gyroscope) in a single log
Supports both real hardware and simulation mode
"""

import time
import math
import random
import logging
import sys
from datetime import datetime
from typing import Tuple, Optional

# Try to import I2C library for real hardware
try:
    import smbus
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("⚠️  Hardware libraries not available. Running in simulation mode.")

class MPULogger:
    def __init__(self, simulation_mode=None, log_to_file=True, update_rate=10):
        """
        Initialize MPU Logger
        
        Args:
            simulation_mode: True for simulation, False for hardware, None for auto-detect
            log_to_file: Whether to log data to file
            update_rate: Updates per second (Hz)
        """
        self.simulation_mode = simulation_mode if simulation_mode is not None else not HARDWARE_AVAILABLE
        self.update_rate = update_rate
        self.update_interval = 1.0 / update_rate
        
        # MPU-6050 configuration
        self.MPU_ADDR = 0x68
        self.PWR_MGMT_1 = 0x6B
        self.ACCEL_XOUT_H = 0x3B
        self.GYRO_XOUT_H = 0x43
        
        # Initialize hardware if available
        if not self.simulation_mode and HARDWARE_AVAILABLE:
            try:
                self.bus = smbus.SMBus(1)  # I2C bus 1 on Raspberry Pi
                self.bus.write_byte_data(self.MPU_ADDR, self.PWR_MGMT_1, 0)  # Wake up MPU
                print("✅ MPU-6050 hardware initialized")
            except Exception as e:
                print(f"❌ Hardware initialization failed: {e}")
                print("🔄 Switching to simulation mode")
                self.simulation_mode = True
        
        # Set up logging
        if log_to_file:
            self.setup_logging()
        
        # Simulation variables
        self.sim_angle = 0.0
        self.sim_time_start = time.time()
        
        print(f"🚀 MPU Logger initialized in {'SIMULATION' if self.simulation_mode else 'HARDWARE'} mode")
        print(f"📊 Update rate: {update_rate} Hz")

    def setup_logging(self):
        """Set up file logging"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"mpu_log_{timestamp}.csv"
        
        # Create CSV logger
        self.file_logger = logging.getLogger('mpu_csv')
        self.file_logger.setLevel(logging.INFO)
        
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        self.file_logger.addHandler(file_handler)
        
        # Write CSV header
        header = "timestamp,ax,ay,az,gx,gy,gz,yaw_calc,gravity_mag"
        self.file_logger.info(header)
        print(f"📝 Logging to: {log_filename}")

    def read_mpu_hardware(self) -> Tuple[float, float, float, float, float, float]:
        """Read data from actual MPU-6050 hardware"""
        try:
            # Read accelerometer data
            accel_data = []
            for i in range(6):  # Read 6 bytes (3 axes * 2 bytes each)
                high = self.bus.read_byte_data(self.MPU_ADDR, self.ACCEL_XOUT_H + i)
                accel_data.append(high)
            
            # Convert to signed values and scale
            ax = self.bytes_to_int(accel_data[0], accel_data[1]) / 16384.0  # ±2g scale
            ay = self.bytes_to_int(accel_data[2], accel_data[3]) / 16384.0
            az = self.bytes_to_int(accel_data[4], accel_data[5]) / 16384.0
            
            # Read gyroscope data
            gyro_data = []
            for i in range(6):  # Read 6 bytes (3 axes * 2 bytes each)
                high = self.bus.read_byte_data(self.MPU_ADDR, self.GYRO_XOUT_H + i)
                gyro_data.append(high)
            
            # Convert to signed values and scale
            gx = self.bytes_to_int(gyro_data[0], gyro_data[1]) / 131.0  # ±250°/s scale
            gy = self.bytes_to_int(gyro_data[2], gyro_data[3]) / 131.0
            gz = self.bytes_to_int(gyro_data[4], gyro_data[5]) / 131.0
            
            return ax, ay, az, gx, gy, gz
        
        except Exception as e:
            print(f"❌ Hardware read error: {e}")
            return 0.0, 0.0, -1.0, 0.0, 0.0, 0.0  # Default values

    def bytes_to_int(self, high_byte, low_byte):
        """Convert two bytes to signed integer"""
        value = (high_byte << 8) + low_byte
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        return value

    def read_mpu_simulation(self) -> Tuple[float, float, float, float, float, float]:
        """Generate simulated MPU data for testing"""
        current_time = time.time()
        elapsed = current_time - self.sim_time_start
        
        # Simulate cube rotating at 15 degrees/second
        self.sim_angle = (elapsed * 15.0) % 360
        if self.sim_angle > 180:
            self.sim_angle -= 360
        
        angle_rad = math.radians(self.sim_angle)
        
        # Simulated accelerometer (hanging cube with slight motion)
        ax = 0.08 * math.sin(angle_rad) + random.uniform(-0.03, 0.03)
        ay = 0.08 * math.cos(angle_rad) + random.uniform(-0.03, 0.03)
        az = -0.98 + random.uniform(-0.08, 0.08)
        
        # Simulated gyroscope (rotation rates)
        gx = random.uniform(-3, 3)
        gy = random.uniform(-3, 3)
        gz = 15 + random.uniform(-8, 8)  # Main rotation around Z-axis
        
        return ax, ay, az, gx, gy, gz

    def calculate_yaw(self, ax: float, ay: float) -> float:
        """Calculate yaw angle from accelerometer data"""
        yaw_rad = math.atan2(ay, ax)
        yaw_deg = yaw_rad * 180.0 / math.pi
        return yaw_deg

    def calculate_gravity_magnitude(self, ax: float, ay: float, az: float) -> float:
        """Calculate total gravity magnitude"""
        return math.sqrt(ax*ax + ay*ay + az*az)

    def format_display_line(self, timestamp, ax, ay, az, gx, gy, gz, yaw, gravity_mag):
        """Format a single line for display"""
        return (f"{timestamp:6.1f} │"
                f"{ax:7.3f} {ay:7.3f} {az:7.3f} │"
                f"{gx:6.1f} {gy:6.1f} {gz:6.1f} │"
                f"{yaw:7.1f} │"
                f"{gravity_mag:6.3f}")

    def start_logging(self):
        """Start the live data logging"""
        print("\n" + "="*85)
        print("🔴 LIVE MPU-6050 DATA LOGGER")
        print("="*85)
        print("📊 All 6 MPU values displayed in real-time")
        print("⏹️  Press Ctrl+C to stop")
        print("-"*85)
        print("Time   │    Accelerometer (g)     │   Gyroscope (°/s)   │  Yaw   │ |G|")
        print("(sec)  │   X      Y      Z       │   X     Y     Z    │ (deg)  │ (g)")
        print("-"*85)
        
        start_time = time.time()
        sample_count = 0
        
        try:
            while True:
                loop_start = time.time()
                elapsed = loop_start - start_time
                
                # Read MPU data
                if self.simulation_mode:
                    ax, ay, az, gx, gy, gz = self.read_mpu_simulation()
                else:
                    ax, ay, az, gx, gy, gz = self.read_mpu_hardware()
                
                # Calculate derived values
                yaw = self.calculate_yaw(ax, ay)
                gravity_mag = self.calculate_gravity_magnitude(ax, ay, az)
                
                # Display data
                display_line = self.format_display_line(elapsed, ax, ay, az, gx, gy, gz, yaw, gravity_mag)
                print(display_line)
                
                # Log to file if enabled
                if hasattr(self, 'file_logger'):
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_line = f"{timestamp_str},{ax:.6f},{ay:.6f},{az:.6f},{gx:.3f},{gy:.3f},{gz:.3f},{yaw:.3f},{gravity_mag:.6f}"
                    self.file_logger.info(log_line)
                
                sample_count += 1
                
                # Periodic status updates
                if sample_count % (self.update_rate * 10) == 0:  # Every 10 seconds
                    print(f"\n📈 Sample #{sample_count} │ Runtime: {elapsed:.1f}s │ Rate: {sample_count/elapsed:.1f} Hz")
                    print(f"🎯 Current Yaw: {yaw:.1f}° │ Gravity: {gravity_mag:.3f}g")
                    if self.simulation_mode:
                        print(f"🎲 Simulation: Target angle {self.sim_angle:.1f}°")
                    print("-"*85)
                
                # Sleep to maintain update rate
                loop_duration = time.time() - loop_start
                sleep_time = max(0, self.update_interval - loop_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.stop_logging(elapsed, sample_count)

    def stop_logging(self, runtime, sample_count):
        """Clean up and display summary when stopping"""
        print(f"\n\n{'='*85}")
        print("🛑 LOGGING STOPPED")
        print("="*85)
        print(f"📊 SESSION SUMMARY:")
        print(f"   • Runtime: {runtime:.1f} seconds")
        print(f"   • Total samples: {sample_count}")
        print(f"   • Average rate: {sample_count/runtime:.1f} Hz")
        print(f"   • Mode: {'SIMULATION' if self.simulation_mode else 'HARDWARE'}")
        
        if hasattr(self, 'file_logger'):
            print(f"   • Data logged to CSV file")
        
        print("\n🔍 UNDERSTANDING THE DATA:")
        print("   • Accelerometer (g): Measures gravity + motion")
        print("     - For hanging cube: X,Y ≈ 0, Z ≈ -1")
        print("   • Gyroscope (°/s): Measures rotation rates")
        print("     - Positive values = rotation direction")
        print("   • Yaw (°): Calculated rotation around vertical axis")
        print("   • |G| (g): Total gravity magnitude (should ≈ 1.0)")
        print("="*85)

def main():
    """Main function to run the MPU logger"""
    print("🚀 MPU-6050 Live Data Logger")
    print("Choose your mode:")
    print("1. Auto-detect (hardware if available, simulation otherwise)")
    print("2. Force simulation mode")
    print("3. Force hardware mode")
    
    try:
        choice = input("Enter choice (1-3) [default: 1]: ").strip()
        if not choice:
            choice = "1"
        
        if choice == "1":
            simulation_mode = None  # Auto-detect
        elif choice == "2":
            simulation_mode = True
        elif choice == "3":
            simulation_mode = False
        else:
            print("Invalid choice, using auto-detect")
            simulation_mode = None
        
        # Configuration options
        print("\nConfiguration:")
        rate_input = input("Update rate in Hz [default: 10]: ").strip()
        update_rate = int(rate_input) if rate_input.isdigit() else 10
        
        log_input = input("Log to file? (y/n) [default: y]: ").strip().lower()
        log_to_file = log_input != 'n'
        
        # Create and start logger
        logger = MPULogger(
            simulation_mode=simulation_mode,
            log_to_file=log_to_file,
            update_rate=update_rate
        )
        
        logger.start_logging()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()