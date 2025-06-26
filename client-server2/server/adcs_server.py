# Required libraries
import time
import sys
import math
import threading
import argparse

import RPi.GPIO as GPIO
import board, busio, smbus
import adafruit_tca9548a
from adafruit_tca9548a import TCA9548A
import adafruit_veml7700
import numpy as np

# ── PIN & I²C SETUP ─────────────────────────────────────────────
PWM_PIN, DIR_PIN, SLEEP_PIN = 13, 19, 26
RPM_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup([PWM_PIN, DIR_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RPM_PIN, GPIO.IN)
GPIO.output(SLEEP_PIN, GPIO.HIGH)

pwm = GPIO.PWM(PWM_PIN, 1000)
pwm.start(0)

i2c = busio.I2C(board.SCL, board.SDA)
tca = TCA9548A(i2c)

lux_sensors = [
  adafruit_veml7700.VEML7700(tca[0]),
  adafruit_veml7700.VEML7700(tca[1]),
  adafruit_veml7700.VEML7700(tca[2]),
]

bus = smbus.SMBus(1)
Device_Address = 0x68
PWR_MGMT_1, SMPLRT_DIV, CONFIG, GYRO_CONFIG, INT_ENABLE = 0x6B, 0x19, 0x1A, 0x1B, 0x38
ACCEL_XOUT_H, ACCEL_YOUT_H, ACCEL_ZOUT_H = 0x3B, 0x3D, 0x3F
GYRO_XOUT_H, GYRO_YOUT_H, GYRO_ZOUT_H = 0x43, 0x45, 0x47

# ── MOTOR HELPERS ────────────────────────────────────────────────
def motor_forward(speed: int):
    GPIO.output(DIR_PIN, GPIO.LOW)
    pwm.ChangeDutyCycle(max(0, min(100, speed)))

def motor_backward(speed: int):
    GPIO.output(DIR_PIN, GPIO.HIGH)
    pwm.ChangeDutyCycle(max(0, min(100, speed)))

def stop_motor():
    pwm.ChangeDutyCycle(0)

# ── MPU INITIALIZATION & READ ────────────────────────────────────
def MPU_Init():
    bus.write_byte_data(Device_Address, SMPLRT_DIV, 7)
    bus.write_byte_data(Device_Address, PWR_MGMT_1, 1)
    bus.write_byte_data(Device_Address, CONFIG, 0)
    bus.write_byte_data(Device_Address, GYRO_CONFIG, 24)
    bus.write_byte_data(Device_Address, INT_ENABLE, 1)

def read_raw_data(addr):
    high = bus.read_byte_data(Device_Address, addr)
    low = bus.read_byte_data(Device_Address, addr+1)
    val = (high << 8) | low
    return val - 65536 if val > 32767 else val

def read_gyroscope():
    return (
        read_raw_data(GYRO_XOUT_H)/131.0,
        read_raw_data(GYRO_YOUT_H)/131.0,
        read_raw_data(GYRO_ZOUT_H)/131.0,
    )

def read_accelerometer():
    return (
        read_raw_data(ACCEL_XOUT_H)/16384.0,
        read_raw_data(ACCEL_YOUT_H)/16384.0,
        read_raw_data(ACCEL_ZOUT_H)/16384.0,
    )

def read_lux_sensors():
    return [s.light for s in lux_sensors]

MPU_Init()

# ── EMERGENCY STOP ───────────────────────────────────────────────
EMERGENCY_PIN = 16
emergency_stop_flag = False

def emergency_stop_handler(channel):
    global emergency_stop_flag
    emergency_stop_flag = True
    stop_motor()
    print("\n*** EMERGENCY STOP ***")
    GPIO.cleanup()
    sys.exit(1)

GPIO.setup(EMERGENCY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(EMERGENCY_PIN, GPIO.FALLING,
                      callback=emergency_stop_handler, bouncetime=200)

# ── COMPLEMENTARY FILTER ────────────────────────────────────────
class ComplementaryFilter:
    def __init__(self, alpha=0.98):
        self.alpha = alpha
        self.angle = 0.0

    def update(self, gyro_rate, accel_angle, dt):
        self.angle = (self.alpha * (self.angle + gyro_rate*dt)
                      + (1-self.alpha)*accel_angle)
        return self.angle

comp_filter = ComplementaryFilter(alpha=0.98)
orientation = 0.0

# ── PD CONTROLLER ───────────────────────────────────────────────
class PDController:
    def __init__(self, Kp, Kd):
        self.Kp, self.Kd = Kp, Kd
        self.prev_error = 0.0

    def compute(self, target, actual, dt):
        error = target - actual
        deriv = (error - self.prev_error)/dt if dt>0 else 0.0
        self.prev_error = error
        return self.Kp*error + self.Kd*deriv

# ── MODES ────────────────────────────────────────────────────────
def orientation_loop():
    global orientation
    print("Starting fused orientation loop (E-stop abort).")
    start = time.perf_counter()
    while not emergency_stop_flag:
        now = time.perf_counter(); dt = now - start; start = now
        gx,gy,gz = read_gyroscope()
        ax,ay,az = read_accelerometer()
        accel_ang = math.atan2(ay, az)
        orientation = comp_filter.update(math.radians(gz), accel_ang, dt)
        print(f"Orient: {math.degrees(orientation):.2f}°", end='\r', flush=True)
        time.sleep(0.01)
    stop_motor()
    GPIO.cleanup()

def environmental_calibration_mode():
    global orientation
    ax,ay,az = read_accelerometer()
    init_ang = math.atan2(ay, az)
    comp_filter.angle = init_ang
    orientation = 0.0
    print(f"Init zero = {math.degrees(init_ang):.2f}° gravity")
    motor_forward(50)
    print("Sweeping @50%… waiting for peak lux.")
    history = []
    start = time.perf_counter()
    peak = False
    while not peak and not emergency_stop_flag:
        now = time.perf_counter(); dt = now - start; start = now
        gx,gy,gz = read_gyroscope()
        ax,ay,az = read_accelerometer()
        orientation = comp_filter.update(math.radians(gz), math.atan2(ay,az), dt)
        lux = read_lux_sensors()
        history.append(lux)
        if len(history)>=3:
            p,c,n = history[-3], history[-2], history[-1]
            for i in range(3):
                if c[i]>p[i] and c[i]>n[i]:
                    print(f"→ Sensor {i} peak {c[i]:.1f} lux")
                    peak = True; break
        time.sleep(0.01)
    zero_off = comp_filter.angle
    print(f"Captured zero offset {math.degrees(zero_off):.2f}°")
    comp_filter.angle = 0.0; orientation = 0.0
    stop_motor()
    print("Env calibration done.")

def manual_orientation_mode():
    print("Manual mode: 'f'=forward, 'b'=backward, 's'=stop, 'q'=quit")
    while True:
        cmd = input("cmd> ").strip().lower()
        if cmd=='f': motor_forward(50)
        elif cmd=='b': motor_backward(50)
        elif cmd=='s': stop_motor()
        elif cmd=='q': break
        else: print("unknown")

def automatic_orientation_mode(target):
    global orientation
    pd = PDController(Kp=1600, Kd=80)
    print(f"Auto mode → {math.degrees(target):.2f}°")
    start = time.perf_counter()
    while not emergency_stop_flag:
        now = time.perf_counter(); dt = now - start; start = now
        gx,gy,gz = read_gyroscope()
        ax,ay,az = read_accelerometer()
        orientation = comp_filter.update(math.radians(gz),
                                        math.atan2(ay,az), dt)
        err = target - orientation
        if abs(err) < math.radians(0.1): break
        ctrl = pd.compute(target, orientation, dt)
        spd = max(0, min(100, abs(ctrl)))
        motor_forward(spd) if ctrl>0 else motor_backward(spd)
        time.sleep(0.01)
    stop_motor()
    print("Auto target reached.")

def detumbling_mode():
    automatic_orientation_mode(0.0)

def live_sensor_mode():
    print("\n=== LIVE SENSOR MODE ===")
    print("  motor cmds: use separate shell with 'motor_forward|motor_backward|stop'")
    print(" Ctrl-C to exit live\n")
    try:
        while True:
            gx,gy,gz = read_gyroscope()
            ax,ay,az = read_accelerometer()
            lux = read_lux_sensors()
            line = (f"Gyro({gx:.1f},{gy:.1f},{gz:.1f})  "
                    f"Accel({ax:.2f},{ay:.2f},{az:.2f})  "
                    f"Lux[{lux[0]:.1f},{lux[1]:.1f},{lux[2]:.1f}]")
            print(line, end='\r', flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nLive mode stopped.")

# ── CLI DISPATCH ────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser("Test ADCS")
    parser.add_argument("cmd", nargs="?", default="live",
                        choices=["motor_forward","motor_backward","stop",
                                 "read_gyro","read_accel",
                                 "orientation","env_cal","manual",
                                 "auto","detumble","live"])
    parser.add_argument("-s","--speed", type=int, default=50)
    parser.add_argument("-a","--angle", type=float, default=0.0)
    args = parser.parse_args()

    try:
        if args.cmd=="motor_forward": motor_forward(args.speed)
        elif args.cmd=="motor_backward": motor_backward(args.speed)
        elif args.cmd=="stop": stop_motor()
        elif args.cmd=="read_gyro": print("Gyro:", read_gyroscope())
        elif args.cmd=="read_accel": print("Accel:", read_accelerometer())
        elif args.cmd=="orientation": orientation_loop()
        elif args.cmd=="env_cal": environmental_calibration_mode()
        elif args.cmd=="manual": manual_orientation_mode()
        elif args.cmd=="auto": automatic_orientation_mode(math.radians(args.angle))
        elif args.cmd=="detumble": detumbling_mode()
        elif args.cmd=="live": live_sensor_mode()
    finally:
        stop_motor()

