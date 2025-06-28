#!/usr/bin/env python3
"""
Integrated ADCS (Attitude Determination and Control System)
Combines sensor reading, orientation calculation, and PD control
for real-time satellite attitude control using a reaction wheel.
"""

import time
import math
import threading
import board
import busio
import adafruit_veml7700
import RPi.GPIO as GPIO
import smbus
from datetime import datetime

# ── HARDWARE PIN DEFINITIONS ──────────────────────────────
# Motor driver pins
DIR_PIN = 19      # Direction control
ENABLE_PIN = 13   # Enable/PWM pin (used as digital enable)
SLEEP_PIN = 26    # Sleep/Standby pin

# Sensor addresses
MPU_ADDR = 0x68   # MPU-6050 I2C address

# ── GPIO SETUP ────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ENABLE_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(SLEEP_PIN, GPIO.OUT, initial=GPIO.HIGH)

# ── SENSOR INITIALIZATION ─────────────────────────────────
# I2C bus for sensors
i2c = busio.I2C(board.SCL, board.SDA)
veml = adafruit_veml7700.VEML7700(i2c)

# MPU-6050 setup
bus = smbus.SMBus(1)
bus.write_byte_data(MPU_ADDR, 0x6B, 0)  # Wake up MPU-6050

# ── MOTOR CONTROL FUNCTIONS ───────────────────────────────
def rotate_clockwise():
    """Rotate reaction wheel clockwise (full speed)"""
    print("[MOTOR] Rotating clockwise")
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(ENABLE_PIN, GPIO.HIGH)

def rotate_counterclockwise():
    """Rotate reaction wheel counterclockwise (full speed)"""
    print("[MOTOR] Rotating counterclockwise")
    GPIO.output(DIR_PIN, GPIO.HIGH)
    GPIO.output(ENABLE_PIN, GPIO.HIGH)

def stop_motor():
    """Stop reaction wheel"""
    print("[MOTOR] Stopping")
    GPIO.output(ENABLE_PIN, GPIO.LOW)

# ── SENSOR READING FUNCTIONS ──────────────────────────────
def mpu_raw_read(addr):
    """Read raw 16-bit value from MPU-6050 register"""
    hi = bus.read_byte_data(MPU_ADDR, addr)
    lo = bus.read_byte_data(MPU_ADDR, addr + 1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu_data():
    """Read accelerometer and gyroscope data from MPU-6050"""
    try:
        # Read accelerometer (convert to g)
        ax = mpu_raw_read(0x3B) / 16384.0
        ay = mpu_raw_read(0x3D) / 16384.0
        az = mpu_raw_read(0x3F) / 16384.0
        
        # Read gyroscope (convert to degrees/sec)
        gx = mpu_raw_read(0x43) / 131.0
        gy = mpu_raw_read(0x45) / 131.0
        gz = mpu_raw_read(0x47) / 131.0
        
        return ax, ay, az, gx, gy, gz
    except Exception as e:
        print(f"[SENSOR] MPU read error: {e}")
        return 0, 0, 0, 0, 0, 0

def read_lux():
    """Read light sensor data"""
    try:
        return veml.light
    except Exception as e:
        print(f"[SENSOR] VEML read error: {e}")
        return 0

def calculate_orientation(ax, ay, az):
    """
    Calculate yaw angle from accelerometer data for hanging cube
    
    Args:
        ax, ay, az: Accelerometer readings in g
        
    Returns:
        yaw: Rotation angle around vertical Z-axis in degrees
        
    Note: For a cube hanging from ceiling, rotating in horizontal plane,
    we use the horizontal accelerometer components to determine yaw angle
    """
    try:
        # Calculate yaw (rotation around Z-axis) from horizontal components
        # When hanging, gravity is primarily in Z, so X,Y show horizontal orientation
        yaw = math.atan2(ay, ax) * 180.0 / math.pi
        
        return yaw
    except Exception as e:
        print(f"[CALC] Orientation calculation error: {e}")
        return 0

# ── PD CONTROLLER CLASS ───────────────────────────────────
class ADCSController:
    def __init__(self, kp=2.0, kd=0.5, deadband=2.0):
        self.kp = kp                    # Proportional gain
        self.kd = kd                    # Derivative gain
        self.deadband = deadband        # Deadband threshold (degrees)
        
        # Target and current orientations (single axis - yaw only)
        self.target_yaw = 0.0
        self.current_yaw = 0.0
        
        # Control variables
        self.previous_error = 0.0
        self.previous_time = time.time()
        
        # Threading control
        self.running = False
        self.sensor_thread = None
        self.control_thread = None
        self.control_frequency = 10  # Hz
        self.sensor_frequency = 20   # Hz
        
        # Data logging
        self.log_data = []
        self.max_log_entries = 1000
        
        # Current sensor data
        self.sensor_data = {
            'ax': 0, 'ay': 0, 'az': 0,
            'gx': 0, 'gy': 0, 'gz': 0,
            'lux': 0,
            'yaw': 0,
            'timestamp': time.time()
        }
        
    def set_target_orientation(self, yaw):
        """Set target yaw angle"""
        self.target_yaw = yaw
        print(f"[ADCS] Target set to Yaw: {self.target_yaw:.1f}°")
        
    def set_gains(self, kp, kd):
        """Update PD controller gains"""
        self.kp = kp
        self.kd = kd
        print(f"[ADCS] Gains updated: Kp={kp:.2f}, Kd={kd:.2f}")
        
    def set_deadband(self, deadband):
        """Update deadband threshold"""
        self.deadband = deadband
        print(f"[ADCS] Deadband set to {deadband:.1f}°")
        
    def sensor_loop(self):
        """Sensor reading loop - runs in separate thread"""
        print("[ADCS] Sensor loop started")
        
        while self.running:
            try:
                # Read sensor data
                ax, ay, az, gx, gy, gz = read_mpu_data()
                lux = read_lux()
                
                # Calculate orientation
                yaw = calculate_orientation(ax, ay, az)
                
                # Update current orientation
                self.current_yaw = yaw
                
                # Store sensor data
                self.sensor_data = {
                    'ax': ax, 'ay': ay, 'az': az,
                    'gx': gx, 'gy': gy, 'gz': gz,
                    'lux': lux,
                    'yaw': yaw,
                    'timestamp': time.time()
                }
                
                # Log data (keep last N entries)
                if len(self.log_data) >= self.max_log_entries:
                    self.log_data.pop(0)
                self.log_data.append(self.sensor_data.copy())
                
                # Sensor loop timing
                time.sleep(1.0 / self.sensor_frequency)
                
            except Exception as e:
                print(f"[ADCS] Sensor loop error: {e}")
                time.sleep(0.1)
                
        print("[ADCS] Sensor loop stopped")
        
    def control_loop(self):
        """Main control loop - runs in separate thread"""
        print(f"[ADCS] Control loop started (Kp={self.kp:.2f}, Kd={self.kd:.2f})")
        
        while self.running:
            try:
                current_time = time.time()
                dt = current_time - self.previous_time
                
                if dt <= 0:
                    dt = 0.01  # Prevent division by zero
                
                # Calculate yaw error
                yaw_error = self.target_yaw - self.current_yaw
                
                # Handle angle wraparound (normalize to ±180°)
                if yaw_error > 180:
                    yaw_error -= 360
                elif yaw_error < -180:
                    yaw_error += 360
                
                # Calculate derivative
                yaw_derivative = (yaw_error - self.previous_error) / dt
                
                # PD control output
                control_output = self.kp * yaw_error + self.kd * yaw_derivative
                
                # Apply deadband and bang-bang control
                if abs(yaw_error) < self.deadband:
                    stop_motor()
                    if abs(yaw_error) > 0.1:
                        print(f"[ADCS] In deadband: Yaw error={yaw_error:.1f}° (target reached)")
                        
                elif control_output > 0:
                    rotate_clockwise()
                    print(f"[ADCS] CW: Yaw error={yaw_error:.1f}°, derivative={yaw_derivative:.2f}, output={control_output:.2f}")
                    
                elif control_output < 0:
                    rotate_counterclockwise()
                    print(f"[ADCS] CCW: Yaw error={yaw_error:.1f}°, derivative={yaw_derivative:.2f}, output={control_output:.2f}")
                    
                else:
                    stop_motor()
                
                # Update for next iteration
                self.previous_error = yaw_error
                self.previous_time = current_time
                
                # Control loop timing
                time.sleep(1.0 / self.control_frequency)
                
            except Exception as e:
                print(f"[ADCS] Control loop error: {e}")
                stop_motor()
                time.sleep(0.1)
                
        print("[ADCS] Control loop stopped")
        
    def start_adcs(self):
        """Start the ADCS system (sensor reading and control)"""
        if not self.running:
            self.running = True
            self.previous_time = time.time()
            
            # Start sensor thread
            self.sensor_thread = threading.Thread(target=self.sensor_loop, daemon=True)
            self.sensor_thread.start()
            
            # Start control thread
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            
            print("[ADCS] System started")
        else:
            print("[ADCS] System already running")
            
    def stop_adcs(self):
        """Stop the ADCS system"""
        if self.running:
            self.running = False
            
            # Stop threads
            if self.sensor_thread:
                self.sensor_thread.join(timeout=2.0)
            if self.control_thread:
                self.control_thread.join(timeout=2.0)
                
            stop_motor()
            print("[ADCS] System stopped")
        else:
            print("[ADCS] System already stopped")
            
    def get_status(self):
        """Get current ADCS status"""
        return {
            'running': self.running,
            'target_yaw': self.target_yaw,
            'current_yaw': self.current_yaw,
            'yaw_error': self.target_yaw - self.current_yaw,
            'sensor_data': self.sensor_data.copy(),
            'kp': self.kp,
            'kd': self.kd,
            'deadband': self.deadband
        }
        
    def get_recent_data(self, num_points=10):
        """Get recent sensor data points"""
        return self.log_data[-num_points:] if self.log_data else []
        
    def save_log(self, filename=None):
        """Save sensor data log to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"adcs_log_{timestamp}.csv"
            
        try:
            with open(filename, 'w') as f:
                # Write header
                f.write("timestamp,ax,ay,az,gx,gy,gz,lux,yaw\n")
                
                # Write data
                for entry in self.log_data:
                    f.write(f"{entry['timestamp']:.3f},{entry['ax']:.4f},{entry['ay']:.4f},{entry['az']:.4f},")
                    f.write(f"{entry['gx']:.2f},{entry['gy']:.2f},{entry['gz']:.2f},")
                    f.write(f"{entry['lux']:.2f},{entry['yaw']:.2f}\n")
                    
            print(f"[ADCS] Data logged to {filename}")
            return filename
        except Exception as e:
            print(f"[ADCS] Error saving log: {e}")
            return None

# ── GLOBAL ADCS CONTROLLER INSTANCE ──────────────────────
adcs = ADCSController(kp=2.0, kd=0.5, deadband=2.0)

# ── CONVENIENCE FUNCTIONS ────────────────────────────────
def start_adcs_control(target_yaw=0.0):
    """Start ADCS control to target yaw angle"""
    adcs.set_target_orientation(target_yaw)
    adcs.start_adcs()

def stop_adcs_control():
    """Stop ADCS control"""
    adcs.stop_adcs()

def set_target(yaw):
    """Set new target yaw angle"""
    adcs.set_target_orientation(yaw)

def tune_adcs(kp, kd, deadband=None):
    """Tune ADCS controller parameters"""
    adcs.set_gains(kp, kd)
    if deadband is not None:
        adcs.set_deadband(deadband)

def get_adcs_status():
    """Get ADCS status"""
    return adcs.get_status()

def cleanup():
    """Clean up GPIO and stop all operations"""
    adcs.stop_adcs()
    GPIO.cleanup()

# ── MAIN TEST INTERFACE ──────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATED ADCS CONTROL SYSTEM")
    print("=" * 60)
    print("Commands:")
    print("  start [yaw]           - Start ADCS (default: 0°)")
    print("  stop                  - Stop ADCS")
    print("  target <yaw>          - Set target yaw angle")
    print("  tune <kp> <kd>        - Tune PD gains")
    print("  deadband <deg>        - Set deadband threshold")
    print("  status                - Show system status")
    print("  sensors               - Show current sensor readings")
    print("  log [filename]        - Save data log to file")
    print("  manual                - Enter manual motor control")
    print("  quit                  - Exit")
    print("=" * 60)
    
    manual_mode = False
    
    try:
        while True:
            if manual_mode:
                cmd = input("manual> ").strip().lower().split()
            else:
                cmd = input("adcs> ").strip().lower().split()
                
            if not cmd:
                continue
                
            if cmd[0] == "quit" or cmd[0] == "q":
                break
                
            elif cmd[0] == "start":
                if len(cmd) == 1:
                    start_adcs_control()
                elif len(cmd) == 2:
                    try:
                        yaw = float(cmd[1])
                        start_adcs_control(yaw)
                    except ValueError:
                        print("Invalid angle")
                else:
                    print("Usage: start [yaw]")
                    
            elif cmd[0] == "stop":
                stop_adcs_control()
                
            elif cmd[0] == "target" and len(cmd) == 2:
                try:
                    yaw = float(cmd[1])
                    set_target(yaw)
                except ValueError:
                    print("Invalid angle")
                    
            elif cmd[0] == "tune" and len(cmd) == 3:
                try:
                    kp = float(cmd[1])
                    kd = float(cmd[2])
                    tune_adcs(kp, kd)
                except ValueError:
                    print("Invalid gains")
                    
            elif cmd[0] == "deadband" and len(cmd) == 2:
                try:
                    deadband = float(cmd[1])
                    adcs.set_deadband(deadband)
                except ValueError:
                    print("Invalid deadband")
                    
            elif cmd[0] == "status":
                status = get_adcs_status()
                print(f"Running: {status['running']}")
                print(f"Target: Yaw={status['target_yaw']:.1f}°")
                print(f"Current: Yaw={status['current_yaw']:.1f}°")
                print(f"Error: Yaw={status['yaw_error']:.1f}°")
                print(f"Gains: Kp={status['kp']:.2f}, Kd={status['kd']:.2f}, Deadband={status['deadband']:.1f}°")
                
            elif cmd[0] == "sensors":
                data = adcs.sensor_data
                print(f"Timestamp: {data['timestamp']:.2f}")
                print(f"Accelerometer (g): X={data['ax']:.3f}, Y={data['ay']:.3f}, Z={data['az']:.3f}")
                print(f"Gyroscope (°/s): X={data['gx']:.1f}, Y={data['gy']:.1f}, Z={data['gz']:.1f}")
                print(f"Light (lux): {data['lux']:.1f}")
                print(f"Yaw angle: {data['yaw']:.1f}°")
                
            elif cmd[0] == "log":
                if len(cmd) == 2:
                    adcs.save_log(cmd[1])
                else:
                    adcs.save_log()
                    
            elif cmd[0] == "manual":
                manual_mode = True
                adcs.stop_adcs()
                print("Manual mode - Commands: cw, ccw, stop, auto")
                
            elif cmd[0] == "auto" and manual_mode:
                manual_mode = False
                print("Returned to ADCS mode")
                
            elif manual_mode:
                if cmd[0] == "cw":
                    rotate_clockwise()
                elif cmd[0] == "ccw":
                    rotate_counterclockwise()
                elif cmd[0] == "stop":
                    stop_motor()
                else:
                    print("Manual commands: cw, ccw, stop, auto")
                    
            else:
                print("Unknown command. Type 'quit' to exit.")
                
    except KeyboardInterrupt:
        print("\nShutting down...")
        
    finally:
        cleanup()
        print("ADCS system shutdown complete.")
