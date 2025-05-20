import subprocess
import time
import cv2
from picamera2 import Picamera2

# Step 1: Start MediaMTX if not already running
try:
    subprocess.run(["pgrep", "mediamtx"], check=True, stdout=subprocess.DEVNULL)
    print("[INFO] MediaMTX already running.")
except subprocess.CalledProcessError:
    print("[INFO] Starting MediaMTX...")
    subprocess.Popen(["mediamtx"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # Wait briefly for MediaMTX to start

# Step 2: Start and configure the PiCamera2
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (1280, 720)}, controls={"FrameRate": 30})
picam2.configure(config)
picam2.start()

# Step 3: FFmpeg command to stream to RTSP server
ffmpeg_cmd = [
    'ffmpeg',
    '-f', 'rawvideo',
    '-pix_fmt', 'yuv420p',
    '-s', '1280x720',
    '-r', '30',
    '-i', 'pipe:',
    '-f', 'rtsp',
    '-rtsp_transport', 'tcp',
    '-fflags', 'nobuffer',
    '-flags', 'low_delay',
    '-an',
    '-vcodec', 'libx264',
    '-preset', 'ultrafast',
    '-tune', 'zerolatency',
    '-pix_fmt', 'yuv420p',
    '-g', '30',  # GOP size
    '-keyint_min', '30',
    '-b:v', '1M',
    '-bufsize', '1M',
    'rtsp://localhost:8554/mystream'
]


process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

# Step 4: Capture frames, convert to YUV420p, send to FFmpeg
try:
    while True:
        frame_rgb = picam2.capture_array("main")  # Capture RGB
        frame_yuv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2YUV_I420)  # Convert to YUV420p
        process.stdin.write(frame_yuv.tobytes())  # Send to FFmpeg
except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user.")
finally:
    process.stdin.close()
    process.wait()
    picam2.stop()
    print("[INFO] Camera and stream stopped.")
