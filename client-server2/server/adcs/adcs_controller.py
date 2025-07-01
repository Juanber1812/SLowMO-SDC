import threading
import time
import logging

from adcs.mpu import MPU6050Sensor
from adcs.lux import LuxSensorManager
from adcs.bangbang import PDBangBangController
from adcs import motor

class ADCSController:
    """Unified ADCS controller handling sensor fusion and bang-bang PD control."""

    def __init__(self):
        print("🛰️ Initializing ADCS Controller...")

        # Initialize sensors
        self.mpu_sensor = MPU6050Sensor()
        self.lux_manager = LuxSensorManager()

        # Initialize motor control
        self.motor_available = motor.setup_motor_control()

        # Initialize controller
        self.pd_controller = PDBangBangController(kp=2.0, kd=0.5, deadband=1.0, min_pulse_time=0.2)

        # Control loop variables
        self.target_yaw = 0.0
        self.data_lock = threading.Lock()
        self.current_data = {
            'yaw': 0.0,
            'gyro_z': 0.0,
            'temperature': 0.0,
            'lux': {1: 0.0, 2: 0.0, 3: 0.0}
        }

        # Threads
        self.stop_threads = False
        self.data_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)

        # Start loops
        self.data_thread.start()
        self.control_thread.start()
        print("✓ ADCS controller threads started")

    def _data_loop(self):
        """Continuously updates sensor readings."""
        while not self.stop_threads:
            yaw = self.mpu_sensor.get_yaw_angle()
            gyro_z = self.mpu_sensor.read_gyroscope()[2]
            temp = self.mpu_sensor.read_temperature()
            lux = self.lux_manager.read_lux_sensors()

            with self.data_lock:
                self.current_data['yaw'] = yaw
                self.current_data['gyro_z'] = gyro_z
                self.current_data['temperature'] = temp
                self.current_data['lux'] = lux

            time.sleep(1 / 20.0)  # 20 Hz

    def _control_loop(self):
        """Executes bang-bang PD control."""
        while not self.stop_threads:
            with self.data_lock:
                yaw = self.current_data['yaw']

            try:
                self.pd_controller.control(current_angle=yaw, target_angle=self.target_yaw)
            except Exception as e:
                logging.warning(f"[ADCS] Control error: {e}")

            time.sleep(1 / 10.0)  # 10 Hz

    def set_target_yaw(self, angle_deg):
        self.target_yaw = angle_deg
        print(f"🎯 Target yaw set to: {angle_deg:.2f}°")

    def calibrate_imu(self):
        self.mpu_sensor.calibrate_gyro()

    def zero_yaw(self):
        self.mpu_sensor.zero_yaw_position()

    def set_pd_gains(self, kp, kd):
        self.pd_controller.set_gains(kp, kd)
        print(f"🛠️ PD gains set: kp={kp}, kd={kd}")

    def set_deadband(self, db):
        self.pd_controller.set_deadband(db)
        print(f"📏 Deadband set to ±{db:.2f}°")

    def get_latest_data(self):
        with self.data_lock:
            return dict(self.current_data)

    def get_adcs_data_for_server(self):
        data = self.get_latest_data()
        return {
            "gyro": f"{data['yaw']:.1f}°",
            "orientation": f"Y:{data['yaw']:.1f}° R:{self.mpu_sensor.angle_roll:.1f}° P:{self.mpu_sensor.angle_pitch:.1f}°",
            "gyro_rate_x": "0.00",
            "gyro_rate_y": "0.00",
            "gyro_rate_z": f"{data['gyro_z']:.2f}",
            "angle_x": f"{self.mpu_sensor.angle_pitch:.1f}",
            "angle_y": f"{self.mpu_sensor.angle_roll:.1f}",
            "angle_z": f"{data['yaw']:.1f}",
            "lux1": f"{data['lux'].get(1, 0.0):.1f}",
            "lux2": f"{data['lux'].get(2, 0.0):.1f}",
            "lux3": f"{data['lux'].get(3, 0.0):.1f}",
            "temperature": f"{data['temperature']:.1f}°C",
            "rpm": "0.0",
            "status": "Nominal"
        }

    def handle_adcs_command(self, mode, command, value):
        try:
            if command == "set_yaw":
                self.set_target_yaw(float(value))
                return {"status": "ok", "message": f"Target yaw set to {value}°"}
            elif command == "zero_yaw":
                self.zero_yaw()
                return {"status": "ok", "message": "Yaw angle zeroed"}
            elif command == "calibrate":
                self.calibrate_imu()
                return {"status": "ok", "message": "IMU calibration started"}
            elif command == "set_gains":
                kp = float(value.get("kp", 1.0))
                kd = float(value.get("kd", 0.1))
                self.set_pd_gains(kp, kd)
                return {"status": "ok", "message": f"Gains updated (kp={kp}, kd={kd})"}
            elif command == "set_deadband":
                db = float(value)
                self.set_deadband(db)
                return {"status": "ok", "message": f"Deadband set to {db}°"}
            else:
                return {"status": "error", "message": f"Unknown ADCS command: {command}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop(self):
        """Stops the motor and background threads."""
        self.stop_threads = True
        motor.stop_motor()
        motor.cleanup_motor_control()

    def shutdown(self):
        """Graceful shutdown hook for server exit."""
        self.stop()
        print("🛑 ADCS controller shutdown complete")

if __name__ == "__main__":
    import sys
    import tty
    import termios

    adcs = ADCSController()

    def getch():
        """Read a single character from stdin (Linux only)"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    print("\n🛰️ ADCS Standalone Test Mode (Key Command Interface)")
    print("Press:")
    print("  s → Start motor control loop")
    print("  x → Stop motor")
    print("  z → Zero yaw")
    print("  y → Set target yaw")
    print("  g → Set PD gains")
    print("  d → Set deadband")
    print("  r → Read sensor snapshot")
    print("  q → Quit")

    try:
        while True:
            print("\n[Key Input] > ", end="", flush=True)
            key = getch().lower()

            if key == 'q':
                break
            elif key == 's':
                pass  # Threads already running
            elif key == 'x':
                adcs.stop()
            elif key == 'z':
                adcs.zero_yaw()
            elif key == 'y':
                try:
                    angle = float(input("Target yaw (deg): "))
                    adcs.set_target_yaw(angle)
                except:
                    pass
            elif key == 'g':
                try:
                    kp = float(input("Kp: "))
                    kd = float(input("Kd: "))
                    adcs.set_pd_gains(kp, kd)
                except:
                    pass
            elif key == 'd':
                try:
                    db = float(input("Deadband (deg): "))
                    adcs.set_deadband(db)
                except:
                    pass
            elif key == 'r':
                data = adcs.get_latest_data()
                print(f"Yaw: {data['yaw']:.2f}°, Gyro Z: {data['gyro_z']:.2f}, Temp: {data['temperature']:.1f}°C")
            else:
                print("Unknown key")

    except KeyboardInterrupt:
        pass

    adcs.shutdown()
