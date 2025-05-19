# sensors.py

from gevent import monkey; monkey.patch_all()

import time, socketio, psutil

SERVER_URL = "http://localhost:5000"
sio = socketio.Client()

@sio.event
def connect():
    print("📡 Connected to server from sensors.py")

@sio.event
def disconnect():
    print("🔌 Disconnected from server")

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
        print("❌ Sensor connection failed:", e)
        return

    print("🌡️ Sensor monitoring started.")
    while True:
        temp = get_temp()
        cpu = psutil.cpu_percent(interval=None)
        sio.emit('sensor_data', {"temperature": temp, "cpu_percent": cpu})
        time.sleep(1)
