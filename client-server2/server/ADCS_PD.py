#!/usr/bin/env python3
"""
🛰️ UNIFIED ADCS CONTROLLER - Step 1: Sensor Reading & Basic Communication
Combines MPU6050 (IMU) + VEML7700 (3x Lux) sensors with server communication interface
- Real-time sensor data acquisition (20Hz)
- Thread-safe data sharing
- Client command handling for calibration
- Live data broadcasting at 20Hz
- PWM PD Motor Control for Yaw Attitude Control
"""

import time
import board
import busio
import smbus2
import threading
import math
import traceback
from datetime import datetime
import logging
import csv
import os
from collections import deque
import datetime

# ── THREADING CONFIGURATION ───────────────────────────────────────────────
# Use standard threading only to avoid gevent/threading conflicts
# This ensures compatibility with Flask-SocketIO server environment
print("ℹ️ Using standard threading for ADCS control")

def create_thread(target, daemon=True):
    """Create a standard daemon thread for ADCS control
    
    Uses only standard threading to avoid conflicts with gevent monkey-patching.
    All threads are created as daemon threads to ensure clean shutdown.
    """
    thread = threading.Thread(target=target, daemon=daemon)
    return thread

# Try to import hardware libraries
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: RPi.GPIO not available - motor control disabled")
    GPIO_AVAILABLE = False

try:
    from adafruit_veml7700 import VEML7700
    LUX_AVAILABLE = True
except ImportError:
    print("Warning: VEML7700 library not available - lux sensors disabled")
    LUX_AVAILABLE = False

# Constants
LOG_FREQUENCY = 20  # Hz - Data acquisition frequency (balanced for control stability)
DISPLAY_FREQUENCY = 20  # Hz - Server broadcast frequency (matches acquisition rate)

# LUX sensor constants
MUX_ADDRESS = 0x70
LUX_CHANNELS = [1, 2, 3]

# MPU6050 constants  
MPU_ADDRESS = 0x68

# ── PD CONTROLLER DEFAULT VALUES ───────────────────────────────────────────
# These values can be easily changed here and will be used for initialization
# The set_pd_values function can still change these during runtime
DEFAULT_KP = 10.0           # Proportional gain
DEFAULT_KD = 2.0            # Derivative gain  
DEFAULT_MAX_POWER = 100     # Maximum PWM power (0-100%)
DEFAULT_DEADBAND = 1.0      # Deadband in degrees (±1° no action zone)
DEFAULT_INTEGRAL_LIMIT = 50.0  # Integral windup protection limit

# ── GPIO PIN DEFINITIONS ───────────────────────────────────────────────
# Motor control pins (PWM)
IN1_PIN = 13    # Clockwise control
IN2_PIN = 19    # Counterclockwise control  
SLEEP_PIN = 26  # Motor driver enable
PWM_FREQUENCY = 1000  # Hz (1kHz for smooth motor control)

# Global PWM objects
motor_cw_pwm = None
motor_ccw_pwm = None

# ── MOTOR CONTROL FUNCTIONS ────────────────────────────────────────────
def setup_motor_control():
    """Setup GPIO pins for PWM motor control"""
    global motor_cw_pwm, motor_ccw_pwm
    if not GPIO_AVAILABLE:
        return False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup([IN1_PIN, IN2_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
        
        # Create PWM instances for each direction
        motor_cw_pwm = GPIO.PWM(IN1_PIN, PWM_FREQUENCY)
        motor_ccw_pwm = GPIO.PWM(IN2_PIN, PWM_FREQUENCY)
        
        # Start PWM with 0% duty cycle (motor off)
        motor_cw_pwm.start(0)
        motor_ccw_pwm.start(0)
        
        # Enable motor driver
        GPIO.output(SLEEP_PIN, GPIO.HIGH)
        print("✓ PWM Motor control GPIO initialized")
        return True
    except Exception as e:
        print(f"✗ PWM Motor control GPIO initialization failed: {e}")
        return False

def set_motor_power(power):
    """
    Set motor power using PWM
    Args:
        power: -100 to 100 (negative = CCW, positive = CW, 0 = stop)
    """
    global motor_cw_pwm, motor_ccw_pwm
    if not GPIO_AVAILABLE or not motor_cw_pwm or not motor_ccw_pwm:
        return
    
    # Clamp power to valid range
    power = max(-100, min(100, power))
    
    # Debug: Print when motor power is first set (only for non-zero values to reduce spam)
    if power != 0 and not hasattr(set_motor_power, '_first_power_set'):
        print(f"[MOTOR DEBUG] First motor power set: {power}")
        set_motor_power._first_power_set = True
    
    try:
        if power > 0:  # Clockwise
            motor_ccw_pwm.ChangeDutyCycle(0)
            motor_cw_pwm.ChangeDutyCycle(abs(power))
        elif power < 0:  # Counter-clockwise
            motor_cw_pwm.ChangeDutyCycle(0)
            motor_ccw_pwm.ChangeDutyCycle(abs(power))
        else:  # Stop
            motor_cw_pwm.ChangeDutyCycle(0)
            motor_ccw_pwm.ChangeDutyCycle(0)
        
        time.sleep(0.001)  # Brief delay to avoid I2C interference
    except Exception as e:
        print(f"[MOTOR DEBUG] Error setting motor power: {e}")
        import traceback
        traceback.print_exc()

def rotate_clockwise():
    """Rotate motor clockwise (full power) - for manual control"""
    set_motor_power(100)

def rotate_counterclockwise():
    """Rotate motor counterclockwise (full power) - for manual control"""
    set_motor_power(-100)

def stop_motor():
    """Stop motor (no power) with small delay for hardware stability"""
    set_motor_power(0)
    # Small delay to ensure motor hardware settles before potential restart
    time.sleep(0.01)

def cleanup_motor_control():
    """Cleanup GPIO pins and PWM"""
    global motor_cw_pwm, motor_ccw_pwm
    if GPIO_AVAILABLE:
        try:
            if motor_cw_pwm:
                motor_cw_pwm.stop()
            if motor_ccw_pwm:
                motor_ccw_pwm.stop()
            GPIO.output(SLEEP_PIN, GPIO.LOW)  # Disable motor driver
            GPIO.cleanup()
        except:
            pass

# --- Utility function removed - using full angle range to infinity ---

class MPU6050Sensor:
    """Dedicated MPU6050 sensor class for ADCS"""
    
    def __init__(self, bus_number=1, device_address=0x68):
        self.bus = smbus2.SMBus(bus_number)
        self.device_address = device_address
        
        # Calibration values - unified system
        self.gyro_x_cal = 0.0
        self.gyro_y_cal = 0.0
        self.gyro_z_cal = 0.0
        
        # Calibration state tracking
        self.calibration_type = "raw"  # "raw", "auto", "manual"
        
        # Angle variables (spacecraft convention: yaw is primary control axis)
        self.angle_yaw = 0.0      # Primary control angle - unified calibrated value
        self.angle_roll = 0.0
        self.angle_pitch = 0.0
        
        # Timing variables
        self.last_time = time.time()
        self.dt = 0.0
        
        # Sensor status
        self.sensor_ready = False
        self.initialize_sensor()
    
    def initialize_sensor(self):
        """Initialize MPU6050 with proper configuration"""
        try:
            # Wake up the MPU6050
            self.bus.write_byte_data(self.device_address, 0x6B, 0)
            
            # Configure for high-speed, stable operation
            self.bus.write_byte_data(self.device_address, 0x19, 0)   # Sample rate divider (1kHz)
            self.bus.write_byte_data(self.device_address, 0x1C, 0)   # Accel ±2g
            self.bus.write_byte_data(self.device_address, 0x1B, 0)   # Gyro ±250°/s
            self.bus.write_byte_data(self.device_address, 0x1A, 0)   # No filter for max speed
            
            print("✓ MPU6050 initialized successfully")
            time.sleep(0.1)
            
            # Skip automatic calibration - use raw values until calibration command is sent
            print("ℹ️ MPU6050 ready - using raw values (calibration available on command)")
            self.sensor_ready = True
            
        except Exception as e:
            print(f"✗ MPU6050 initialization failed: {e}")
            self.sensor_ready = False
    
    def calibrate_gyro(self, samples=2000):
        """Calibrate gyroscope - keep sensor stationary during this process"""
        print("🔧 Calibrating MPU6050... Keep sensor stationary!")
        
        gyro_sum = [0, 0, 0]
        
        for i in range(samples):
            try:
                gyro_data = self.read_gyroscope_raw()
                if gyro_data:
                    for j in range(3):
                        gyro_sum[j] += gyro_data[j]
                
                # Progress indicator
                if i % 400 == 0:
                    print(f"Calibration progress: {(i/samples)*100:.1f}%")
                
                time.sleep(0.004)  # 250Hz sampling for thorough calibration
            except:
                continue
        
        self.gyro_x_cal = gyro_sum[0] / samples
        self.gyro_y_cal = gyro_sum[1] / samples  
        self.gyro_z_cal = gyro_sum[2] / samples
        self.calibration_type = "auto"  # Mark as auto-calibrated
        
        print(f"✓ MPU6050 auto-calibration complete!")
        print(f"  Offsets - X: {self.gyro_x_cal:.3f}, Y: {self.gyro_y_cal:.3f}, Z: {self.gyro_z_cal:.3f}")
        print(f"  Calibration type: {self.calibration_type}")
    
    def set_manual_calibration(self, gyro_z_offset):
        """Set manual calibration for Z-axis gyro"""
        self.gyro_z_cal = gyro_z_offset
        self.calibration_type = "manual"  # Mark as manually calibrated
        print(f"✓ MPU6050 manual calibration set!")
        print(f"  Z-axis offset: {self.gyro_z_cal:.3f}")
        print(f"  Calibration type: {self.calibration_type}")
    
    def read_raw_data(self, addr):
        """Read raw 16-bit data from sensor"""
        if not self.sensor_ready:
            return 0
        try:
            high = self.bus.read_byte_data(self.device_address, addr)
            low = self.bus.read_byte_data(self.device_address, addr + 1)
            value = (high << 8) + low
            return value - 65536 if value >= 32768 else value
        except:
            return 0
    
    def read_gyroscope_raw(self):
        """Read raw gyroscope data"""
        if not self.sensor_ready:
            return None
        try:
            gx = self.read_raw_data(0x43) / 131.0  # Convert to deg/s
            gy = self.read_raw_data(0x45) / 131.0
            gz = self.read_raw_data(0x47) / 131.0
            return [gx, gy, gz]
        except:
            return None
    
    def read_gyroscope(self):
        """Read calibrated gyroscope data"""
        gyro_raw = self.read_gyroscope_raw()
        if not gyro_raw:
            return [0.0, 0.0, 0.0]
        
        # Apply calibration
        return [
            gyro_raw[0] - self.gyro_x_cal,
            gyro_raw[1] - self.gyro_y_cal, 
            gyro_raw[2] - self.gyro_z_cal
        ]
    
    def read_accelerometer(self):
        """Read accelerometer data"""
        if not self.sensor_ready:
            return [0.0, 0.0, 0.0]
        try:
            ax = self.read_raw_data(0x3B) / 16384.0  # Convert to g
            ay = self.read_raw_data(0x3D) / 16384.0
            az = self.read_raw_data(0x3F) / 16384.0
            return [ax, ay, az]
        except:
            return [0.0, 0.0, 0.0]
    
    def read_temperature(self):
        """Read MPU6050 temperature"""
        if not self.sensor_ready:
            return 0.0
        try:
            temp_raw = self.read_raw_data(0x41)
            return (temp_raw / 340.0) + 36.53
        except:
            return 0.0
    
    def update_angles(self):
        """Update yaw angle using gyro integration - unified calibrated system"""
        current_time = time.time()
        self.dt = current_time - self.last_time
        self.last_time = current_time
        
        # Read gyroscope data (always uses current calibration)
        gyro = self.read_gyroscope()
        
        if gyro and self.dt > 0:
            # Integrate yaw angle (Z-axis gyro) - no wrapping, full range
            self.angle_yaw += gyro[2] * self.dt  # Primary control angle

            # Update other angles for completeness
            self.angle_roll += gyro[1] * self.dt
            self.angle_pitch += gyro[0] * self.dt
    
    def get_yaw_angle(self):
        """Get current calibrated yaw angle for control"""
        self.update_angles()
        return self.angle_yaw  # Always returns unified calibrated value
    
    def zero_yaw_position(self):
        """Zero the current yaw position - set as reference"""
        self.angle_yaw = 0.0
        self.angle_roll = 0.0
        self.angle_pitch = 0.0
        print(f"✓ Yaw position zeroed - current orientation set as zero reference (calibration: {self.calibration_type})")
    
    def attempt_reconnection(self):
        """Try to reconnect to the MPU6050 sensor"""
        try:
            print("🔄 Attempting MPU6050 reconnection...")
            self.bus.close()
            self.bus = smbus2.SMBus(1)
            time.sleep(0.1)
            self.initialize_sensor()
            return self.sensor_ready
        except Exception as e:
            print(f"✗ MPU6050 reconnection failed: {e}")
            return False

    # Removed duplicate wrap_angle method - using full angle range

    def get_zeroed_yaw(self, mpu_yaw):
        """Return yaw adjusted so sun is at 0° using the last detected offset."""
        offset = getattr(self, "lux_zero_offset", 0.0)
        return self.wrap_angle(mpu_yaw - offset)

class LuxSensorManager:
    """Manages VEML7700 lux sensors with multiplexer"""
    
    def __init__(self):
        self.lux_i2c = None
        self.lux_sensors = {}
        self.sensors_ready = False
        
        if LUX_AVAILABLE:
            self.initialize_lux_sensors()
    
    def initialize_lux_sensors(self):
        """Initialize VEML7700 lux sensors"""
        try:
            self.lux_i2c = busio.I2C(board.SCL, board.SDA)
            self.lux_sensors = {}
            
            print("🔧 Initializing VEML7700 lux sensors...")
            for ch in LUX_CHANNELS:
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    sensor = VEML7700(self.lux_i2c)
                    # Test sensor
                    test_read = sensor.lux
                    self.lux_sensors[ch] = sensor
                    print(f"✓ Lux channel {ch} initialized (test: {test_read:.1f} lux)")
                except Exception as e:
                    print(f"✗ Lux channel {ch} failed: {e}")
                    self.lux_sensors[ch] = None
            
            active_sensors = len([s for s in self.lux_sensors.values() if s is not None])
            print(f"✓ {active_sensors}/{len(LUX_CHANNELS)} lux sensors ready")
            self.sensors_ready = active_sensors > 0
            
        except Exception as e:
            print(f"✗ Lux sensor initialization failed: {e}")
            self.sensors_ready = False
    
    def select_lux_channel(self, channel):
        """Select multiplexer channel for lux sensors"""
        if 0 <= channel <= 7 and self.lux_i2c:
            self.lux_i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.002)
    
    def read_lux_sensors(self):
        """Read all lux sensors"""
        lux_data = {ch: 0.0 for ch in LUX_CHANNELS}
        
        if not self.sensors_ready:
            return lux_data
        
        for ch in LUX_CHANNELS:
            try:
                if ch in self.lux_sensors and self.lux_sensors[ch] is not None:
                    self.select_lux_channel(ch)
                    lux_data[ch] = self.lux_sensors[ch].lux
                else:
                    lux_data[ch] = 0.0
            except Exception as e:
                # Try to reinitialize failed sensor
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    self.lux_sensors[ch] = VEML7700(self.lux_i2c)
                    lux_data[ch] = self.lux_sensors[ch].lux
                except:
                    lux_data[ch] = 0.0
                    self.lux_sensors[ch] = None
        
        return lux_data

class PDControllerPWM:
    """
    PWM-based PD Controller for smooth motor control
    """
    def __init__(self, kp=DEFAULT_KP, kd=DEFAULT_KD, max_power=DEFAULT_MAX_POWER, deadband=DEFAULT_DEADBAND, integral_limit=DEFAULT_INTEGRAL_LIMIT):
        """
        PWM PD Controller
        
        Args:
            kp: Proportional gain (default from DEFAULT_KP)
            kd: Derivative gain (default from DEFAULT_KD)
            max_power: Maximum PWM power 0-100% (default from DEFAULT_MAX_POWER)
            deadband: Angle deadband in degrees (default from DEFAULT_DEADBAND)
            integral_limit: Maximum integral windup protection (default from DEFAULT_INTEGRAL_LIMIT)
        """
        self.kp = kp
        self.kd = kd
        self.max_power = max_power
        self.deadband = deadband
        self.integral_limit = integral_limit
        
        # Control state
        self.target_yaw = 0.0
        self.previous_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
        
        # Controller enable/disable
        self.controller_enabled = False
        self.input_mode = False
        
        # Logging
        self.log_data = []
        self.enable_logging = False
        
        # Yaw data logging for settling time analysis
        self.yaw_log_data = []
        self.enable_yaw_logging = False
        self.yaw_log_start_time = None
        
    def set_target(self, target_angle):
        """Set target yaw angle in degrees - no wrapping, full range"""
        self.target_yaw = target_angle  # Use full angle range
        # Reset integral when target changes to prevent windup
        self.integral = 0.0
        # print(f"Target yaw set to: {self.target_yaw:.1f}°")  # Commented out to reduce spam
    
    def start_controller(self):
        """Start the PD controller"""
        print(f"[PD DEBUG] Starting PD controller...")
        self.controller_enabled = True
        self.integral = 0.0  # Reset integral
        print(f"[PD DEBUG] PD controller started - enabled: {self.controller_enabled}")
        # print("PWM PD Controller STARTED - Motor control active")  # Commented out to reduce spam
    
    def stop_controller(self):
        """Stop the PD controller and motor with proper cleanup"""
        print(f"[PD DEBUG] Stopping PD controller...")
        self.controller_enabled = False
        self.integral = 0.0
        stop_motor()  # Immediately stop motor
        
        # Wait for control thread to finish cleanly
        if hasattr(self, 'control_thread') and self.control_thread and self.control_thread.is_alive():
            try:
                self.stop_control_thread = True
                self.control_thread.join(timeout=2.0)  # Wait up to 2 seconds
                if self.control_thread.is_alive():
                    print(f"[PD DEBUG] Warning: Control thread did not stop cleanly")
                else:
                    print(f"[PD DEBUG] Control thread stopped cleanly")
            except Exception as e:
                print(f"[PD DEBUG] Error stopping control thread: {e}")
        
        print(f"[PD DEBUG] PD controller stopped")
        # print("PWM PD Controller STOPPED - Motor disabled")  # Commented out to reduce spam
    
    def update(self, current_yaw, gyro_rate, dt):
        """
        Update PWM PD controller and return motor power
        
        Args:
            current_yaw: Current yaw angle in degrees
            gyro_rate: Current yaw rate in °/s
            dt: Time step in seconds
            
        Returns:
            motor_power: PWM power (-100 to 100)
            error: Current error in degrees
            pd_output: Raw PD output before limiting
        """
        # Calculate error - no wrapping, direct difference
        error = self.target_yaw - current_yaw
        
        # If controller is disabled or in input mode, don't execute control
        if not self.controller_enabled or self.input_mode:
            return 0, error, 0.0
        
        # Apply deadband - no action if error is small
        if abs(error) < self.deadband:
            motor_power = 0
            pd_output = 0.0
        else:
            # Calculate derivative
            if dt > 0:
                derivative = (error - self.previous_error) / dt
            else:
                derivative = 0.0
            
            # PD control output
            pd_output = self.kp * error + self.kd * derivative
            
            # Convert to motor power (-100 to +100)
            motor_power = pd_output
            
            # Limit motor power to maximum
            motor_power = max(-self.max_power, min(self.max_power, motor_power))
            
            # Apply minimum power threshold (20% minimum when active)
            if motor_power != 0:  # Only apply minimum when motor should be active
                if motor_power > 0:
                    motor_power = max(5, motor_power)  # Minimum 20% CW
                else:
                    motor_power = min(-5, motor_power)  # Minimum 20% CCW
        
        # Apply motor power
        if self.controller_enabled:
            set_motor_power(motor_power)
        
        # Store previous error for next derivative calculation
        self.previous_error = error
        
        # Log data if enabled
        current_time = time.time()
        if self.enable_logging:
            self.log_data.append({
                'time': current_time,
                'target': self.target_yaw,
                'current': current_yaw,
                'error': error,
                'derivative': derivative if 'derivative' in locals() else 0.0,
                'pd_output': pd_output,
                'motor_power': motor_power,
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
                'motor_power': motor_power,
                'controller_active': self.controller_enabled
            })
        
        return motor_power, error, pd_output

class ADCSController:
    """
    Unified ADCS Controller - Step 1: Sensor Reading & Communication Interface
    """
    
    def __init__(self):
        print("🛰️ Initializing UNIFIED ADCS Controller...")
        
        # Initialize sensor components
        self.mpu_sensor = MPU6050Sensor()
        self.lux_manager = LuxSensorManager()
        
        # Initialize motor control
        self.motor_available = setup_motor_control()
        self.running = True
        self.manual_control_active = False
        self.status = "Initializing"
        
        # Initialize PWM PD controller with default values
        self.pd_controller = PDControllerPWM(
            kp=DEFAULT_KP,          # Proportional gain
            kd=DEFAULT_KD,          # Derivative gain
            max_power=DEFAULT_MAX_POWER,  # Maximum PWM power
            deadband=DEFAULT_DEADBAND     # Deadband (±degrees)
        )
        
        # Shared data and threading
        self.data_thread = None
        self.control_thread = None
        self.stop_data_thread = False
        self.stop_control_thread = False
        
        # Use standard threading locks only to avoid gevent conflicts
        self.data_lock = threading.RLock()
            
        self.last_reading_time = time.time()
        
        # Current sensor data (shared between threads)
        self.current_data = {
            'mpu': {
                'yaw': 0.0, 'roll': 0.0, 'pitch': 0.0, 'temp': 0.0,
                'gyro_rate_x': 0.0, 'gyro_rate_y': 0.0, 'gyro_rate_z': 0.0,
                'angle_x': 0.0, 'angle_y': 0.0, 'angle_z': 0.0
            },
            'lux': {ch: 0.0 for ch in LUX_CHANNELS},
            'status': 'Initializing',
            'controller': {
                'enabled': False,
                'target_yaw': 0.0,
                'error': 0.0,
                'motor_power': 0,
                'pd_output': 0.0
            }
        }
        
        # Yaw history for timestamp matching
        self.yaw_history = deque(maxlen=100)  # Store (timestamp, yaw) tuples
        
        # Auto zero tag control with request-response system
        self.auto_zero_tag_enabled = False
        self.auto_zero_tag_target_set = False  # Track if we've already set target to 0
        self.last_rtt_ms = 0  # Last measured round-trip time in milliseconds
        
        # Request-response system for AprilTag data
        self.apriltag_request_timer = None
        self.apriltag_request_start_time = 0
        self.apriltag_request_interval = 2.0  # Request every 2 seconds
        self.apriltag_request_callback = None  # Callback to send requests to server
        
        # Start high-speed data acquisition
        self.start_data_thread()
        
        # Start control thread
        self.start_control_thread()
        
        # print("✓ ADCS Controller initialization complete")  # Commented out to reduce spam
    
    def start_data_thread(self):
        """Start high-speed data acquisition thread"""
        self.stop_data_thread = False
        self.data_thread = create_thread(target=self._data_thread_worker)
        self.data_thread.start()
        # print(f"🚀 Data acquisition started at {LOG_FREQUENCY}Hz")  # Commented out to reduce spam
    
    def _data_thread_worker(self):
        """High-speed sensor data acquisition worker"""
        interval = 1.0 / LOG_FREQUENCY
        next_read_time = time.time()
        
        while not self.stop_data_thread:
            try:
                current_time = time.time()
                
                if current_time >= next_read_time:
                    try:
                        # Read all sensors
                        new_data = self.read_all_sensors()
                        
                        # Thread-safe update
                        with self.data_lock:
                            self.current_data.update(new_data)
                            self.last_reading_time = current_time
                            # Store yaw history for timestamp matching
                            self.yaw_history.append((current_time, new_data['mpu']['yaw']))
                        
                        next_read_time += interval
                        
                    except Exception as e:
                        print(f"Error in data thread: {e}")
                        with self.data_lock:
                            self.current_data['status'] = 'Error'
                
                time.sleep(0.001)  # 1ms sleep
                
            except (KeyboardInterrupt, SystemExit):
                # Handle graceful shutdown
                print("Data thread received shutdown signal")
                break
            except Exception as e:
                print(f"Unexpected error in data thread: {e}")
                time.sleep(0.01)  # Brief pause on unexpected errors
    
    def start_control_thread(self):
        """Start high-speed control thread"""
        self.stop_control_thread = False
        self.control_thread = create_thread(target=self._control_thread_worker)
        self.control_thread.start()
        # print(f"🎮 Control thread started at 10Hz")  # Commented out to reduce spam

    def _control_thread_worker(self):
        """High-speed control worker thread"""
        print(f"[CONTROL DEBUG] Control thread started")
        interval = 1.0 / 10  # 10Hz control loop (reduced further for stability testing)
        next_control_time = time.time()
        last_time = time.time()
        loop_count = 0
        
        while not self.stop_control_thread:
            try:
                current_time = time.time()
                loop_count += 1
                
                # Debug print every 200 loops (20 seconds at 10Hz)
                if loop_count % 200 == 0:
                    print(f"[CONTROL DEBUG] Control loop running, count: {loop_count}")
                
                # Fix: Make manual_control_active access thread-safe
                with self.data_lock:
                    manual_active = self.manual_control_active
                
                if manual_active:
                    time.sleep(0.05)  # Sleep briefly to prevent busy-waiting
                    continue
                
                if current_time >= next_control_time:
                    try:
                        # Debug: Print when control loop first starts active control
                        if loop_count <= 20 and self.pd_controller.controller_enabled:  # First 2 seconds at 10Hz
                            print(f"[CONTROL DEBUG] Active control loop {loop_count}, enabled: {self.pd_controller.controller_enabled}")
                        
                        # Get current sensor data
                        with self.data_lock:
                            current_yaw = self.current_data['mpu']['yaw']
                            gyro_rate = self.current_data['mpu']['gyro_rate_z']
                        
                        # Debug: Print first few control calculations
                        if loop_count <= 10 and self.pd_controller.controller_enabled:
                            print(f"[CONTROL DEBUG] Control calc {loop_count}: yaw={current_yaw:.1f}, target={self.pd_controller.target_yaw:.1f}")
                        
                        # Calculate time step
                        dt = current_time - last_time
                        last_time = current_time
                        
                        # Update PWM PD controller
                        motor_power, error, pd_output = self.pd_controller.update(current_yaw, gyro_rate, dt)
                        
                        # Update shared data
                        with self.data_lock:
                            self.current_data['controller'].update({
                                'enabled': self.pd_controller.controller_enabled,
                                'target_yaw': self.pd_controller.target_yaw,
                                'error': error,
                                'motor_power': motor_power,
                                'pd_output': pd_output
                            })
                        
                        next_control_time += interval
                        
                    except Exception as e:
                        print(f"[CONTROL DEBUG] Error in control thread inner loop: {e}")
                        import traceback
                        traceback.print_exc()
                
                time.sleep(0.001)  # 1ms sleep
                
            except (KeyboardInterrupt, SystemExit):
                # Handle graceful shutdown
                print("[CONTROL DEBUG] Control thread received shutdown signal")
                break
            except Exception as e:
                print(f"[CONTROL DEBUG] Unexpected error in control thread: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.01)  # Brief pause on unexpected errors
    
    def read_all_sensors(self):
        """Read all sensors and return formatted data"""
        data = {
            'mpu': {
                'yaw': 0.0, 'roll': 0.0, 'pitch': 0.0, 'temp': 0.0,
                'gyro_rate_x': 0.0, 'gyro_rate_y': 0.0, 'gyro_rate_z': 0.0,
                'angle_x': 0.0, 'angle_y': 0.0, 'angle_z': 0.0
            },
            'lux': {ch: 0.0 for ch in LUX_CHANNELS},
            'status': 'Active'
        }
        
        # Read MPU6050
        if self.mpu_sensor.sensor_ready:
            try:
                yaw_angle = self.mpu_sensor.get_yaw_angle()  # Get unified calibrated yaw
                gyro = self.mpu_sensor.read_gyroscope()
                accel = self.mpu_sensor.read_accelerometer()
                temp = self.mpu_sensor.read_temperature()
                
                # Position angles (integrated from gyro) - no wrapping
                data['mpu']['yaw'] = yaw_angle  # Primary control angle (unified calibrated)
                data['mpu']['roll'] = self.mpu_sensor.angle_roll
                data['mpu']['pitch'] = self.mpu_sensor.angle_pitch
                data['mpu']['temp'] = temp
                
                # All gyro rates (deg/s)
                if gyro:
                    data['mpu']['gyro_rate_x'] = gyro[0]  # Pitch rate
                    data['mpu']['gyro_rate_y'] = gyro[1]  # Roll rate  
                    data['mpu']['gyro_rate_z'] = gyro[2]  # Yaw rate
                
                # All angle positions (degrees) - no wrapping
                data['mpu']['angle_x'] = self.mpu_sensor.angle_pitch  # Pitch angle
                data['mpu']['angle_y'] = self.mpu_sensor.angle_roll   # Roll angle
                data['mpu']['angle_z'] = self.mpu_sensor.angle_yaw    # Yaw angle
                
            except Exception as e:
                print(f"MPU read error: {e}")
                data['status'] = 'MPU Error'
        else:
            data['status'] = 'MPU Not Ready'
        
        # Read Lux sensors
        if self.lux_manager.sensors_ready:
            try:
                lux_readings = self.lux_manager.read_lux_sensors()
                data['lux'].update(lux_readings)
            except Exception as e:
                print(f"Lux read error: {e}")
        
        return data
    
    def get_current_data(self):
        """Get current sensor data (thread-safe)"""
        with self.data_lock:
            return self.current_data.copy(), self.last_reading_time
    
    def get_adcs_data_for_server(self):
        """Format data for server ADCS broadcast"""
        data, _ = self.get_current_data()
        yaw = data['mpu']['yaw']    # Use full range yaw
        roll = data['mpu']['roll']   # Use full range roll
        pitch = data['mpu']['pitch'] # Use full range pitch
        
        return {
            # Primary display values (legacy format)
            'gyro': f"{yaw:.1f}°",
            'orientation': f"Y:{yaw:.1f}° R:{roll:.1f}° P:{pitch:.1f}°",
            'lux1': f"{data['lux'][1]:.1f}" if 1 in data['lux'] else "0.0",
            'lux2': f"{data['lux'][2]:.1f}" if 2 in data['lux'] else "0.0", 
            'lux3': f"{data['lux'][3]:.1f}" if 3 in data['lux'] else "0.0",
            'rpm': "0.0",  # TODO: Add tachometer in next step
            'status': data.get('status', 'Unknown'),
            
            # Complete gyro rates (deg/s) for all axes
            'gyro_rate_x': f"{data['mpu']['gyro_rate_x']:.2f}",  # Pitch rate
            'gyro_rate_y': f"{data['mpu']['gyro_rate_y']:.2f}",  # Roll rate
            'gyro_rate_z': f"{data['mpu']['gyro_rate_z']:.2f}",  # Yaw rate
            
            # Complete angle positions (degrees) for all axes  
            'angle_x': f"{data['mpu']['angle_x']:.1f}",  # Pitch angle
            'angle_y': f"{data['mpu']['angle_y']:.1f}",  # Roll angle
            'angle_z': f"{data['mpu']['angle_z']:.1f}",  # Yaw angle
            
            # Temperature
            'temperature': f"{data['mpu']['temp']:.1f}°C",
            
            # PWM PD Controller data
            'controller_enabled': data['controller']['enabled'],
            'target_yaw': f"{data['controller']['target_yaw']:.1f}°",
            'yaw_error': f"{data['controller']['error']:.1f}°",
            'motor_power': f"{data['controller']['motor_power']:.0f}%",
            'pd_output': f"{data['controller']['pd_output']:.2f}",
            'motor_available': self.motor_available
        }
    
    def handle_adcs_command(self, mode, command, value=None):
        """Handle ADCS commands from client"""
        try:
            # print(f"🎛️ ADCS Command: Mode='{mode}', Command='{command}', Value='{value}'")  # Commented out to reduce spam

            # Handle calibration commands
            if mode == "Calibration" or (mode == "adcs" and command == "calibrate"):
                if command == "start_calibration" or command == "calibrate":
                    return self.calibrate_sensors()
                    
            # Handle manual control commands
            elif mode == "adcs":
                if command == "zero_yaw":
                    return self.zero_yaw_position()
                elif command == "manual_clockwise_start":
                    return self.start_manual_control("CW")
                elif command == "manual_stop":
                    return self.stop_manual_control()
                elif command == "manual_counterclockwise_start":
                    return self.start_manual_control("CCW")
                if command == "set_zero":
                    return self.zero_yaw_position()
                elif command == "set_value":
                    return self.set_target_yaw(value)
                elif command == "start":
                    return self.start_auto_control(mode)
                elif command == "stop":
                    return self.stop_auto_control()
                elif command == "set_pd_values":
                    return self.set_controller_gains(value)
                # --- Handle new zero commands ---
                elif command == "auto_zero_tag":
                    return self.start_auto_zero_tag()
                elif command == "auto_zero_lux":
                    return self.start_auto_zero_env()
                elif command == "stop_auto_zero_tag":
                    self.stop_auto_zero_tag()
                    return {"status": "success", "message": "Stopped AprilTag"}
                elif command == "stop_auto_zero_lux":
                    self.stop_auto_zero_env()
                    return {"status": "success", "message": "Stopped Environmental"}
                elif command == "manual_cal":
                    return self.manual_calibration(value)
                elif command == "raw":
                    return self.return_to_raw_mode()
            
        except Exception as e:
            error_msg = f"ADCS command error: {e}"
            print(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}
    

    def manual_calibration(self, yaw_rate_offset):
        """
        Manually calibrate the gyro Z rate by setting a bias offset.
        Args:
            yaw_rate_offset: The value (in deg/s) to offset the gyro Z rate.
        """
        try:
            if yaw_rate_offset is None:
                return {"status": "error", "message": "No yaw rate offset provided"}
            offset = float(yaw_rate_offset)
            with self.data_lock:
                self.mpu_sensor.set_manual_calibration(offset)
            # print(f"[MANUAL CAL] Gyro Z rate offset set to {offset:.3f} deg/s (type: manual)")  # Commented out to reduce spam
            return {"status": "success", "message": f"Manual calibration set: {offset:.3f} deg/s (overrides auto calibration)"}
        except Exception as e:
            return {"status": "error", "message": f"Manual calibration failed: {e}"}

    def return_to_raw_mode(self):
        """
        Return system to raw mode - stops all controllers and auto modes.
        This is a clean return to normal state from any mode.
        """
        try:
            # print("🛑 Returning to raw mode - stopping all systems...")  # Commented out to reduce spam
            
            # Stop PD controller
            self.pd_controller.stop_controller()
            
            # Stop all auto zero modes
            if getattr(self, 'auto_zero_tag_enabled', False):
                self.stop_auto_zero_tag()
            
            if getattr(self, 'auto_zero_env_enabled', False):
                self.stop_auto_zero_env()
            
            # Stop manual control
            with self.data_lock:
                self.manual_control_active = False
            
            # Stop motor
            stop_motor()
            
            # print("✓ Raw mode activated - all systems stopped")  # Commented out to reduce spam
            return {"status": "success", "message": "Raw mode activated - all systems stopped"}
            
        except Exception as e:
            return {"status": "error", "message": f"Return to raw mode failed: {e}"}

    def zero_yaw_position(self):
        """Zero the yaw position"""
        try:
            self.mpu_sensor.zero_yaw_position()
            return {"status": "success", "message": "Yaw position zeroed"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to zero yaw: {e}"}
    
    def calibrate_sensors(self):
        """Calibrate all sensors"""
        try:
            # print("🎯 Starting sensor calibration...")  # Commented out to reduce spam
            
            # Calibrate MPU6050
            if self.mpu_sensor.sensor_ready:
                self.mpu_sensor.calibrate_gyro()
            else:
                # Try to reconnect and calibrate
                if self.mpu_sensor.attempt_reconnection():
                    self.mpu_sensor.calibrate_gyro()
                else:
                    return {"status": "error", "message": "MPU6050 not available for calibration"}
            
            # Reinitialize lux sensors
            if LUX_AVAILABLE:
                self.lux_manager.initialize_lux_sensors()
            
            return {"status": "success", "message": "Sensor calibration complete"}
            
        except Exception as e:
            return {"status": "error", "message": f"Calibration failed: {e}"}
    
    def display_readings(self):
        """Display current sensor readings (for debugging)"""
        data, reading_time = self.get_current_data()
        
        # MPU data with all axes
        mpu_info = f"YAW:{data['mpu']['angle_z']:+6.1f}° ROLL:{data['mpu']['angle_y']:+6.1f}° PITCH:{data['mpu']['angle_x']:+6.1f}°"
        gyro_info = f"GyroX:{data['mpu']['gyro_rate_x']:+6.1f}°/s GyroY:{data['mpu']['gyro_rate_y']:+6.1f}°/s GyroZ:{data['mpu']['gyro_rate_z']:+6.1f}°/s"
        temp_info = f"T:{data['mpu']['temp']:4.1f}°C"
        
        # Controller info
        ctrl_status = "[ON]" if data['controller']['enabled'] else "[OFF]"
        ctrl_info = f"Target:{data['controller']['target_yaw']:+6.1f}° Error:{data['controller']['error']:+5.1f}° Power:{data['controller']['motor_power']:+4.0f}% {ctrl_status}"
        
        # Lux data
        lux_parts = []
        for ch in LUX_CHANNELS:
            lux_parts.append(f"L{ch}:{data['lux'][ch]:6.1f}")
        lux_info = " ".join(lux_parts)
        
        status = f"{mpu_info} | {gyro_info} | {temp_info} | {ctrl_info} | {lux_info} | Status: {data['status']}"
        print(f"\r{status}", end="", flush=True)
    
    def start_manual_control(self, direction):
        """Start manual motor control - special handling for AprilTag mode"""
        try:
            if not self.motor_available:
                return {"status": "error", "message": "Motor control not available"}
            
            # SPECIAL CASE: If AprilTag mode is active, only pause PD controller
            if getattr(self, 'auto_zero_tag_enabled', False):
                # print("� AprilTag mode active - pausing PD controller only")  # Commented out to reduce spam
                self.pd_controller.stop_controller()  # Just pause PD controller
                
                # Set manual control flag thread-safely
                with self.data_lock:
                    self.manual_control_active = True

                if direction == "CW":
                    rotate_clockwise()
                    return {"status": "success", "message": "Manual CW started (AprilTag mode paused)"}
                elif direction == "CCW":
                    rotate_counterclockwise()
                    return {"status": "success", "message": "Manual CCW started (AprilTag mode paused)"}
                else:
                    return {"status": "error", "message": "Invalid direction"}
            
            # NORMAL CASE: Stop all other modes
            # print("🛑 Manual control requested - stopping all other modes...")  # Commented out to reduce spam
            
            # Stop PD controller
            self.pd_controller.stop_controller()
            
            # Stop auto zero env mode  
            if getattr(self, 'auto_zero_env_enabled', False):
                self.stop_auto_zero_env()
            
            # Set manual control flag thread-safely
            with self.data_lock:
                self.manual_control_active = True

            if direction == "CW":
                rotate_clockwise()
                # print("🔄 Manual clockwise started (all other modes stopped)")  # Commented out to reduce spam
                return {"status": "success", "message": "Manual CW started"}
            elif direction == "CCW":
                rotate_counterclockwise()
                # print("🔄 Manual counterclockwise started (all other modes stopped)")  # Commented out to reduce spam
                return {"status": "success", "message": "Manual CCW started"}
            else:
                return {"status": "error", "message": "Invalid direction"}
                
        except Exception as e:
            return {"status": "error", "message": f"Manual control error: {e}"}

    def stop_manual_control(self):
        """Stop manual motor control - special handling for AprilTag mode"""
        try:
            # Set manual control flag thread-safely
            with self.data_lock:
                self.manual_control_active = False
            
            stop_motor()
            
            # SPECIAL CASE: If AprilTag mode is still active, resume PD controller
            if getattr(self, 'auto_zero_tag_enabled', False):
                self.pd_controller.start_controller()
                # print("⏹️ Manual control stopped - AprilTag mode resumed")  # Commented out to reduce spam
                return {"status": "success", "message": "Manual control stopped (AprilTag mode resumed)"}
            else:
                # print("⏹️ Manual control stopped")  # Commented out to reduce spam
                return {"status": "success", "message": "Manual control stopped"}
        except Exception as e:
            return {"status": "error", "message": f"Stop manual control error: {e}"}

    def set_target_yaw(self, target_angle):
        """Set target yaw angle for PD controller"""
        try:
            if target_angle is None:
                return {"status": "error", "message": "Target angle not provided"}
            
            target = float(target_angle)
            self.pd_controller.set_target(target)
            return {"status": "success", "message": f"Target yaw set to {target:.1f}°"}
        except Exception as e:
            return {"status": "error", "message": f"Set target error: {e}"}

    def start_auto_control(self, mode):
        """Start automatic control mode"""
        try:
            print(f"[ADCS DEBUG] Starting auto control - mode: {mode}")
            
            if not self.motor_available:
                print(f"[ADCS DEBUG] Motor not available")
                return {"status": "error", "message": "Motor control not available"}
            
            if not self.mpu_sensor.sensor_ready:
                print(f"[ADCS DEBUG] MPU sensor not ready")
                return {"status": "error", "message": "MPU6050 sensor not ready"}
            
            # Check if manual control is active
            with self.data_lock:
                manual_active = self.manual_control_active
                print(f"[ADCS DEBUG] Manual control active: {manual_active}")
                
                if manual_active:
                    return {"status": "error", "message": "Cannot start auto control - manual control is active. Stop manual control first."}
            
            print(f"[ADCS DEBUG] Starting PD controller...")
            self.pd_controller.start_controller()
            
            # Add a small delay to allow system to stabilize
            import time
            time.sleep(0.1)
            
            print(f"[ADCS DEBUG] PD controller started successfully")
            
            # Check system resources after starting
            resources = self.get_system_resources()
            print(f"[ADCS DEBUG] System resources after start - Threads: {resources.get('threads', 'unknown')}, Refs: {resources.get('ref_count', 'unknown')}")
            
            # print(f"▶️ {mode} mode started with PWM PD controller")  # Commented out to reduce spam
            return {"status": "success", "message": f"{mode} mode started"}
        except Exception as e:
            print(f"[ADCS DEBUG] Exception in start_auto_control: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Auto control start error: {e}"}

    def stop_auto_control(self):
        """Stop automatic control mode"""
        try:
            self.pd_controller.stop_controller()
            # print("⏹️ Auto control stopped")  # Commented out to reduce spam
            return {"status": "success", "message": "Auto control stopped"}
        except Exception as e:
            return {"status": "error", "message": f"Auto control stop error: {e}"}

    def set_controller_gains(self, gains):
        """Set PD controller gains"""
        try:
            if isinstance(gains, dict):
                if 'kp' in gains:
                    self.pd_controller.kp = float(gains['kp'])
                if 'kd' in gains:
                    self.pd_controller.kd = float(gains['kd'])
                if 'deadband' in gains:
                    self.pd_controller.deadband = float(gains['deadband'])
                if 'max_power' in gains:
                    self.pd_controller.max_power = float(gains['max_power'])
                
                # print(f"PWM Controller gains updated: Kp={self.pd_controller.kp}, Kd={self.pd_controller.kd}, Max Power={self.pd_controller.max_power}%, Deadband={self.pd_controller.deadband}")  # Commented out to reduce spam
                return {"status": "success", "message": "Controller gains updated"}
            else:
                return {"status": "error", "message": "Gains must be a dictionary"}
        except Exception as e:
            return {"status": "error", "message": f"Set gains error: {e}"}

    def shutdown(self):
        """Shutdown the ADCS controller"""
        # print("\n🛰️ ADCS Controller shutdown...")  # Commented out to reduce spam
        
        # Stop PD controller
        self.pd_controller.stop_controller()
        
        # Stop logging if active
        if self.pd_controller.enable_logging:
            self.pd_controller.stop_logging()
        if self.pd_controller.enable_yaw_logging:
            self.pd_controller.stop_yaw_logging()
        
        # Stop threads cleanly
        self.stop_data_thread = True
        self.stop_control_thread = True
        
        # Wait for data thread to finish
        if hasattr(self, 'data_thread') and self.data_thread and self.data_thread.is_alive():
            try:
                self.data_thread.join(timeout=2.0)
                if self.data_thread.is_alive():
                    print("[ADCS DEBUG] Warning: Data thread did not stop cleanly")
                else:
                    print("[ADCS DEBUG] Data thread stopped cleanly")
            except Exception as e:
                print(f"[ADCS DEBUG] Error stopping data thread: {e}")
                
        # Wait for control thread to finish  
        if hasattr(self, 'control_thread') and self.control_thread and self.control_thread.is_alive():
            try:
                self.control_thread.join(timeout=2.0)
                if self.control_thread.is_alive():
                    print("[ADCS DEBUG] Warning: Control thread did not stop cleanly")
                else:
                    print("[ADCS DEBUG] Control thread stopped cleanly")
            except Exception as e:
                print(f"[ADCS DEBUG] Error stopping control thread: {e}")
        
        # Cleanup motor control
        cleanup_motor_control()
        # print("✓ ADCS Controller shutdown complete")  # Commented out to reduce spam

    def start_auto_zero_env(self):
        """
        Environmental auto-zeroing routine:
        1. Zero yaw and start controller.
        2. Wait until stationary.
        3. Set PD controller target to yaw+30° in a loop (fixed error), record lux peaks.
        4. After 2 full rotations, set target to 0° and leave PD controller on.
        5. Enter continuous mode: update sun reference to 0° on new peaks.
        """
        # Check if manual control is active
        with self.data_lock:
            if self.manual_control_active:
                print("[AUTO ZERO ENV] Cannot start - manual control is active. Stop manual control first.")
                return {"status": "error", "message": "Cannot start Environmental mode - manual control is active"}
        
        print("[AUTO ZERO ENV] Starting environmental auto-zeroing routine...")
        self.auto_zero_env_enabled = True
        self.lux_peak_windows = {1: [], 2: [], 3: []}
        self.lux_angles = {1: 90, 2: -150, 3: -30}
        self.lux_zero_offset = 0.0
        self.env_peak_log = []

        # 1. Zero yaw and start controller
        self.zero_yaw_position()
        self.pd_controller.set_target(0.0)
        self.pd_controller.start_controller()
        print("[AUTO ZERO ENV] Controller started, waiting to reach stationary...")

        # 2. Wait until stationary (yaw rate < 1 deg/s for 2 seconds)
        stationary_time = 0
        while stationary_time < 2.0:
            with self.data_lock:
                gyro_rate = abs(self.current_data['mpu']['gyro_rate_z'])
            if gyro_rate < 1.0:
                stationary_time += 0.1
            else:
                stationary_time = 0
            time.sleep(0.1)
        print("[AUTO ZERO ENV] Stationary achieved.")

        # 3. Set PD controller target to yaw+30° in a loop, record peaks, detect 2 wraps
        print("[AUTO ZERO ENV] Rotating with fixed error (target = yaw + 30°)...")
        yaw_wraps = 0
        last_yaw = None
        peak_log = []

        while yaw_wraps < 2:
            with self.data_lock:
                yaw = self.current_data['mpu']['yaw']
                lux = self.current_data['lux'].copy()
            # Set PD target to always be 30° ahead of current yaw
            self.pd_controller.set_target(yaw + 30)  # No wrapping needed

            # Detect yaw wrap-around
            if last_yaw is not None:
                if (last_yaw < -150 and yaw > 150):
                    yaw_wraps += 1
                    print(f"[AUTO ZERO ENV] Yaw wrap detected: {yaw_wraps}")
            last_yaw = yaw

            # Peak detection for each channel
            for ch in [1, 2, 3]:
                win = self.lux_peak_windows[ch]
                win.append(lux[ch])
                if len(win) > 3:
                    win.pop(0)
                if len(win) == 3:
                    if win[1] > win[0] and win[1] > win[2] and win[1] > 50:  # 50 lux threshold
                        peak_log.append({'ch': ch, 'lux': win[1], 'yaw': yaw, 'time': time.time()})
                        print(f"[AUTO ZERO ENV] Peak detected: Lux{ch} {win[1]:.1f} at yaw {yaw:.1f}")

            time.sleep(0.02)

        print("[AUTO ZERO ENV] 2 full rotations detected. Rotations complete. Analysing peaks...")

        # 4. Set PD controller target to 0 and leave controller on
        self.pd_controller.set_target(0.0)
        print("[AUTO ZERO ENV] Target set to 0°. PD controller remains ON.")

        # 5. Analyse and print comparison
        for peak in peak_log:
            ch = peak['ch']
            sensor_angle = self.lux_angles[ch]
            print(f"  Peak: Lux{ch} at yaw {peak['yaw']:.1f}°, sensor angle {sensor_angle}° (lux={peak['lux']:.1f})")

        # 6. Enter continuous mode: update sun reference on new peaks
        print("[AUTO ZERO ENV] Entering continuous sun reference mode (sun = 0°)...")
        self.env_peak_log = []
        self.lux_zero_offset = 0.0

        def continuous_env_loop():
            while self.auto_zero_env_enabled:
                with self.data_lock:
                    yaw = self.current_data['mpu']['yaw']
                    lux = self.current_data['lux'].copy()
                for ch in [1, 2, 3]:
                    win = self.lux_peak_windows[ch]
                    win.append(lux[ch])
                    if len(win) > 3:
                        win.pop(0)
                    if len(win) == 3:
                        # Thresholds: lux > 50, angle change > 10°
                        if win[1] > win[0] and win[1] > win[2] and win[1] > 50:
                            last_peak = self.env_peak_log[-1] if self.env_peak_log else None
                            if not last_peak or abs(yaw - last_peak['yaw']) > 10:  # No wrapping needed
                                sensor_angle = self.lux_angles[ch]
                                offset = yaw - sensor_angle  # Direct calculation
                                self.lux_zero_offset = offset
                                self.env_peak_log.append({'ch': ch, 'lux': win[1], 'yaw': yaw, 'offset': offset, 'time': time.time()})
                                print(f"[AUTO ZERO ENV] [LIVE] Peak Lux{ch} {win[1]:.1f} at yaw {yaw:.1f}°, offset set to {offset:.1f}°")
                time.sleep(0.05)

        env_thread = create_thread(target=continuous_env_loop)
        env_thread.start()
        print("[AUTO ZERO ENV] You may now point to any target. Sun reference will update on new peaks.")
        return {"status": "success", "message": "Environmental mode started"}
    
    def stop_auto_zero_env(self):
        """Disable environmental (lux-based) auto zeroing and stop motor cleanly."""
        self.auto_zero_env_enabled = False
        stop_motor()
        print("[AUTO ZERO ENV] Environmental auto zero DISABLED.")

    def auto_zero_env(self):
        """
        Call this method regularly (e.g. in your data thread) to analyze live lux data,
        detect peaks, and set the yaw offset so the sun is at 0°.
        """
        if not getattr(self, "auto_zero_env_enabled", False):
            return

        # Get current lux and yaw data (thread-safe)
        with self.data_lock:
            lux_data = self.current_data['lux'].copy()
            mpu_yaw = self.current_data['mpu']['yaw']

        for ch in [1, 2, 3]:
            win = self.lux_peak_windows[ch]
            win.append(lux_data[ch])
            if len(win) > 3:
                win.pop(0)
            if len(win) == 3:
                if win[1] > win[0] and win[1] > win[2]:
                    # Peak detected for this channel
                    sensor_angle = self.lux_angles[ch]
                    offset = self.wrap_angle(mpu_yaw - sensor_angle)
                    self.lux_zero_offset = offset
                    print(f"[AUTO ZERO ENV] Peak detected on Lux{ch} at yaw {mpu_yaw:.1f}°, sensor angle {sensor_angle}°, offset set to {offset:.1f}°")
                    # Optionally, break after first peak detected
                    break

    def auto_zero_tag(self, data):
        """
        Called when scanning_mode_data is received or when AprilTag command is triggered.
        
        SIMPLIFIED APPROACH: Just compare timestamps and update MPU angle directly.
        - Compare timestamp from AprilTag data with current MPU timestamp
        - Print timestamp difference in ms
        - Simply update current MPU yaw angle with received relative angle
        """
        if not self.auto_zero_tag_enabled:
            # Silently ignore when disabled to reduce spam
            return
        try:
            rel_angle = data.get("relative_angle")
            apriltag_timestamp = data.get("timestamp")
            
            if rel_angle is None:
                # Only print once when AprilTag is lost to avoid spam
                if not hasattr(self, '_apriltag_lost_printed') or not self._apriltag_lost_printed:
                    # Silently handle AprilTag loss to reduce spam
                    self._apriltag_lost_printed = True
                return
            else:
                # Reset the lost flag when AprilTag is detected again
                self._apriltag_lost_printed = False
                
            # Get current MPU data and timestamp
            current_time = time.time()
            with self.data_lock:
                current_mpu_yaw = self.current_data['mpu']['yaw']
                
            # Parse AprilTag timestamp and calculate difference
            timestamp_diff_ms = 0
            if apriltag_timestamp:
                try:
                    # Parse ISO timestamp from AprilTag data
                    import datetime
                    apriltag_dt = datetime.datetime.fromisoformat(apriltag_timestamp.replace('Z', '+00:00'))
                    apriltag_time = apriltag_dt.timestamp()
                    timestamp_diff_ms = (current_time - apriltag_time) * 1000
                except Exception as e:
                    print(f"[AUTO ZERO] Could not parse timestamp: {e}")
                    timestamp_diff_ms = 0
            
            # Simple update: set MPU angle to negative of relative angle
            # (We want MPU to read negative rel_angle when pointing at tag)
            desired_mpu_yaw = -float(rel_angle)
            
            # Update the MPU angle directly
            with self.data_lock:
                self.mpu_sensor.angle_yaw = desired_mpu_yaw
                
            # Set PD controller target to 0° (now aligned with AprilTag)
            self.pd_controller.set_target(0.0)
            
            # Print concise update (only essential info)
            print(f"[AUTO ZERO] AprilTag: {rel_angle:.1f}° → MPU: {desired_mpu_yaw:.1f}° (Δt: {timestamp_diff_ms:.0f}ms)")

        except Exception as e:
            # Only print error once to avoid spam
            if not hasattr(self, '_last_error_msg') or self._last_error_msg != str(e):
                print(f"[AUTO ZERO] Error: {e}")
                self._last_error_msg = str(e)
            
        # Comment out the complex RTT-based approach for now
        # # OLD RTT-BASED APPROACH (commented out for simplicity)
        # try:
        #     rel_angle = data.get("relative_angle")
        #     rtt_ms = data.get("rtt_ms", self.last_rtt_ms)  # Use provided RTT or last known
        #     
        #     if rel_angle is None:
        #         # Only set target to 0° once when AprilTag is lost, then let controller stabilize
        #         if not self.auto_zero_tag_target_set:
        #             print("[AUTO ZERO] AprilTag lost, setting PD target to 0° (ONCE) - maintaining current position.")
        #             self.pd_controller.set_target(0.0)
        #             self.auto_zero_tag_target_set = True
        #         return
        #         
        #     # AprilTag detected - reset the "target set" flag for next time it's lost
        #     self.auto_zero_tag_target_set = False
        #     
        #     # Update last known RTT
        #     if rtt_ms > 0:
        #         self.last_rtt_ms = rtt_ms
        #     
        #     # Get current MPU data and apply motion compensation
        #     with self.data_lock:
        #         current_mpu_yaw = self.current_data['mpu']['yaw']
        #         gyro_rate = self.current_data['mpu']['gyro_rate_z']
        #     
        #     # Estimate MPU position when AprilTag measurement was taken
        #     # RTT includes both directions, so divide by 2 for one-way delay
        #     one_way_delay_s = (rtt_ms / 2.0) / 1000.0
        #     
        #     # Compensate for rotation during transmission delay
        #     rotation_during_delay = gyro_rate * one_way_delay_s
        #     estimated_mpu_at_capture = current_mpu_yaw - rotation_during_delay
        #     
        #     # Calculate the alignment correction
        #     desired_mpu_yaw = -float(rel_angle)  # We want MPU to read negative rel_angle when pointing at tag
        #     correction_needed = desired_mpu_yaw - estimated_mpu_at_capture
        #     
        #     # Apply the correction to the current MPU angle
        #     with self.data_lock:
        #         self.mpu_sensor.angle_yaw += correction_needed
        #         corrected_yaw = self.mpu_sensor.angle_yaw
        #         
        #     # Set PD controller target to 0° (now aligned with AprilTag)
        #     self.pd_controller.set_target(0.0)
        #     
        #     print(f"[AUTO ZERO RTT] AprilTag alignment with motion compensation:")
        #     print(f"  AprilTag relative angle: {rel_angle:.2f}°")
        #     print(f"  Round-trip time: {rtt_ms:.0f}ms (one-way: {one_way_delay_s*1000:.0f}ms)")
        #     print(f"  Current MPU yaw: {current_mpu_yaw:.2f}°")
        #     print(f"  Gyro rate: {gyro_rate:.2f}°/s")
        #     print(f"  Rotation during delay: {rotation_during_delay:.2f}°")
        #     print(f"  Estimated MPU at capture: {estimated_mpu_at_capture:.2f}°")
        #     print(f"  Correction applied: {correction_needed:.2f}°")
        #     print(f"  MPU yaw after correction: {corrected_yaw:.2f}°")
        #     print(f"  PD target set to 0° - now aligned with AprilTag")
        #
        # except Exception as e:
        #     print(f"[AUTO ZERO RTT] Error: {e}")


    def start_auto_zero_tag(self):
        """Enable AprilTag auto zeroing with simple timestamp comparison."""
        # Check if manual control is active
        with self.data_lock:
            if self.manual_control_active:
                print("[AUTO ZERO TAG] Cannot start - manual control is active. Stop manual control first.")
                return {"status": "error", "message": "Cannot start AprilTag mode - manual control is active"}
        
        self.auto_zero_tag_enabled = True
        self.auto_zero_tag_target_set = False  # Reset the flag when starting
        
        # Simple approach - just enable the auto_zero_tag function
        # It will be called when scanning_mode_data is received
        # print("[AUTO ZERO TAG] AprilTag mode enabled with simple timestamp comparison")  # Commented out to reduce spam
        return {"status": "success", "message": "AprilTag mode enabled"}

    def stop_auto_zero_tag(self):
        """Disable AprilTag auto zeroing."""
        self.auto_zero_tag_enabled = False
        # Stop the request-response system (commented out for now)
        # self.stop_apriltag_requests()
        # print("[AUTO ZERO] auto_zero_tag DISABLED.")  # Commented out to reduce spam

    def get_system_state(self):
        """Get current system state for debugging"""
        with self.data_lock:
            manual_active = self.manual_control_active
        
        return {
            "manual_control_active": manual_active,
            "pd_controller_enabled": self.pd_controller.controller_enabled,
            "auto_zero_tag_enabled": getattr(self, 'auto_zero_tag_enabled', False),
            "auto_zero_env_enabled": getattr(self, 'auto_zero_env_enabled', False),
            "motor_available": self.motor_available,
            "mpu_sensor_ready": self.mpu_sensor.sensor_ready
        }

    def stop_all_modes(self):
        """Emergency stop all modes - helper method"""
        try:
            print("🛑 EMERGENCY STOP - Stopping all modes...")
            
            # Stop PD controller
            self.pd_controller.stop_controller()
            
            # Stop auto zero modes
            if getattr(self, 'auto_zero_tag_enabled', False):
                self.stop_auto_zero_tag()
            
            if getattr(self, 'auto_zero_env_enabled', False):
                self.stop_auto_zero_env()
            
            # Stop manual control
            with self.data_lock:
                self.manual_control_active = False
            
            # Stop motor
            stop_motor()
            
            print("✓ All modes stopped")
            return {"status": "success", "message": "All modes stopped"}
        except Exception as e:
            return {"status": "error", "message": f"Emergency stop failed: {e}"}

    # REQUEST-RESPONSE FUNCTIONS (commented out for simple approach)
    # def set_apriltag_request_callback(self, callback):
    #     """Set the callback function to send AprilTag data requests to server"""
    #     self.apriltag_request_callback = callback
    #     print("[AUTO ZERO] AprilTag request callback set")

    # def start_apriltag_requests(self):
    #     """Start periodic AprilTag data requests"""
    #     if not self.apriltag_request_callback:
    #         print("[AUTO ZERO] ERROR: No request callback set! Call set_apriltag_request_callback() first")
    #         return False
    #         
    #     print(f"[AUTO ZERO] Starting AprilTag requests every {self.apriltag_request_interval}s")
    #     self._send_apriltag_request()
    #     return True

    # def stop_apriltag_requests(self):
    #     """Stop periodic AprilTag data requests"""
    #     if self.apriltag_request_timer:
    #         self.apriltag_request_timer.cancel()
    #         self.apriltag_request_timer = None
    #     print("[AUTO ZERO] AprilTag requests stopped")

    # def _send_apriltag_request(self):
    #     """Internal method to send a single AprilTag data request"""
    #     if not self.auto_zero_tag_enabled:
    #         return
    #         
    #     try:
    #         # Record request start time
    #         self.apriltag_request_start_time = time.time()
    #         
    #         # Send request through callback
    #         if self.apriltag_request_callback:
    #             self.apriltag_request_callback("request_apriltag_data")
    #             print(f"[AUTO ZERO] AprilTag data request sent at {self.apriltag_request_start_time:.3f}")
    #         
    #         # Schedule next request
    #         if self.auto_zero_tag_enabled:
    #             import threading
    #             self.apriltag_request_timer = threading.Timer(
    #                 self.apriltag_request_interval, 
    #                 self._send_apriltag_request
    #             )
    #             self.apriltag_request_timer.start()
    #             
    #     except Exception as e:
    #         print(f"[AUTO ZERO] Error sending AprilTag request: {e}")

    # def handle_apriltag_response(self, relative_angle):
    #     """
    #     Handle AprilTag data response and calculate RTT
    #     
    #     Args:
    #         relative_angle: The relative angle measurement from AprilTag (or None if lost)
    #     """
    #     if not self.auto_zero_tag_enabled:
    #         return
    #         
    #     # Calculate round-trip time
    #     response_time = time.time()
    #     if self.apriltag_request_start_time > 0:
    #         rtt_seconds = response_time - self.apriltag_request_start_time
    #         rtt_ms = rtt_seconds * 1000
    #         self.last_rtt_ms = rtt_ms
    #         
    #         print(f"[AUTO ZERO] AprilTag response received, RTT: {rtt_ms:.1f}ms")
    #         
    #         # Create data structure similar to old format
    #         data = {
    #             "relative_angle": relative_angle,
    #             "rtt_ms": rtt_ms
    #         }
    #         
    #         # Process the data using existing logic
    #         self.auto_zero_tag(data)
    #     else:
    #         print("[AUTO ZERO] Warning: Received AprilTag response without pending request")

    def get_system_resources(self):
        """Get current system resource usage for debugging"""
        try:
            import gc
            import threading
            
            resources = {
                'active_threads': threading.active_count(),
                'ref_count': len(gc.get_objects()),
                'data_thread_alive': hasattr(self, 'data_thread') and self.data_thread and self.data_thread.is_alive(),
                'control_thread_alive': hasattr(self, 'control_thread') and self.control_thread and self.control_thread.is_alive(),
                'pd_controller_enabled': self.pd_controller.controller_enabled if hasattr(self, 'pd_controller') else False,
                'manual_control_active': getattr(self, 'manual_control_active', False)
            }
            return resources
        except Exception as e:
            return {'error': str(e)}

def main():
    """Main function for testing"""

    print("🛰️ ADCS Controller - PWM PD Version")
    print("=" * 70)
    
    controller = ADCSController()
    
    try:
        print("\nTesting sensor readings and PWM PD controller...")
        print("Commands:")
        print("  'z' = zero_yaw")
        print("  'c' = calibrate sensors")
        print("  'g' = start PD controller")
        print("  's' = stop PD controller") 
        print("  '1' = target +20°")
        print("  '2' = target +45°")
        print("  '3' = target +90°")
        print("  '4' = target -20°")
        print("  '5' = target -45°")
        print("  '6' = target -90°")
        print("  '0' = target 0°")
        print("  'q' = quit")
        print("-" * 50)
        
        while True:
            # Display readings at 5Hz (data acquisition runs at 20Hz in background)
            controller.display_readings()
            
            # Check for commands (simplified for testing)
            import select
            import sys
            
            if select.select([sys.stdin], [], [], 0.2)[0]:
                command = sys.stdin.read(1).lower().strip()
                
                if command == 'q':
                    break
                elif command == 'z':
                    print(f"\n🎯 {controller.zero_yaw_position()}")
                elif command == 'c':
                    print(f"\n🎯 {controller.calibrate_sensors()}")
                elif command == 'g':
                    print(f"\n🎯 {controller.start_auto_control('PWM PD')}")
                elif command == 's':
                    print(f"\n🎯 {controller.stop_auto_control()}")
                elif command == '1':
                    print(f"\n🎯 {controller.set_target_yaw(20.0)}")
                elif command == '2':
                    print(f"\n🎯 {controller.set_target_yaw(45.0)}")
                elif command == '3':
                    print(f"\n🎯 {controller.set_target_yaw(90.0)}")
                elif command == '4':
                    print(f"\n🎯 {controller.set_target_yaw(-20.0)}")
                elif command == '5':
                    print(f"\n🎯 {controller.set_target_yaw(-45.0)}")
                elif command == '6':
                    print(f"\n🎯 {controller.set_target_yaw(-90.0)}")
                elif command == '0':
                    print(f"\n🎯 {controller.set_target_yaw(0.0)}")
                    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        controller.shutdown()

if __name__ == "__main__":
    main()