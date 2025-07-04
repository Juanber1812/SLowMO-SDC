# unified_monitoring.py

"""
Unified monitoring module that combines sensors, power, communication, and thermal monitoring
into a single thread to reduce resource usage.
"""

import time
import logging
import threading
import psutil
from datetime import datetime

# Import monitoring modules
try:
    from power import PowerMonitor
    POWER_AVAILABLE = True
except ImportError:
    POWER_AVAILABLE = False

try:
    from communication import CommunicationMonitor
    COMMUNICATION_AVAILABLE = True
except ImportError:
    COMMUNICATION_AVAILABLE = False

try:
    from temperature import W1ThermSensor, BATTERY_SENSOR_ID, W1THERM_AVAILABLE
except ImportError:
    W1THERM_AVAILABLE = False

class UnifiedMonitor:
    """Unified monitoring system that handles all monitoring tasks in a single thread"""
    
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self.running = False
        self.thread = None
        
        # Monitoring intervals (seconds)
        self.SENSOR_INTERVAL = 2.0      # Pi sensors every 2 seconds
        self.POWER_INTERVAL = 0.5       # Power every 500ms (2Hz)
        self.THERMAL_INTERVAL = 0.5     # Thermal every 500ms (2Hz)  
        self.COMMUNICATION_INTERVAL = 2.0  # Communication every 2 seconds
        
        # Last update times
        self.last_sensor_time = 0
        self.last_power_time = 0
        self.last_thermal_time = 0
        self.last_communication_time = 0
        
        # Sensor start time for uptime calculation
        self.sensor_start_time = time.time()
        
        # Temperature storage for thermal monitoring
        self.latest_battery_temp = None
        self.latest_pi_temp = None
        self.latest_payload_temp = None
        
        # Initialize hardware interfaces (no threads)
        self.power_monitor = None
        self.communication_monitor = None
        self.battery_sensor = None
        
        if POWER_AVAILABLE:
            self.power_monitor = PowerMonitor()
            self.power_monitor.init_sensor()  # Just init, don't start thread
            
        if COMMUNICATION_AVAILABLE:
            self.communication_monitor = CommunicationMonitor()
            # Don't start monitoring thread
            
        if W1THERM_AVAILABLE:
            try:
                self.battery_sensor = W1ThermSensor(sensor_id=BATTERY_SENSOR_ID)
            except:
                self.battery_sensor = None
        
        self.connected_clients = set()
        
    def add_client(self, client_id):
        """Add a connected client"""
        self.connected_clients.add(client_id)
        
    def remove_client(self, client_id):
        """Remove a disconnected client"""
        self.connected_clients.discard(client_id)
        
    def get_temp(self):
        """Get Pi temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                return int(f.read()) / 1000.0
        except:
            return None

    def get_memory_usage(self):
        """Get memory usage statistics"""
        try:
            memory = psutil.virtual_memory()
            return {
                'percent': round(memory.percent, 1),
                'used_gb': round(memory.used / (1024**3), 2),
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2)
            }
        except:
            return None

    def get_uptime(self):
        """Calculate uptime since monitoring started"""
        current_time = time.time()
        uptime_seconds = current_time - self.sensor_start_time
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"

    def get_system_status(self, cpu_percent, memory_percent):
        """Generate system status based on CPU and memory usage"""
        try:
            if cpu_percent >= 95 or memory_percent >= 95:
                return "Critical"
            elif cpu_percent >= 80 or memory_percent >= 85:
                return "High Load"
            elif cpu_percent >= 50 or memory_percent >= 70:
                return "Moderate Load"
            elif cpu_percent <= 20 and memory_percent <= 50:
                return "Optimal"
            else:
                return "Normal"
        except:
            return "Unknown"

    def update_sensors(self):
        """Update Pi sensor data"""
        try:
            temp = self.get_temp()
            cpu = psutil.cpu_percent(interval=None)
            memory = self.get_memory_usage()
            uptime = self.get_uptime()
            
            memory_percent = memory.get('percent', 0) if memory else 0
            system_status = self.get_system_status(cpu, memory_percent)
            
            # Store Pi temperature for thermal monitoring
            self.latest_pi_temp = temp
            
            sensor_data = {
                "temperature": temp,
                "cpu_percent": cpu,
                "memory": memory,
                "uptime": uptime,
                "status": system_status
            }
            
            self.socketio.emit("sensor_broadcast", {
                "temperature": sensor_data.get("temperature"),
                "cpu_percent": sensor_data.get("cpu_percent"),
                "memory_percent": memory_percent,
                "uptime": sensor_data.get("uptime"),
                "status": sensor_data.get("status")
            })
            
        except Exception as e:
            logging.error(f"Error updating sensors: {e}")

    def update_power(self):
        """Update power monitoring data"""
        if not self.power_monitor:
            return
            
        try:
            power_data = self.power_monitor.get_power_values()
            if power_data:
                # Store battery temperature for thermal monitoring
                if power_data.get('status') not in ['Disconnected', 'Error - Disconnected', 'Error']:
                    self.latest_battery_temp = power_data.get('temperature_c')
                else:
                    self.latest_battery_temp = None
                
                # Format and emit power data
                if power_data.get('status') in ['Disconnected', 'Error - Disconnected', 'Error']:
                    formatted_data = {
                        "current": "0.000",
                        "voltage": "0.0", 
                        "power": "0.00",
                        "energy": "0.00",
                        "temperature": "0.0",
                        "battery_percentage": 0,
                        "status": "Disconnected"
                    }
                else:
                    status_mapping = {
                        "OK": "Nominal",
                        "Battery Low": "Battery Low", 
                        "Battery Critical": "Battery Critical",
                        "High Current": "High Current",
                        "Current Critical": "Current Critical",
                        "Current Error": "Current Error",
                        "High Power": "High Power",
                        "High Temperature": "High Temperature",
                        "Overheating": "Overheating",
                        "V close to UVLO": "Near UVLO",
                        "Operational": "Nominal"
                    }
                    
                    client_status = status_mapping.get(power_data['status'], power_data['status'])
                    
                    formatted_data = {
                        "current": f"{power_data['current_ma'] / 1000:.3f}",
                        "voltage": f"{power_data['voltage_v']:.1f}",
                        "power": f"{power_data['power_mw'] / 1000:.2f}",
                        "energy": f"{power_data['energy_j'] / 3600:.2f}",
                        "temperature": f"{power_data['temperature_c']:.1f}",
                        "battery_percentage": power_data['battery_percentage'],
                        "status": client_status
                    }
                
                self.socketio.emit("power_broadcast", formatted_data)
                
        except Exception as e:
            logging.error(f"Error updating power: {e}")

    def update_communication(self):
        """Update communication monitoring data"""
        if not self.communication_monitor or len(self.connected_clients) == 0:
            return
            
        try:
            # Update communication metrics without starting a separate thread
            self.communication_monitor._update_signal_strength()
            self.communication_monitor._update_wifi_frequency()
            self.communication_monitor._update_status()
            
            comm_data = self.communication_monitor.get_current_data()
            
            formatted_data = {
                "downlink_frequency": comm_data.get('downlink_frequency', 0.0),
                "data_transmission_rate": comm_data.get('data_transmission_rate', 0.0),
                "server_signal_strength": comm_data.get('server_signal_strength', 0),
                "latency": comm_data.get('latency', 0.0),
                "status": comm_data.get('status', 'Disconnected')
            }
            
            self.socketio.emit("communication_broadcast", formatted_data)
            
        except Exception as e:
            logging.error(f"Error updating communication: {e}")

    def determine_thermal_status(self, battery_temp, pi_temp, payload_temp):
        """Determine overall thermal status"""
        statuses = []
        
        if battery_temp is not None:
            if battery_temp >= 60:
                statuses.append("Battery Critical")
            elif battery_temp >= 50:
                statuses.append("Battery Hot")
            elif battery_temp >= 40:
                statuses.append("Battery Warm")
        
        if pi_temp is not None:
            if pi_temp >= 80:
                statuses.append("Pi Critical")
            elif pi_temp >= 70:
                statuses.append("Pi Hot")
            elif pi_temp >= 60:
                statuses.append("Pi Warm")
        
        if payload_temp is not None:
            if payload_temp >= 70:
                statuses.append("Payload Critical")
            elif payload_temp >= 60:
                statuses.append("Payload Hot")
            elif payload_temp >= 50:
                statuses.append("Payload Warm")
        
        if any("Critical" in status for status in statuses):
            return "Critical"
        elif any("Hot" in status for status in statuses):
            return "Hot"
        elif any("Warm" in status for status in statuses):
            return "Warm"
        else:
            return "Nominal"

    def update_thermal(self):
        """Update thermal monitoring data"""
        try:
            # Read battery temperature if sensor is available
            if self.battery_sensor:
                try:
                    self.latest_battery_temp = self.battery_sensor.get_temperature()
                except:
                    pass  # Keep existing value or None
            
            status = self.determine_thermal_status(
                self.latest_battery_temp, 
                self.latest_pi_temp, 
                self.latest_payload_temp
            )
            
            thermal_data = {
                "battery_temp": f"{self.latest_battery_temp:.1f}" if self.latest_battery_temp is not None else "N/A",
                "pi_temp": f"{self.latest_pi_temp:.1f}" if self.latest_pi_temp is not None else "N/A",
                "payload_temp": f"{self.latest_payload_temp:.1f}" if self.latest_payload_temp is not None else "N/A",
                "status": status
            }
            
            self.socketio.emit("thermal_broadcast", thermal_data)
            
        except Exception as e:
            logging.error(f"Error updating thermal: {e}")

    def set_payload_temperature(self, payload_temp):
        """Set payload temperature from ADCS data"""
        self.latest_payload_temp = payload_temp

    def monitoring_loop(self):
        """Main unified monitoring loop"""
        logging.info("Unified monitoring loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Update sensors (2 seconds interval)
                if current_time - self.last_sensor_time >= self.SENSOR_INTERVAL:
                    self.update_sensors()
                    self.last_sensor_time = current_time
                
                # Update power (500ms interval)
                if current_time - self.last_power_time >= self.POWER_INTERVAL:
                    self.update_power()
                    self.last_power_time = current_time
                
                # Update thermal (500ms interval)
                if current_time - self.last_thermal_time >= self.THERMAL_INTERVAL:
                    self.update_thermal()
                    self.last_thermal_time = current_time
                
                # Update communication (2 seconds interval)
                if current_time - self.last_communication_time >= self.COMMUNICATION_INTERVAL:
                    self.update_communication()
                    self.last_communication_time = current_time
                
                # Sleep for 100ms to prevent CPU spinning
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Error in unified monitoring loop: {e}")
                time.sleep(1)
        
        logging.info("Unified monitoring loop stopped")

    def start_monitoring(self):
        """Start unified monitoring"""
        if self.running:
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.thread.start()
        logging.info("Unified monitoring started")
        return True

    def stop_monitoring(self):
        """Stop unified monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logging.info("Unified monitoring stopped")
