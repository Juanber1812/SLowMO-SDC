import smbus2, time

I2C_BUS       = 1
LIDAR_ADDR    = 0x62
ACQ_COMMAND   = 0x00
ACQUIRE_VAL   = 0x04
STATUS_REG    = 0x01
DIST_LOW_REG  = 0x10
DIST_HIGH_REG = 0x11

bus = smbus2.SMBus(I2C_BUS)

def read_distance():
    # 1) Trigger measurement
    bus.write_byte_data(LIDAR_ADDR, ACQ_COMMAND, ACQUIRE_VAL)
    # 2) Poll busy flag
    while (bus.read_byte_data(LIDAR_ADDR, STATUS_REG) & 0x01):
        time.sleep(0.005)
    # 3) Read low then high
    low  = bus.read_byte_data(LIDAR_ADDR, DIST_LOW_REG)
    high = bus.read_byte_data(LIDAR_ADDR, DIST_HIGH_REG)
    return (high << 8) | low

try:
    while True:
        try:
            d = read_distance()
            print(f"Distance: {d} cm")
        except OSError as e:
            print("I2C error:", e)
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    bus.close()
