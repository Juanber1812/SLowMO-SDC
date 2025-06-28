import time
import board
import busio
from adafruit_veml7700 import VEML7700

# Constants
MUX_ADDRESS = 0x70  # I2C address of the multiplexer
CHANNELS = [0, 1, 2]  # Channels where VEML7700s are connected

# Setup I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Function to select multiplexer channel
def select_channel(channel):
    if 0 <= channel <= 7:
        i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
    else:
        raise ValueError("Invalid channel: must be 0-7")

# Initialize sensors
sensors = []
for ch in CHANNELS:
    select_channel(ch)
    time.sleep(0.1)  # allow I2C bus to settle
    sensor = VEML7700(i2c)
    sensors.append(sensor)

# Read loop
print("Reading lux values from channels 0–2:")
try:
    while True:
        for idx, ch in enumerate(CHANNELS):
            select_channel(ch)
            time.sleep(0.05)
            lux = sensors[idx].lux
            print(f"Channel {ch}: {lux:.2f} lux")
        print("-" * 30)
        time.sleep(1.0)

except KeyboardInterrupt:
    print("\nStopped by user.")
