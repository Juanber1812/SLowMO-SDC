import time
import sys
import board # type: ignore
import adafruit_ina228 # type: ignore

try:
    i2c = board.I2C()
except Exception as e:
    print(f"Error initializing I2C: {e}")
    sys.exit(1)

try:
    ina228 = adafruit_ina228.INA228(i2c)
except Exception as e:
    print(f"Error initializing INA228 sensor: {e}")
    sys.exit(1)

while True:
    try:
        print(f"Current: {ina228.current:.2f} mA")
        print(f"Bus Voltage: {ina228.voltage:.2f} V")
        print(f"Shunt Voltage: {ina228.shunt_voltage*1000:.2f} mV")
        print(f"Power: {ina228.power:.2f} mW")
        print(f"Energy: {ina228.energy:.2f} J")
        print(f"Temperature: {ina228.temperature:.2f} C")
    except Exception as e:
        print(f"Error reading sensor data: {e}")
    time.sleep(1)
