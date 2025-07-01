#!/usr/bin/env python3
"""
🛰️ UNIFIED ADCS CONTROLLER - Step 1: Sensor Reading & Basic Communication
Combines MPU6050 (IMU) + VEML7700 (3x Lux) sensors with server communication interface
- Real-time sensor data acquisition (20Hz)
- Thread-safe data sharing
- Client command handling for calibration
- Live data broadcasting at 20Hz
- PD Bang-Bang Motor Control for Yaw Attitude Control
"""

import time
import board
import busio
import smbus2
import threading
import math
from datetime import datetime
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
# Motor control pins (from motor_test.py)
IN1_PIN = 13    # Clockwise control
IN2_PIN = 19    # Counterclockwise control  
SLEEP_PIN = 26  # Motor driver enable

# ── MOTOR CONTROL FUNCTIONS ────────────────────────────────────────────
def setup_motor_control():
    """Setup GPIO pins for motor control"""
    if not GPIO_AVAILABLE:
        return False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup([IN1_PIN, IN2_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(SLEEP_PIN, GPIO.HIGH)  # Enable motor driver
        print("✓ Motor control GPIO initialized")
        return True
    except Exception as e:
        print(f"✗ Motor control GPIO initialization failed: {e}")
        return False

def rotate_clockwise():
    """Rotate motor clockwise (full power) with I2C protection"""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.HIGH)
        GPIO.output(IN2_PIN, GPIO.LOW)
        time.sleep(0.001)  # Brief delay to avoid I2C interference

def rotate_counterclockwise():
    """Rotate motor counterclockwise (full power) with I2C protection"""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.HIGH)
        time.sleep(0.001)  # Brief delay to avoid I2C interference

def stop_motor():
    """Stop motor (no power) with I2C protection"""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.LOW)
        time.sleep(0.001)  # Brief delay to avoid I2C interference

def cleanup_motor_control():
    """Cleanup GPIO pins"""
    if GPIO_AVAILABLE:
        stop_motor()
        GPIO.cleanup()

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
        
        # Initialize PD controller
        self.pd_controller = PDBangBangController(
            kp=2.0,           # Proportional gain
            kd=0.5,           # Derivative gain
            deadband=1.0,     # ±1° deadband
            min_pulse_time=0.2  # 200ms minimum pulse
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
                'motor_cmd': 'STOP',
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
                    
                    # Update PD controller
                    motor_cmd, error, pd_output = self.pd_controller.update(current_yaw, gyro_rate, dt)
                    
                    # Execute motor command if motor is available
                    if self.motor_available and self.pd_controller.controller_enabled:
                        if motor_cmd == "CW":
                            rotate_clockwise()
                        elif motor_cmd == "CCW":
                            rotate_counterclockwise()
                        else:
                            stop_motor()
                    else:
                        stop_motor()  # Ensure motor is stopped when controller is disabled
                    
                    # Update shared data
                    with self.data_lock:
                        self.current_data['controller'].update({
                            'enabled': self.pd_controller.controller_enabled,
                            'target_yaw': self.pd_controller.target_yaw,
                            'error': error,
                            'motor_cmd': motor_cmd,
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
            
            # PD Controller data
            'controller_enabled': data['controller']['enabled'],
            'target_yaw': f"{data['controller']['target_yaw']:.1f}°",
            'yaw_error': f"{data['controller']['error']:.1f}°",
            'motor_command': data['controller']['motor_cmd'],
            'pd_output': f"{data['controller']['pd_output']:.2f}",
            'motor_available': self.motor_available
        }
    
    def handle_adcs_command(self, mode, command, value=None):
        """Handle ADCS commands from client"""
        try:
            print(f"🎛️ ADCS Command: Mode='{mode}', Command='{command}', Value='{value}'")

            if mode == "Manual":
                if command == "manual_clockwise_start":
                    return self.start_manual_control("CW")
                elif command == "manual_clockwise_stop":
                    return self.stop_manual_control()
                elif command == "manual_anticlockwise_start":
                    return self.start_manual_control("CCW")
                elif command == "manual_anticlockwise_stop":
                    return self.stop_manual_control()
                elif command == "enable_motor":
                    if value is True:
                        return self.enable_motor_driver()
                    elif value is False:
                        return self.disable_motor_driver()
                    else:
                        return {"status": "error", "message": "Invalid value for enable_motor (must be True/False)"}
                elif command == "calibrate":
                    return self.calibrate_sensors()
                else:
                    return {"status": "error", "message": f"Unknown Manual command: {command}"}

            elif mode in ["Raw", "Env", "AprilTag"]:
                if command == "set_zero":
                    return self.zero_yaw_position()
                elif command == "set_value":
                    return self.set_target_yaw(value)
                elif command == "start":
                    return self.start_auto_control(mode)
                elif command == "stop":
                    return self.stop_auto_control()
                elif command == "set_pd_values":
                    # Expects value as dict with kp, kd
                    if isinstance(value, dict) and "kp" in value and "kd" in value:
                        self.pd_controller.set_gains(float(value["kp"]), float(value["kd"]))
                        return {"status": "success", "message": f"PD gains set: kp={value['kp']}, kd={value['kd']}"}
                    else:
                        return {"status": "error", "message": "set_pd_values requires dict with 'kp' and 'kd'"}
                else:
                    return {"status": "error", "message": f"Unknown {mode} command: {command}"}

            # PD Controller specific commands (legacy)
            elif mode == "PD_Control":
                if command == "start_controller":
                    return self.start_pd_controller()
                elif command == "stop_controller":
                    return self.stop_pd_controller()
                elif command == "set_target":
                    return self.set_target_yaw(value)
                elif command == "set_gains":
                    # Expects value as dict with kp, kd, deadband, min_pulse_time
                    return self.set_controller_gains(value)
                else:
                    return {"status": "error", "message": f"Unknown PD_Control command: {command}"}

            elif mode == "Calibration":
                if command == "start_calibration":
                    return self.calibrate_sensors()
                else:
                    return {"status": "error", "message": f"Unknown Calibration command: {command}"}

            else:
                return {"status": "error", "message": f"Unknown mode: {mode}"}

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
        ctrl_info = f"Target:{data['controller']['target_yaw']:+6.1f}° Error:{data['controller']['error']:+5.1f}° Motor:{data['controller']['motor_cmd']:>4s} {ctrl_status}"
        
        # Lux data
        lux_parts = []
        for ch in LUX_CHANNELS:
            lux_parts.append(f"L{ch}:{data['lux'][ch]:6.1f}")
        lux_info = " ".join(lux_parts)
        
        status = f"{mpu_info} | {gyro_info} | {temp_info} | {ctrl_info} | {lux_info} | Status: {data['status']}"
        print(f"\r{status}", end="", flush=True)
    
    def enable_motor_driver(self):
        """Enable the motor driver (set SLEEP_PIN high)"""
        try:
            if GPIO_AVAILABLE:
                GPIO.output(SLEEP_PIN, GPIO.HIGH)
                print("Motor driver enabled (SLEEP_PIN high)")
                return {"status": "success", "message": "Motor driver enabled"}
            else:
                return {"status": "error", "message": "GPIO not available"}
        except Exception as e:
            return {"status": "error", "message": f"Enable motor error: {e}"}

    def disable_motor_driver(self):
        """Disable the motor driver (set SLEEP_PIN low)"""
        try:
            if GPIO_AVAILABLE:
                GPIO.output(SLEEP_PIN, GPIO.LOW)
                print("Motor driver disabled (SLEEP_PIN low)")
                return {"status": "success", "message": "Motor driver disabled"}
            else:
                return {"status": "error", "message": "GPIO not available"}
        except Exception as e:
            return {"status": "error", "message": f"Disable motor error: {e}"}

    def shutdown(self):
        """Shutdown the ADCS controller"""
        print("\n🛰️ ADCS Controller shutdown...")
        
        # Stop PD controller
        self.pd_controller.stop_controller()
        
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
        # Calculate error
        error = self.target_yaw - current_yaw
        
        # If controller is disabled or in input mode, don't execute control but still calculate error for display
        if not self.controller_enabled or self.input_mode:
            return "STOP", error, 0.0
        
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
        
        return motor_command, error, pd_output
    
    def set_gains(self, kp, kd):
        """Set PD controller gains"""
        self.kp = kp
        self.kd = kd
        print(f"Controller gains updated - Kp: {kp}, Kd: {kd}")
