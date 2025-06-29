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
            'server_signal_strength': 0,
            'client_signal_strength': 0,
            'status': 'Disconnected'
        }
        
        # Upload speed calculation
        self.upload_start_time = None
        self.upload_total_bytes = 0
        self.upload_speed_history = []
        
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
                    
                    # Update data upload speed
                    self._update_data_upload_speed()
                    
                    # Check if we need to run WiFi speed test
                    current_time = time.time()
                    if current_time - self.last_wifi_test > self.wifi_test_interval:
                        self._update_wifi_speed()
                        self.last_wifi_test = current_time
                    
                    # Update status
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
