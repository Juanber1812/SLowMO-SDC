"""
Communication monitoring module for SLowMO system.
Simplified to monitor: downlink frequency, WiFi speed, server signal strength, 
data transmission rate (via throughput tests), and overall status.
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
        self.throughput_test_callback = None
        self.thread = None
        
        # Current metrics - simplified to only required ones
        self.current_data = {
            'downlink_frequency': 0.0,  # WiFi downlink frequency in GHz
            'wifi_download_speed': 0.0,  # Internet download speed in Mbps
            'wifi_upload_speed': 0.0,    # Internet upload speed in Mbps
            'data_transmission_rate': 0.0,  # True channel throughput in KB/s
            'server_signal_strength': 0,  # WiFi signal strength in dBm
            'latency': 0.0,              # One-way latency in ms (server to client)
            'status': 'Disconnected'      # Overall connection status
        }
        
        # Channel throughput testing
        self.throughput_test_data = None
        self.throughput_test_start = None
        self.throughput_results = []
        
        # Latency tracking
        self.latency_results = []
        
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
    
    def set_throughput_test_callback(self, callback):
        """Set callback function for initiating throughput tests with client."""
        self.throughput_test_callback = callback
    
    def initiate_throughput_test(self):
        """Initiate a throughput test by sending test data to client."""
        try:
            # Generate test data (10KB for quick test)
            test_data_size = 10240  # 10KB
            test_data = b'T' * test_data_size
            
            # Record start time and data
            self.throughput_test_start = time.time()
            self.throughput_test_data = test_data
            
            # Send throughput test command to client via callback
            if hasattr(self, 'throughput_test_callback') and self.throughput_test_callback:
                self.throughput_test_callback('throughput_test', {
                    'test_data': test_data,
                    'size': test_data_size,
                    'timestamp': self.throughput_test_start
                })
                return True
        except Exception as e:
            self.logger.error(f"Failed to initiate throughput test: {e}")
        return False
    
    def handle_throughput_response(self, response_data, response_size):
        """Handle response from client throughput test."""
        try:
            if self.throughput_test_start and self.throughput_test_data:
                # Calculate round-trip time
                end_time = time.time()
                round_trip_time = end_time - self.throughput_test_start
                
                # Calculate throughput (bytes per second, then convert to KB/s)
                if round_trip_time > 0:
                    throughput_bps = (response_size * 2) / round_trip_time  # *2 for round trip
                    throughput_kbps = throughput_bps / 1024
                    
                    # Store result and update current data
                    self.throughput_results.append(throughput_kbps)
                    
                    # Keep only last 5 results for averaging
                    if len(self.throughput_results) > 5:
                        self.throughput_results = self.throughput_results[-5:]
                    
                    # Update current data transmission rate (average of recent tests)
                    with self.lock:
                        self.current_data['data_transmission_rate'] = round(sum(self.throughput_results) / len(self.throughput_results), 2)
                
                # Reset test state
                self.throughput_test_start = None
                self.throughput_test_data = None
                
        except Exception as e:
            self.logger.error(f"Error handling throughput response: {e}")
    
    def handle_latency_response(self, client_receive_time):
        """Handle latency measurement from client."""
        try:
            if self.throughput_test_start:
                # Calculate one-way latency (server to client)
                latency_seconds = client_receive_time - self.throughput_test_start
                latency_ms = latency_seconds * 1000  # Convert to milliseconds
                
                # Store latency result
                self.latency_results.append(latency_ms)
                
                # Keep only last 5 results for averaging
                if len(self.latency_results) > 5:
                    self.latency_results = self.latency_results[-5:]
                
                # Update current latency (average of recent tests)
                with self.lock:
                    self.current_data['latency'] = round(sum(self.latency_results) / len(self.latency_results), 1)
                    
        except Exception as e:
            self.logger.error(f"Error handling latency response: {e}")
    
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
        """Main monitoring loop - simplified to focus on required metrics only."""
        throughput_test_interval = 2  # Test throughput every 2 seconds
        last_throughput_test = 0
        
        while self.is_monitoring:
            try:
                current_time = time.time()
                
                with self.lock:
                    # Update WiFi signal strength
                    self._update_signal_strength()
                    
                    # Update WiFi downlink frequency
                    self._update_wifi_frequency()
                    
                    # Update overall status based on metrics
                    self._update_status()
                    
                    # Check if we need to run WiFi speed test (every 5 minutes)
                    if current_time - self.last_wifi_test > self.wifi_test_interval:
                        self._update_wifi_speed()
                        self.last_wifi_test = current_time
                    
                    # Initiate throughput test periodically
                    if current_time - last_throughput_test > throughput_test_interval:
                        if self.initiate_throughput_test():
                            last_throughput_test = current_time
                    
                    # Send update via callback
                    if self.update_callback:
                        self.update_callback(self.current_data.copy())
                
                time.sleep(2)  # Update every 2 seconds
                
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
    
    def _update_wifi_frequency(self):
        """Update WiFi downlink frequency."""
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
                                self.current_data['downlink_frequency'] = round(frequency, 3)
                                break
                else:
                    self.current_data['downlink_frequency'] = 0.0
            else:
                # For Windows/other systems - default values
                if platform.system() == "Windows":
                    # Could implement netsh wlan show profiles name="profile" key=clear
                    # For now, use common 2.4GHz default
                    self.current_data['downlink_frequency'] = 2.4
                else:
                    self.current_data['downlink_frequency'] = 0.0
                    
        except Exception as e:
            self.logger.error(f"Error updating WiFi frequency: {e}")
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
    
    def _update_status(self):
        """Update overall status based on available metrics."""
        try:
            signal = self.current_data['server_signal_strength']
            wifi_down = self.current_data['wifi_download_speed']
            throughput = self.current_data['data_transmission_rate']
            
            # Determine status based on metrics
            if not self._is_connected():
                self.current_data['status'] = 'Disconnected'
            elif signal < -80 or (wifi_down > 0 and wifi_down < 1):
                self.current_data['status'] = 'Poor Connection'
            elif signal < -70 or (wifi_down > 0 and wifi_down < 5):
                self.current_data['status'] = 'Fair Connection'
            elif signal >= -50 and wifi_down >= 10:
                self.current_data['status'] = 'Excellent'
            else:
                self.current_data['status'] = 'Good'
                
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            self.current_data['status'] = 'Unknown'
    
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
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current communication data."""
        with self.lock:
            return self.current_data.copy()
