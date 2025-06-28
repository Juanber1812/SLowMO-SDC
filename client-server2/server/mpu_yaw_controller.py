#!/usr/bin/env python3
"""
MPU6050 Yaw PD Bang-Bang Controller
Uses yaw angle from MPU6050 to control motor with bang-bang (ON/OFF) logic
Combines PD control algorithm with simple binary motor commands
Uses the exact same MPU6050 class and yaw calculation from mpu.py
"""

import time
import RPi.GPIO as GPIO
import smbus2
import math
from datetime import datetime
import csv
import os
import sys
import select
import termios
import tty

# ── GPIO PIN DEFINITIONS ───────────────────────────────────────────────
# Motor control pins (from motor_test.py)
IN1_PIN = 13    # Clockwise control
IN2_PIN = 19    # Counterclockwise control  
SLEEP_PIN = 26  # Motor driver enable

# ── MOTOR CONTROL SETUP ────────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup([IN1_PIN, IN2_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
GPIO.output(SLEEP_PIN, GPIO.HIGH)  # Enable motor driver

def rotate_clockwise():
    """Rotate motor clockwise (full power)"""
    GPIO.output(IN1_PIN, GPIO.HIGH)
    GPIO.output(IN2_PIN, GPIO.LOW)

def rotate_counterclockwise():
    """Rotate motor counterclockwise (full power)"""
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.HIGH)

def stop_motor():
    """Stop motor (no power)"""
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.LOW)

# ── MPU-6050 SETUP FROM MPU.PY ─────────────────────────────────────────
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
        
        # Control mode settings
        self.use_gyro_only = True  # Use pure gyro for control (no accelerometer bias)
        self.disable_accel_correction = False
        self.angle_yaw_pure = 0.0  # Pure gyro integration for control
        
        # Initialize the sensor
        self.sensor_ready = False
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
            self.sensor_ready = True
            
        except Exception as e:
            print(f"Warning: Could not initialize MPU6050: {e}")
            print("The controller will continue but sensor data will not be available.")
            print("Please check connections and try restarting the program.")
            self.sensor_ready = False
    
    def calibrate_gyro(self, samples=2000):
        """Calibrate gyroscope by averaging readings when stationary"""
        try:
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
            
        except Exception as e:
            print(f"Error during calibration: {e}")
            print("Using default calibration values (0, 0, 0)")
            self.gyro_x_cal = 0.0
            self.gyro_y_cal = 0.0
            self.gyro_z_cal = 0.0
    
    def read_raw_data(self, addr):
        """Read raw 16-bit data from sensor with robust error handling"""
        try:
            high = self.bus.read_byte_data(self.device_address, addr)
            low = self.bus.read_byte_data(self.device_address, addr + 1)
            
            # Combine high and low bytes
            value = (high << 8) + low
            
            # Convert to signed 16-bit
            if value >= 32768:
                value = value - 65536
                
            return value
        except OSError as e:
            # Handle all I2C-related OSError exceptions (errno 5, 121, etc.)
            self.sensor_ready = False  # Mark sensor as not ready
            if e.errno in [5, 121]:  # Input/output error or Remote I/O error
                print(f"\nI2C communication error: {e}")
                print("Trying to reconnect to MPU6050...")
                time.sleep(0.1)
                try:
                    # Try to reinitialize the bus connection
                    self.bus.close()
                    self.bus = smbus2.SMBus(1)
                    # Wake up the MPU6050 again
                    self.bus.write_byte_data(self.device_address, self.PWR_MGMT_1, 0)
                    self.sensor_ready = True  # Mark as ready if successful
                    print("Reconnection successful!")
                    return 0  # Return safe value
                except Exception as reconnect_error:
                    print(f"Failed to reconnect: {reconnect_error}")
                    return 0  # Return safe value and continue
            else:
                print(f"\nUnexpected I2C error: {e}")
                return 0  # Return safe value for any other I2C error
    
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
        
        # Apply output filtering for smooth control (remapped)
        self.angle_yaw_output = (self.angle_yaw_output * self.output_filter_alpha + 
                                self.angle_yaw * (1 - self.output_filter_alpha))        # Primary
        self.angle_roll_output = (self.angle_roll_output * self.output_filter_alpha + 
                                self.angle_roll * (1 - self.output_filter_alpha))
        self.angle_pitch_output = (self.angle_pitch_output * self.output_filter_alpha + 
                                 self.angle_pitch * (1 - self.output_filter_alpha))     # Secondary
    
    def get_yaw_for_control_pure(self):
        """Get pure gyro-integrated yaw for control (no accelerometer bias)"""
        self.update_angles()
        return self.angle_yaw_pure if hasattr(self, 'angle_yaw_pure') else self.angle_yaw
    
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

    def attempt_reconnection(self):
        """Try to reconnect to the MPU6050 sensor"""
        try:
            print("\nAttempting to reconnect to MPU6050...")
            # Close and reopen the I2C bus
            self.bus.close()
            self.bus = smbus2.SMBus(1)
            time.sleep(0.1)
            
            # Re-initialize the sensor
            self.initialize_sensor()
            
            if self.sensor_ready:
                print("MPU6050 reconnected successfully!")
            return self.sensor_ready
            
        except Exception as e:
            print(f"Reconnection failed: {e}")
            return False
    
    # ...existing code...
# ── PD BANG-BANG CONTROLLER ────────────────────────────────────────────
class PDBangBangController:
    def __init__(self, kp=1.0, kd=0.1, deadband=2.0, min_pulse_time=0.1):
        """
        PD Bang-Bang Controller
        
        Args:
            kp: Proportional gain
            kd: Derivative gain  
            deadband: Angle deadband in degrees (no action within this range)
            min_pulse_time: Minimum motor pulse duration in seconds
        """
        self.kp = kp
        self.kd = kd
        self.deadband = deadband
        self.min_pulse_time = min_pulse_time
        
        # Control state
        self.target_yaw = 0.0
        self.previous_error = 0.0
        self.last_control_time = 0.0
        self.motor_state = "STOP"  # "CW", "CCW", "STOP"
        self.pulse_start_time = 0.0
        
        # Controller enable/disable
        self.controller_enabled = False  # Controller starts disabled
        self.input_mode = False  # Flag to indicate when user is typing
        
        # Logging
        self.log_data = []
        self.enable_logging = False
        
        # Yaw data logging for settling time analysis
        self.yaw_log_data = []
        self.enable_yaw_logging = False
        self.yaw_log_start_time = None
        
    def set_target(self, target_angle):
        """Set target yaw angle in degrees"""
        self.target_yaw = target_angle
        print(f"Target yaw set to: {target_angle:.1f}°")
    
    def start_controller(self):
        """Start the PD controller"""
        self.controller_enabled = True
        print("Controller STARTED - Motor control active")
    
    def stop_controller(self):
        """Stop the PD controller and motor"""
        self.controller_enabled = False
        self.motor_state = "STOP"
        stop_motor()  # Immediately stop motor
        print("Controller STOPPED - Motor disabled")
    
    def update(self, current_yaw, gyro_rate, dt):
        """
        Update PD controller and return motor command
        
        Args:
            current_yaw: Current yaw angle in degrees
            gyro_rate: Current yaw rate in °/s
            dt: Time step in seconds
            
        Returns:
            motor_command: "CW", "CCW", or "STOP"
        """
        # If controller is disabled or in input mode, always return STOP
        if not self.controller_enabled or self.input_mode:
            return "STOP", 0.0, 0.0
        
        # Calculate error
        error = self.target_yaw - current_yaw
        
        # Calculate derivative (rate of error change)
        if dt > 0:
            derivative = (error - self.previous_error) / dt
        else:
            derivative = 0.0
        
        # PD control output
        pd_output = self.kp * error + self.kd * derivative
        
        # Apply deadband - no action if error is small
        if abs(error) < self.deadband:
            motor_command = "STOP"
        else:
            # Bang-bang logic based on PD output
            if pd_output > 0:
                motor_command = "CW"    # Positive error -> rotate clockwise
            elif pd_output < 0:
                motor_command = "CCW"   # Negative error -> rotate counterclockwise
            else:
                motor_command = "STOP"
        
        # Minimum pulse time logic (prevent chattering)
        current_time = time.time()
        if self.motor_state != motor_command:
            if self.motor_state != "STOP":
                # Check if minimum pulse time has elapsed
                if (current_time - self.pulse_start_time) < self.min_pulse_time:
                    motor_command = self.motor_state  # Continue current command
                else:
                    self.pulse_start_time = current_time
                    self.motor_state = motor_command
            else:
                self.pulse_start_time = current_time
                self.motor_state = motor_command
        
        # Store previous error for next derivative calculation
        self.previous_error = error
        
        # Log data if enabled
        if self.enable_logging:
            self.log_data.append({
                'time': current_time,
                'target': self.target_yaw,
                'current': current_yaw,
                'error': error,
                'derivative': derivative,
                'pd_output': pd_output,
                'motor_cmd': motor_command,
                'gyro_rate': gyro_rate
            })
        
        # Log yaw data for settling time analysis
        if self.enable_yaw_logging:
            relative_time = current_time - self.yaw_log_start_time if self.yaw_log_start_time else 0
            self.yaw_log_data.append({
                'time': current_time,
                'relative_time': relative_time, 
                'yaw_angle': current_yaw,
                'target_yaw': self.target_yaw,
                'error': error,
                'gyro_rate': gyro_rate,
                'motor_cmd': motor_command,
                'controller_active': self.controller_enabled
            })
        
        return motor_command, error, pd_output
    
    def start_logging(self):
        """Start data logging"""
        self.log_data = []
        self.enable_logging = True
        print("Controller logging started")
    
    def stop_logging(self, filename=None):
        """Stop logging and save to CSV"""
        if not self.enable_logging:
            return
            
        self.enable_logging = False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pd_bangbang_log_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'time', 'target', 'current', 'error', 'derivative', 
                    'pd_output', 'motor_cmd', 'gyro_rate'
                ])
                writer.writeheader()
                writer.writerows(self.log_data)
            print(f"Log saved to: {filename}")
        except Exception as e:
            print(f"Error saving log: {e}")
    
    def start_yaw_logging(self):
        """Start yaw data logging for settling time analysis"""
        self.yaw_log_data = []
        self.enable_yaw_logging = True
        self.yaw_log_start_time = time.time()
        print("Yaw data logging started for settling time analysis")
    
    def stop_yaw_logging(self, filename=None):
        """Stop yaw logging and save to CSV"""
        if not self.enable_yaw_logging:
            print("Yaw logging not active!")
            return
            
        self.enable_yaw_logging = False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"yaw_settling_data_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'time', 'relative_time', 'yaw_angle', 'target_yaw', 'error', 
                    'gyro_rate', 'motor_cmd', 'controller_active'
                ])
                writer.writeheader()
                writer.writerows(self.yaw_log_data)
            print(f"Yaw settling data saved to: {filename}")
            
            # Calculate and display settling time analysis
            self.analyze_settling_time()
            
        except Exception as e:
            print(f"Error saving yaw log: {e}")
    
    def analyze_settling_time(self):
        """Analyze settling time from logged data"""
        if not self.yaw_log_data:
            return
            
        print("\n" + "="*50)
        print("SETTLING TIME ANALYSIS")
        print("="*50)
        
        # Find target changes
        target_changes = []
        current_target = None
        
        for i, data in enumerate(self.yaw_log_data):
            if current_target is None or abs(data['target_yaw'] - current_target) > 0.1:
                current_target = data['target_yaw']
                target_changes.append({
                    'time': data['relative_time'],
                    'target': current_target,
                    'index': i
                })
        
        # Calculate settling time for each target change
        settling_threshold = 2.0  # degrees - within 2° of target
        settling_time_threshold = 1.0  # seconds - must stay within threshold for this long
        
        for j, change in enumerate(target_changes):
            target = change['target']
            start_time = change['time']
            start_index = change['index']
            
            # Find when it first reaches within threshold
            first_in_threshold = None
            settling_time = None
            
            # Look for settling from this target change onwards
            for i in range(start_index, len(self.yaw_log_data)):
                data = self.yaw_log_data[i]
                error = abs(data['error'])
                
                if error <= settling_threshold:
                    if first_in_threshold is None:
                        first_in_threshold = data['relative_time']
                    
                    # Check if it stays within threshold for required time
                    check_time = data['relative_time']
                    if check_time - first_in_threshold >= settling_time_threshold:
                        # Verify it stayed within threshold
                        stayed_in_threshold = True
                        for k in range(i - int(settling_time_threshold * 100), i):  # Assuming ~100Hz logging
                            if k >= 0 and k < len(self.yaw_log_data):
                                if abs(self.yaw_log_data[k]['error']) > settling_threshold:
                                    stayed_in_threshold = False
                                    break
                        
                        if stayed_in_threshold:
                            settling_time = check_time - start_time
                            break
                else:
                    first_in_threshold = None
            
            print(f"Target: {target:+6.1f}° | Start: {start_time:6.2f}s | Settling Time: {settling_time:6.2f}s" if settling_time else f"Target: {target:+6.1f}° | Start: {start_time:6.2f}s | Did not settle")
        
        print("="*50)

# ── MAIN CONTROL LOOP ──────────────────────────────────────────────────
def main():
    """Main control loop with interactive commands"""
    print("PD Bang-Bang Controller with MPU6050 Yaw Feedback")
    print("=" * 60)
    
    # Initialize components
    mpu = MPU6050()  # Use the same MPU6050 class from mpu.py
    controller = PDBangBangController(
        kp=2.0,           # Proportional gain
        kd=0.5,           # Derivative gain
        deadband=1.0,     # ±1° deadband
        min_pulse_time=0.2  # 200ms minimum pulse
    )
    
    print("\nSystem ready!")
    print("Single Key Commands (just press the key, no ENTER needed):")
    print("  g          - Start controller (GO)")
    print("  s          - Stop controller")
    print("  z          - Zero current position")
    print("  r          - Reconnect sensor")
    print("TARGET ANGLES:")
    print("  1          - Target   +20°")
    print("  2          - Target   +45°") 
    print("  3          - Target   +90°")
    print("  4          - Target  +135°")
    print("  5          - Target  +180°")
    print("  6          - Target   -20°")
    print("  7          - Target   -45°")
    print("  8          - Target   -90°")
    print("  9          - Target  -135°")
    print("  0          - Target     0°")
    print("LOGGING:")
    print("  l          - Start PD logging")
    print("  x          - Stop PD logging and save")
    print("  y          - Start YAW logging (settling time)")
    print("  t          - Stop YAW logging and analyze")
    print("  q          - Quit")
    print("-" * 60)
    
    # Set terminal to non-blocking mode
    old_settings = None
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
    except:
        print("Warning: Non-blocking input not available")
    
    try:
        loop_count = 0
        last_time = time.time()
        
        while True:
            # Check for single-key commands
            command = check_single_key_input()
            if command:
                if command == 'g':
                    if mpu.sensor_ready:
                        controller.start_controller()
                    else:
                        print("\nError: Sensor not ready! Cannot start controller.")
                elif command == 's':
                    controller.stop_controller()
                elif command == 'r':
                    print("\nAttempting sensor reconnection...")
                    mpu.attempt_reconnection()
                elif command == 'z':
                    if mpu.sensor_ready:
                        mpu.calibrate_at_current_position()
                        controller.set_target(0.0)
                    else:
                        print("\nError: Sensor not ready! Cannot zero position.")
                elif command == '1':
                    controller.set_target(20.0)
                elif command == '2':
                    controller.set_target(45.0)
                elif command == '3':
                    controller.set_target(90.0)
                elif command == '4':
                    controller.set_target(135.0)
                elif command == '5':
                    controller.set_target(180.0)
                elif command == '6':
                    controller.set_target(-20.0)
                elif command == '7':
                    controller.set_target(-45.0)
                elif command == '8':
                    controller.set_target(-90.0)
                elif command == '9':
                    controller.set_target(-135.0)
                elif command == '0':
                    controller.set_target(0.0)
                elif command == 'l':
                    controller.start_logging()
                elif command == 'x':
                    controller.stop_logging()
                elif command == 'y':
                    controller.start_yaw_logging()
                elif command == 't':
                    controller.stop_yaw_logging()
                elif command == 'q':
                    break
            
            # Get yaw angle using the same method as mpu.py
            current_yaw = mpu.get_yaw_for_control_pure()  # Pure gyro yaw (no accelerometer bias)
            
            # Get gyro rate for display
            gyro_x, gyro_y, gyro_z = mpu.read_gyroscope()
            gyro_rate = gyro_z  # Yaw rate
            
            # Auto-stop controller if sensor becomes unavailable
            if not mpu.sensor_ready and controller.controller_enabled:
                print("\nSensor lost! Stopping controller for safety.")
                controller.stop_controller()
            
            # Calculate time step
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Update PD controller
            motor_cmd, error, pd_output = controller.update(current_yaw, gyro_rate, dt)
            
            # Execute motor command only if controller is enabled and not in input mode
            if controller.controller_enabled and not controller.input_mode:
                if motor_cmd == "CW":
                    rotate_clockwise()
                elif motor_cmd == "CCW":
                    rotate_counterclockwise()
                else:
                    stop_motor()
            else:
                stop_motor()  # Ensure motor is stopped when controller is disabled or in input mode
            
            # Display status every 10 loops (~10Hz)
            if loop_count % 10 == 0:
                pd_log_status = " [PD-LOG]" if controller.enable_logging else ""
                yaw_log_status = " [YAW-LOG]" if controller.enable_yaw_logging else ""
                sensor_status = " [SENSOR OK]" if mpu.sensor_ready else " [SENSOR ERR]"
                if controller.input_mode:
                    ctrl_status = " [PAUSE]"
                elif controller.controller_enabled:
                    ctrl_status = " [ON]"
                else:
                    ctrl_status = " [OFF]"
                status = (
                    f"\rYaw: {current_yaw:+7.1f}° | "
                    f"Target: {controller.target_yaw:+7.1f}° | "
                    f"Error: {error:+6.1f}° | "
                    f"Rate: {gyro_rate:+5.1f}°/s | "
                    f"PD: {pd_output:+6.2f} | "
                    f"Motor: {motor_cmd:>4s}{ctrl_status}{sensor_status}{pd_log_status}{yaw_log_status}"
                )
                print(status, end='', flush=True)
            
            loop_count += 1
            time.sleep(0.01)  # 100Hz control loop
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        # Cleanup
        stop_motor()
        GPIO.cleanup()
        
        # Restore terminal settings
        if old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass
        
        # Save any remaining log data
        if controller.enable_logging:
            controller.stop_logging()
        if controller.enable_yaw_logging:
            controller.stop_yaw_logging()
        
        print("Cleanup complete.")

def check_single_key_input():
    """Check for single key press without blocking"""
    try:
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            char = sys.stdin.read(1)
            # Return the character immediately, no need for Enter
            if char and ord(char) >= 32:  # Printable character
                return char.lower()
            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
    except:
        pass
    return None

if __name__ == "__main__":
    main()
