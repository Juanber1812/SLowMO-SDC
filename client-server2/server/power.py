try:
    import board # type: ignore
    import adafruit_ina228 # type: ignore
    import time
    import csv
    import os
    from datetime import datetime
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

# Hi Juan, this is a placeholder until next week when I will add the battery percentage retrieval logic.
def get_battery_percentage(voltage=7.4):
    # Placeholder function for battery percentage
    # This should be replaced with actual battery percentage retrieval logic
    return 0

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
            print(f"Device ID: {ina228.device_id:#06x}")
        except Exception as e:
            print(f"Error reading device ID: {e}")

        try:
            battery_percentage = get_battery_percentage(ina228.bus_voltage)
            if battery_percentage is not None and battery_percentage >= 0 and battery_percentage <= 100:
                print(f"Battery Percentage: {battery_percentage}%")
            else:
                print(f"Battery percentage is out of range (0-100%) - received: {battery_percentage}")
        except Exception as e:
            print(f"Error calculating battery percentage: {e}")

        return {
            "current": ina228.current,
            "voltage": ina228.bus_voltage,
            "power": ina228.power,
            "energy": ina228.energy,
            "temperature": ina228.die_temperature,
            "battery_percentage": battery_percentage,  # Placeholder for battery percentage
        }
    except Exception as e:
        print(f"Error reading sensor data: {e}")
        return None

# Print until the script is stopped - FOR TESTING ONLY
def print_sensor_data_loop():
    ina228 = init_sensor()
    data_rows = []
    headers = ['current', 'voltage', 'power', 'energy', 'temperature']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'power_log_{timestamp}.csv'
    try:
        while True:
            try:
                input("Press Enter to read sensor data (Ctrl+C to exit)...")
                power_data = get_power_values(ina228)
                if power_data:
                    print(f"Power Data: {power_data}")
                    row = [power_data.get(h) for h in headers]
                    data_rows.append(row)
                else:
                    print("No power data available.")
            except KeyboardInterrupt:
                print("Stopping sensor data printing. Saving CSV file...")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
    finally:
        if data_rows:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(data_rows)
            print(f"Data saved to {filename}")
        else:
            print("No data to save.")

if __name__ == "__main__":
    sensor = init_sensor()
    power_readings = get_power_values(sensor)
    print("Power readings:", power_readings)