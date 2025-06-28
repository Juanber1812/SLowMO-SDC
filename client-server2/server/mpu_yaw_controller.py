#!/usr/bin/env python3
"""
MPU6050 Yaw PD Bang-Bang Controller
Uses yaw angle from MPU6050 to control motor with bang-bang (ON/OFF) logic
Combines PD control algorithm with simple binary motor commands
"""

import time
import board, busio
import adafruit_veml7700
import RPi.GPIO as GPIO
import smbus
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
IN1_PIN = 19    # Clockwise control
IN2_PIN = 13    # Counterclockwise control  
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

# ── MPU-6050 SETUP ─────────────────────────────────────────────────────
MPU_ADDR = 0x68
bus = smbus.SMBus(1)
bus.write_byte_data(MPU_ADDR, 0x6B, 0)  # Exit sleep mode

def mpu_raw(addr):
    """Read raw 16-bit data from MPU6050"""
    hi = bus.read_byte_data(MPU_ADDR, addr)
    lo = bus.read_byte_data(MPU_ADDR, addr+1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu():
    """Read MPU6050 accelerometer and gyroscope data"""
    ax = mpu_raw(0x3B) / 16384.0  # Accelerometer X (g)
    ay = mpu_raw(0x3D) / 16384.0  # Accelerometer Y (g)
    az = mpu_raw(0x3F) / 16384.0  # Accelerometer Z (g)
    gx = mpu_raw(0x43) / 131.0    # Gyroscope X (°/s)
    gy = mpu_raw(0x45) / 131.0    # Gyroscope Y (°/s)
    gz = mpu_raw(0x47) / 131.0    # Gyroscope Z (°/s)
    return ax, ay, az, gx, gy, gz

# ── YAW ANGLE CALCULATION ──────────────────────────────────────────────
class YawEstimator:
    def __init__(self):
        self.yaw_angle = 0.0
        self.yaw_gyro = 0.0
        self.yaw_accel = 0.0
        self.last_time = time.time()
        self.initialized = False
        
        # Complementary filter parameter
        self.alpha = 0.98  # Gyro weight (98% gyro, 2% accelerometer)
        
        # Calibration offsets (determined experimentally)
        self.gyro_z_offset = 0.0
        self.accel_offset = 0.0
        
    def calibrate_gyro(self, samples=1000):
        """Calibrate gyroscope Z-axis offset"""
        print("Calibrating gyroscope... Keep sensor still!")
        gyro_sum = 0.0
        
        for i in range(samples):
            _, _, _, _, _, gz = read_mpu()
            gyro_sum += gz
            if i % 100 == 0:
                print(f"Calibration: {(i/samples)*100:.1f}%")
            time.sleep(0.01)
        
        self.gyro_z_offset = gyro_sum / samples
        print(f"Gyro Z offset: {self.gyro_z_offset:.3f} °/s")
    
    def update(self):
        """Update yaw angle using complementary filter"""
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Read sensor data
        ax, ay, az, gx, gy, gz = read_mpu()
        
        # Apply gyro calibration
        gz -= self.gyro_z_offset
        
        # Gyroscope integration (primary source for yaw)
        self.yaw_gyro += gz * dt
        
        # Accelerometer yaw estimation (for drift correction)
        # Using atan2 for better quadrant handling
        acc_magnitude = math.sqrt(ax*ax + ay*ay + az*az)
        if acc_magnitude > 0.1:  # Avoid division by zero
            # Simple yaw estimation from accelerometer (limited accuracy)
            self.yaw_accel = math.degrees(math.atan2(ay, math.sqrt(ax*ax + az*az)))
        
        # Complementary filter
        if not self.initialized:
            self.yaw_angle = self.yaw_accel
            self.yaw_gyro = self.yaw_accel
            self.initialized = True
        else:
            self.yaw_angle = self.alpha * self.yaw_gyro + (1 - self.alpha) * self.yaw_accel
            
        return self.yaw_angle, gz  # Return angle and gyro rate
    
    def reset(self):
        """Reset yaw angle to zero"""
        self.yaw_angle = 0.0
        self.yaw_gyro = 0.0
        self.yaw_accel = 0.0
        print("Yaw angle reset to 0°")

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
        
        # Logging
        self.log_data = []
        self.enable_logging = False
        
    def set_target(self, target_angle):
        """Set target yaw angle in degrees"""
        self.target_yaw = target_angle
        print(f"Target yaw set to: {target_angle:.1f}°")
    
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

# ── MAIN CONTROL LOOP ──────────────────────────────────────────────────
def main():
    """Main control loop with interactive commands"""
    print("PD Bang-Bang Controller with MPU6050 Yaw Feedback")
    print("=" * 60)
    
    # Initialize components
    yaw_estimator = YawEstimator()
    controller = PDBangBangController(
        kp=2.0,           # Proportional gain
        kd=0.5,           # Derivative gain
        deadband=1.0,     # ±1° deadband
        min_pulse_time=0.2  # 200ms minimum pulse
    )
    
    # Calibrate gyroscope
    print("\nCalibrating gyroscope...")
    yaw_estimator.calibrate_gyro(samples=500)
    
    print("\nSystem ready!")
    print("Commands:")
    print("  t <angle>  - Set target angle (e.g., 't 45')")
    print("  z          - Zero current position")
    print("  l          - Start logging")
    print("  s          - Stop logging and save")
    print("  p <kp> <kd> - Set PD gains (e.g., 'p 2.0 0.5')")
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
            # Check for keyboard commands
            command = check_keyboard_input()
            if command:
                if command.startswith('t '):
                    try:
                        target = float(command.split()[1])
                        controller.set_target(target)
                    except:
                        print("\nInvalid target angle")
                elif command == 'z':
                    yaw_estimator.reset()
                    controller.set_target(0.0)
                elif command == 'l':
                    controller.start_logging()
                elif command == 's':
                    controller.stop_logging()
                elif command.startswith('p '):
                    try:
                        parts = command.split()
                        kp, kd = float(parts[1]), float(parts[2])
                        controller.kp = kp
                        controller.kd = kd
                        print(f"\nPD gains set: Kp={kp}, Kd={kd}")
                    except:
                        print("\nInvalid PD gains")
                elif command == 'q':
                    break
            
            # Update yaw estimation
            current_yaw, gyro_rate = yaw_estimator.update()
            
            # Calculate time step
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            # Update PD controller
            motor_cmd, error, pd_output = controller.update(current_yaw, gyro_rate, dt)
            
            # Execute motor command
            if motor_cmd == "CW":
                rotate_clockwise()
            elif motor_cmd == "CCW":
                rotate_counterclockwise()
            else:
                stop_motor()
            
            # Display status every 10 loops (~10Hz)
            if loop_count % 10 == 0:
                log_status = " [LOG]" if controller.enable_logging else ""
                status = (
                    f"\rYaw: {current_yaw:+6.1f}° | "
                    f"Target: {controller.target_yaw:+6.1f}° | "
                    f"Error: {error:+6.1f}° | "
                    f"Rate: {gyro_rate:+5.1f}°/s | "
                    f"PD: {pd_output:+6.2f} | "
                    f"Motor: {motor_cmd:>4s}{log_status}"
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
        
        print("Cleanup complete.")

def check_keyboard_input():
    """Check for keyboard input without blocking"""
    try:
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            line = ""
            while True:
                char = sys.stdin.read(1)
                if char == '\n' or char == '\r':
                    return line.strip().lower()
                elif char == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                elif char == '\x7f':  # Backspace
                    if line:
                        line = line[:-1]
                        print('\b \b', end='', flush=True)
                else:
                    line += char
                    print(char, end='', flush=True)
    except:
        pass
    return None

if __name__ == "__main__":
    main()
