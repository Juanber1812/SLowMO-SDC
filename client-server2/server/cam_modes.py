# list_camera_modes.py
from picamera2 import Picamera2

picam2 = Picamera2()
modes = picam2.sensor_modes

print("\n📸 Supported Sensor Modes:\n")
for i, mode in enumerate(modes):
    print(f"{i}: Resolution = {mode['size']}, Format = {mode['format']}, "
          f"Bit Depth = {mode['bit_depth']}, FPS = {mode['fps']}")
