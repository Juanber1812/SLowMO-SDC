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
        print(f"Current: {ina228.current:.2f} mA")
        print(f"Bus Voltage: {ina228.voltage:.2f} V")
        print(f"Shunt Voltage: {ina228.shunt_voltage*1000:.2f} mV")
        print(f"Power: {ina228.power:.2f} mW")
        print(f"Energy: {ina228.energy:.2f} J")
        print(f"Temperature: {ina228.temperature:.2f} C")

        # Additional INA228 data
        print(f"Alert: {ina228.alert}")
        print(f"Conversion Ready: {ina228.conversion_ready}")
        print(f"ADC Conversion Time: {ina228.adc_conversion_time} us")
        print(f"ADC Averaging: {ina228.adc_averaging}")
        print(f"Shunt Calibration: {ina228.shunt_calibration}")
        print(f"Manufacturer ID: {ina228.manufacturer_id:#06x}")
        print(f"Device ID: {ina228.device_id:#06x}")

        return {
            "current": ina228.current,
            "voltage": ina228.voltage,
            "power": ina228.power,
            "energy": ina228.energy,
            "temperature": ina228.temperature,
        }
    except Exception as e:
        print(f"Error reading sensor data: {e}")
        return None
    
if __name__ == "__main__":
    sensor = init_sensor()
    get_power_values(sensor)