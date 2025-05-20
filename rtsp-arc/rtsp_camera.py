from picamera2 import Picamera2
import subprocess
import time

# Initialize camera
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (1280, 720)}, controls={"FrameRate": 30})
picam2.configure(config)
picam2.start()

# Start ffmpeg subprocess to stream H.264 to MediaMTX RTSP server
ffmpeg_cmd = [
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "rgb24",
    "-s", "1280x720",
    "-r", "30",
    "-i", "-",  # Input from stdin
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-f", "rtsp",
    "rtsp://localhost:8554/mystream"
]

process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

try:
    while True:
        frame = picam2.capture_array("main")
        process.stdin.write(frame.tobytes())
except KeyboardInterrupt:
    print("Interrupted. Stopping stream...")
finally:
    process.stdin.close()
    process.wait()
    picam2.stop()
