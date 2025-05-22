# sensors.py

from gevent import monkey; monkey.patch_all()

import time
import socketio
import psutil

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

@sio.event
def connect():


@sio.event
def disconnect():


def get_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read()) / 1000.0
    except:
        return None

def start_sensors():
    try:
        sio.connect(SERVER_URL)
    except Exception as e:
        return

    while True:
        temp = get_temp()
        cpu = psutil.cpu_percent(interval=None)
        sio.emit('sensor_data', {"temperature": temp, "cpu_percent": cpu})
        time.sleep(3)  # Update every 3 seconds (adjustable)
