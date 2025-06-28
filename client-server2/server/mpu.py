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
import json
import numpy as np
from datetime import datetime
from typing import Tuple, Optional, Dict

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
        
        # Calibration data
        self.gyro_bias = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.accel_bias = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.is_calibrated = False
        self.calibration_file = "mpu_calibration.json"
        
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
        
        # Load existing calibration if available
        self.load_calibration()
        
        # Set up logging
        if log_to_file:
            self.setup_logging()
        
        # Simulation variables
        self.sim_angle = 0.0
        self.sim_time_start = time.time()
        
        print(f"🚀 MPU Logger initialized in {'SIMULATION' if self.simulation_mode else 'HARDWARE'} mode")
        print(f"📊 Update rate: {update_rate} Hz")
        print(f"🎯 Calibration: {'LOADED' if self.is_calibrated else 'NOT CALIBRATED'}")

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
        header = "timestamp,ax,ay,az,gx,gy,gz,ax_cal,ay_cal,az_cal,gx_cal,gy_cal,gz_cal,yaw_calc,gravity_mag"
        self.file_logger.info(header)
        print(f"📝 Logging to: {log_filename}")

    def load_calibration(self):
        """Load calibration data from file"""
        try:
            with open(self.calibration_file, 'r') as f:
                cal_data = json.load(f)
                self.gyro_bias = cal_data.get('gyro_bias', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                self.accel_bias = cal_data.get('accel_bias', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                self.is_calibrated = True
                print(f"📁 Calibration loaded from {self.calibration_file}")
                print(f"   Gyro bias: X={self.gyro_bias['x']:.3f}, Y={self.gyro_bias['y']:.3f}, Z={self.gyro_bias['z']:.3f}")
                print(f"   Accel bias: X={self.accel_bias['x']:.3f}, Y={self.accel_bias['y']:.3f}, Z={self.accel_bias['z']:.3f}")
        except FileNotFoundError:
            print(f"⚠️  No calibration file found ({self.calibration_file})")
        except Exception as e:
            print(f"❌ Error loading calibration: {e}")

    def save_calibration(self):
        """Save calibration data to file"""
        try:
            cal_data = {
                'gyro_bias': self.gyro_bias,
                'accel_bias': self.accel_bias,
                'calibration_date': datetime.now().isoformat(),
                'notes': 'Calibration performed with MPU stationary'
            }
            with open(self.calibration_file, 'w') as f:
                json.dump(cal_data, f, indent=2)
            print(f"💾 Calibration saved to {self.calibration_file}")
        except Exception as e:
            print(f"❌ Error saving calibration: {e}")

    def perform_calibration(self, duration_seconds=30, sample_rate=50):
        """
        Perform calibration by collecting samples while MPU is stationary
        
        Args:
            duration_seconds: How long to collect calibration data
            sample_rate: Samples per second during calibration
        """
        print("\n" + "="*70)
        print("🎯 MPU CALIBRATION PROCEDURE")
        print("="*70)
        print("📋 INSTRUCTIONS:")
        print("   1. Place the MPU-6050 on a FLAT, STABLE surface")
        print("   2. Ensure the device is COMPLETELY STILL")
        print("   3. Do NOT touch or move the device during calibration")
        print("   4. Calibration will take", duration_seconds, "seconds")
        print("-"*70)
        
        input("Press ENTER when ready to start calibration...")
        
        print(f"🔄 Collecting {duration_seconds}s of calibration data...")
        print("⏳ Please keep the MPU perfectly still!")
        
        # Collect calibration samples
        samples_ax, samples_ay, samples_az = [], [], []
        samples_gx, samples_gy, samples_gz = [], [], []
        
        sample_interval = 1.0 / sample_rate
        total_samples = duration_seconds * sample_rate
        
        start_time = time.time()
        for i in range(total_samples):
            # Read raw data
            if self.simulation_mode:
                # For simulation, use fixed bias values
                ax, ay, az = 0.02, -0.01, -1.00  # Slight tilt + gravity
                gx, gy, gz = -3.8, -0.9, -2.6   # Typical bias values
            else:
                ax, ay, az, gx, gy, gz = self.read_mpu_hardware()
            
            samples_ax.append(ax)
            samples_ay.append(ay)
            samples_az.append(az)
            samples_gx.append(gx)
            samples_gy.append(gy)
            samples_gz.append(gz)
            
            # Progress indicator
            if (i + 1) % (sample_rate * 5) == 0:  # Every 5 seconds
                progress = (i + 1) / total_samples * 100
                print(f"   Progress: {progress:.0f}% ({i+1}/{total_samples} samples)")
            
            time.sleep(sample_interval)
        
        # Calculate biases
        self.gyro_bias = {
            'x': float(np.mean(samples_gx)),
            'y': float(np.mean(samples_gy)),
            'z': float(np.mean(samples_gz))
        }
        
        self.accel_bias = {
            'x': float(np.mean(samples_ax)),
            'y': float(np.mean(samples_ay)),
            'z': float(np.mean(samples_az)) + 1.0  # Compensate for gravity (-1g -> 0g)
        }
        
        self.is_calibrated = True
        
        # Display results
        print("\n" + "="*70)
        print("✅ CALIBRATION COMPLETE!")
        print("="*70)
        print("📊 CALCULATED BIASES:")
        print(f"   Gyroscope:")
        print(f"     X: {self.gyro_bias['x']:8.3f} °/s")
        print(f"     Y: {self.gyro_bias['y']:8.3f} °/s")
        print(f"     Z: {self.gyro_bias['z']:8.3f} °/s")
        print(f"   Accelerometer:")
        print(f"     X: {self.accel_bias['x']:8.3f} g")
        print(f"     Y: {self.accel_bias['y']:8.3f} g")
        print(f"     Z: {self.accel_bias['z']:8.3f} g")
        
        # Calculate standard deviations for quality assessment
        gx_std = float(np.std(samples_gx))
        gy_std = float(np.std(samples_gy))
        gz_std = float(np.std(samples_gz))
        
        print(f"\n📈 CALIBRATION QUALITY (Standard Deviation):")
        print(f"   Gyro noise: X={gx_std:.3f}, Y={gy_std:.3f}, Z={gz_std:.3f} °/s")
        
        if max(gx_std, gy_std, gz_std) > 2.0:
            print("⚠️  WARNING: High noise detected! Ensure MPU was perfectly still.")
        else:
            print("✅ Good calibration quality - low noise detected")
        
        # Save calibration
        self.save_calibration()
        print("="*70)

    def apply_calibration(self, ax, ay, az, gx, gy, gz):
        """
        Apply calibration correction to raw sensor data
        
        Returns:
            Tuple of calibrated values: (ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal)
        """
        if not self.is_calibrated:
            return ax, ay, az, gx, gy, gz
        
        # Apply bias correction
        ax_cal = ax - self.accel_bias['x']
        ay_cal = ay - self.accel_bias['y']
        az_cal = az - self.accel_bias['z']
        
        gx_cal = gx - self.gyro_bias['x']
        gy_cal = gy - self.gyro_bias['y']
        gz_cal = gz - self.gyro_bias['z']
        
        return ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal

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

    def format_display_line(self, timestamp, ax, ay, az, gx, gy, gz, ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal, yaw, gravity_mag):
        """Format a single line for display"""
        if self.is_calibrated:
            return (f"{timestamp:6.1f} │"
                    f"{ax:6.2f} {ay:6.2f} {az:6.2f} │"
                    f"{gx:5.1f} {gy:5.1f} {gz:5.1f} │"
                    f"{ax_cal:6.2f} {ay_cal:6.2f} {az_cal:6.2f} │"
                    f"{gx_cal:5.1f} {gy_cal:5.1f} {gz_cal:5.1f} │"
                    f"{yaw:6.1f} │"
                    f"{gravity_mag:5.3f}")
        else:
            return (f"{timestamp:6.1f} │"
                    f"{ax:7.3f} {ay:7.3f} {az:7.3f} │"
                    f"{gx:6.1f} {gy:6.1f} {gz:6.1f} │"
                    f"{yaw:7.1f} │"
                    f"{gravity_mag:6.3f}")

    def start_logging(self):
        """Start the live data logging"""
        print("\n" + "="*120)
        print("🔴 LIVE MPU-6050 DATA LOGGER")
        print("="*120)
        print("📊 All 6 MPU values displayed in real-time")
        if self.is_calibrated:
            print("✅ Showing both RAW and CALIBRATED values")
        else:
            print("⚠️  No calibration loaded - showing RAW values only")
        print("⏹️  Press Ctrl+C to stop")
        print("-"*120)
        
        if self.is_calibrated:
            print("Time   │      Raw Accel (g)      │  Raw Gyro (°/s)  │    Calibrated Accel     │ Cal Gyro (°/s) │  Yaw  │ |G|")
            print("(sec)  │   X     Y     Z        │   X    Y    Z    │   X     Y     Z        │   X    Y    Z  │ (deg) │ (g)")
        else:
            print("Time   │    Accelerometer (g)     │   Gyroscope (°/s)   │  Yaw   │ |G|")
            print("(sec)  │   X      Y      Z       │   X     Y     Z    │ (deg)  │ (g)")
        print("-"*120)
        
        start_time = time.time()
        sample_count = 0
        
        try:
            while True:
                loop_start = time.time()
                elapsed = loop_start - start_time
                
                # Read raw MPU data
                if self.simulation_mode:
                    ax, ay, az, gx, gy, gz = self.read_mpu_simulation()
                else:
                    ax, ay, az, gx, gy, gz = self.read_mpu_hardware()
                
                # Apply calibration
                ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal = self.apply_calibration(ax, ay, az, gx, gy, gz)
                
                # Calculate derived values using calibrated data
                yaw = self.calculate_yaw(ax_cal, ay_cal)
                gravity_mag = self.calculate_gravity_magnitude(ax_cal, ay_cal, az_cal)
                
                # Display data
                display_line = self.format_display_line(elapsed, ax, ay, az, gx, gy, gz, 
                                                      ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal, 
                                                      yaw, gravity_mag)
                print(display_line)
                
                # Log to file if enabled
                if hasattr(self, 'file_logger'):
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_line = (f"{timestamp_str},{ax:.6f},{ay:.6f},{az:.6f},{gx:.3f},{gy:.3f},{gz:.3f},"
                               f"{ax_cal:.6f},{ay_cal:.6f},{az_cal:.6f},{gx_cal:.3f},{gy_cal:.3f},{gz_cal:.3f},"
                               f"{yaw:.3f},{gravity_mag:.6f}")
                    self.file_logger.info(log_line)
                
                sample_count += 1
                
                # Periodic status updates
                if sample_count % (self.update_rate * 10) == 0:  # Every 10 seconds
                    print(f"\n📈 Sample #{sample_count} │ Runtime: {elapsed:.1f}s │ Rate: {sample_count/elapsed:.1f} Hz")
                    print(f"🎯 Current Yaw: {yaw:.1f}° │ Gravity: {gravity_mag:.3f}g")
                    if self.is_calibrated:
                        print(f"🔧 Calibrated Gyro: X={gx_cal:.1f}, Y={gy_cal:.1f}, Z={gz_cal:.1f} °/s")
                    if self.simulation_mode:
                        print(f"🎲 Simulation: Target angle {self.sim_angle:.1f}°")
                    print("-"*120)
                
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
        print(f"   • Calibration: {'APPLIED' if self.is_calibrated else 'NOT APPLIED'}")
        
        if hasattr(self, 'file_logger'):
            print(f"   • Data logged to CSV file")
        
        print("\n🔍 UNDERSTANDING THE DATA:")
        print("   • Accelerometer (g): Measures gravity + motion")
        print("     - For hanging cube: X,Y ≈ 0, Z ≈ -1")
        print("   • Gyroscope (°/s): Measures rotation rates")
        print("     - Positive values = rotation direction")
        if self.is_calibrated:
            print("   • Calibrated values: Bias-corrected sensor readings")
            print("     - Gyro should read ~0 when stationary")
        print("   • Yaw (°): Calculated rotation around vertical axis")
        print("   • |G| (g): Total gravity magnitude (should ≈ 1.0)")
        print("="*85)

def main():
    """Main function to run the MPU logger"""
    print("🚀 MPU-6050 Live Data Logger with Calibration")
    print("=" * 50)
    print("Options:")
    print("1. Start logging (auto-detect mode)")
    print("2. Perform calibration first, then log")
    print("3. Force simulation mode")
    print("4. Force hardware mode")
    print("5. Calibration only (no logging)")
    print("6. View current calibration")
    
    try:
        choice = input("Enter choice (1-6) [default: 1]: ").strip()
        if not choice:
            choice = "1"
        
        # Determine simulation mode
        if choice in ["1", "2"]:
            simulation_mode = None  # Auto-detect
        elif choice == "3":
            simulation_mode = True
        elif choice in ["4", "5", "6"]:
            simulation_mode = False
        else:
            print("Invalid choice, using auto-detect")
            simulation_mode = None
            choice = "1"
        
        # Create logger instance
        logger = MPULogger(simulation_mode=simulation_mode, log_to_file=False, update_rate=10)
        
        if choice == "6":
            # View calibration only
            if logger.is_calibrated:
                print("\n✅ Current Calibration Data:")
                print(f"Gyro Bias: X={logger.gyro_bias['x']:.3f}, Y={logger.gyro_bias['y']:.3f}, Z={logger.gyro_bias['z']:.3f} °/s")
                print(f"Accel Bias: X={logger.accel_bias['x']:.3f}, Y={logger.accel_bias['y']:.3f}, Z={logger.accel_bias['z']:.3f} g")
            else:
                print("\n❌ No calibration data found")
            return
        
        if choice in ["2", "5"]:
            # Perform calibration
            print("\n🎯 Starting calibration procedure...")
            duration = input("Calibration duration in seconds [default: 30]: ").strip()
            duration = int(duration) if duration.isdigit() else 30
            
            logger.perform_calibration(duration_seconds=duration)
            
            if choice == "5":
                print("✅ Calibration complete. Exiting.")
                return
        
        if choice in ["1", "2", "3", "4"]:
            # Configure logging
            print("\nLogging Configuration:")
            rate_input = input("Update rate in Hz [default: 10]: ").strip()
            update_rate = int(rate_input) if rate_input.isdigit() else 10
            
            log_input = input("Log to file? (y/n) [default: y]: ").strip().lower()
            log_to_file = log_input != 'n'
            
            # Update logger settings
            logger.update_rate = update_rate
            logger.update_interval = 1.0 / update_rate
            
            if log_to_file:
                logger.setup_logging()
            
            # Start logging
            logger.start_logging()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()