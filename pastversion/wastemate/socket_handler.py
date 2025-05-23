# socket_handler.py

import socketio
import threading
import time
import logging
from config import SERVER_URL

sio = socketio.Client()

# === Public API for UI to call ===
def connect():
    try:
        sio.connect(SERVER_URL, wait_timeout=5)
    except Exception as e:
        logging.exception("Socket connect failed")

def disconnect():
    try:
        sio.disconnect()
    except Exception as e:
        logging.exception("Socket disconnect failed")

def is_connected():
    return sio.connected

def emit(event, data=None):
    try:
        sio.emit(event, data)
    except Exception as e:
        logging.exception(f"Emit failed: {event}")

def start_socket_thread():
    threading.Thread(target=_socket_thread, daemon=True).start()

def _socket_thread():
    while True:
        try:
            connect()
            sio.wait()
        except Exception as e:
            logging.exception("SocketIO connection error")
            time.sleep(5)

# === Socket Event Handlers ===

@sio.event
def connect():
    print("[✓] Connected to server")
    emit("get_camera_status")

@sio.event
def disconnect():
    print("[×] Disconnected from server")
