# temperature.py

import time
import logging
from multiprocessing import Process, Queue

# Try to import w1thermsensor - it may not be available on all systems
try:
    from w1thermsensor import W1ThermSensor
    W1THERM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"w1thermsensor not available: {e}")
    W1ThermSensor = None
    W1THERM_AVAILABLE = False

# Your DS18B20's ID
BATTERY_SENSOR_ID = '0b24404e94cd'

def _thermal_worker(q: Queue):
    """
    Runs in its own process. Reads the sensor once per second
    (blocking in the child process only) and pushes {"battery_temp": …} into q.
    """
    if not W1THERM_AVAILABLE:
        logging.error("[ThermalWorker] w1thermsensor library not available")
        # Send error data and exit
        q.put({"battery_temp": None})
        return
    
    try:
        sensor = W1ThermSensor(sensor_id=BATTERY_SENSOR_ID)
    except Exception as e:
        logging.error(f"[ThermalWorker] init failed: {e}")
        # Send error data periodically so the queue doesn't starve
        while True:
            q.put({"battery_temp": None})
            time.sleep(5.0)
        return

    while True:
        try:
            # Default get_temperature() returns °C
            temp_c = sensor.get_temperature()
            q.put({"battery_temp": round(temp_c, 1)})
        except Exception as e:
            logging.error(f"[ThermalWorker] read failed: {e}")
            q.put({"battery_temp": None})
        time.sleep(1.0)


def start_thermal_subprocess() -> Queue:
    """
    Spawn the thermal worker in a separate process.
    Returns a multiprocessing.Queue on which you'll receive dicts {"battery_temp": …}.
    Returns None if thermal monitoring cannot be started.
    """
    if not W1THERM_AVAILABLE:
        logging.warning("Cannot start thermal monitoring: w1thermsensor not available")
        return None
    
    try:
        q = Queue()
        p = Process(target=_thermal_worker, args=(q,), daemon=True)
        p.start()
        return q
    except Exception as e:
        logging.error(f"Failed to start thermal subprocess: {e}")
        return None


if __name__ == "__main__":
    # Quick standalone test
    q = start_thermal_subprocess()
    print("Reading 5 samples (one per second)…")
    for _ in range(5):
        data = q.get()
        print(data)
