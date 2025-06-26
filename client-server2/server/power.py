try:
    import board # type: ignore
    import adafruit_ina228 # type: ignore
except ImportError as e:
    print(f"Error importing libraries: {e}")
    print("Make sure you have the required libraries installed.")
    raise

def init_sensor():
    try:
        i2c = board.I2C()
    except Exception as e:
        print(f"Error initializing I2C: {e}")
        raise

    try:
        ina228 = adafruit_ina228.INA228(i2c)
    except Exception as e:
        print(f"Error initializing INA228 sensor: {e}")
        raise
    return ina228

def get_power_values(ina228):
    try:
        try:
            print(f"Current: {ina228.current:.2f} mA")
        except Exception as e:
            print(f"Error reading current: {e}")

        try:
            print(f"Bus Voltage: {ina228.bus_voltage:.2f} V")
        except Exception as e:
            print(f"Error reading bus voltage: {e}")

        try:
            print(f"Shunt Voltage: {ina228.shunt_voltage*1000:.2f} mV")
        except Exception as e:
            print(f"Error reading shunt voltage: {e}")

        try:
            print(f"Power: {ina228.power:.2f} mW")
        except Exception as e:
            print(f"Error reading power: {e}")

        try:
            print(f"Energy: {ina228.energy:.2f} J")
        except Exception as e:
            print(f"Error reading energy: {e}")

        try:
            print(f"Temperature: {ina228.die_temperature:.2f} C")
        except Exception as e:
            print(f"Error reading temperature: {e}")

        # Additional INA228 data
        try:
            print(f"Alert: {ina228.alert}")
        except Exception as e:
            print(f"Error reading alert: {e}")

        try:
            print(f"Device ID: {ina228.device_id:#06x}")
        except Exception as e:
            print(f"Error reading device ID: {e}")

        return {
            "current": ina228.current,
            "voltage": ina228.bus_voltage,
            "power": ina228.power,
            "energy": ina228.energy,
            "temperature": ina228.die_temperature,
        }
    except Exception as e:
        print(f"Error reading sensor data: {e}")
        return None
    
if __name__ == "__main__":
    sensor = init_sensor()
    power_readings = get_power_values(sensor)
    print("Power readings:", power_readings)