# main.py

import sys
import threading
import time
from PyQt6.QtWidgets import QApplication
from ui.ui_main import MainWindow
from config import SERVER_URL
from socket_instance import sio

def setup_socket_events(main_window):
    @sio.event
    def connect():
        print("[✓] Connected to server")
        main_window.comms_status_label.setText("Status: Connected")
        main_window.toggle_btn.setEnabled(True)
        main_window.detector_btn.setEnabled(True)
        main_window.apply_btn.setEnabled(True)
        main_window.reconnect_btn.setEnabled(True)
        # Optionally auto-apply config on connect
        # main_window.apply_btn.click()
        time.sleep(0.2)
        if not getattr(main_window, "streaming", False):
            sio.emit("stop_camera")
        sio.emit("get_camera_status")

    @sio.event
    def disconnect():
        print("[×] Disconnected from server")
        main_window.comms_status_label.setText("Status: Disconnected")
        main_window.toggle_btn.setEnabled(False)
        main_window.detector_btn.setEnabled(False)
        main_window.apply_btn.setEnabled(False)
        main_window.reconnect_btn.setEnabled(True)

    @sio.on("frame")
    def on_frame(data):
        import numpy as np
        import cv2
        from bridge import bridge
        arr = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            bridge.frame_received.emit(frame)

    @sio.on("sensor_broadcast")
    def on_sensor_data(data):
        try:
            from bridge import bridge
            temp = data.get("temperature", 0)
            cpu = data.get("cpu_percent", 0)
            bridge.update_system_info.emit(temp, cpu)
        except Exception as e:
            print("Sensor data error:", e)

    @sio.on("camera_status")
    def on_camera_status(data):
        try:
            status = data.get("status", "Unknown")
            main_window.camera_status_label.setText(f"Camera: {status}")
            error_statuses = {"error", "not connected", "damaged", "not found", "unavailable", "failed"}
            if hasattr(main_window, "camera_ready_label"):
                if status.lower() in error_statuses:
                    main_window.camera_ready_label.setText("Status: Not Ready")
                    main_window.camera_ready_label.setStyleSheet("color: #f00;")
                else:
                    main_window.camera_ready_label.setText("Status: Ready")
                    main_window.camera_ready_label.setStyleSheet("color: #0f0;")
        except Exception as e:
            print("Camera status error:", e)

    @sio.on("camera_info")
    def on_camera_info(data):
        try:
            fps = data.get("fps", "--")
            frame_size = data.get("frame_size", "--")
            speed = data.get("speed", "--")
            max_frame = data.get("max_frame", "--")
            main_window.info_labels["fps"].setText(f"FPS: {fps}")
            main_window.info_labels["frame_size"].setText(f"Frame Size: {frame_size} KB")
            main_window.info_labels["speed"].setText(f"Upload: {speed} Mbps")
            main_window.info_labels["max_frame"].setText(f"Max Frame: {max_frame} KB")
        except Exception as e:
            print("Camera info error:", e)

def socket_thread():
    while True:
        try:
            sio.connect(SERVER_URL, wait_timeout=5)
            sio.wait()
        except Exception as e:
            print("SocketIO connection error:", e)
            time.sleep(5)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.showMaximized()

    setup_socket_events(win)

    thread = threading.Thread(target=socket_thread, daemon=True)
    thread.start()
    exit_code = app.exec()
    sio.disconnect()
    sys.exit(exit_code)

# In ui_main.py or MainWindow class
def measure_speed(self):
    self.info_labels["speed"].setText("Upload: Testing...")
    self.info_labels["max_frame"].setText("Max Frame: ...")

    def run_speedtest():
        try:
            import speedtest
            st = speedtest.Speedtest()
            upload = st.upload()
            upload_mbps = upload / 1_000_000
            self.info_labels["speed"].setText(f"Upload: {upload_mbps:.2f} Mbps")
            fps = self.fps_slider.value()
            max_bytes_per_sec = upload / 8
            max_frame_size = max_bytes_per_sec / fps
            self.info_labels["max_frame"].setText(f"Max Frame: {max_frame_size / 1024:.1f} KB")
        except Exception:
            self.info_labels["speed"].setText("Upload: Error")
            self.info_labels["max_frame"].setText("Max Frame: -- KB")

    threading.Thread(target=run_speedtest, daemon=True).start()
