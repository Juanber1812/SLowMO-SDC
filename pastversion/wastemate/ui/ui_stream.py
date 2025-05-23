# ui/ui_stream.py

from PyQt6.QtWidgets import (
    QVBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QSlider, QHBoxLayout
)
from PyQt6.QtCore import Qt
from config import RES_PRESETS, SERVER_URL
from socket_instance import sio
import time


def create_stream_section(main_window):
    layout = QVBoxLayout()

    # === Live Stream Preview ===
    stream_group = QGroupBox("Live Stream")
    stream_layout = QVBoxLayout()
    main_window.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
    main_window.image_label.setFixedSize(384, 216)
    main_window.image_label.setStyleSheet("background: #222; border: 1px solid #888;")
    stream_layout.addWidget(main_window.image_label)
    stream_group.setLayout(stream_layout)
    layout.addWidget(stream_group)

    # === Stream Controls ===
    controls_group = QGroupBox("Stream Controls")
    controls_layout = QHBoxLayout()

    # Start/Stop Stream Button
    main_window.toggle_btn = QPushButton("Start Stream")
    main_window.toggle_btn.setEnabled(False)
    main_window.toggle_btn.clicked.connect(lambda: toggle_stream(main_window))
    controls_layout.addWidget(main_window.toggle_btn)

    main_window.reconnect_btn = QPushButton("Reconnect")
    main_window.reconnect_btn.clicked.connect(lambda: reconnect_to_server(main_window))
    controls_layout.addWidget(main_window.reconnect_btn)

    controls_group.setLayout(controls_layout)
    layout.addWidget(controls_group)

    # === Camera Settings ===
    settings_group = QGroupBox("Camera Settings")
    grid = QGridLayout()

    # --- Place your code here ---
    main_window.jpeg_slider = QSlider(Qt.Orientation.Horizontal)
    main_window.jpeg_slider.setRange(1, 100)
    main_window.jpeg_slider.setValue(70)
    main_window.jpeg_label = QLabel("JPEG: 70")
    main_window.jpeg_slider.valueChanged.connect(lambda val: main_window.jpeg_label.setText(f"JPEG: {val}"))

    main_window.res_dropdown = QComboBox()
    for label, _ in RES_PRESETS:
        main_window.res_dropdown.addItem(label)
    main_window.res_dropdown.currentIndexChanged.connect(lambda _: update_fps_slider(main_window))

    main_window.fps_slider = QSlider(Qt.Orientation.Horizontal)
    main_window.fps_slider.setRange(1, 120)
    main_window.fps_slider.setValue(10)
    main_window.fps_label = QLabel("FPS: 10")
    main_window.fps_slider.valueChanged.connect(lambda val: main_window.fps_label.setText(f"FPS: {val}"))

    # --- Add widgets to grid ---
    grid.addWidget(main_window.jpeg_label, 0, 0)
    grid.addWidget(main_window.jpeg_slider, 0, 1)
    grid.addWidget(QLabel("Resolution"), 1, 0)
    grid.addWidget(main_window.res_dropdown, 1, 1)
    grid.addWidget(main_window.fps_label, 2, 0)
    grid.addWidget(main_window.fps_slider, 2, 1)

    # Apply Settings Button
    main_window.apply_btn = QPushButton("Apply Settings")
    main_window.apply_btn.setEnabled(False)
    main_window.apply_btn.clicked.connect(lambda: apply_camera_config(main_window))
    grid.addWidget(main_window.apply_btn, 3, 0, 1, 2)

    settings_group.setLayout(grid)
    layout.addWidget(settings_group)

    return layout


def toggle_stream(main_window):
    print("toggle_stream called")
    if not sio.connected:
        print("Socket not connected!")
        return
    main_window.streaming = not main_window.streaming
    main_window.toggle_btn.setText("Stop Stream" if main_window.streaming else "Start Stream")
    print(f"Emitting: {'start_camera' if main_window.streaming else 'stop_camera'}")
    sio.emit("start_camera" if main_window.streaming else "stop_camera")


def reconnect_to_server(main_window):
    was_streaming = main_window.streaming
    try:
        if was_streaming:
            main_window.streaming = False
            main_window.toggle_btn.setText("Start Stream")
            sio.emit("stop_camera")
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
        # Always request camera status after reconnect
        sio.emit("get_camera_status")
    except Exception as e:
        print("Reconnect failed:", e)


def apply_camera_config(main_window):
    from config import RES_PRESETS

    was_streaming = main_window.streaming
    if was_streaming:
        # Stop stream before applying config
        main_window.streaming = False
        main_window.toggle_btn.setText("Start Stream")
        sio.emit("stop_camera")
        time.sleep(0.5)
    res_idx = main_window.res_dropdown.currentIndex()
    _, resolution = RES_PRESETS[res_idx]
    fps = main_window.fps_slider.value()
    config = {
        "jpeg_quality": main_window.jpeg_slider.value(),
        "fps": fps,
        "resolution": resolution
    }
    sio.emit("camera_config", config)
    print(f"Sent config: {config}")
    if was_streaming:
        sio.emit("start_camera")
        main_window.streaming = True
        main_window.toggle_btn.setText("Stop Stream")


def update_fps_slider(main_window):
    # Optionally adjust FPS range based on resolution
    pass
