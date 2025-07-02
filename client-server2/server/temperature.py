# thermal_subprocess.py

from multiprocessing import Process, Queue
import time
import logging
from w1thermsensor import W1ThermSensor, units, RESOLUTION_9_BIT

# ID of your battery sensor
BATTERY_SENSOR_ID = '0b24404e94cd'

def _thermal_worker(q: Queue):
    """
    Runs in a separate process: reads the sensor every second
    at 9-bit resolution (≈94 ms conversion) and pushes a dict into q.
    """
    try:
        sensor = W1ThermSensor(sensor_id=BATTERY_SENSOR_ID)
        sensor.set_resolution(RESOLUTION_9_BIT)
    except Exception as e:
        logging.error(f"Could not initialize W1ThermSensor: {e}")
        return

    while True:
        try:
            temp = sensor.get_temperature(units.DEGREES_C)
            q.put({"battery_temp": round(temp, 1)})
        except Exception as e:
            logging.error(f"Error reading temperature: {e}")
            q.put({"battery_temp": None})
        time.sleep(1.0)


def start_thermal_subprocess() -> Queue:
    """
    Spawns the thermal worker in its own process.
    Returns a multiprocessing.Queue you can .get() from to receive readings.
    """
    q = Queue()
    p = Process(target=_thermal_worker, args=(q,), daemon=True)
    p.start()
    return q


if __name__ == "__main__":
    # Quick test of the subprocess
    q = start_thermal_subprocess()
    print("Thermal subprocess started; reading 5 samples...")
    for _ in range(5):
        data = q.get()   # blocks until the first reading arrives
        print(data)
