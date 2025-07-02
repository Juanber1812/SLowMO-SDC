from w1thermsensor import W1ThermSensor
import time
import threading
import logging

# need to run sudo apt-get install python3-w1thermsensor
# documentation: https://github.com/timofurrer/w1thermsensor
# Example output:
# {"battery": 25.0, "main": 26.5, "number_of_sensors": 2}
# Last edited 20250628T15:12

BATTERY_SENSOR_ID = '0b24404e94cd' # depending on setup, you may need to swap these
#MAIN_SENSOR_ID = '0b2440864105'

# Global variable to store the latest temperature data
latest_temperatures = {
    "battery_temp": None,
}

# Callback function for broadcasting temperature data
thermal_data_callback = None

def get_temperature(sensor_id):
    try:
        sensor = W1ThermSensor(sensor_id=sensor_id)
        temperature = sensor.get_temperature()
        return temperature
    except Exception as e:
        print(f"Error reading temperature from sensor {sensor_id}: {e}")
        return None

# Juan, you'll want to call this function to get a JSON of all temperatures
# from all sensors, including the battery and main sensor.
def get_all_temperatures():
    sensors = W1ThermSensor.get_available_sensors()
    temperatures = {}
    for sensor in sensors:
        temp = get_temperature(sensor.id)
        if temp is not None:
            if sensor.id == BATTERY_SENSOR_ID:
                temperatures['battery'] = temp
            #elif sensor.id == MAIN_SENSOR_ID:
                #temperatures['main'] = temp
            else:
                temperatures[sensor.id] = temp
    temperatures["number_of_sensors"] = len(temperatures)
    return temperatures

def set_thermal_data_callback(callback_function):
    """Set the callback function for thermal data broadcasting"""
    global thermal_data_callback
    thermal_data_callback = callback_function

def update_thermal_data():
    """Update thermal data and broadcast it"""
    global latest_temperatures
    
    try:
        # Read battery temperature
        battery_temp = get_temperature(BATTERY_SENSOR_ID)
        
        # Update global temperature data - only battery temperature
        if battery_temp is not None:
            latest_temperatures["battery_temp"] = round(battery_temp, 1)
        else:
            latest_temperatures["battery_temp"] = None
        
        # Call the callback function to broadcast data if it's set
        # Status computation is now handled in the server
        if thermal_data_callback:
            thermal_data_callback(latest_temperatures.copy())
            
    except Exception as e:
        logging.error(f"Error updating thermal data: {e}")
        latest_temperatures["battery_temp"] = None
        if thermal_data_callback:
            thermal_data_callback(latest_temperatures.copy())

def start_thermal_monitoring():
    """Start continuous thermal monitoring in a separate thread"""
    def thermal_monitoring_loop():
        logging.info("Thermal monitoring started")
        while True:
            try:
                update_thermal_data()
                time.sleep(1.0)  # Update every second as requested
            except Exception as e:
                logging.error(f"Error in thermal monitoring loop: {e}")
                time.sleep(5.0)  # Wait longer on error before retrying
    
    # Start the monitoring thread
    thermal_thread = threading.Thread(target=thermal_monitoring_loop, daemon=True)
    thermal_thread.start()
    return thermal_thread

def get_latest_temperatures():
    """Get the latest temperature readings"""
    return latest_temperatures.copy()

if __name__ == "__main__":
    print('Running temperature sensor script...')
    temperatures = get_all_temperatures()
    print('Temperature sensors found:', temperatures.get("number_of_sensors", 0))
    print(f"Combined temperature readings from all sensors: {temperatures}")
    if temperatures:
        for sensor_id, temp in temperatures.items():
            if sensor_id == 'number_of_sensors':
                continue
            print(f"Sensor {sensor_id} has temperature {temp:.3f} °C")
    else:
        print("No temperature sensors found.")
    print('Temperature sensor script finished.')
