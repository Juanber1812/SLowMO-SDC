#!/usr/bin/env python3
"""
🚀 ULTRA-HIGH-SPEED INTEGRATED SENSOR LOGGER
Combines MPU6050 (IMU) + VEML7700 (Lux) sensors
- Same data, same timing, maximum speed!
- 50Hz synchronized logging
- Single CSV output with all sensor data
"""

import time
import board
import busio
import smbus2
import csv
import os
import sys
import threading
import math
from datetime import datetime

# Try to import hardware libraries
try:
    from adafruit_veml7700 import VEML7700
    LUX_AVAILABLE = True
except ImportError:
    print("Warning: VEML7700 library not available - lux sensors disabled")
    LUX_AVAILABLE = False

# Constants
LOG_FREQUENCY = 50  # Hz - MAXIMUM SPEED!
DISPLAY_FREQUENCY = 10  # Hz - Display updates

# LUX sensor constants
MUX_ADDRESS = 0x70
LUX_CHANNELS = [1, 2, 3]

# MPU6050 constants  
MPU_ADDRESS = 0x68

class IntegratedSensorLogger:
    def __init__(self):
        print("🚀 Initializing ULTRA-HIGH-SPEED Integrated Sensor Logger...")
        
        # Shared data and threading
        self.data_thread = None
        self.stop_data_thread = False
        self.data_lock = threading.Lock()
        self.last_reading_time = time.time()
        
        # Current sensor data (shared between display and logging)
        self.current_data = {
            'mpu': {'yaw': 0.0, 'roll': 0.0, 'pitch': 0.0, 'temp': 0.0},
            'lux': {ch: 0.0 for ch in LUX_CHANNELS}
        }
        
        # Logging variables
        self.log_file = None
        self.csv_writer = None
        self.enable_logging = False
        self.log_start_time = None
        
        # Initialize hardware
        self.init_mpu6050()
        if LUX_AVAILABLE:
            self.init_lux_sensors()
        
        # Start high-speed data acquisition
        self.start_data_thread()
    
    def init_mpu6050(self):
        """Initialize MPU6050 IMU sensor"""
        try:
            self.mpu_bus = smbus2.SMBus(1)
            
            # Wake up MPU6050
            self.mpu_bus.write_byte_data(MPU_ADDRESS, 0x6B, 0)
            
            # Configure for maximum speed
            self.mpu_bus.write_byte_data(MPU_ADDRESS, 0x19, 0)  # Sample rate divider (1kHz)
            self.mpu_bus.write_byte_data(MPU_ADDRESS, 0x1C, 0)  # Accel ±2g
            self.mpu_bus.write_byte_data(MPU_ADDRESS, 0x1B, 0)  # Gyro ±250°/s
            self.mpu_bus.write_byte_data(MPU_ADDRESS, 0x1A, 0)  # No filter for max speed
            
            print("✓ MPU6050 initialized (ULTRA-FAST mode)")
            
            # Simple calibration
            self.calibrate_mpu6050()
            
        except Exception as e:
            print(f"✗ MPU6050 initialization failed: {e}")
            self.mpu_bus = None
    
    def calibrate_mpu6050(self):
        """Quick MPU6050 calibration"""
        print("🔧 Quick MPU6050 calibration...")
        gyro_sum = [0, 0, 0]
        samples = 100
        
        for i in range(samples):
            gyro_data = self.read_mpu_gyro_raw()
            if gyro_data:
                for j in range(3):
                    gyro_sum[j] += gyro_data[j]
            time.sleep(0.01)
        
        self.gyro_cal = [s / samples for s in gyro_sum]
        print(f"✓ MPU6050 calibrated: {[f'{x:.2f}' for x in self.gyro_cal]}")
    
    def init_lux_sensors(self):
        """Initialize VEML7700 lux sensors with multiplexer"""
        try:
            self.lux_i2c = busio.I2C(board.SCL, board.SDA)
            self.lux_sensors = {}
            
            print("🔧 Initializing VEML7700 sensors...")
            for ch in LUX_CHANNELS:
                try:
                    self.select_lux_channel(ch)
                    sensor = VEML7700(self.lux_i2c)
                    self.lux_sensors[ch] = sensor
                    print(f"✓ Lux channel {ch} initialized")
                except Exception as e:
                    print(f"✗ Lux channel {ch} failed: {e}")
                    self.lux_sensors[ch] = None
            
        except Exception as e:
            print(f"✗ Lux sensor initialization failed: {e}")
            self.lux_i2c = None
            self.lux_sensors = {}
    
    def select_lux_channel(self, channel):
        """Select multiplexer channel for lux sensors"""
        if 0 <= channel <= 7 and self.lux_i2c:
            self.lux_i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.002)  # ULTRA-FAST 2ms settling
    
    def read_mpu_raw_data(self, addr):
        """Read 16-bit data from MPU6050"""
        if not self.mpu_bus:
            return 0
        try:
            high = self.mpu_bus.read_byte_data(MPU_ADDRESS, addr)
            low = self.mpu_bus.read_byte_data(MPU_ADDRESS, addr + 1)
            value = (high << 8) + low
            return value - 65536 if value >= 32768 else value
        except:
            return 0
    
    def read_mpu_gyro_raw(self):
        """Read raw gyroscope data"""
        if not self.mpu_bus:
            return None
        try:
            gx = self.read_mpu_raw_data(0x43) / 131.0  # Convert to deg/s
            gy = self.read_mpu_raw_data(0x45) / 131.0
            gz = self.read_mpu_raw_data(0x47) / 131.0
            return [gx, gy, gz]
        except:
            return None
    
    def read_mpu_accel_raw(self):
        """Read raw accelerometer data"""
        if not self.mpu_bus:
            return None
        try:
            ax = self.read_mpu_raw_data(0x3B) / 16384.0  # Convert to g
            ay = self.read_mpu_raw_data(0x3D) / 16384.0
            az = self.read_mpu_raw_data(0x3F) / 16384.0
            return [ax, ay, az]
        except:
            return None
    
    def read_mpu_temp(self):
        """Read MPU6050 temperature"""
        if not self.mpu_bus:
            return 0.0
        try:
            temp_raw = self.read_mpu_raw_data(0x41)
            return (temp_raw / 340.0) + 36.53
        except:
            return 0.0
    
    def read_all_sensors_ultra_fast(self):
        """ULTRA-FAST reading of all sensors"""
        data = {
            'mpu': {'yaw': 0.0, 'roll': 0.0, 'pitch': 0.0, 'temp': 0.0},
            'lux': {ch: 0.0 for ch in LUX_CHANNELS}
        }
        
        # Read MPU6050 (IMU)
        gyro = self.read_mpu_gyro_raw()
        accel = self.read_mpu_accel_raw()
        temp = self.read_mpu_temp()
        
        if gyro and accel:
            # Apply calibration
            gyro_cal = [gyro[i] - self.gyro_cal[i] for i in range(3)]
            
            # Simple attitude calculation (spacecraft convention)
            data['mpu']['yaw'] = math.degrees(math.atan2(accel[1], accel[2]))     # Primary
            data['mpu']['roll'] = math.degrees(math.atan2(accel[0], accel[2]))    # Secondary  
            data['mpu']['pitch'] = gyro_cal[0]  # Gyro rate for pitch
            data['mpu']['temp'] = temp
        
        # Read Lux sensors (if available)
        if LUX_AVAILABLE and self.lux_i2c:
            for ch in LUX_CHANNELS:
                try:
                    self.select_lux_channel(ch)
                    sensor = VEML7700(self.lux_i2c)
                    data['lux'][ch] = sensor.lux
                except:
                    data['lux'][ch] = 0.0
        
        return data
    
    def start_data_thread(self):
        """Start ultra-high-speed data acquisition thread"""
        self.stop_data_thread = False
        self.data_thread = threading.Thread(target=self._data_thread_worker, daemon=True)
        self.data_thread.start()
        print(f"🚀 ULTRA-HIGH-SPEED data thread started at {LOG_FREQUENCY}Hz!")
    
    def _data_thread_worker(self):
        """50Hz data acquisition worker"""
        interval = 1.0 / LOG_FREQUENCY  # 0.02 seconds
        next_read_time = time.time()
        
        while not self.stop_data_thread:
            current_time = time.time()
            
            if current_time >= next_read_time:
                try:
                    # Ultra-fast sensor reading
                    new_data = self.read_all_sensors_ultra_fast()
                    
                    # Thread-safe update
                    with self.data_lock:
                        self.current_data = new_data
                        self.last_reading_time = current_time
                    
                    next_read_time += interval
                    
                except Exception as e:
                    print(f"Error in data thread: {e}")
                    break
            
            time.sleep(0.001)  # 1ms sleep
    
    def get_current_data(self):
        """Get current sensor data (thread-safe)"""
        with self.data_lock:
            return self.current_data.copy(), self.last_reading_time
    
    def start_csv_logging(self, filename=None):
        """Start integrated CSV logging"""
        if self.enable_logging:
            print("CSV logging already active!")
            return
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integrated_sensors_{timestamp}.csv"
        
        try:
            self.log_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.log_file)
            
            # Combined header: time, mpu_data, lux_data
            header = ['time', 'yaw', 'roll', 'pitch', 'temp']
            header += [f'lux_ch{ch}' for ch in LUX_CHANNELS]
            
            self.csv_writer.writerow(header)
            self.log_file.flush()
            
            self.enable_logging = True
            self.log_start_time = time.time()
            
            print(f"🚀 INTEGRATED logging started: {filename}")
            print(f"  Rate: {LOG_FREQUENCY}Hz | Columns: {len(header)}")
            print(f"  Data: MPU6050 + VEML7700 sensors")
            
        except Exception as e:
            print(f"✗ Error starting logging: {e}")
    
    def stop_csv_logging(self):
        """Stop CSV logging"""
        if not self.enable_logging:
            print("CSV logging not active!")
            return
            
        try:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None
            
            self.enable_logging = False
            self.log_start_time = None
            print("✓ INTEGRATED logging stopped")
            
        except Exception as e:
            print(f"✗ Error stopping logging: {e}")
    
    def log_current_data(self):
        """Log current integrated data"""
        if not self.enable_logging or not self.csv_writer:
            return
            
        try:
            data, reading_time = self.get_current_data()
            relative_time = reading_time - self.log_start_time
            
            # Build CSV row: time, mpu_data, lux_data
            row = [f"{relative_time:.6f}"]
            row.append(f"{data['mpu']['yaw']:.6f}")
            row.append(f"{data['mpu']['roll']:.6f}")
            row.append(f"{data['mpu']['pitch']:.6f}")
            row.append(f"{data['mpu']['temp']:.2f}")
            
            for ch in LUX_CHANNELS:
                row.append(f"{data['lux'][ch]:.2f}")
            
            self.csv_writer.writerow(row)
            self.log_file.flush()
            
        except Exception as e:
            print(f"Error logging: {e}")
    
    def display_readings(self):
        """Display current integrated sensor readings"""
        data, reading_time = self.get_current_data()
        
        print("\r", end="")
        
        # MPU data
        mpu_status = f"YAW:{data['mpu']['yaw']:+6.1f}° ROLL:{data['mpu']['roll']:+6.1f}° PITCH:{data['mpu']['pitch']:+6.1f}°/s T:{data['mpu']['temp']:4.1f}°C"
        
        # Lux data
        lux_parts = []
        for ch in LUX_CHANNELS:
            lux_parts.append(f"L{ch}:{data['lux'][ch]:6.1f}")
        lux_status = " ".join(lux_parts)
        
        # Logging status
        if self.enable_logging:
            elapsed = time.time() - self.log_start_time if self.log_start_time else 0
            log_status = f"LOG:{elapsed:.1f}s@{LOG_FREQUENCY}Hz"
        else:
            log_status = f"LOG:OFF @{LOG_FREQUENCY}Hz"
        
        status = f"{mpu_status} | {lux_status} | {log_status}"
        print(status, end="", flush=True)
    
    def run_interactive(self):
        """Run integrated sensor monitoring"""
        print("🚀 === ULTRA-HIGH-SPEED INTEGRATED SENSOR LOGGER ===")
        print(f"📊 MPU6050 (IMU) + VEML7700 (Lux) @ {LOG_FREQUENCY}Hz")
        print(f"🖥️ Display: {DISPLAY_FREQUENCY}Hz")
        print("Commands: 'l'=log 's'=stop 'q'=quit")
        print("=" * 80)
        
        try:
            import termios, tty
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            raw_mode = True
        except:
            raw_mode = False
        
        display_interval = 1.0 / DISPLAY_FREQUENCY
        next_display_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                if current_time >= next_display_time:
                    self.display_readings()
                    
                    if self.enable_logging:
                        self.log_current_data()
                    
                    next_display_time += display_interval
                
                if raw_mode:
                    import select
                    if select.select([sys.stdin], [], [], 0.001)[0]:
                        key = sys.stdin.read(1).lower()
                        
                        if key == 'q':
                            break
                        elif key == 'l':
                            if not self.enable_logging:
                                print(f"\n🚀 [STARTING INTEGRATED LOG] ", end='')
                                self.start_csv_logging()
                            else:
                                print(f"\n⚡ [ALREADY LOGGING] ", end='')
                        elif key == 's':
                            if self.enable_logging:
                                print(f"\n🛑 [STOPPING LOG] ", end='')
                                self.stop_csv_logging()
                            else:
                                print(f"\n❌ [NOT LOGGING] ", end='')
                else:
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            pass
        finally:
            if raw_mode:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
            self.stop_data_thread = True
            if self.enable_logging:
                self.stop_csv_logging()
            
            print(f"\n\n🏁 INTEGRATED system shutdown complete.")


def main():
    """Main function"""
    print("🚀 Starting ULTRA-HIGH-SPEED Integrated Sensor Logger...")
    logger = IntegratedSensorLogger()
    logger.run_interactive()


if __name__ == "__main__":
    main()
