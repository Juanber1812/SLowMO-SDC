# imu_control.py
import time, random, socketio
from gevent import monkey; monkey.patch_all()

SERVER_URL = "http://0.0.0.0:5000"
sio = socketio.Client()
sio.connect(SERVER_URL)

def main():
    while True:
        imu = {
            "accel": [random.uniform(-1,1) for _ in range(3)],
            "gyro":  [random.uniform(-180,180) for _ in range(3)]
        }
        ctrl = {"wheel_speed_rpm": random.uniform(-1000,1000)}
        sio.emit('imu_data', imu)
        sio.emit('control_data', ctrl)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
