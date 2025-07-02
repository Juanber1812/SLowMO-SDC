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
from datetime import datetime
import logging
import csv
import os

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
        print(f"Error setting motor power: {e}")

def rotate_clockwise():
    """Rotate motor clockwise (full power) - for manual control"""
    set_motor_power(100)

def rotate_counterclockwise():
    """Rotate motor counterclockwise (full power) - for manual control"""
    set_motor_power(-100)

def stop_motor():
    """Stop motor (no power)"""
    set_motor_power(0)

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

class MPU6050Sensor:
    """Dedicated MPU6050 sensor class for ADCS"""
    
    def __init__(self, bus_number=1, device_address=0x68):
        self.bus = smbus2.SMBus(bus_number)
        self.device_address = device_address
        
        # Calibration values
        self.gyro_x_cal = 0.0
        self.gyro_y_cal = 0.0
        self.gyro_z_cal = 0.0
        
        # Angle variables (spacecraft convention: yaw is primary control axis)
        self.angle_yaw = 0.0      # Primary control angle
        self.angle_roll = 0.0
        self.angle_pitch = 0.0
        self.angle_yaw_pure = 0.0  # Pure gyro integration for control
        
        # Timing variables
        self.last_time = time.time()
        self.dt = 0.0
        
        # Filter parameters
        self.use_gyro_only = True  # Use pure gyro for control
        
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
        
        print(f"✓ MPU6050 calibration complete!")
        print(f"  Offsets - X: {self.gyro_x_cal:.3f}, Y: {self.gyro_y_cal:.3f}, Z: {self.gyro_z_cal:.3f}")
    
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
        """Update yaw angle using gyro integration"""
        current_time = time.time()
        self.dt = current_time - self.last_time
        self.last_time = current_time
        
        # Read gyroscope data
        gyro = self.read_gyroscope()
        
        if gyro and self.dt > 0:
            # Pure gyro integration for yaw (primary control axis)
            self.angle_yaw_pure += gyro[2] * self.dt  # Z-axis gyro for yaw
            
            # Update other angles for completeness
            self.angle_roll += gyro[1] * self.dt
            self.angle_pitch += gyro[0] * self.dt
            
            # For display purposes, use pure gyro yaw
            self.angle_yaw = self.angle_yaw_pure
    
    def get_yaw_angle(self):
        """Get current yaw angle for control"""
        self.update_angles()
        return self.angle_yaw_pure
    
    def zero_yaw_position(self):
        """Zero the current yaw position - set as reference"""
        self.angle_yaw = 0.0
        self.angle_yaw_pure = 0.0
        self.angle_roll = 0.0
        self.angle_pitch = 0.0
        print("✓ Yaw position zeroed - current orientation set as zero reference")
    
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
    def __init__(self, kp=10.0, kd=2.0, max_power=80, deadband=1.0, integral_limit=50.0):
        """
        PWM PD Controller
        
        Args:
            kp: Proportional gain
            kd: Derivative gain
            max_power: Maximum PWM power (0-100%)
            deadband: Angle deadband in degrees (no action within this range)
            integral_limit: Maximum integral windup protection
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
        """Set target yaw angle in degrees"""
        self.target_yaw = target_angle
        # Reset integral when target changes to prevent windup
        self.integral = 0.0
        print(f"Target yaw set to: {target_angle:.1f}°")
    
    def start_controller(self):
        """Start the PD controller"""
        self.controller_enabled = True
        self.integral = 0.0  # Reset integral
        print("PWM PD Controller STARTED - Motor control active")
    
    def stop_controller(self):
        """Stop the PD controller and motor"""
        self.controller_enabled = False
        self.integral = 0.0
        stop_motor()  # Immediately stop motor
        print("PWM PD Controller STOPPED - Motor disabled")
    
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
        # Calculate error
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
                    motor_power = max(25, motor_power)  # Minimum 20% CW
                else:
                    motor_power = min(-25, motor_power)  # Minimum 20% CCW
        
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
        
        # Initialize PWM PD controller
        self.pd_controller = PDControllerPWM(
            kp=10.0,          # Proportional gain
            kd=2.0,           # Derivative gain
            max_power=80,     # Maximum PWM power (80%)
            deadband=1.0      # ±1° deadband
        )
        
        # Shared data and threading
        self.data_thread = None
        self.control_thread = None
        self.stop_data_thread = False
        self.stop_control_thread = False
        self.data_lock = threading.Lock()
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
        
        # Start high-speed data acquisition
        self.start_data_thread()
        
        # Start control thread
        self.start_control_thread()
        
        print("✓ ADCS Controller initialization complete")
    
    def start_data_thread(self):
        """Start high-speed data acquisition thread"""
        self.stop_data_thread = False
        self.data_thread = threading.Thread(target=self._data_thread_worker, daemon=True)
        self.data_thread.start()
        print(f"🚀 Data acquisition started at {LOG_FREQUENCY}Hz")
    
    def _data_thread_worker(self):
        """High-speed sensor data acquisition worker"""
        interval = 1.0 / LOG_FREQUENCY
        next_read_time = time.time()
        
        while not self.stop_data_thread:
            current_time = time.time()
            
            if current_time >= next_read_time:
                try:
                    # Read all sensors
                    new_data = self.read_all_sensors()
                    
                    # Thread-safe update
                    with self.data_lock:
                        self.current_data.update(new_data)
                        self.last_reading_time = current_time
                    
                    next_read_time += interval
                    
                except Exception as e:
                    print(f"Error in data thread: {e}")
                    with self.data_lock:
                        self.current_data['status'] = 'Error'
            
            time.sleep(0.001)  # 1ms sleep
    
    def start_control_thread(self):
        """Start high-speed control thread"""
        self.stop_control_thread = False
        self.control_thread = threading.Thread(target=self._control_thread_worker, daemon=True)
        self.control_thread.start()
        print(f"🎮 Control thread started at 50Hz")

    def _control_thread_worker(self):
        """High-speed control worker thread"""
        interval = 1.0 / 50  # 50Hz control loop
        next_control_time = time.time()
        last_time = time.time()
        
        while not self.stop_control_thread:
            # If in manual mode, skip the automatic control logic
            if self.manual_control_active:
                time.sleep(0.05) # Sleep briefly to prevent busy-waiting
                continue

            current_time = time.time()
            
            if current_time >= next_control_time:
                try:
                    # Get current sensor data
                    with self.data_lock:
                        current_yaw = self.current_data['mpu']['yaw']
                        gyro_rate = self.current_data['mpu']['gyro_rate_z']
                    
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
                    print(f"Error in control thread: {e}")
            
            time.sleep(0.001)  # 1ms sleep
    
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
                yaw_angle = self.mpu_sensor.get_yaw_angle()
                gyro = self.mpu_sensor.read_gyroscope()
                accel = self.mpu_sensor.read_accelerometer()
                temp = self.mpu_sensor.read_temperature()
                
                # Position angles (integrated from gyro)
                data['mpu']['yaw'] = yaw_angle  # Primary control angle (Z-axis)
                data['mpu']['roll'] = self.mpu_sensor.angle_roll  # Y-axis rotation
                data['mpu']['pitch'] = self.mpu_sensor.angle_pitch  # X-axis rotation
                data['mpu']['temp'] = temp
                
                # All gyro rates (deg/s)
                if gyro:
                    data['mpu']['gyro_rate_x'] = gyro[0]  # Pitch rate
                    data['mpu']['gyro_rate_y'] = gyro[1]  # Roll rate  
                    data['mpu']['gyro_rate_z'] = gyro[2]  # Yaw rate
                
                # All angle positions (degrees)
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
        
        return {
            # Primary display values (legacy format)
            'gyro': f"{data['mpu']['yaw']:.1f}°",
            'orientation': f"Y:{data['mpu']['yaw']:.1f}° R:{data['mpu']['roll']:.1f}° P:{data['mpu']['pitch']:.1f}°",
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
            print(f"🎛️ ADCS Command: Mode='{mode}', Command='{command}', Value='{value}'")
            
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
        
        except Exception as e:
            error_msg = f"ADCS command error: {e}"
            print(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}
    
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
            print("🎯 Starting sensor calibration...")
            
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
        """Start manual motor control"""
        try:
            if not self.motor_available:
                return {"status": "error", "message": "Motor control not available"}
            
            # Stop PD controller first
            self.pd_controller.stop_controller()
            self.manual_control_active = True

            if direction == "CW":
                rotate_clockwise()
                print("🔄 Manual clockwise started")
                return {"status": "success", "message": "Manual CW started"}
            elif direction == "CCW":
                rotate_counterclockwise()
                print("🔄 Manual counterclockwise started")
                return {"status": "success", "message": "Manual CCW started"}
            else:
                return {"status": "error", "message": "Invalid direction"}
                
        except Exception as e:
            return {"status": "error", "message": f"Manual control error: {e}"}

    def stop_manual_control(self):
        """Stop manual motor control"""
        try:
            self.manual_control_active = False
            stop_motor()
            print("⏹️ Manual control stopped")
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
            if not self.motor_available:
                return {"status": "error", "message": "Motor control not available"}
            
            if not self.mpu_sensor.sensor_ready:
                return {"status": "error", "message": "MPU6050 sensor not ready"}
            
            self.pd_controller.start_controller()
            print(f"▶️ {mode} mode started with PWM PD controller")
            return {"status": "success", "message": f"{mode} mode started"}
        except Exception as e:
            return {"status": "error", "message": f"Auto control start error: {e}"}

    def stop_auto_control(self):
        """Stop automatic control mode"""
        try:
            self.pd_controller.stop_controller()
            print("⏹️ Auto control stopped")
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
                
                print(f"PWM Controller gains updated: Kp={self.pd_controller.kp}, Kd={self.pd_controller.kd}, Max Power={self.pd_controller.max_power}%, Deadband={self.pd_controller.deadband}")
                return {"status": "success", "message": "Controller gains updated"}
            else:
                return {"status": "error", "message": "Gains must be a dictionary"}
        except Exception as e:
            return {"status": "error", "message": f"Set gains error: {e}"}

    def shutdown(self):
        """Shutdown the ADCS controller"""
        print("\n🛰️ ADCS Controller shutdown...")
        
        # Stop PD controller
        self.pd_controller.stop_controller()
        
        # Stop logging if active
        if self.pd_controller.enable_logging:
            self.pd_controller.stop_logging()
        if self.pd_controller.enable_yaw_logging:
            self.pd_controller.stop_yaw_logging()
        
        # Stop threads
        self.stop_data_thread = True
        self.stop_control_thread = True
        
        if self.data_thread:
            self.data_thread.join(timeout=1.0)
        if self.control_thread:
            self.control_thread.join(timeout=1.0)
        
        # Cleanup motor control
        cleanup_motor_control()
        print("✓ ADCS Controller shutdown complete")

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