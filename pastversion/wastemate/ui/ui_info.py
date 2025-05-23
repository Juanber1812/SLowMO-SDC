# ui/ui_info.py

from PyQt6.QtWidgets import (
    QVBoxLayout, QGroupBox, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from socket_instance import sio
from config import SERVER_URL
import time

def reconnect_to_server(main_window):
    was_streaming = main_window.streaming
    try:
        if was_streaming:
            main_window.streaming = False
            main_window.toggle_btn.setText("Start Stream")
            sio.emit("stop_camera")
            # time.sleep(0.5)  # REMOVE or reduce this
        sio.disconnect()
    except Exception:
        pass
    try:
        sio.connect(SERVER_URL, wait_timeout=5)
        apply_camera_config(main_window)
        if was_streaming:
            sio.emit("start_camera")
            main_window.streaming = True
            main_window.toggle_btn.setText("Stop Stream")
    except Exception as e:
        print("Reconnect failed:", e)

def create_info_section(main_window):
    layout = QVBoxLayout()

    # === Print Health Report Button ===
    print_report_btn = QPushButton("Print Health Check Report")
    print_report_btn.setEnabled(False)
    layout.addWidget(print_report_btn)

    # === System Info ===
    info_group = QGroupBox("System Info")
    info_layout = QVBoxLayout()

    main_window.info_labels = {
        "temp": QLabel("Temp: -- °C"),
        "cpu": QLabel("CPU: --%"),
        "speed": QLabel("Upload: -- Mbps"),
        "max_frame": QLabel("Max Frame: -- KB"),
        "fps": QLabel("FPS: --"),
        "frame_size": QLabel("Frame Size: -- KB"),
    }

    for label in main_window.info_labels.values():
        label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(label)

    info_group.setLayout(info_layout)
    layout.addWidget(info_group)

    # === Subsystem Boxes ===
    layout.addWidget(_subsystem_box("Power Subsystem", [
        "Battery Voltage: Pending...",
        "Battery Current: Pending...",
        "Battery Temp: Pending...",
        "Status: Pending..."
    ]))

    layout.addWidget(_subsystem_box("Thermal Subsystem", [
        "Internal Temp: Pending...",
        "Status: Pending..."
    ]))

    layout.addWidget(_subsystem_box("Communication Subsystem", [
        "Downlink Frequency: Pending...",
        "Uplink Frequency: Pending...",
        "Signal Strength: Pending...",
        "Data Rate: Pending..."
    ], ref_label=("comms_status_label", main_window)))

    layout.addWidget(_subsystem_box("ADCS Subsystem", [
        "Gyro: Pending...",
        "Orientation: Pending...",
        "Sun Sensor: Pending...",
        "Wheel Rpm: Pending...",
        "Status: Pending..."
    ]))

    layout.addWidget(_subsystem_box("Payload Subsystem", [
        "Camera: Pending...",
        "Status: Not Ready"
    ], ref_labels=[("camera_status_label", main_window), ("camera_ready_label", main_window)]))

    layout.addWidget(_subsystem_box("Command & Data Handling Subsystem", [
        "Memory Usage: Pending...",
        "Last Command: Pending...",
        "Uptime: Pending...",
        "Status: Pending..."
    ]))

    layout.addWidget(_subsystem_box("Error Log", [
        "No Critical Errors Detected: Pending..."
    ]))

    layout.addWidget(_subsystem_box("Overall Status", [
        "No Anomalies Detected: Pending...",
        "Recommended Actions: Pending..."
    ]))

    return layout


def _subsystem_box(title, lines, ref_label=None, ref_labels=None):
    box = QGroupBox(title)
    box_layout = QVBoxLayout()

    labels = []
    for line in lines:
        lbl = QLabel(line)
        lbl.setStyleSheet("color: #bbb;")
        box_layout.addWidget(lbl)
        labels.append(lbl)

    box.setLayout(box_layout)

    # Optionally expose labels for later updates
    if ref_label:
        name, target = ref_label
        setattr(target, name, labels[0])

    if ref_labels:
        for (name, target), lbl in zip(ref_labels, labels):
            setattr(target, name, lbl)

    return box
