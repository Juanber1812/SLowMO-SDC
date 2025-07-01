import time
import smbus2

# MPU6050 constants
MPU_ADDRESS = 0x68

class MPU6050Sensor:
    """Handles communication and yaw-angle integration for MPU6050."""

    def __init__(self, bus_number=1, device_address=MPU_ADDRESS):
        self.bus = smbus2.SMBus(bus_number)
        self.device_address = device_address

        # Calibration values
        self.gyro_x_cal = 0.0
        self.gyro_y_cal = 0.0
        self.gyro_z_cal = 0.0

        # Orientation angles
        self.angle_yaw = 0.0
        self.angle_yaw_pure = 0.0  # Control axis
        self.angle_roll = 0.0
        self.angle_pitch = 0.0

        # Timing
        self.last_time = time.time()
        self.dt = 0.0

        # Status
        self.sensor_ready = False
        self.initialize_sensor()

    def initialize_sensor(self):
        """Initializes MPU6050 with standard settings."""
        try:
            self.bus.write_byte_data(self.device_address, 0x6B, 0)   # Wake
            self.bus.write_byte_data(self.device_address, 0x19, 0)   # 1kHz sample rate
            self.bus.write_byte_data(self.device_address, 0x1C, 0)   # Accel ±2g
            self.bus.write_byte_data(self.device_address, 0x1B, 0)   # Gyro ±250°/s
            self.bus.write_byte_data(self.device_address, 0x1A, 0)   # No filter

            print("✓ MPU6050 initialized successfully")
            time.sleep(0.1)
            self.sensor_ready = True
        except Exception as e:
            print(f"✗ MPU6050 initialization failed: {e}")
            self.sensor_ready = False

    def calibrate_gyro(self, samples=2000):
        """Calibrate gyroscope with the sensor stationary."""
        print("🔧 Calibrating MPU6050... Keep sensor still")
        gyro_sum = [0, 0, 0]

        for i in range(samples):
            try:
                g = self.read_gyroscope_raw()
                if g:
                    gyro_sum = [gyro_sum[j] + g[j] for j in range(3)]
                if i % 400 == 0:
                    print(f"Calibration {100*i/samples:.1f}%")
                time.sleep(0.004)
            except:
                continue

        self.gyro_x_cal = gyro_sum[0] / samples
        self.gyro_y_cal = gyro_sum[1] / samples
        self.gyro_z_cal = gyro_sum[2] / samples
        print(f"✓ Calibration complete: X={self.gyro_x_cal:.2f}, Y={self.gyro_y_cal:.2f}, Z={self.gyro_z_cal:.2f}")

    def read_raw_data(self, addr):
        """Reads raw 16-bit value from MPU6050."""
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
        """Reads uncalibrated gyro rates in deg/s."""
        if not self.sensor_ready:
            return None
        try:
            gx = self.read_raw_data(0x43) / 131.0
            gy = self.read_raw_data(0x45) / 131.0
            gz = self.read_raw_data(0x47) / 131.0
            return [gx, gy, gz]
        except:
            return None

    def read_gyroscope(self):
        """Returns calibrated gyro rates."""
        raw = self.read_gyroscope_raw()
        if not raw:
            return [0.0, 0.0, 0.0]
        return [
            raw[0] - self.gyro_x_cal,
            raw[1] - self.gyro_y_cal,
            raw[2] - self.gyro_z_cal
        ]

    def read_temperature(self):
        """Returns internal temperature in °C."""
        if not self.sensor_ready:
            return 0.0
        try:
            temp_raw = self.read_raw_data(0x41)
            return (temp_raw / 340.0) + 36.53
        except:
            return 0.0

    def update_angles(self):
        """Integrate gyro to update yaw, pitch, roll."""
        current_time = time.time()
        self.dt = current_time - self.last_time
        self.last_time = current_time

        gyro = self.read_gyroscope()
        if gyro and self.dt > 0:
            self.angle_yaw_pure += gyro[2] * self.dt
            self.angle_roll     += gyro[1] * self.dt
            self.angle_pitch    += gyro[0] * self.dt
            self.angle_yaw = self.angle_yaw_pure  # For display

    def get_yaw_angle(self):
        """Returns current yaw angle from pure gyro integration."""
        self.update_angles()
        return self.angle_yaw_pure

    def zero_yaw_position(self):
        """Zero the yaw position."""
        self.angle_yaw = 0.0
        self.angle_yaw_pure = 0.0
        self.angle_roll = 0.0
        self.angle_pitch = 0.0
        print("✓ Yaw zeroed to current orientation")

    def attempt_reconnection(self):
        """Attempts to reset the MPU6050 bus and reinitialize."""
        try:
            print("🔄 Reconnecting to MPU6050...")
            self.bus.close()
            self.bus = smbus2.SMBus(1)
            time.sleep(0.1)
            self.initialize_sensor()
            return self.sensor_ready
        except Exception as e:
            print(f"✗ Reconnection failed: {e}")
            return False
