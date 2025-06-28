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
        self.accel_scale = {'x': 1.0, 'y': 1.0, 'z': 1.0}  # Scale factors
        self.accel_cross_axis = {  # Cross-axis coupling matrix
            'xy': 0.0, 'xz': 0.0,
            'yx': 0.0, 'yz': 0.0, 
            'zx': 0.0, 'zy': 0.0
        }
        self.is_calibrated = False
        self.is_accel_calibrated = False
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
        print(f"🎯 Gyro Calibration: {'LOADED' if self.is_calibrated else 'NOT CALIBRATED'}")
        print(f"📐 Accel Calibration: {'LOADED' if self.is_accel_calibrated else 'NOT CALIBRATED'}")

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
                
                # Load gyro calibration
                self.gyro_bias = cal_data.get('gyro_bias', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                
                # Load accelerometer calibration
                self.accel_bias = cal_data.get('accel_bias', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                self.accel_scale = cal_data.get('accel_scale', {'x': 1.0, 'y': 1.0, 'z': 1.0})
                self.accel_cross_axis = cal_data.get('accel_cross_axis', {
                    'xy': 0.0, 'xz': 0.0, 'yx': 0.0, 'yz': 0.0, 'zx': 0.0, 'zy': 0.0
                })
                
                self.is_calibrated = True
                self.is_accel_calibrated = cal_data.get('accel_calibrated', False)
                
                print(f"📁 Calibration loaded from {self.calibration_file}")
                print(f"   Gyro bias: X={self.gyro_bias['x']:.3f}, Y={self.gyro_bias['y']:.3f}, Z={self.gyro_bias['z']:.3f}")
                print(f"   Accel bias: X={self.accel_bias['x']:.3f}, Y={self.accel_bias['y']:.3f}, Z={self.accel_bias['z']:.3f}")
                if self.is_accel_calibrated:
                    print(f"   Accel scale: X={self.accel_scale['x']:.3f}, Y={self.accel_scale['y']:.3f}, Z={self.accel_scale['z']:.3f}")
                    
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
                'accel_scale': self.accel_scale,
                'accel_cross_axis': self.accel_cross_axis,
                'accel_calibrated': self.is_accel_calibrated,
                'calibration_date': datetime.now().isoformat(),
                'notes': 'MPU calibration with gyro bias and accelerometer corrections'
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

    def perform_accelerometer_calibration(self):
        """
        Perform 6-position accelerometer calibration for bias and scale correction
        This method requires placing the MPU in 6 different orientations
        """
        print("\n" + "="*80)
        print("📐 ADVANCED ACCELEROMETER CALIBRATION")
        print("="*80)
        print("📋 This calibration corrects for:")
        print("   • Bias offsets (zero-g offset)")
        print("   • Scale factor errors (sensitivity variations)")
        print("   • Cross-axis coupling (misalignment)")
        print("\n🔄 You will need to place the MPU in 6 orientations:")
        print("   1. +X up (X axis pointing up)")
        print("   2. -X up (X axis pointing down)")  
        print("   3. +Y up (Y axis pointing up)")
        print("   4. -Y up (Y axis pointing down)")
        print("   5. +Z up (Z axis pointing up)")
        print("   6. -Z up (Z axis pointing down)")
        print("\n⚠️  Each position must be held steady for data collection")
        print("-"*80)
        
        if not input("Ready to start? (y/n): ").lower().startswith('y'):
            print("Accelerometer calibration cancelled")
            return
        
        positions = [
            ("+X up", "X axis pointing UP (device rotated 90° left)"),
            ("-X up", "X axis pointing DOWN (device rotated 90° right)"),
            ("+Y up", "Y axis pointing UP (device rotated 90° forward)"),
            ("-Y up", "Y axis pointing DOWN (device rotated 90° backward)"),
            ("+Z up", "Z axis pointing UP (device flat, normal position)"),
            ("-Z up", "Z axis pointing DOWN (device upside down)")
        ]
        
        all_samples = []
        expected_values = [
            [1.0, 0.0, 0.0],   # +X up
            [-1.0, 0.0, 0.0],  # -X up
            [0.0, 1.0, 0.0],   # +Y up
            [0.0, -1.0, 0.0],  # -Y up
            [0.0, 0.0, 1.0],   # +Z up
            [0.0, 0.0, -1.0]   # -Z up
        ]
        
        for i, (pos_name, description) in enumerate(positions):
            print(f"\n📍 Position {i+1}/6: {pos_name}")
            print(f"   {description}")
            input("   Position the device and press ENTER...")
            
            print("   Collecting data for 5 seconds...")
            samples_x, samples_y, samples_z = [], [], []
            
            for j in range(100):  # 100 samples over 5 seconds
                if self.simulation_mode:
                    # Simulate perfect accelerometer readings for each position
                    ax, ay, az = expected_values[i]
                    # Add some realistic noise
                    ax += random.uniform(-0.02, 0.02)
                    ay += random.uniform(-0.02, 0.02) 
                    az += random.uniform(-0.02, 0.02)
                else:
                    ax, ay, az, _, _, _ = self.read_mpu_hardware()
                
                samples_x.append(ax)
                samples_y.append(ay)
                samples_z.append(az)
                time.sleep(0.05)  # 20 Hz sampling
            
            # Calculate averages for this position
            avg_x = np.mean(samples_x)
            avg_y = np.mean(samples_y)
            avg_z = np.mean(samples_z)
            
            all_samples.append([avg_x, avg_y, avg_z])
            
            print(f"   ✅ Position {i+1} complete: X={avg_x:.3f}, Y={avg_y:.3f}, Z={avg_z:.3f}")
        
        # Calculate calibration parameters using least squares
        print(f"\n🧮 Calculating calibration parameters...")
        
        # Convert to numpy arrays
        measured = np.array(all_samples)
        expected = np.array(expected_values)
        
        # Solve for bias and scale using least squares
        # For each axis: measured = scale * (true + bias)
        # Rearranged: measured = scale * true + scale * bias
        
        calibration_results = {}
        
        for axis_idx, axis_name in enumerate(['x', 'y', 'z']):
            axis_data = measured[:, axis_idx]
            axis_expected = expected[:, axis_idx]
            
            # Simple bias and scale calculation
            # Find the max and min readings for this axis
            pos_reading = axis_data[axis_expected == 1.0][0] if np.any(axis_expected == 1.0) else 0
            neg_reading = axis_data[axis_expected == -1.0][0] if np.any(axis_expected == -1.0) else 0
            
            # Calculate bias (should be zero when corrected)
            bias = (pos_reading + neg_reading) / 2.0
            
            # Calculate scale factor
            scale = 2.0 / (pos_reading - neg_reading) if (pos_reading - neg_reading) != 0 else 1.0
            
            calibration_results[axis_name] = {'bias': bias, 'scale': scale}
        
        # Update calibration parameters
        self.accel_bias = {
            'x': calibration_results['x']['bias'],
            'y': calibration_results['y']['bias'], 
            'z': calibration_results['z']['bias']
        }
        
        self.accel_scale = {
            'x': calibration_results['x']['scale'],
            'y': calibration_results['y']['scale'],
            'z': calibration_results['z']['scale']
        }
        
        self.is_accel_calibrated = True
        
        # Display results
        print("\n" + "="*80)
        print("✅ ACCELEROMETER CALIBRATION COMPLETE!")
        print("="*80)
        print("📊 CALIBRATION PARAMETERS:")
        print(f"   Bias Correction:")
        print(f"     X: {self.accel_bias['x']:8.4f} g")
        print(f"     Y: {self.accel_bias['y']:8.4f} g")
        print(f"     Z: {self.accel_bias['z']:8.4f} g")
        print(f"   Scale Factors:")
        print(f"     X: {self.accel_scale['x']:8.4f}")
        print(f"     Y: {self.accel_scale['y']:8.4f}")
        print(f"     Z: {self.accel_scale['z']:8.4f}")
        
        # Test the calibration
        print(f"\n🧪 CALIBRATION VERIFICATION:")
        for i, (pos_name, _) in enumerate(positions):
            raw_vals = all_samples[i]
            corrected = self.apply_accel_calibration(raw_vals[0], raw_vals[1], raw_vals[2])
            expected_vals = expected_values[i]
            
            error_x = abs(corrected[0] - expected_vals[0])
            error_y = abs(corrected[1] - expected_vals[1])
            error_z = abs(corrected[2] - expected_vals[2])
            total_error = np.sqrt(error_x**2 + error_y**2 + error_z**2)
            
            print(f"   {pos_name:6}: Expected [{expected_vals[0]:5.1f}, {expected_vals[1]:5.1f}, {expected_vals[2]:5.1f}] "
                  f"Got [{corrected[0]:5.2f}, {corrected[1]:5.2f}, {corrected[2]:5.2f}] Error: {total_error:.3f}g")
        
        avg_error = np.mean([np.sqrt(sum((self.apply_accel_calibration(*all_samples[i]) - np.array(expected_values[i]))**2)) 
                           for i in range(6)])
        
        print(f"\n📈 CALIBRATION QUALITY:")
        print(f"   Average error: {avg_error:.4f} g")
        if avg_error < 0.05:
            print("   ✅ Excellent calibration!")
        elif avg_error < 0.1:
            print("   ✅ Good calibration")
        else:
            print("   ⚠️  Poor calibration - consider recalibrating")
        
        # Save calibration
        self.save_calibration()
        print("="*80)

    def apply_accel_calibration(self, ax, ay, az):
        """
        Apply comprehensive accelerometer calibration
        
        Returns:
            Tuple of calibrated accelerometer values: (ax_cal, ay_cal, az_cal)
        """
        if not self.is_accel_calibrated:
            # Basic bias correction only
            ax_cal = ax - self.accel_bias['x']
            ay_cal = ay - self.accel_bias['y'] 
            az_cal = az - self.accel_bias['z']
            return ax_cal, ay_cal, az_cal
        
        # Apply bias correction first
        ax_biased = ax - self.accel_bias['x']
        ay_biased = ay - self.accel_bias['y']
        az_biased = az - self.accel_bias['z']
        
        # Apply scale factor correction
        ax_cal = ax_biased * self.accel_scale['x']
        ay_cal = ay_biased * self.accel_scale['y']
        az_cal = az_biased * self.accel_scale['z']
        
        # Apply cross-axis correction (if available)
        if any(abs(val) > 0.001 for val in self.accel_cross_axis.values()):
            ax_corrected = ax_cal - (self.accel_cross_axis['xy'] * ay_cal + self.accel_cross_axis['xz'] * az_cal)
            ay_corrected = ay_cal - (self.accel_cross_axis['yx'] * ax_cal + self.accel_cross_axis['yz'] * az_cal)
            az_corrected = az_cal - (self.accel_cross_axis['zx'] * ax_cal + self.accel_cross_axis['zy'] * ay_cal)
            return ax_corrected, ay_corrected, az_corrected
        
        return ax_cal, ay_cal, az_cal

    def apply_calibration(self, ax, ay, az, gx, gy, gz):
        """
        Apply calibration correction to raw sensor data
        
        Returns:
            Tuple of calibrated values: (ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal)
        """
        # Apply accelerometer calibration (comprehensive or basic)
        ax_cal, ay_cal, az_cal = self.apply_accel_calibration(ax, ay, az)
        
        # Apply gyroscope bias correction
        if self.is_calibrated:
            gx_cal = gx - self.gyro_bias['x']
            gy_cal = gy - self.gyro_bias['y']
            gz_cal = gz - self.gyro_bias['z']
        else:
            gx_cal, gy_cal, gz_cal = gx, gy, gz
        
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
        if self.is_calibrated or self.is_accel_calibrated:
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
        if self.is_calibrated or self.is_accel_calibrated:
            print("✅ Showing both RAW and CALIBRATED values")
            if self.is_calibrated and self.is_accel_calibrated:
                print("🎯 Full calibration active (gyro bias + accel scale/bias)")
            elif self.is_calibrated:
                print("🎯 Gyro calibration active (bias correction)")
            elif self.is_accel_calibrated:
                print("📐 Advanced accel calibration active (scale + bias)")
        else:
            print("⚠️  No calibration loaded - showing RAW values only")
        print("⏹️  Press Ctrl+C to stop")
        print("-"*120)
        
        if self.is_calibrated or self.is_accel_calibrated:
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
                    if self.is_calibrated or self.is_accel_calibrated:
                        if self.is_calibrated:
                            print(f"🔧 Calibrated Gyro: X={gx_cal:.1f}, Y={gy_cal:.1f}, Z={gz_cal:.1f} °/s")
                        if self.is_accel_calibrated:
                            print(f"📐 Calibrated Accel: X={ax_cal:.3f}, Y={ay_cal:.3f}, Z={az_cal:.3f} g")
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
    print("🚀 MPU-6050 Live Data Logger with Advanced Calibration")
    print("=" * 60)
    print("Options:")
    print("1. Start logging (auto-detect mode)")
    print("2. Perform gyro calibration first, then log")
    print("3. Perform full calibration (gyro + accelerometer), then log")
    print("4. Force simulation mode")
    print("5. Force hardware mode")
    print("6. Gyro calibration only")
    print("7. Accelerometer calibration only")
    print("8. View current calibration")
    
    try:
        choice = input("Enter choice (1-8) [default: 1]: ").strip()
        if not choice:
            choice = "1"
        
        # Determine simulation mode
        if choice in ["1", "2", "3"]:
            simulation_mode = None  # Auto-detect
        elif choice == "4":
            simulation_mode = True
        elif choice in ["5", "6", "7", "8"]:
            simulation_mode = False
        else:
            print("Invalid choice, using auto-detect")
            simulation_mode = None
            choice = "1"
        
        # Create logger instance
        logger = MPULogger(simulation_mode=simulation_mode, log_to_file=False, update_rate=10)
        
        if choice == "8":
            # View calibration only
            print("\n📊 Current Calibration Status:")
            if logger.is_calibrated:
                print("✅ Gyro Calibration:")
                print(f"   Bias: X={logger.gyro_bias['x']:.3f}, Y={logger.gyro_bias['y']:.3f}, Z={logger.gyro_bias['z']:.3f} °/s")
            else:
                print("❌ No gyro calibration found")
                
            if logger.is_accel_calibrated:
                print("✅ Advanced Accelerometer Calibration:")
                print(f"   Bias: X={logger.accel_bias['x']:.4f}, Y={logger.accel_bias['y']:.4f}, Z={logger.accel_bias['z']:.4f} g")
                print(f"   Scale: X={logger.accel_scale['x']:.4f}, Y={logger.accel_scale['y']:.4f}, Z={logger.accel_scale['z']:.4f}")
            else:
                print("❌ No advanced accelerometer calibration found")
                if any(abs(val) > 0.001 for val in logger.accel_bias.values()):
                    print("⚠️  Basic accelerometer bias correction available")
            return
        
        if choice in ["2", "3", "6"]:
            # Perform gyro calibration
            print("\n🎯 Starting gyro calibration procedure...")
            duration = input("Calibration duration in seconds [default: 30]: ").strip()
            duration = int(duration) if duration.isdigit() else 30
            
            logger.perform_calibration(duration_seconds=duration)
        
        if choice in ["3", "7"]:
            # Perform accelerometer calibration
            print("\n📐 Starting accelerometer calibration procedure...")
            logger.perform_accelerometer_calibration()
            
        if choice in ["6", "7"]:
            print("✅ Calibration complete. Exiting.")
            return
        
        if choice in ["1", "2", "3", "4", "5"]:
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