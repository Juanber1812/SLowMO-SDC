# camera.py (refactored)

from gevent import monkey; monkey.patch_all()
import time
import socketio
import cv2
from picamera2 import Picamera2

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

last_status = None
last_fps_value = None

def print_status_line(status, resolution, jpeg_quality, fps, fps_value):
    global last_status, last_fps_value
    msg = f"[CAMERA] {status} | Res:{resolution} | Q:{jpeg_quality} | FPS:{fps} | {fps_value}fps"
    # Only print a new line if status (Idle/Streaming) changes
    if last_status != status:
        print()  # Move to a new line if status changes (optional, can remove for always-in-place)
        last_status = status
    # Always update the line in place
    print(msg.ljust(80), end='\r', flush=True)
    last_fps_value = fps_value

class CameraStreamer:
    def __init__(self):
        self.streaming = False
        self.connected = False
        self.config = {
            "jpeg_quality": 70,
            "fps": 10,
            "resolution": [1536, 864],
            "brightness": 0.0,             # Default brightness
            "exposure_time": None,         # None means auto         # Enable AE by default
        }
        self.picam = Picamera2()

    def connect_socket(self):
        try:
            sio.connect(SERVER_URL)
            self.connected = True
            sio.emit("camera_status", {"status": "Idle"})
            # Send initial camera info
            sio.emit("camera_info", {
                "fps": 0,
                "frame_size": 0,
                "upload_speed": 0,
                "status": "OK"
            })
        except Exception as e:
            print("[ERROR] Socket connection failed:", e)
            sio.emit("camera_status", {"status": "Error"})

    def apply_config(self):
        try:
            res = self.config["resolution"]
            jpeg_quality = self.config["jpeg_quality"]
            fps = self.config["fps"]
            duration = int(1e6 / max(fps, 1))

            if self.picam.started:
                self.picam.stop()

            # build controls dict with new parameters
            controls = {
                "FrameDurationLimits": (duration, duration),
                "Brightness": self.config.get("brightness", 0.0),
            }

            # if manual exposure requested, override AE
            if not self.config.get("auto_exposure", False):
                exposure = self.config.get("exposure_time")
                if exposure:
                    controls["ExposureTime"] = exposure

            # debug print
            print("[CONFIG] Applying controls:", controls)

            stream_cfg = self.picam.create_preview_configuration(
                main={"format": "XRGB8888", "size": res},
                controls=controls
            )
            self.picam.configure(stream_cfg)
            self.picam.start()
        except Exception as e:
            print("[ERROR] Failed to configure camera:", e)
            sio.emit("camera_status", {"status": "Error"})
            # Send camera info on error
            sio.emit("camera_info", {
                "fps": 0,
                "frame_size": 0,
                "upload_speed": 0,
                "status": "Error"
            })

    def stream_loop(self):
        frame_count = 0
        last_time = time.time()
        bytes_sent = 0
        last_bytes_sent = 0

        while True:
            try:
                if self.streaming:
                    frame = self.picam.capture_array()
                    ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.config["jpeg_quality"]])
                    if not ok:
                        continue

                    frame_bytes = buf.tobytes()
                    sio.emit("frame", frame_bytes)
                    frame_count += 1
                    bytes_sent += len(frame_bytes)

                    now = time.time()
                    if now - last_time >= 1.0:
                        fps = frame_count
                        frame_size = len(frame_bytes) // 1024  # KB
                        upload_speed = (bytes_sent - last_bytes_sent) // 1024  # KB/s

                        # EMIT CAMERA INFO EVENT WITH STATUS
                        sio.emit("camera_info", {
                            "fps": fps,
                            "frame_size": frame_size,
                            "upload_speed": upload_speed,
                            "status": "OK"
                        })

                        frame_count = 0
                        last_time = now
                        last_bytes_sent = bytes_sent
                else:
                    time.sleep(0.5)
            except Exception as e:
                print("[ERROR] Stream loop exception:", e)
                time.sleep(1)

    def capture_image(self, path=None):
        """Capture a high-resolution still image"""
        try:
            if path is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                # Use the current user's home directory instead of /home/pi
                import os
                home_dir = os.path.expanduser("~")  # This will be /home/slowmo
                path = os.path.join(home_dir, "captures", f"image_{timestamp}.jpg")
            
            # Ensure capture directory exists
            import os
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # If camera is not started, start it temporarily
            temp_start = False
            was_streaming = self.streaming
            
            if not self.picam.started:
                # Create still configuration for high quality capture
                still_cfg = self.picam.create_still_configuration(
                    main={"size": (4608, 2592)},  # Full resolution for Pi Camera V3
                    controls={"FrameDurationLimits": (100000, 100000)}  # 10 FPS
                )
                self.picam.configure(still_cfg)
                self.picam.start()
                temp_start = True
                time.sleep(2)  # Allow camera to adjust
            else:
                # Camera is already running, temporarily stop streaming for capture
                if self.streaming:
                    self.streaming = False
                    time.sleep(0.1)  # Brief pause
            
            # Capture the frame
            frame = self.picam.capture_array()
            
            # Save as high-quality JPEG
            success = cv2.imwrite(path, frame, [
                int(cv2.IMWRITE_JPEG_QUALITY), 95  # High quality
            ])
            
            if success:
                print(f"[INFO] High-res image saved: {path}")
                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                print(f"[INFO] File size: {file_size:.2f} MB")
                
                # Restore previous state
                if temp_start and not was_streaming:
                    self.picam.stop()
                elif temp_start and was_streaming:
                    # Reconfigure for streaming
                    self.apply_config()
                    self.streaming = True
                elif not temp_start and was_streaming:
                    # Resume streaming
                    self.streaming = True
                
                return {"success": True, "path": path, "size_mb": round(file_size, 2)}
            else:
                # Restore streaming state on failure
                if was_streaming:
                    self.streaming = True
                return {"success": False, "error": "Failed to save image"}
                
        except Exception as e:
            print(f"[ERROR] Image capture failed: {e}")
            # Restore streaming state on exception
            if 'was_streaming' in locals() and was_streaming:
                self.streaming = True
            return {"success": False, "error": str(e)}

streamer = CameraStreamer()


@sio.event
def connect():
    streamer.connected = True
    print("📡 Connected to server from camera.py")
    # Send camera info on connection
    sio.emit("camera_info", {
        "fps": 0,
        "frame_size": 0,
        "upload_speed": 0,
        "status": "OK"
    })

@sio.event
def disconnect():
    streamer.connected = False
    streamer.streaming = False
    if hasattr(streamer, "picam") and getattr(streamer.picam, "started", False):
        streamer.picam.stop()
    print("🔌 Camera disconnected")
    # Send camera info on disconnection
    sio.emit("camera_info", {
        "fps": 0,
        "frame_size": 0,
        "upload_speed": 0,
        "status": "Error"
    })

@sio.on("start_camera")
def on_start_camera(_):
    streamer.streaming = True
    if not streamer.picam.started:
        streamer.apply_config()
    sio.emit("camera_status", {"status": "Streaming"})
    # Send camera info on start
    sio.emit("camera_info", {
        "fps": 0,
        "frame_size": 0,
        "upload_speed": 0,
        "status": "OK"
    })

@sio.on("stop_camera")
def on_stop_camera(_):
    streamer.streaming = False
    sio.emit("camera_status", {"status": "Idle"})
    # Send camera info on stop
    sio.emit("camera_info", {
        "fps": 0,
        "frame_size": 0,
        "upload_speed": 0,
        "status": "OK"
    })

@sio.on("camera_config")
def on_camera_config(data):
    streamer.config.update(data)
    if not streamer.streaming:
        streamer.apply_config()
        sio.emit("camera_status", {"status": "Ready"})
        # Send camera info on config change
        sio.emit("camera_info", {
            "fps": 0,
            "frame_size": 0,
            "upload_speed": 0,
            "status": "OK"
        })

@sio.on("get_camera_status")
def on_get_camera_status(_):
    status = "Streaming" if streamer.streaming else "Idle"
    sio.emit("camera_status", {"status": status})

@sio.on("set_camera_idle")
def on_set_camera_idle(_):
    streamer.streaming = False
    sio.emit("camera_status", {"status": "Idle"})

@sio.on("camera_update")
def on_camera_update(_):
    """Handle request for camera status update"""
    try:
        # Determine current status
        if streamer.connected:
            if streamer.streaming:
                camera_status = "Streaming"
                fps = streamer.config.get("fps", 0)
            else:
                camera_status = "Idle"
                fps = 0
            
            # Send current camera info
            sio.emit("camera_info", {
                "fps": fps,
                "frame_size": 0,  # Could be calculated if needed
                "camera_status": camera_status.lower(),
                "status": "OK"
            })
            print(f"[INFO] Camera status update sent: {camera_status}")
        else:
            # Camera disconnected
            sio.emit("camera_info", {
                "fps": 0,
                "frame_size": 0,
                "camera_status": "disconnected",
                "status": "Error"
            })
            print("[INFO] Camera status update sent: Disconnected")
    except Exception as e:
        print(f"[ERROR] camera_update handler: {e}")

def start_stream():
    streamer.connect_socket()
    streamer.apply_config()
    print("[INFO] Camera ready.")
    streamer.stream_loop()

if __name__ == "__main__":
    sio.connect("http://localhost:5000")  # Change to your server address
    streamer.stream_loop()
