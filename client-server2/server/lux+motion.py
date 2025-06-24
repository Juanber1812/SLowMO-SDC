#!/usr/bin/env python3
# combo_test.py – Motor + VEML7700 + MPU6050 interactive demo with dual-PWM

import time
import board, busio
import adafruit_veml7700
import RPi.GPIO as GPIO
import smbus

# ── GPIO PIN DEFINITIONS ─────────────────────────────
IN1 = 13  # Motor input 1 (PWM)
IN2 = 19  # Motor input 2 (PWM)
SLEEP = 26

# ── SET UP GPIO PINS ─────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setup([IN1, IN2, SLEEP], GPIO.OUT)
GPIO.output(SLEEP, GPIO.HIGH)  # Wake up driver

pwm1 = GPIO.PWM(IN1, 1000)  # 1 kHz PWM on IN1
pwm2 = GPIO.PWM(IN2, 1000)  # 1 kHz PWM on IN2
pwm1.start(0)
pwm2.start(0)

def motor_forward(speed):
    pwm2.ChangeDutyCycle(0)  # IN2 low
    pwm1.ChangeDutyCycle(speed)  # PWM on IN1

def motor_reverse(speed):
    pwm1.ChangeDutyCycle(0)  # IN1 low
    pwm2.ChangeDutyCycle(speed)  # PWM on IN2

def motor_stop():
    pwm1.ChangeDutyCycle(0)
    pwm2.ChangeDutyCycle(0)

# ── VEML7700 (lux sensor) ────────────────────────────
i2c = busio.I2C(board.SCL, board.SDA)
veml = adafruit_veml7700.VEML7700(i2c)

# ── MPU-6050 (motion sensor) ─────────────────────────
MPU_ADDR = 0x68
bus = smbus.SMBus(1)
bus.write_byte_data(MPU_ADDR, 0x6B, 0)  # Wake MPU6050

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

# ── INTERACTIVE CLI ──────────────────────────────────
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
            speed = min(max(int(cmd[1]), 0), 100)
            motor_forward(speed)
            print(f"Forward at {speed}%")
        elif cmd[0] == "r" and len(cmd) == 2:
            speed = min(max(int(cmd[1]), 0), 100)
            motor_reverse(speed)
            print(f"Reverse at {speed}%")
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
    pwm1.stop()
    pwm2.stop()
    GPIO.cleanup()
    print("\nGood-bye!")
