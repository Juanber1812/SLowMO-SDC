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
import csv
import os

class MPU6050:
    def __init__(self, bus_number=1, device_address=0x68):
        """Initialize MPU6050 sensor with complementary filter"""
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
        
        # Calibration values (renamed: pitch->yaw for spacecraft convention)
        self.gyro_x_cal = 0.0
        self.gyro_y_cal = 0.0
        self.gyro_z_cal = 0.0
        self.accel_yaw_cal = 0.0     # Primary control calibration (was pitch_cal)
        self.accel_roll_cal = 0.0
        
        # Angle variables (renamed: pitch->yaw, yaw->pitch for spacecraft convention)
        self.angle_yaw = 0.0      # Primary control angle (was pitch)
        self.angle_roll = 0.0
        self.angle_pitch = 0.0    # Secondary angle (was yaw)
        self.angle_yaw_acc = 0.0  # Accelerometer yaw (was pitch_acc)
        self.angle_roll_acc = 0.0
        
        # Output angles (filtered)
        self.angle_yaw_output = 0.0    # Primary control output (was pitch_output)
        self.angle_roll_output = 0.0
        self.angle_pitch_output = 0.0  # Secondary output (was yaw_output)
        
        # Filter and timing variables
        self.set_gyro_angles = False
        self.last_time = time.time()
        self.dt = 0.0
        
        # Pitch drift compensation (renamed from yaw drift)
        self.yaw_drift_rate = 0.0  # deg/s drift rate (actually pitch now)
        self.yaw_reference_time = time.time()
        self.yaw_zero_velocity_threshold = 0.5  # deg/s
        self.yaw_zero_velocity_count = 0
        self.yaw_drift_samples = []
        
        # Filter parameters (adjustable for PD controller)
        self.complementary_alpha = 0.9996  # Gyro weight (0.9996 = 99.96%)
        self.output_filter_alpha = 0.9     # Output smoothing (90% previous, 10% new)
        
        # Initialize the sensor
        self.initialize_sensor()
        
        # Control mode settings
        self.use_gyro_only = False
        self.disable_accel_correction = False
        self.angle_yaw_pure = 0.0  # Pure gyro integration for control
        
        # Initialize CSV logging
        self.log_file = None
        self.csv_writer = None
        self.enable_logging = False
        self.last_log_time = time.time()  # For 10Hz logging timing
    
    def initialize_sensor(self):
        """Initialize MPU6050 with proper configuration"""
        try:
            # Wake up the MPU6050 (it starts in sleep mode)
            self.bus.write_byte_data(self.device_address, self.PWR_MGMT_1, 0)
            
            # Set sample rate to 250Hz (1000Hz / (1 + 3))
            self.bus.write_byte_data(self.device_address, self.SMPLRT_DIV, 3)
            
            # Set accelerometer configuration (+/- 2g)
            self.bus.write_byte_data(self.device_address, self.ACCEL_CONFIG, 0)
            
            # Set gyroscope configuration (+/- 250 deg/s)
            self.bus.write_byte_data(self.device_address, self.GYRO_CONFIG, 0)
            
            # Set filter bandwidth to 21Hz
            self.bus.write_byte_data(self.device_address, self.CONFIG, 0)
            
            print("MPU6050 initialized successfully!")
            time.sleep(0.1)  # Give sensor time to stabilize
            
            # Perform calibration
            self.calibrate_gyro()
            
        except Exception as e:
            print(f"Error initializing MPU6050: {e}")
            sys.exit(1)
    
    def calibrate_gyro(self, samples=2000):
        """Calibrate gyroscope by averaging readings when stationary"""
        print("Calibrating gyroscope... Keep sensor stationary!")
        
        gyro_x_sum = 0
        gyro_y_sum = 0
        gyro_z_sum = 0
        
        for i in range(samples):
            gyro_x, gyro_y, gyro_z = self.read_gyroscope_raw()
            gyro_x_sum += gyro_x
            gyro_y_sum += gyro_y
            gyro_z_sum += gyro_z
            
            if i % 200 == 0:
                print(f"Calibration progress: {(i/samples)*100:.1f}%")
            
            time.sleep(0.004)  # 250Hz sampling
        
        self.gyro_x_cal = gyro_x_sum / samples
        self.gyro_y_cal = gyro_y_sum / samples
        self.gyro_z_cal = gyro_z_sum / samples
        
        print(f"Gyro calibration complete!")
        print(f"Offsets - X: {self.gyro_x_cal:.3f}, Y: {self.gyro_y_cal:.3f}, Z: {self.gyro_z_cal:.3f}")
    
    def calibrate_accelerometer(self, yaw_offset=0.0, roll_offset=0.0):
        """Set accelerometer calibration offsets (determine by placing sensor level)"""
        self.accel_yaw_cal = yaw_offset    # Primary control calibration (was pitch_cal)
        self.accel_roll_cal = roll_offset
        print(f"Accelerometer calibration set - Yaw: {yaw_offset:.3f}°, Roll: {roll_offset:.3f}°")
    
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
    
    def read_gyroscope_raw(self):
        """Read raw gyroscope data (x, y, z) in deg/s"""
        gyro_x = self.read_raw_data(self.GYRO_XOUT_H)
        gyro_y = self.read_raw_data(self.GYRO_XOUT_H + 2)
        gyro_z = self.read_raw_data(self.GYRO_XOUT_H + 4)
        
        # Convert to deg/s (131 LSB/deg/s for +/- 250 deg/s range)
        gyro_x = gyro_x / 131.0
        gyro_y = gyro_y / 131.0
        gyro_z = gyro_z / 131.0
        
        return gyro_x, gyro_y, gyro_z
    
    def read_gyroscope(self):
        """Read calibrated gyroscope data (x, y, z) in deg/s"""
        gyro_x, gyro_y, gyro_z = self.read_gyroscope_raw()
        
        # Apply calibration
        gyro_x -= self.gyro_x_cal
        gyro_y -= self.gyro_y_cal
        gyro_z -= self.gyro_z_cal
        
        return gyro_x, gyro_y, gyro_z
    
    def read_temperature(self):
        """Read temperature in Celsius"""
        temp_raw = self.read_raw_data(self.TEMP_OUT_H)
        # Temperature in degrees C = (TEMP_OUT Register Value as a signed number)/340 + 36.53
        temperature = (temp_raw / 340.0) + 36.53
        return temperature
    
    def update_angles(self):
        """Update pitch, roll, and yaw angles using complementary filter"""
        current_time = time.time()
        self.dt = current_time - self.last_time
        self.last_time = current_time
        
        # Read sensor data
        gyro_x, gyro_y, gyro_z = self.read_gyroscope()
        acc_x, acc_y, acc_z = self.read_accelerometer()
        
        # Gyro angle calculations (integration) - remapped for spacecraft convention
        # Convert gyro rates to angle changes
        dt_factor = self.dt  # Time step for integration
        
        self.angle_yaw += gyro_z * dt_factor      # Primary control (was pitch)
        self.angle_roll += gyro_y * dt_factor
        self.angle_pitch += gyro_x * dt_factor    # Secondary angle (was yaw)
        
        # Pure gyro integration for control (no accelerometer bias)
        if not hasattr(self, 'angle_yaw_pure'):
            self.angle_yaw_pure = 0.0
        self.angle_yaw_pure += gyro_z * dt_factor
        
        # Pitch compensation for yaw and roll (transfer angles during pitch rotation)
        pitch_rad = math.radians(gyro_x * dt_factor)
        self.angle_yaw += self.angle_roll * math.sin(pitch_rad)
        self.angle_roll -= self.angle_yaw * math.sin(pitch_rad)
        
        # Accelerometer angle calculations
        acc_total_vector = math.sqrt(acc_x*acc_x + acc_y*acc_y + acc_z*acc_z)
        
        if acc_total_vector > 0:  # Avoid division by zero
            # Calculate yaw and roll from accelerometer (remapped for spacecraft)
            self.angle_yaw_acc = math.degrees(math.asin(acc_y / acc_total_vector))      # Primary (was pitch)
            self.angle_roll_acc = math.degrees(math.asin(acc_z / acc_total_vector)) * -1
            
            # Apply accelerometer calibration
            self.angle_yaw_acc -= self.accel_yaw_cal     # Primary calibration (was pitch_cal)
            self.angle_roll_acc -= self.accel_roll_cal
        else:
            # Avoid invalid angle calculations
            self.angle_yaw_acc = 0.0
            self.angle_roll_acc = 0.0
        
        # Complementary filter (remapped for spacecraft convention)
        if self.set_gyro_angles:
            if self.use_gyro_only:
                # CONTROL MODE: Use pure gyro integration (no accelerometer bias)
                pass  # Keep gyro-integrated values as-is
            elif self.disable_accel_correction:
                # CONTROL MODE: Reduced accelerometer influence
                weak_alpha = 0.9999  # Even weaker accelerometer influence
                self.angle_yaw = (self.angle_yaw * weak_alpha + 
                                 self.angle_yaw_acc * (1 - weak_alpha))
                self.angle_roll = (self.angle_roll * weak_alpha + 
                                 self.angle_roll_acc * (1 - weak_alpha))
            else:
                # NORMAL MODE: Standard complementary filter
                self.angle_yaw = (self.angle_yaw * self.complementary_alpha + 
                                 self.angle_yaw_acc * (1 - self.complementary_alpha))    # Primary
                self.angle_roll = (self.angle_roll * self.complementary_alpha + 
                                 self.angle_roll_acc * (1 - self.complementary_alpha))
        else:
            # First startup - use accelerometer values
            self.angle_yaw = self.angle_yaw_acc      # Primary (was pitch)
            self.angle_roll = self.angle_roll_acc
            self.angle_yaw_pure = self.angle_yaw_acc  # Initialize pure gyro
            self.set_gyro_angles = True
        
        # Pitch drift compensation (secondary angle, was yaw drift)
        self.compensate_pitch_drift(gyro_x)
        
        # Apply output filtering for smooth control (remapped)
        self.angle_yaw_output = (self.angle_yaw_output * self.output_filter_alpha + 
                                self.angle_yaw * (1 - self.output_filter_alpha))        # Primary
        self.angle_roll_output = (self.angle_roll_output * self.output_filter_alpha + 
                                self.angle_roll * (1 - self.output_filter_alpha))
        self.angle_pitch_output = (self.angle_pitch_output * self.output_filter_alpha + 
                                 self.angle_pitch * (1 - self.output_filter_alpha))     # Secondary
    
    def compensate_pitch_drift(self, gyro_x):
        """Compensate for pitch drift using zero velocity detection (was yaw drift)"""
        # Detect if pitch rate is near zero (stationary)
        if abs(gyro_x) < self.yaw_zero_velocity_threshold:
            self.yaw_zero_velocity_count += 1
            
            # If stationary for long enough, estimate drift
            if self.yaw_zero_velocity_count > 50:  # ~0.2 seconds at 250Hz
                current_time = time.time()
                time_elapsed = current_time - self.yaw_reference_time
                
                if time_elapsed > 0:
                    # Calculate apparent drift rate
                    apparent_drift = gyro_x  # Small residual rate when "stationary"
                    self.yaw_drift_samples.append(apparent_drift)
                    
                    # Keep only recent samples
                    if len(self.yaw_drift_samples) > 100:
                        self.yaw_drift_samples.pop(0)
                    
                    # Update drift estimate
                    if len(self.yaw_drift_samples) >= 10:
                        self.yaw_drift_rate = sum(self.yaw_drift_samples) / len(self.yaw_drift_samples)
        else:
            self.yaw_zero_velocity_count = 0
        
        # Apply drift compensation to pitch (secondary angle)
        self.angle_pitch -= self.yaw_drift_rate * self.dt
    
    def reset_pitch(self):
        """Reset pitch angle to zero (useful for reference point) - was reset_yaw"""
        self.angle_pitch = 0.0
        self.angle_pitch_output = 0.0
        self.yaw_reference_time = time.time()
        print("Pitch angle reset to 0°")
    
    def set_filter_parameters(self, complementary_alpha=None, output_alpha=None):
        """Adjust filter parameters for PD controller tuning"""
        if complementary_alpha is not None:
            self.complementary_alpha = complementary_alpha
            print(f"Complementary filter alpha set to {complementary_alpha}")
        
        if output_alpha is not None:
            self.output_filter_alpha = output_alpha
            print(f"Output filter alpha set to {output_alpha}")
    
    def get_angles(self):
        """Get current angle estimates (remapped: yaw=primary, pitch=secondary)"""
        return {
            'yaw': self.angle_yaw_output,        # Primary control angle (was pitch)
            'roll': self.angle_roll_output,
            'pitch': self.angle_pitch_output,    # Secondary angle (was yaw)
            'yaw_raw': self.angle_yaw,           # Primary raw (was pitch_raw)
            'roll_raw': self.angle_roll,
            'pitch_raw': self.angle_pitch,       # Secondary raw (was yaw_raw)
            'yaw_pure': getattr(self, 'angle_yaw_pure', 0.0)  # Pure gyro integration
        }
    
    def read_all_data(self):
        """Read all sensor data and update angles"""
        # Update angle calculations
        self.update_angles()
        
        # Get raw sensor data
        acc_x, acc_y, acc_z = self.read_accelerometer()
        gyro_x, gyro_y, gyro_z = self.read_gyroscope()
        temperature = self.read_temperature()
        
        # Get angle estimates
        angles = self.get_angles()
        
        # Log data to CSV file
        if self.enable_logging and self.csv_writer is not None:
            try:
                self.csv_writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    acc_x, acc_y, acc_z,
                    gyro_x, gyro_y, gyro_z,
                    temperature,
                    angles['yaw'], angles['roll'], angles['pitch'],    # Remapped order
                    self.dt, self.yaw_drift_rate
                ])
                self.log_file.flush()  # Ensure data is written to file
            except Exception as e:
                print(f"Error writing to log file: {e}")
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'accel': {'x': acc_x, 'y': acc_y, 'z': acc_z},
            'gyro': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z},
            'temperature': temperature,
            'angles': angles,
            'dt': self.dt,
            'yaw_drift_rate': self.yaw_drift_rate
        }
    
    def start_logging(self, file_path):
        """Start logging data to a CSV file"""
        try:
            # Close existing log file if open
            if self.log_file is not None:
                self.log_file.close()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Open new log file
            self.log_file = open(file_path, mode='a', newline='')
            self.csv_writer = csv.writer(self.log_file)
            
            # Write header row if file is new
            if os.stat(file_path).st_size == 0:
                self.csv_writer.writerow([
                    'Timestamp', 'Accel_X', 'Accel_Y', 'Accel_Z',
                    'Gyro_X', 'Gyro_Y', 'Gyro_Z',
                    'Temperature',
                    'Yaw', 'Roll', 'Pitch',    # Remapped header order
                    'Delta_Time', 'Yaw_Drift_Rate'
                ])
            
            self.enable_logging = True
            print(f"Logging started: {file_path}")
        except Exception as e:
            print(f"Error starting logging: {e}")
    
    def stop_logging(self):
        """Stop logging data to CSV file"""
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None
            self.enable_logging = False
            print("Logging stopped.")
    
    def start_csv_logging(self, filename=None):
        """Start CSV logging of IMU data at 10Hz"""
        if self.enable_logging:
            print("CSV logging already active!")
            return
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"imu_data_{timestamp}.csv"
        
        try:
            self.log_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.log_file)
            
            # Write header (remapped: yaw first as primary control)
            self.csv_writer.writerow(['timestamp', 'yaw', 'roll', 'pitch'])
            self.log_file.flush()
            
            self.enable_logging = True
            self.last_log_time = time.time()
            print(f"CSV logging started: {filename}")
            
        except Exception as e:
            print(f"Error starting CSV logging: {e}")
            
    def stop_csv_logging(self):
        """Stop CSV logging and close file"""
        if not self.enable_logging:
            print("CSV logging not active!")
            return
            
        try:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None
            
            self.enable_logging = False
            print("CSV logging stopped")
            
        except Exception as e:
            print(f"Error stopping CSV logging: {e}")
    
    def log_data_if_needed(self):
        """Log data at 10Hz if logging is enabled"""
        if not self.enable_logging or not self.csv_writer:
            return
            
        current_time = time.time()
        if current_time - self.last_log_time >= 0.1:  # 10Hz = 0.1 seconds
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # millisecond precision
                self.csv_writer.writerow([
                    timestamp,
                    round(self.angle_yaw_output, 3),      # Primary control (was pitch)
                    round(self.angle_roll_output, 3),
                    round(self.angle_pitch_output, 3)     # Secondary (was yaw)
                ])
                self.log_file.flush()  # Ensure data is written immediately
                self.last_log_time = current_time
                
            except Exception as e:
                print(f"Error logging data: {e}")
    
    def get_yaw_for_control(self):
        """Get yaw angle optimized for control (primary control angle)"""
        self.update_angles()
        
        # Choose control angle based on mode
        if self.use_gyro_only:
            return self.angle_yaw_pure  # Pure gyro, no accelerometer bias
        elif self.disable_accel_correction:
            return self.angle_yaw  # Reduced accelerometer influence
        else:
            return self.angle_yaw  # Standard filtered angle
    
    def get_yaw_for_control_pure(self):
        """Get pure gyro-integrated yaw for control (no accelerometer bias)"""
        self.update_angles()
        return self.angle_yaw_pure if hasattr(self, 'angle_yaw_pure') else self.angle_yaw
    
    def get_pitch_for_control(self):
        """Get pitch angle optimized for control (secondary angle, was yaw)"""
        self.update_angles()
        return self.angle_pitch  # Raw pitch for control
    
    def calibrate_at_current_position(self):
        """Calibrate the current position as zero reference"""
        self.angle_yaw = 0.0        # Primary control (was pitch)
        self.angle_roll = 0.0
        self.angle_pitch = 0.0      # Secondary (was yaw)
        self.angle_yaw_output = 0.0 # Primary output (was pitch_output)
        self.angle_roll_output = 0.0
        self.angle_pitch_output = 0.0  # Secondary output (was yaw_output)
        self.angle_yaw_pure = 0.0   # Reset pure gyro integration
        print("Position calibrated - current orientation set as zero reference")
    
    def set_control_mode(self, use_gyro_only=False, disable_accel_correction=False, verbose=True):
        """Configure filter for control applications"""
        self.use_gyro_only = use_gyro_only
        self.disable_accel_correction = disable_accel_correction
        
        if verbose:
            if use_gyro_only:
                print("Control mode: GYRO ONLY (no accelerometer bias)")
            elif disable_accel_correction:
                print("Control mode: REDUCED ACCELEROMETER CORRECTION")
            else:
                print("Control mode: NORMAL (with accelerometer correction)")
    
    def get_yaw_for_control_pure(self):
        """Get pure gyro-integrated yaw for control (no accelerometer bias)"""
        self.update_angles()
        return self.angle_yaw_pure if hasattr(self, 'angle_yaw_pure') else self.angle_yaw
    
def main(auto_log=False, log_filename=None):
    """Main loop to read and display MPU6050 data with attitude estimation"""
    print("Starting MPU6050 Attitude Estimation System...")
    print("Features: Complementary Filter, Yaw Drift Compensation, PD Controller Ready")
    print("Press Ctrl+C to exit")
    print("-" * 90)
    
    try:
        # Initialize sensor
        mpu = MPU6050()
        
        # Auto-start logging if requested
        if auto_log:
            mpu.start_csv_logging(log_filename)
        
        print("System ready! Live data display active (angles + raw sensor data)")
        print("Commands: 'l' = start logging, 's' = stop logging, 'q' = quit, 'z' = zero pitch")
        print("=" * 90)
        
        while True:
            # Read sensor data and update angles
            data = mpu.read_all_data()
            
            # Log data at 10Hz if logging is enabled
            mpu.log_data_if_needed()
            
            # Extract data for display
            accel = data['accel']
            gyro = data['gyro']
            angles = data['angles']
            temp = data['temperature']
            
            # Live display with both angles and raw data (overwrite same line) - remapped order
            log_status = " [LOGGING]" if mpu.enable_logging else ""
            live_display = (
                f"\rYaw: {angles['yaw']:+6.1f}° | "        # Primary control (was pitch)
                f"Roll: {angles['roll']:+6.1f}° | "
                f"Pitch: {angles['pitch']:+6.1f}° | "     # Secondary (was yaw)
                f"Accel: X={accel['x']:+5.2f}g Y={accel['y']:+5.2f}g Z={accel['z']:+5.2f}g | "
                f"Gyro: X={gyro['x']:+5.1f} Y={gyro['y']:+5.1f} Z={gyro['z']:+5.1f} °/s | "
                f"T: {temp:4.1f}°C{log_status}"
            )
            
            # Update live display
            print(live_display, end='', flush=True)
            
            # Small delay to prevent excessive CPU usage (targeting ~100Hz for smooth display)
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n\nExiting MPU6050 attitude estimation...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure CSV logging is stopped and file is closed
        if 'mpu' in locals():
            mpu.stop_csv_logging()
        print("Cleanup complete.")

def pd_controller_demo():
    """Demonstration of PD controller integration"""
    print("PD Controller Demo - Yaw Stabilization (Primary Control)")
    print("=" * 50)
    
    try:
        mpu = MPU6050()
        
        # PD Controller parameters
        kp = 1.0  # Proportional gain
        kd = 0.1  # Derivative gain
        target_yaw = 0.0  # Target angle
        
        previous_error = 0.0
        
        while True:
            data = mpu.read_all_data()
            current_yaw = data['angles']['yaw']    # Primary control angle
            
            # PD Controller calculation
            error = target_yaw - current_yaw
            derivative = (error - previous_error) / data['dt'] if data['dt'] > 0 else 0
            
            control_output = kp * error + kd * derivative
            
            print(f"\rYaw: {current_yaw:+6.1f}° | Error: {error:+6.1f}° | Control: {control_output:+6.2f}", 
                  end='', flush=True)
            
            previous_error = error
            time.sleep(0.004)
            
    except KeyboardInterrupt:
        print("\nPD Controller demo stopped.")
    
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='MPU6050 IMU Data Reader with CSV Logging')
    parser.add_argument('--log', '-l', action='store_true', help='Start CSV logging immediately')
    parser.add_argument('--filename', '-f', type=str, help='Custom CSV filename')
    parser.add_argument('--pd', action='store_true', help='Run PD controller demo')
    
    args = parser.parse_args()
    
    if args.pd:
        pd_controller_demo()
    else:
        # Auto-start logging if requested
        if args.log:
            print("Auto-starting CSV logging...")
            # This will be handled in the main() function
        main(auto_log=args.log, log_filename=args.filename)