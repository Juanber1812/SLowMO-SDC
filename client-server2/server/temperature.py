from w1thermsensor import W1ThermSensor

# need to run sudo apt-get install python3-w1thermsensor
# documentation: https://github.com/timofurrer/w1thermsensor
# Example output:
# Sensor 28-000007602ffa has temperature 22.50
# Sensor 28-000007602ffb has temperature 23.00
# Sensor 28-000007602ffb has temperature 23.00
# Last edited 20250625T21:06

BATTERY_SENSOR_ID = '0b24404e94cd'
MAIN_SENSOR_ID = 'UNKNOWN'

def get_temperature(sensor_id):
    try:
        sensor = W1ThermSensor(sensor_id=sensor_id)
        temperature = sensor.get_temperature()
        return temperature
    except Exception as e:
        print(f"Error reading temperature from sensor {sensor_id}: {e}")
        return None

def get_all_temperatures():
    sensors = W1ThermSensor.get_available_sensors()
    temperatures = {}
    for sensor in sensors:
        temp = get_temperature(sensor.id)
        if temp is not None:
            if sensor.id == BATTERY_SENSOR_ID:
                temperatures['battery'] = temp
            elif sensor.id == MAIN_SENSOR_ID:
                temperatures['main'] = temp
            else:
                temperatures[sensor.id] = temp
    temperatures["number_of_sensors"] = len(temperatures)
    return temperatures

if __name__ == "__main__":
    print('Running temperature sensor script...')
    temperatures = get_all_temperatures()
    print('Temperature sensors found:', len(temperatures))
    print(f"Combined temperature readings from all sensors: {temperatures}")
    if temperatures:
        for sensor_id, temp in temperatures.items():
            if sensor_id == 'number_of_sensors':
                continue
            print(f"Sensor {sensor_id} has temperature {temp:.3f} °C")
    else:
        print("No temperature sensors found.")
    print('Temperature sensor script finished.')
