try:
    import board # type: ignore
    import adafruit_ina228 # type: ignore
    import time
    import csv
    import os
    import threading
    import logging
    from datetime import datetime
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
        
    def set_update_callback(self, callback):
        """Set callback function to receive power data updates"""
        self.callback = callback
        
    def init_sensor(self):
        """Initialize the INA228 sensor"""
        if not self.hardware_available:
            logging.warning("Power sensor libraries not available - status will be disconnected")
            self.sensor_connected = False
            return False
            
        try:
            i2c = board.I2C()
            # Try to initialize INA228 at default address 0x40
            self.ina228 = adafruit_ina228.INA228(i2c, address=0x40)
            
            # Test if we can actually read from the sensor
            test_voltage = self.ina228.bus_voltage
            logging.info(f"INA228 power sensor initialized successfully at 0x40, test voltage: {test_voltage:.2f}V")
            self.sensor_connected = True
            return True
            
        except Exception as e:
            logging.error(f"Error initializing INA228 sensor at 0x40: {e}")
            logging.info("Power sensor hardware not responding - status will be disconnected")
            self.sensor_connected = False
            return False

    def get_battery_percentage(self, voltage=7.4):
        """Calculate battery percentage based on voltage (placeholder logic)"""
        # TODO: Implement proper battery percentage calculation
        # For now, use a simple linear approximation
        # Typical Li-ion: 3.0V (0%) to 4.2V (100%) per cell
        # Assuming 2S battery pack: 6.0V (0%) to 8.4V (100%)
        if voltage >= 8.4:
            return 100
        elif voltage <= 6.0:
            return 0
        else:
            return int(((voltage - 6.0) / (8.4 - 6.0)) * 100)

    def get_power_values(self):
        """Read power values from sensor or return disconnected status"""
        if not self.sensor_connected or not self.ina228:
            # Return disconnected status with no data
            return {
                "current_ma": 0.0,
                "voltage_v": 0.0,
                "power_mw": 0.0,
                "energy_j": 0.0,
                "temperature_c": 0.0,
                "battery_percentage": 0,
                "status": "Disconnected"
            }
            
        try:
            # Read actual values from INA228
            current_ma = self.ina228.current * 1000  # Convert A to mA
            voltage_v = self.ina228.bus_voltage
            power_mw = self.ina228.power * 1000  # Convert W to mW
            energy_j = getattr(self.ina228, 'energy', 0.0)  # Some versions may not have energy
            temperature_c = getattr(self.ina228, 'die_temperature', 25.0)  # Fallback temp
            battery_pct = self.get_battery_percentage(voltage_v)
            
            return {
                "current_ma": current_ma,
                "voltage_v": voltage_v,
                "power_mw": power_mw,
                "energy_j": energy_j,
                "temperature_c": temperature_c,
                "battery_percentage": battery_pct,
                "status": "Operational"
            }
            
        except Exception as e:
            logging.error(f"Error reading sensor data: {e}")
            # If we get an error reading, mark as disconnected
            self.sensor_connected = False
            return {
                "current_ma": 0.0,
                "voltage_v": 0.0,
                "power_mw": 0.0,
                "energy_j": 0.0,
                "temperature_c": 0.0,
                "battery_percentage": 0,
                "status": "Error - Disconnected"
            }

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
    # Test the power monitor - will connect to real hardware if available
    monitor = PowerMonitor()
    
    if monitor.start_monitoring():
        try:
            # Run for a few seconds to test
            time.sleep(5)
            latest = monitor.get_latest_data()
            print("Latest power readings:", latest)
            print("Monitor status:", monitor.get_status())
        finally:
            monitor.stop_monitoring()
    else:
        print("Failed to start power monitoring")