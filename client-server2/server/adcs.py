import time
import threading
import random

# --- Simple MPU6050 Sensor Stub ---
class MPU6050Sensor:
    def __init__(self):
        self.yaw = 0.0
        self.gyro_z_offset = 0.0
        self.sensor_ready = True

    def calibrate_gyro(self):
        self.gyro_z_offset = random.uniform(-0.5, 0.5)
        print(f"[CALIBRATION] Gyro Z offset set to {self.gyro_z_offset:.3f}")

    def zero_yaw_position(self):
        self.yaw = 0.0
        print("[MPU] Yaw zeroed.")

    def read_gyroscope(self):
        # Simulate gyro rate
        return 0.0, 0.0, random.uniform(-1, 1) + self.gyro_z_offset

    def get_yaw_angle(self):
        # Simulate yaw drift
        self.yaw += random.uniform(-0.2, 0.2)
        return self.yaw

# --- Simple Lux Sensor Stub ---
class LuxSensorManager:
    def __init__(self):
        self.sensors_ready = True
        self.lux = {1: 100.0, 2: 100.0, 3: 100.0}

    def read_lux_sensors(self):
        # Simulate lux readings
        for ch in self.lux:
            self.lux[ch] = random.uniform(80, 120)
        return self.lux.copy()

# --- Simple Motor Control ---
def rotate_clockwise():
    print("[MOTOR] Rotating clockwise.")

def rotate_counterclockwise():
    print("[MOTOR] Rotating counterclockwise.")

def stop_motor():
    print("[MOTOR] Stopped.")

# --- Simple PD Controller ---
class SimplePDController:
    def __init__(self):
        self.target = 0.0
        self.enabled = False

    def set_target(self, target):
        self.target = target
        print(f"[PD] Target set to {self.target:.1f}°")

    def start(self):
        self.enabled = True
        print("[PD] Controller started.")

    def stop(self):
        self.enabled = False
        stop_motor()
        print("[PD] Controller stopped.")

    def update(self, current_yaw):
        if not self.enabled:
            return
        error = self.target - current_yaw
        if abs(error) < 1.0:
            stop_motor()
        elif error > 0:
            rotate_clockwise()
        else:
            rotate_counterclockwise()

# --- Main ADCS Controller ---
class SimpleADCS:
    def __init__(self):
        self.mpu = MPU6050Sensor()
        self.lux = LuxSensorManager()
        self.pd = SimplePDController()
        self.manual_mode = False
        self.running = True
        self.thread = threading.Thread(target=self.loop)
        self.thread.daemon = True
        self.thread.start()

    def loop(self):
        while self.running:
            if self.pd.enabled and not self.manual_mode:
                yaw = self.mpu.get_yaw_angle()
                self.pd.update(yaw)
            time.sleep(0.1)

    def handle_command(self, cmd, value=None):
        # Accept both simple and legacy command names for compatibility
        if cmd in ("cw", "manual_clockwise_start"):
            self.manual_mode = True
            self.pd.stop()
            rotate_clockwise()
        elif cmd in ("ccw", "manual_counterclockwise_start"):
            self.manual_mode = True
            self.pd.stop()
            rotate_counterclockwise()
        elif cmd in ("stop", "manual_stop"):
            self.manual_mode = False
            stop_motor()
        elif cmd in ("pd_start", "start"):
            self.manual_mode = False
            self.pd.start()
        elif cmd in ("pd_stop", "stop_pd"):
            self.pd.stop()
        elif cmd in ("set_target", "set_value"):
            try:
                target = float(value)
                self.pd.set_target(target)
            except:
                print("[ERROR] Invalid target value.")
        elif cmd in ("set_zero",):
            self.mpu.zero_yaw_position()
        elif cmd in ("calibrate",):
            self.mpu.calibrate_gyro()
        elif cmd in ("read_lux",):
            print("[LUX]", self.lux.read_lux_sensors())
        else:
            print(f"[ERROR] Unknown command: {cmd}")

    def shutdown(self):
        self.running = False
        self.pd.stop()
        stop_motor()
        print("[ADCS] Shutdown complete.")

# --- Simple CLI for Testing ---
def main():
    adcs = SimpleADCS()
    print("Simple ADCS Controller. Commands: cw, ccw, stop, pd_start, pd_stop, set_target <deg>, set_zero, calibrate, read_lux, quit")
    try:
        while True:
            cmd = input("Command: ").strip().split()
            if not cmd:
                continue
            if cmd[0] == "quit":
                break
            elif len(cmd) == 2:
                adcs.handle_command(cmd[0], cmd[1])
            else:
                adcs.handle_command(cmd[0])
    except KeyboardInterrupt:
        pass
    finally:
        adcs.shutdown()

if __name__ == "__main__":
    main()
