# temperature.py

import time
import logging
from multiprocessing import Process, Queue
from w1thermsensor import W1ThermSensor, units

# Your DS18B20 ID
BATTERY_SENSOR_ID = '0b24404e94cd'

def _thermal_worker(q: Queue):
    """
    Child process loop: reads the sensor once a second
    (at its default resolution) and pushes results into q.
    """
    try:
        sensor = W1ThermSensor(sensor_id=BATTERY_SENSOR_ID)
    except Exception as e:
        logging.error(f"[ThermalWorker] init failed: {e}")
        return

    while True:
        try:
            temp = sensor.get_temperature(units.DEGREES_C)
            q.put({"battery_temp": round(temp, 1)})
        except Exception as e:
            logging.error(f"[ThermalWorker] read failed: {e}")
            q.put({"battery_temp": None})
        time.sleep(1.0)


def start_thermal_subprocess() -> Queue:
    """
    Spawns the thermal worker in a child process.
    Returns a Queue that will receive dicts {"battery_temp": …}.
    """
    q = Queue()
    p = Process(target=_thermal_worker, args=(q,), daemon=True)
    p.start()
    return q


if __name__ == "__main__":
    # Quick standalone test
    q = start_thermal_subprocess()
    print("Reading 5 samples (one per second)…")
    for _ in range(5):
        data = q.get()   # blocks until next reading
        print(data)
