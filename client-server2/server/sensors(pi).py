# sensors.py
import time, psutil, socketio
from gevent import monkey; monkey.patch_all()

SERVER_URL = "http://192.168.65.89:5000"
sio = socketio.Client()
sio.connect(SERVER_URL)

def read_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read()) / 1000.0
    except:
        return None

def main():
    while True:
        temp = read_temp()
        cpu = psutil.cpu_percent(interval=None)
        payload = {"temperature": temp, "cpu_percent": cpu}
        sio.emit('sensor_data', payload)
        time.sleep(1)

if __name__ == "__main__":
    main()
