#!/usr/bin/env python3
# combo_test.py  –  Motor + VEML7700 + MPU6050 interactive demo
import time
import board, busio
import adafruit_veml7700
import RPi.GPIO as GPIO
import smbus

# ── GPIO PIN DEFINITIONS ───────────────────────────────────────────────
PWM_PIN   = 13   # IN1  (hardware-PWM)
DIR_PIN   = 19   # IN2
SLEEP_PIN = 26   # SLEEP (enable)

# ── SET UP MOTOR DRIVER PINS ───────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setup([PWM_PIN, DIR_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
pwm = GPIO.PWM(PWM_PIN, 1000)        # 1 kHz PWM
pwm.start(0)                         # speed = 0 %

GPIO.output(SLEEP_PIN, GPIO.HIGH)    # wake up driver

def motor_forward(speed):
    GPIO.output(DIR_PIN, GPIO.LOW)
    pwm.ChangeDutyCycle(speed)

def motor_reverse(speed):
    GPIO.output(DIR_PIN, GPIO.HIGH)
    pwm.ChangeDutyCycle(speed)

def motor_stop():
    pwm.ChangeDutyCycle(0)

# ── VEML7700 (lux sensor) ─────────────────────────────────────────────
i2c = busio.I2C(board.SCL, board.SDA)
veml = adafruit_veml7700.VEML7700(i2c)

# ── MPU-6050 (motion sensor) ───────────────────────────────────────────
MPU_ADDR = 0x68
bus = smbus.SMBus(1)
bus.write_byte_data(MPU_ADDR, 0x6B, 0)          # exit sleep

def mpu_raw(addr):
    hi = bus.read_byte_data(MPU_ADDR, addr)
    lo = bus.read_byte_data(MPU_ADDR, addr+1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu():
    ax = mpu_raw(0x3B) / 16384.0
    ay = mpu_raw(0x3D) / 16384.0
    az = mpu_raw(0x3F) / 16384.0
    gx = mpu_raw(0x43) / 131.0
    gy = mpu_raw(0x45) / 131.0
    gz = mpu_raw(0x47) / 131.0
    return ax, ay, az, gx, gy, gz

# ── INTERACTIVE CLI ────────────────────────────────────────────────────
menu = """
Commands:
  f [0-100]   – forward  (e.g. f 60)
  r [0-100]   – reverse  (e.g. r 30)
  s           – stop motor
  lux         – read lux sensor
  mpu         – read accelerometer & gyro
  q           – quit
"""

print(menu)
try:
    while True:
        cmd = input(">").strip().lower().split()
        if not cmd:
            continue
        if cmd[0] == "q":
            break
        elif cmd[0] == "s":
            motor_stop()
            print("Motor stopped.")
        elif cmd[0] == "f" and len(cmd) == 2:
            motor_forward(min(max(int(cmd[1]), 0), 100))
            print(f"Forward at {cmd[1]} %")
        elif cmd[0] == "r" and len(cmd) == 2:
            motor_reverse(min(max(int(cmd[1]), 0), 100))
            print(f"Reverse at {cmd[1]} %")
        elif cmd[0] == "lux":
            print(f"Lux: {veml.light:.2f} lx")
        elif cmd[0] == "mpu":
            ax, ay, az, gx, gy, gz = read_mpu()
            print(f"Accel  g:  X={ax:.2f} Y={ay:.2f} Z={az:.2f}")
            print(f"Gyro °/s:  X={gx:.2f} Y={gy:.2f} Z={gz:.2f}")
        else:
            print("Unknown command.")
            print(menu)
except KeyboardInterrupt:
    pass
finally:
    motor_stop()
    pwm.stop()
    GPIO.cleanup()
    print("\nGood-bye!")
