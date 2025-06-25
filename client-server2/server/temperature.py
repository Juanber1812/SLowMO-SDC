from w1thermsensor import W1ThermSensor

# need to run sudo apt-get install python3-w1thermsensor
# documentation: https://github.com/timofurrer/w1thermsensor
# Example output:
# Sensor 28-000007602ffa has temperature 22.50
# Sensor 28-000007602ffb has temperature 23.00
# Sensor 28-000007602ffb has temperature 23.00

def get_temperature(sensor_id):
    try:
        sensor = W1ThermSensor(sensor_id=sensor_id)
        temperature = sensor.get_temperature()
        return temperature
    except Exception as e:
        print(f"Error reading temperature from sensor {sensor_id}: {e}")
        return None
    
    
if __name__ == "__main__":
    print('Running temperature sensor script...')
    sensors = W1ThermSensor.get_available_sensors()
    print(f"Found {len(sensors)} temperature sensors:")
    for sensor in sensors:
        print("Sensor %s has temperature %.2f" % (sensor.id, sensor.get_temperature()))
    for sensor in sensors:
        temp = get_temperature(sensor.id)
        if temp is not None:
            print(f"Sensor {sensor.id} has temperature {temp:.2f} °C")
        else:
            print(f"Failed to read temperature from sensor {sensor.id}")
            print(f"Failed to read temperature from sensor {sensor.id}")