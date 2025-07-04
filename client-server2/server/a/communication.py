"""
Communication monitoring module for SLowMO system.
Monitors: downlink frequency, server signal strength, 
data transmission rate (via throughput tests), latency, and overall status.
"""

import threading
import time
import subprocess
import json
import logging
import psutil
import platform
from typing import Dict, Any, Optional, Callable

class CommunicationMonitor:
    """Monitor communication metrics including signal strength and data transmission rate."""
    
    def __init__(self):
        self.is_monitoring = False
        self.update_callback = None
        self.throughput_test_callback = None
        self.thread = None
        
        # Current metrics - focused on local network performance
        self.current_data = {
            'downlink_frequency': 0.0,  # WiFi downlink frequency in GHz
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
    

    # Remove all threading and background monitoring logic for single-threaded polling
    def start_monitoring(self) -> bool:
        """Initialize for polling (no thread)"""
        self.is_monitoring = True
        self.logger.info("Communication monitoring ready for polling (no thread)")
        return True

    def stop_monitoring(self):
        self.is_monitoring = False
        self.logger.info("Communication monitoring stopped (no thread)")

    def poll(self):
        """Poll all communication metrics once (call from main server thread)"""
        with self.lock:
            self._update_signal_strength()
            self._update_wifi_frequency()
            self._update_status()
            # Optionally, initiate throughput test if needed (can be called externally)
            # self.initiate_throughput_test()
        return self.current_data.copy()
    
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
    
    def _update_status(self):
        """Update overall status based on available metrics."""
        try:
            signal = self.current_data['server_signal_strength']
            throughput = self.current_data['data_transmission_rate']
            latency = self.current_data['latency']
            
            # Determine status based on local network metrics only
            if not self._is_connected():
                self.current_data['status'] = 'Disconnected'
            elif signal < -80 or throughput < 50:  # Very poor signal or low throughput
                self.current_data['status'] = 'Poor Connection'
            elif signal < -70 or throughput < 200 or latency > 100:  # Fair conditions
                self.current_data['status'] = 'Fair Connection'
            elif signal >= -50 and throughput >= 500 and latency <= 20:  # Excellent conditions
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
