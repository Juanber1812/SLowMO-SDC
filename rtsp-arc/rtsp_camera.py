import subprocess
import time
from picamera2 import Picamera2

# Step 1: Start MediaMTX if not already running
try:
    subprocess.run(["pgrep", "mediamtx"], check=True, stdout=subprocess.DEVNULL)
    print("[INFO] MediaMTX already running.")
except subprocess.CalledProcessError:
    print("[INFO] Starting MediaMTX...")
    subprocess.Popen(["mediamtx"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # Give it time to start

# Step 2: Start camera
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (1280, 720)}, controls={"FrameRate": 30})
picam2.configure(config)
picam2.start()

# Step 3: Launch FFmpeg to stream
ffmpeg_cmd = [
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "rgb24",
    "-s", "1280x720",
    "-r", "30",
    "-i", "-",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-f", "rtsp",
    "rtsp://localhost:8554/mystream"
]
process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

# Step 4: Capture and send frames
try:
    while True:
        frame = picam2.capture_array("main")
        process.stdin.write(frame.tobytes())
except KeyboardInterrupt:
    print("Interrupted.")
finally:
    process.stdin.close()
    process.wait()
    picam2.stop()
