import time
import board
import busio
import smbus
import adafruit_veml7700

# ─── I2C Setup ─────────────────────────────
i2c = busio.I2C(board.SCL, board.SDA)

# ─── VEML7700 (Light Sensor) ───────────────
veml = adafruit_veml7700.VEML7700(i2c)

# ─── MPU6050 (Motion Sensor) ───────────────
mpu_addr = 0x68
bus = smbus.SMBus(1)
bus.write_byte_data(mpu_addr, 0x6B, 0)  # Wake up sensor

def read_raw_data(addr):
    high = bus.read_byte_data(mpu_addr, addr)
    low = bus.read_byte_data(mpu_addr, addr+1)
    val = (high << 8) | low
    if val > 32767: val -= 65536
    return val

# ─── Main Loop ─────────────────────────────
while True:
    # Light
    lux = veml.light

    # Accelerometer
    ax = read_raw_data(0x3B) / 16384.0
    ay = read_raw_data(0x3D) / 16384.0
    az = read_raw_data(0x3F) / 16384.0

    # Gyroscope
    gx = read_raw_data(0x43) / 131.0
    gy = read_raw_data(0x45) / 131.0
    gz = read_raw_data(0x47) / 131.0

    print(f"Lux: {lux:.2f} lx")
    print(f"Accel: X={ax:.2f}g Y={ay:.2f}g Z={az:.2f}g")
    print(f"Gyro:  X={gx:.2f}°/s Y={gy:.2f}°/s Z={gz:.2f}°/s")
    print("-" * 40)
    time.sleep(1)
