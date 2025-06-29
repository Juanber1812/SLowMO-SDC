"""
Communication monitoring module for SLowMO system.
Handles WiFi speed testing, upload speed calculation, and signal strength monitoring.
"""

import threading
import time
import subprocess
import json
import logging
import speedtest
import psutil
import platform
from typing import Dict, Any, Optional, Callable

class CommunicationMonitor:
    """Monitor communication metrics including WiFi speed, upload speed, and signal strength."""
    
    def __init__(self):
        self.is_monitoring = False
        self.update_callback = None
        self.thread = None
        
        # Current metrics
        self.current_data = {
            'wifi_download_speed': 0.0,
            'wifi_upload_speed': 0.0,
            'data_upload_speed': 0.0,  # Actual data upload speed (e.g., from camera)
            'data_transmission_rate': 0.0,  # Current data transmission rate in KB/s
            'uplink_frequency': 0.0,  # WiFi uplink frequency in GHz
            'downlink_frequency': 0.0,  # WiFi downlink frequency in GHz
            'server_signal_strength': 0,
            'client_signal_strength': 0,
            'connection_quality': 'Unknown',  # Poor, Fair, Good, Excellent
            'network_latency': 0.0,  # Ping latency in ms
            'packet_loss': 0.0,  # Packet loss percentage
            'status': 'Disconnected'
        }
        
        # Upload speed calculation
        self.upload_start_time = None
        self.upload_total_bytes = 0
        self.upload_speed_history = []
        
        # Data transmission tracking
        self.transmission_start_time = None
        self.transmission_total_bytes = 0
        self.transmission_history = []
        
        # Network performance tracking
        self.latency_history = []
        self.packet_loss_history = []
        
        # Lock for thread-safe operations
        self.lock = threading.Lock()
        
        # Speed test instance (created when needed)
        self.speed_test = None
        
        # WiFi speed test interval (seconds)
        self.wifi_test_interval = 300  # 5 minutes
        self.last_wifi_test = 0
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def set_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback function to receive communication data updates."""
        self.update_callback = callback
    
    def start_monitoring(self) -> bool:
        """Start communication monitoring."""
        if self.is_monitoring:
            return True
        
        try:
            self.is_monitoring = True
            self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.thread.start()
            self.logger.info("Communication monitoring started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start communication monitoring: {e}")
            self.is_monitoring = False
            return False
    
    def stop_monitoring(self):
        """Stop communication monitoring."""
        self.is_monitoring = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.logger.info("Communication monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                with self.lock:
                    # Update signal strength
                    self._update_signal_strength()
                    
                    # Update WiFi frequencies
                    self._update_wifi_frequencies()
                    
                    # Update data upload speed
                    self._update_data_upload_speed()
                    
                    # Update data transmission rate
                    self._update_data_transmission_rate()
                    
                    # Update network performance metrics
                    self._update_network_performance()
                    
                    # Check if we need to run WiFi speed test
                    current_time = time.time()
                    if current_time - self.last_wifi_test > self.wifi_test_interval:
                        self._update_wifi_speed()
                        self.last_wifi_test = current_time
                    
                    # Update connection quality and status
                    self._update_connection_quality()
                    self.current_data['status'] = 'Connected' if self._is_connected() else 'Disconnected'
                    
                    # Send update via callback
                    if self.update_callback:
                        self.update_callback(self.current_data.copy())
                
                time.sleep(1)  # Update every second
                
            except Exception as e:
                self.logger.error(f"Error in communication monitoring loop: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _update_signal_strength(self):
        """Update WiFi signal strength for server."""
        try:
            if platform.system() == "Linux":
                # For Raspberry Pi - use iwconfig
                result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    output = result.stdout
                    for line in output.split('\n'):
                        if 'Signal level' in line:
                            # Extract signal strength (e.g., "Signal level=-45 dBm")
                            parts = line.split('Signal level=')
                            if len(parts) > 1:
                                signal_str = parts[1].split()[0]
                                self.current_data['server_signal_strength'] = int(signal_str)
                                break
                else:
                    self.current_data['server_signal_strength'] = 0
            else:
                # For Windows/other systems - use netsh (Windows) or default to 0
                if platform.system() == "Windows":
                    result = subprocess.run(
                        ['netsh', 'wlan', 'show', 'profiles'],
                        capture_output=True, text=True, timeout=5
                    )
                    # This is a simplified approach - in reality, you'd need to parse the output
                    # For now, set a default value
                    self.current_data['server_signal_strength'] = -50  # Default reasonable value
                else:
                    self.current_data['server_signal_strength'] = 0
                    
        except Exception as e:
            self.logger.error(f"Error updating signal strength: {e}")
            self.current_data['server_signal_strength'] = 0
    
    def _update_wifi_frequencies(self):
        """Update WiFi uplink and downlink frequencies."""
        try:
            if platform.system() == "Linux":
                # For Raspberry Pi - use iwconfig to get frequency
                result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    output = result.stdout
                    for line in output.split('\n'):
                        if 'Frequency:' in line:
                            # Extract frequency (e.g., "Frequency:2.437 GHz")
                            parts = line.split('Frequency:')
                            if len(parts) > 1:
                                freq_str = parts[1].split()[0]
                                frequency = float(freq_str)
                                # For WiFi, uplink and downlink are typically the same frequency
                                self.current_data['uplink_frequency'] = round(frequency, 3)
                                self.current_data['downlink_frequency'] = round(frequency, 3)
                                break
                else:
                    self.current_data['uplink_frequency'] = 0.0
                    self.current_data['downlink_frequency'] = 0.0
            else:
                # For Windows/other systems - default values
                if platform.system() == "Windows":
                    # Could implement netsh wlan show profiles name="profile" key=clear
                    # For now, use common 2.4GHz default
                    self.current_data['uplink_frequency'] = 2.4
                    self.current_data['downlink_frequency'] = 2.4
                else:
                    self.current_data['uplink_frequency'] = 0.0
                    self.current_data['downlink_frequency'] = 0.0
                    
        except Exception as e:
            self.logger.error(f"Error updating WiFi frequencies: {e}")
            self.current_data['uplink_frequency'] = 0.0
            self.current_data['downlink_frequency'] = 0.0
    
    def _update_wifi_speed(self):
        """Update WiFi speed using speedtest."""
        try:
            if not self.speed_test:
                self.speed_test = speedtest.Speedtest()
            
            # Get best server
            self.speed_test.get_best_server()
            
            # Test download speed
            download_speed = self.speed_test.download() / 1_000_000  # Convert to Mbps
            self.current_data['wifi_download_speed'] = round(download_speed, 2)
            
            # Test upload speed
            upload_speed = self.speed_test.upload() / 1_000_000  # Convert to Mbps
            self.current_data['wifi_upload_speed'] = round(upload_speed, 2)
            
            self.logger.info(f"WiFi speed test completed: {download_speed:.2f} Mbps down, {upload_speed:.2f} Mbps up")
            
        except Exception as e:
            self.logger.error(f"Error running WiFi speed test: {e}")
            self.current_data['wifi_download_speed'] = 0.0
            self.current_data['wifi_upload_speed'] = 0.0
    
    def _update_data_upload_speed(self):
        """Update actual data upload speed based on data transfer."""
        try:
            # Calculate average upload speed from recent history
            if self.upload_speed_history:
                recent_speeds = self.upload_speed_history[-10:]  # Last 10 measurements
                avg_speed = sum(recent_speeds) / len(recent_speeds)
                self.current_data['data_upload_speed'] = round(avg_speed, 2)
            else:
                self.current_data['data_upload_speed'] = 0.0
                
        except Exception as e:
            self.logger.error(f"Error updating data upload speed: {e}")
            self.current_data['data_upload_speed'] = 0.0
    
    def _update_data_transmission_rate(self):
        """Update current data transmission rate based on recent activity."""
        try:
            # Calculate current transmission rate from recent history
            if self.transmission_history:
                recent_transmissions = self.transmission_history[-5:]  # Last 5 measurements
                avg_rate = sum(recent_transmissions) / len(recent_transmissions)
                self.current_data['data_transmission_rate'] = round(avg_rate, 2)
            else:
                self.current_data['data_transmission_rate'] = 0.0
                
        except Exception as e:
            self.logger.error(f"Error updating data transmission rate: {e}")
            self.current_data['data_transmission_rate'] = 0.0
    
    def _update_network_performance(self):
        """Update network latency and packet loss metrics."""
        try:
            # Ping test to measure latency
            if platform.system() == "Linux":
                # Ping gateway or common DNS server
                result = subprocess.run(['ping', '-c', '1', '-W', '1', '8.8.8.8'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    output = result.stdout
                    for line in output.split('\n'):
                        if 'time=' in line:
                            # Extract time (e.g., "time=23.4 ms")
                            parts = line.split('time=')
                            if len(parts) > 1:
                                time_str = parts[1].split()[0]
                                latency = float(time_str)
                                self.latency_history.append(latency)
                                break
                else:
                    self.latency_history.append(999.0)  # High latency for failed ping
            else:
                # Windows ping
                result = subprocess.run(['ping', '-n', '1', '-w', '1000', '8.8.8.8'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    output = result.stdout
                    for line in output.split('\n'):
                        if 'time<' in line or 'time=' in line:
                            if 'time<' in line:
                                latency = 1.0  # Less than 1ms
                            else:
                                parts = line.split('time=')
                                if len(parts) > 1:
                                    time_str = parts[1].split('ms')[0]
                                    latency = float(time_str)
                            self.latency_history.append(latency)
                            break
                else:
                    self.latency_history.append(999.0)
            
            # Keep only recent latency history
            if len(self.latency_history) > 10:
                self.latency_history = self.latency_history[-10:]
            
            # Calculate average latency
            if self.latency_history:
                avg_latency = sum(self.latency_history) / len(self.latency_history)
                self.current_data['network_latency'] = round(avg_latency, 1)
                
                # Simple packet loss calculation (failed pings)
                failed_pings = sum(1 for lat in self.latency_history[-5:] if lat >= 999.0)
                packet_loss = (failed_pings / min(5, len(self.latency_history))) * 100
                self.current_data['packet_loss'] = round(packet_loss, 1)
            else:
                self.current_data['network_latency'] = 0.0
                self.current_data['packet_loss'] = 0.0
                
        except Exception as e:
            self.logger.error(f"Error updating network performance: {e}")
            self.current_data['network_latency'] = 0.0
            self.current_data['packet_loss'] = 0.0
    
    def _update_connection_quality(self):
        """Update connection quality based on signal strength, latency, and packet loss."""
        try:
            signal = self.current_data['server_signal_strength']
            latency = self.current_data['network_latency']
            packet_loss = self.current_data['packet_loss']
            
            # Quality assessment based on multiple factors
            if signal >= -50 and latency <= 20 and packet_loss <= 1:
                quality = 'Excellent'
            elif signal >= -60 and latency <= 50 and packet_loss <= 3:
                quality = 'Good'
            elif signal >= -70 and latency <= 100 and packet_loss <= 5:
                quality = 'Fair'
            else:
                quality = 'Poor'
            
            self.current_data['connection_quality'] = quality
            
        except Exception as e:
            self.logger.error(f"Error updating connection quality: {e}")
            self.current_data['connection_quality'] = 'Unknown'
    
    def _is_connected(self) -> bool:
        """Check if there's an active network connection."""
        try:
            # Check network interfaces
            interfaces = psutil.net_if_stats()
            for interface, stats in interfaces.items():
                if stats.isup and interface not in ['lo', 'localhost']:
                    return True
            return False
        except:
            return False
    
    def record_upload_data(self, bytes_sent: int):
        """Record data upload for speed calculation."""
        try:
            current_time = time.time()
            
            with self.lock:
                if self.upload_start_time is None:
                    self.upload_start_time = current_time
                    self.upload_total_bytes = 0
                
                self.upload_total_bytes += bytes_sent
                
                # Calculate speed every second
                time_diff = current_time - self.upload_start_time
                if time_diff >= 1.0:
                    speed_kbps = (self.upload_total_bytes / 1024) / time_diff
                    self.upload_speed_history.append(speed_kbps)
                    
                    # Keep only recent history
                    if len(self.upload_speed_history) > 30:
                        self.upload_speed_history = self.upload_speed_history[-30:]
                    
                    # Reset for next measurement
                    self.upload_start_time = current_time
                    self.upload_total_bytes = 0
                    
                    # Also update transmission rate tracking
                    self._record_transmission_rate(speed_kbps)
                    
        except Exception as e:
            self.logger.error(f"Error recording upload data: {e}")
    
    def _record_transmission_rate(self, rate_kbps: float):
        """Record transmission rate for real-time monitoring."""
        try:
            self.transmission_history.append(rate_kbps)
            
            # Keep only recent transmission history
            if len(self.transmission_history) > 20:
                self.transmission_history = self.transmission_history[-20:]
                
        except Exception as e:
            self.logger.error(f"Error recording transmission rate: {e}")
    
    def record_data_transmission(self, bytes_sent: int):
        """Record data transmission for transmission rate calculation."""
        try:
            current_time = time.time()
            
            with self.lock:
                if self.transmission_start_time is None:
                    self.transmission_start_time = current_time
                    self.transmission_total_bytes = 0
                
                self.transmission_total_bytes += bytes_sent
                
                # Calculate transmission rate every 0.5 seconds for more responsive updates
                time_diff = current_time - self.transmission_start_time
                if time_diff >= 0.5:
                    rate_kbps = (self.transmission_total_bytes / 1024) / time_diff
                    self._record_transmission_rate(rate_kbps)
                    
                    # Reset for next measurement
                    self.transmission_start_time = current_time
                    self.transmission_total_bytes = 0
                    
        except Exception as e:
            self.logger.error(f"Error recording upload data: {e}")
    
    def update_client_signal_strength(self, signal_strength: int):
        """Update client signal strength (received from client)."""
        with self.lock:
            self.current_data['client_signal_strength'] = signal_strength
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current communication data."""
        with self.lock:
            return self.current_data.copy()
