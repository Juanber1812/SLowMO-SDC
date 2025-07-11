try:
    import board # type: ignore
    import adafruit_ina228 # type: ignore
    import time
    import csv
    import os
    import threading
    import logging
    from datetime import datetime
    import numpy as np

except ImportError as e:
    print(f"Error importing libraries: {e}")
    print("Make sure you have the required libraries installed.")
    print("Juan, for the adafruit_ina228 library, you can install it using: pip install adafruit-circuitpython-ina228")
    print("If it's not working let me know, I had some issues and had to use python 3.9 rather than 3.11")
    # For development/testing without hardware, create mock objects
    board = None
    adafruit_ina228 = None

# Last edited 20250629T19:30

class PowerMonitor:
    """Power monitoring system using INA228 sensor"""
    
    def __init__(self, update_interval=2.0, mock_mode=False):
        print("[PowerMonitor.__init__] Initializing PowerMonitor")
        self.update_interval = update_interval
        # Never use mock mode - if hardware isn't available, show disconnected
        self.mock_mode = False
        self.hardware_available = board is not None and adafruit_ina228 is not None
        self.running = False
        self.thread = None
        self.ina228 = None
        self.callback = None
        self.last_data = {}
        self.sensor_connected = False
        
        # CSV logging
        self.log_data = []
        self.csv_headers = ['timestamp', 'current_ma', 'voltage_v', 'power_mw', 'energy_j', 'temperature_c', 'battery_percentage']
        
        logging.info(f"PowerMonitor initialized (hardware_available: {self.hardware_available})")
        print(f"[PowerMonitor.__init__] hardware_available: {self.hardware_available}")

    def set_update_callback(self, callback):
        print("[PowerMonitor.set_update_callback] Callback set")
        """Set callback function to receive power data updates"""
        self.callback = callback
        
    def init_sensor(self):
        print("[PowerMonitor.init_sensor] Called")
        """Initialize the INA228 sensor"""
        if not self.hardware_available:
            print("[PowerMonitor.init_sensor] hardware not available")
            logging.warning("Power sensor libraries not available - status will be disconnected")
            self.sensor_connected = False
            return False
            
        try:
            i2c = board.I2C()
            # Try to initialize INA228 at default address 0x40
            self.ina228 = adafruit_ina228.INA228(i2c, address=0x40)
            
            # Test if we can actually read from the sensor
            test_voltage = self.ina228.bus_voltage
            print(f"[PowerMonitor.init_sensor] INA228 initialized, test voltage: {test_voltage:.2f}V")
            logging.info(f"INA228 power sensor initialized successfully at 0x40, test voltage: {test_voltage:.2f}V")
            self.sensor_connected = True
            return True
            
        except Exception as e:
            print(f"[PowerMonitor.init_sensor] Exception: {e}")
            logging.error(f"Error initializing INA228 sensor at 0x40: {e}")
            logging.info("Power sensor hardware not responding - status will be disconnected")
            self.sensor_connected = False
            return False
    
    def get_battery_percentage(self, voltage, current):
        """
        Estimate battery percentage for 2S Li-ion pack using compensated voltage.
        """
        # 2S Li-ion typical discharge curve (approximate, adjust as needed)
        self.voltages = np.array([6.0, 6.2, 6.4, 6.6, 6.8, 7.0, 7.2, 7.4, 7.6, 7.8, 8.0, 8.2, 8.4])
        self.percentages = np.array([0, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        self.internal_resistance = 0.10  # Ohms, typical for a pack (adjust if needed)

        estimated_voltage = voltage + (current * self.internal_resistance)
        estimated_voltage = min(max(estimated_voltage, self.voltages[0]), self.voltages[-1])
        pct = np.interp(estimated_voltage, self.voltages, self.percentages)
        return int(round(pct))
        
    print
    def get_power_values(self):
        """Read power values from sensor or return partial data with per-field errors"""
        logging.debug("[get_power_values] Called. sensor_connected=%s, ina228=%s", self.sensor_connected, self.ina228 is not None)
        if not self.sensor_connected or not self.ina228:
            logging.warning("[get_power_values] Not connected or INA228 missing. Returning Disconnected.")
            return {
                "current_ma": "error",
                "voltage_v": "error",
                "power_mw": "error",
                "energy_j": "error",
                "temperature_c": "error",
                "battery_percentage": "error",
                "status": "Disconnected"
            }

        result = {}
        errors = {}
        # Try to get each value independently
        try:
            current_ma = self.ina228.current * 1000
            result["current_ma"] = current_ma
            logging.debug(f"[get_power_values] current_ma: {current_ma}")
        except Exception as e:
            logging.error(f"Error reading current: {e}")
            result["current_ma"] = "error"
            errors["current_ma"] = str(e)

        try:
            voltage_v = self.ina228.bus_voltage
            result["voltage_v"] = voltage_v
            logging.debug(f"[get_power_values] voltage_v: {voltage_v}")
        except Exception as e:
            logging.error(f"Error reading voltage: {e}")
            result["voltage_v"] = "error"
            errors["voltage_v"] = str(e)

        try:
            power_mw = self.ina228.power * 1000
            result["power_mw"] = power_mw
            logging.debug(f"[get_power_values] power_mw: {power_mw}")
        except Exception as e:
            logging.error(f"Error reading power: {e}")
            result["power_mw"] = "error"
            errors["power_mw"] = str(e)

        try:
            energy_j = getattr(self.ina228, 'energy', None)
            if energy_j is None:
                raise AttributeError("INA228 object has no attribute 'energy'")
            result["energy_j"] = energy_j
            logging.debug(f"[get_power_values] energy_j: {energy_j}")
        except Exception as e:
            logging.error(f"Error reading energy: {e}")
            result["energy_j"] = "error"
            errors["energy_j"] = str(e)

        try:
            temperature_c = getattr(self.ina228, 'die_temperature', None)
            if temperature_c is None:
                raise AttributeError("INA228 object has no attribute 'die_temperature'")
            result["temperature_c"] = temperature_c
            logging.debug(f"[get_power_values] temperature_c: {temperature_c}")
        except Exception as e:
            logging.error(f"Error reading temperature: {e}")
            result["temperature_c"] = "error"
            errors["temperature_c"] = str(e)

        # Battery percentage depends on voltage and current
        try:
            if isinstance(result.get("voltage_v"), (int, float)) and isinstance(result.get("current_ma"), (int, float)):
                battery_pct = self.get_battery_percentage(result["voltage_v"], result["current_ma"] / 1000)
                result["battery_percentage"] = battery_pct
                logging.debug(f"[get_power_values] battery_percentage: {battery_pct}")
            else:
                raise ValueError("voltage_v or current_ma unavailable for battery percentage calculation")
        except Exception as e:
            logging.error(f"Error calculating battery percentage: {e}")
            result["battery_percentage"] = "error"
            errors["battery_percentage"] = str(e)

        # Determine status if possible
        try:
            if all(isinstance(result.get(k), (int, float)) for k in ["current_ma", "voltage_v", "power_mw", "battery_percentage"]):
                temp_val = result["temperature_c"] if isinstance(result["temperature_c"], (int, float)) else None
                power_status = self.determine_power_status(
                    result["current_ma"], result["voltage_v"], result["power_mw"], result["battery_percentage"], temp_val
                )
                result["status"] = power_status
                logging.debug(f"[get_power_values] status: {power_status}")
            else:
                result["status"] = "Partial Error"
                logging.debug(f"[get_power_values] status: Partial Error")
        except Exception as e:
            logging.error(f"Error determining power status: {e}")
            result["status"] = "error"
            errors["status"] = str(e)

        if errors:
            result["field_errors"] = errors
        logging.debug(f"[get_power_values] Final result: {result}")
        return result

    def log_data_to_csv(self, data):
        """Log power data to CSV file - only log real data, not disconnected status"""
        # Don't log disconnected or error states
        if data.get('status') in ['Disconnected', 'Error - Disconnected']:
            return
            
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [
                timestamp,
                data.get('current_ma', 0),
                data.get('voltage_v', 0),
                data.get('power_mw', 0),
                data.get('energy_j', 0),
                data.get('temperature_c', 0),
                data.get('battery_percentage', 0)
            ]
            self.log_data.append(row)
            
            # Save to file every 60 readings (about 2 minutes at 2Hz)
            if len(self.log_data) >= 60:
                self.save_csv_log()
                
        except Exception as e:
            logging.error(f"Error logging power data: {e}")

    def save_csv_log(self):
        """Save logged data to CSV file"""
        if not self.log_data:
            return
            
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'power_log_{timestamp}.csv'
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.csv_headers)
                writer.writerows(self.log_data)
                
            logging.info(f"Power data saved to {filename} ({len(self.log_data)} entries)")
            self.log_data.clear()
            
        except Exception as e:
            logging.error(f"Error saving CSV log: {e}")

    def monitoring_loop(self):
        """Main monitoring loop running in separate thread"""
        logging.info("Power monitoring loop started")

        while self.running:
            try:
                # Get power data
                power_data = self.get_power_values()

                if power_data:
                    self.last_data = power_data

                    # Log to CSV
                    self.log_data_to_csv(power_data)

                    # Send update via callback
                    if self.callback:
                        try:
                            self.callback(power_data)
                        except Exception as e:
                            logging.error(f"Error in power data callback: {e}")

                    # Debug logging (reduced frequency)
                    if len(self.log_data) % 30 == 0:  # Log every 30 readings
                        logging.debug(f"Power: {power_data['power_mw']:.1f}mW, "
                                    f"Current: {power_data['current_ma']:.1f}mA, "
                                    f"Voltage: {power_data['voltage_v']:.2f}V, "
                                    f"Temp: {power_data['temperature_c']:.1f}°C")

                time.sleep(self.update_interval)

            except Exception as e:
                logging.error(f"Error in power monitoring loop: {e}")
                time.sleep(self.update_interval)

        logging.info("Power monitoring loop stopped")

    def start_monitoring(self):
        """Start power monitoring in background thread"""
        if self.running:
            logging.warning("Power monitoring already running")
            return False
            
        # Try to initialize sensor
        sensor_init_success = self.init_sensor()
        if not sensor_init_success:
            logging.warning("Starting power monitoring without sensor - will show disconnected status")
        else:
            logging.info("Power sensor connected successfully")
                
        self.running = True
        self.thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.thread.start()
        logging.info("Power monitoring started")
        return True

    def stop_monitoring(self):
        """Stop power monitoring"""
        if not self.running:
            return
            
        logging.info("Stopping power monitoring...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
            
        # Save any remaining logged data
        self.save_csv_log()
        logging.info("Power monitoring stopped")

    def get_latest_data(self):
        """Get the most recent power data"""
        return self.last_data.copy() if self.last_data else {}

    def get_status(self):
        """Get power monitor status"""
        return {
            "running": self.running,
            "sensor_connected": self.sensor_connected,
            "hardware_available": self.hardware_available,
            "last_update": datetime.now().isoformat() if self.last_data else None
        }

    def determine_power_status(self, current_ma, voltage_v, power_mw, battery_pct, temperature_c=None):
        """Determine overall power system status based on readings"""
        # Only treat voltage==0 as error, not battery_pct==0
        if voltage_v == 0:
            return "Error"
        
        # If power is zero but current is not zero, that's an error (should be P = V × I)
        if power_mw == 0 and current_ma != 0:
            return "Error"
        
        # Check for abnormally low/high voltage (could indicate sensor issues)
        if voltage_v < 3.0 or voltage_v > 12.0:
            return "Error"
        
        # Check for very high current draw (more than 5A = 5000mA) - critical error
        if current_ma > 5000:
            return "Current Error"
        
        # Check for overheating (more than 60°C) - highest priority after Error
        if temperature_c and temperature_c > 60.0:
            return "Overheating"
        
        # Check for very high current draw (more than 2.5A = 2500mA) - critical
        if current_ma > 2500:
            return "Current Critical"
        
        # Check for voltage close to under-voltage lockout (UVLO) - typically around 5.3V
        if voltage_v < 5.5:
            return "V close to UVLO"  # Voltage close to under-voltage lockout
        
        # Check for critically low battery (less than 10%)
        if battery_pct < 10:
            return "Battery Critical"
        
        # Check for high temperature (more than 50°C) but not critical
        if temperature_c and temperature_c > 50.0:
            return "High Temperature"
        
        # Check for high current draw (more than 2A = 2000mA)
        if current_ma > 2000:
            return "High Current"
        
        # Check for low battery (less than 25%)
        if battery_pct < 25:
            return "Battery Low"
        
        # Check for high power consumption (more than 15W)
        if power_mw > 15000:
            return "High Power"
        
        # If all checks pass, system is OK
        return "OK"

# Standalone testing functions
def init_sensor():
    """Legacy function for backward compatibility"""
    monitor = PowerMonitor(mock_mode=True)
    monitor.init_sensor()
    return monitor

def get_power_values(ina228_or_monitor):
    """Legacy function for backward compatibility"""
    if isinstance(ina228_or_monitor, PowerMonitor):
        return ina228_or_monitor.get_power_values()
    else:
        # Original behavior for direct INA228 object
        monitor = PowerMonitor(mock_mode=False)
        monitor.ina228 = ina228_or_monitor
        return monitor.get_power_values()

# Print until the script is stopped - FOR TESTING ONLY
def print_sensor_data_loop():
    """Legacy testing function - now uses PowerMonitor class"""
    monitor = PowerMonitor(update_interval=1.0)
    
    def print_callback(data):
        if data.get('status') == 'Disconnected':
            print("Power Monitor: Disconnected - No data available")
        else:
            print(f"Power Data: Current: {data['current_ma']:.1f}mA, "
                  f"Voltage: {data['voltage_v']:.2f}V, "
                  f"Power: {data['power_mw']:.1f}mW, "
                  f"Energy: {data['energy_j']:.2f}J, "
                  f"Temp: {data['temperature_c']:.1f}°C, "
                  f"Battery: {data['battery_percentage']}%")
    
    monitor.set_update_callback(print_callback)
    
    try:
        monitor.start_monitoring()
        print("Power monitoring started. Press Ctrl+C to stop...")
        
        while True:
            try:
                input("Press Enter to continue monitoring (Ctrl+C to exit)...")
            except KeyboardInterrupt:
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop_monitoring()
        print("Power monitoring stopped")

if __name__ == "__main__":
    print("=== PowerMonitor Standalone Test ===")
    monitor = PowerMonitor()
    print("[MAIN] Created PowerMonitor instance")
    
    started = monitor.start_monitoring()
    print(f"[MAIN] start_monitoring() returned: {started}")
    
    if started:
        try:
            for i in range(5):
                print(f"[MAIN] Sleeping... ({i+1}/5)")
                time.sleep(1)
                latest = monitor.get_latest_data()
                print("[MAIN] Latest power readings:", latest)
                print("[MAIN] Monitor status:", monitor.get_status())
        finally:
            print("[MAIN] Stopping monitor...")
            monitor.stop_monitoring()
            print("[MAIN] Power monitoring stopped")
    else:
        print("[MAIN] Failed to start power monitoring")