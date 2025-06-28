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
        
        # Calibration values
        self.gyro_x_cal = 0.0
        self.gyro_y_cal = 0.0
        self.gyro_z_cal = 0.0
        self.accel_pitch_cal = 0.0
        self.accel_roll_cal = 0.0
        
        # Angle variables
        self.angle_pitch = 0.0
        self.angle_roll = 0.0
        self.angle_yaw = 0.0
        self.angle_pitch_acc = 0.0
        self.angle_roll_acc = 0.0
        
        # Output angles (filtered)
        self.angle_pitch_output = 0.0
        self.angle_roll_output = 0.0
        self.angle_yaw_output = 0.0
        
        # Filter and timing variables
        self.set_gyro_angles = False
        self.last_time = time.time()
        self.dt = 0.0
        
        # Yaw drift compensation
        self.yaw_drift_rate = 0.0  # deg/s drift rate
        self.yaw_reference_time = time.time()
        self.yaw_zero_velocity_threshold = 0.5  # deg/s
        self.yaw_zero_velocity_count = 0
        self.yaw_drift_samples = []
        
        # Filter parameters (adjustable for PD controller)
        self.complementary_alpha = 0.9996  # Gyro weight (0.9996 = 99.96%)
        self.output_filter_alpha = 0.9     # Output smoothing (90% previous, 10% new)
        
        # Initialize the sensor
        self.initialize_sensor()
        
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
    
    def calibrate_accelerometer(self, pitch_offset=0.0, roll_offset=0.0):
        """Set accelerometer calibration offsets (determine by placing sensor level)"""
        self.accel_pitch_cal = pitch_offset
        self.accel_roll_cal = roll_offset
        print(f"Accelerometer calibration set - Pitch: {pitch_offset:.3f}°, Roll: {roll_offset:.3f}°")
    
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
        
        # Gyro angle calculations (integration)
        # Convert gyro rates to angle changes
        dt_factor = self.dt  # Time step for integration
        
        self.angle_pitch += gyro_z * dt_factor
        self.angle_roll += gyro_y * dt_factor
        self.angle_yaw += gyro_x * dt_factor
        
        # Yaw compensation for pitch and roll (transfer angles during yaw rotation)
        yaw_rad = math.radians(gyro_x * dt_factor)
        self.angle_pitch += self.angle_roll * math.sin(yaw_rad)
        self.angle_roll -= self.angle_pitch * math.sin(yaw_rad)
        
        # Accelerometer angle calculations
        acc_total_vector = math.sqrt(acc_x*acc_x + acc_y*acc_y + acc_z*acc_z)
        
        if acc_total_vector > 0:  # Avoid division by zero
            # Calculate pitch and roll from accelerometer
            self.angle_pitch_acc = math.degrees(math.asin(acc_y / acc_total_vector))
            self.angle_roll_acc = math.degrees(math.asin(acc_z / acc_total_vector)) * -1
            
            # Apply accelerometer calibration
            self.angle_pitch_acc -= self.accel_pitch_cal
            self.angle_roll_acc -= self.accel_roll_cal
        
        # Complementary filter
        if self.set_gyro_angles:
            # Combine gyro and accelerometer data
            self.angle_pitch = (self.angle_pitch * self.complementary_alpha + 
                              self.angle_pitch_acc * (1 - self.complementary_alpha))
            self.angle_roll = (self.angle_roll * self.complementary_alpha + 
                             self.angle_roll_acc * (1 - self.complementary_alpha))
        else:
            # First startup - use accelerometer values
            self.angle_pitch = self.angle_pitch_acc
            self.angle_roll = self.angle_roll_acc
            self.set_gyro_angles = True
        
        # Yaw drift compensation
        self.compensate_yaw_drift(gyro_x)
        
        # Apply output filtering for smooth control
        self.angle_pitch_output = (self.angle_pitch_output * self.output_filter_alpha + 
                                 self.angle_pitch * (1 - self.output_filter_alpha))
        self.angle_roll_output = (self.angle_roll_output * self.output_filter_alpha + 
                                self.angle_roll * (1 - self.output_filter_alpha))
        self.angle_yaw_output = (self.angle_yaw_output * self.output_filter_alpha + 
                               self.angle_yaw * (1 - self.output_filter_alpha))
    
    def compensate_yaw_drift(self, gyro_x):
        """Compensate for yaw drift using zero velocity detection"""
        # Detect if yaw rate is near zero (stationary)
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
        
        # Apply drift compensation
        self.angle_yaw -= self.yaw_drift_rate * self.dt
    
    def reset_yaw(self):
        """Reset yaw angle to zero (useful for reference point)"""
        self.angle_yaw = 0.0
        self.angle_yaw_output = 0.0
        self.yaw_reference_time = time.time()
        print("Yaw angle reset to 0°")
    
    def set_filter_parameters(self, complementary_alpha=None, output_alpha=None):
        """Adjust filter parameters for PD controller tuning"""
        if complementary_alpha is not None:
            self.complementary_alpha = complementary_alpha
            print(f"Complementary filter alpha set to {complementary_alpha}")
        
        if output_alpha is not None:
            self.output_filter_alpha = output_alpha
            print(f"Output filter alpha set to {output_alpha}")
    
    def get_angles(self):
        """Get current angle estimates"""
        return {
            'pitch': self.angle_pitch_output,
            'roll': self.angle_roll_output,
            'yaw': self.angle_yaw_output,
            'pitch_raw': self.angle_pitch,
            'roll_raw': self.angle_roll,
            'yaw_raw': self.angle_yaw
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
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'accel': {'x': acc_x, 'y': acc_y, 'z': acc_z},
            'gyro': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z},
            'temperature': temperature,
            'angles': angles,
            'dt': self.dt,
            'yaw_drift_rate': self.yaw_drift_rate
        }

def main():
    """Main loop to read and display MPU6050 data with attitude estimation"""
    print("Starting MPU6050 Attitude Estimation System...")
    print("Features: Complementary Filter, Yaw Drift Compensation, PD Controller Ready")
    print("Press Ctrl+C to exit")
    print("-" * 90)
    
    try:
        # Initialize sensor
        mpu = MPU6050()
        
        print("System ready! Live data display active (angles + raw sensor data)")
        print("=" * 90)
        
        while True:
            # Read sensor data and update angles
            data = mpu.read_all_data()
            
            # Extract data for display
            accel = data['accel']
            gyro = data['gyro']
            angles = data['angles']
            temp = data['temperature']
            
            # Live display with both angles and raw data (overwrite same line)
            live_display = (
                f"\rPitch: {angles['pitch']:+6.1f}° | "
                f"Roll: {angles['roll']:+6.1f}° | "
                f"Yaw: {angles['yaw']:+6.1f}° | "
                f"Accel: X={accel['x']:+5.2f}g Y={accel['y']:+5.2f}g Z={accel['z']:+5.2f}g | "
                f"Gyro: X={gyro['x']:+5.1f} Y={gyro['y']:+5.1f} Z={gyro['z']:+5.1f} °/s | "
                f"T: {temp:4.1f}°C"
            )
            
            # Update live display (no logging)
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
        print("Cleanup complete.")

def pd_controller_demo():
    """Demonstration of PD controller integration"""
    print("PD Controller Demo - Yaw Stabilization")
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
            current_yaw = data['angles']['yaw']
            
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
    
    if len(sys.argv) > 1 and sys.argv[1] == "pd":
        pd_controller_demo()
    else:
        main()