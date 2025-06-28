#!/usr/bin/env python3
"""
Controllable VEML7700 Lux Sensors with Data Logging
Supports 3 sensors via I2C multiplexer with timestamped logging
"""

import time
import board
import busio
from adafruit_veml7700 import VEML7700
import csv
import sys
import select
import termios
import tty
from datetime import datetime

# Constants
MUX_ADDRESS = 0x70  # I2C address of the multiplexer
CHANNELS = [1, 2, 3]  # Channels where VEML7700s are connected

class LuxSensorController:
    def __init__(self):
        """Initialize the lux sensor controller"""
        self.running = False
        self.logging_enabled = False
        self.log_data = []
        self.log_interval = 0.1  # Fixed 10Hz (0.1 seconds) logging interval
        self.display_interval = 0.1  # Fixed 10Hz (0.1 seconds) display interval
        self.sensors_ready = False  # Track if sensors are available
        
        # Setup I2C
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            print("I2C bus initialized successfully")
        except Exception as e:
            print(f"Error initializing I2C bus: {e}")
            self.sensors_ready = False
            return
        
        # Initialize sensors
        self.initialize_sensors()
    
    def select_channel(self, channel):
        """Select multiplexer channel with error handling"""
        try:
            if 0 <= channel <= 7:
                self.i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
                return True
            else:
                print(f"Invalid channel: {channel} (must be 0-7)")
                return False
        except Exception as e:
            print(f"Error selecting channel {channel}: {e}")
            return False
    
    def initialize_sensors(self):
        """Initialize all VEML7700 sensors with error handling"""
        print("Initializing VEML7700 sensors...")
        successful_channels = []
        
        for ch in CHANNELS:
            try:
                print(f"Attempting to initialize sensor on channel {ch}...")
                if not self.select_channel(ch):
                    continue
                    
                time.sleep(0.2)  # Allow more time for I2C bus to settle
                sensor = VEML7700(self.i2c)
                
                # Test read to verify sensor is working
                test_lux = sensor.lux
                print(f"Sensor on channel {ch} initialized successfully (test reading: {test_lux:.2f} lux)")
                
                successful_channels.append(ch)
                
            except Exception as e:
                print(f"Failed to initialize sensor on channel {ch}: {e}")
                print(f"  This could be due to:")
                print(f"  - Sensor not connected to channel {ch}")
                print(f"  - I2C multiplexer not connected")
                print(f"  - I2C wiring issues")
        
        if successful_channels:
            print(f"Successfully initialized sensors on channels: {successful_channels}")
            self.sensors_ready = len(successful_channels) > 0
        else:
            print("Warning: No sensors were successfully initialized!")
            print("The controller will continue but sensor data will not be available.")
            self.sensors_ready = False
    
    def read_all_sensors(self):
        """Read lux values from all sensors - creates fresh sensor instance per channel"""
        lux_values = []
        try:
            for ch in CHANNELS:
                try:
                    # Select channel and wait for stabilization
                    if not self.select_channel(ch):
                        lux_values.append(0.0)
                        continue
                    
                    time.sleep(0.05)  # Allow channel to stabilize
                    
                    # Create fresh VEML7700 instance for this channel
                    sensor = VEML7700(self.i2c)
                    lux = sensor.lux
                    lux_values.append(lux)
                    
                except Exception as ch_error:
                    print(f"\nError reading channel {ch}: {ch_error}")
                    lux_values.append(0.0)  # Safe fallback for this channel
                    
            return lux_values
        except Exception as e:
            print(f"\nError reading sensors: {e}")
            return [0.0] * len(CHANNELS)  # Return safe values for all channels
    
    def start_monitoring(self):
        """Start sensor monitoring"""
        self.running = True
        print("Lux monitoring STARTED")
    
    def stop_monitoring(self):
        """Stop sensor monitoring"""
        self.running = False
        print("Lux monitoring STOPPED")
    
    def start_logging(self):
        """Start data logging"""
        self.log_data = []
        self.logging_enabled = True
        print("Data logging STARTED")
    
    def stop_logging(self, filename=None):
        """Stop logging and save to CSV"""
        if not self.logging_enabled:
            return
        
        self.logging_enabled = False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lux_data_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'datetime', 'channel_1_lux', 'channel_2_lux', 'channel_3_lux'
                ])
                writer.writeheader()
                writer.writerows(self.log_data)
            print(f"Log saved to: {filename} ({len(self.log_data)} records)")
        except Exception as e:
            print(f"Error saving log: {e}")
    
    def set_intervals(self, display_interval=None, log_interval=None):
        """Set display and logging intervals"""
        if display_interval is not None:
            self.display_interval = display_interval
            print(f"Display interval set to {display_interval}s")
        if log_interval is not None:
            self.log_interval = log_interval
            print(f"Logging interval set to {log_interval}s")

def check_single_key_input():
    """Check for single key press without blocking"""
    try:
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            char = sys.stdin.read(1)
            if char and ord(char) >= 32:  # Printable character
                return char.lower()
            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
    except:
        pass
    return None

def main():
    """Main control loop with interactive commands"""
    print("Controllable VEML7700 Lux Sensor Monitor")
    print("=" * 60)
    
    # Initialize controller
    controller = LuxSensorController()
    
    print("\nSystem ready! (Fixed 10Hz sampling rate)")
    print("Single Key Commands (just press the key, no ENTER needed):")
    print("  s          - Start/Stop monitoring")
    print("  l          - Start logging")
    print("  x          - Stop logging and save")
    print("  r          - Read sensors once")
    print("  i          - Re-initialize sensors")
    print("  q          - Quit")
    print("-" * 60)
    
    # Set terminal to non-blocking mode
    old_settings = None
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
    except:
        print("Warning: Non-blocking input not available")
    
    try:
        last_display_time = 0
        last_log_time = 0
        
        while True:
            current_time = time.time()
            
            # Check for single-key commands
            command = check_single_key_input()
            if command:
                if command == 's':
                    if controller.sensors_ready:
                        if controller.running:
                            controller.stop_monitoring()
                        else:
                            controller.start_monitoring()
                    else:
                        print("\nError: Sensors not ready! Cannot start monitoring.")
                elif command == 'l':
                    if controller.sensors_ready:
                        controller.start_logging()
                    else:
                        print("\nError: Sensors not ready! Cannot start logging.")
                elif command == 'x':
                    controller.stop_logging()
                elif command == 'i':
                    print("\nRe-initializing sensors...")
                    controller.initialize_sensors()
                elif command == 'r':
                    # Single reading
                    if controller.sensors_ready:
                        lux_values = controller.read_all_sensors()
                        timestamp = datetime.now()
                        print(f"\nSingle reading at {timestamp.strftime('%H:%M:%S')}:")
                        for i, lux in enumerate(lux_values):
                            print(f"  Channel {CHANNELS[i]}: {lux:.2f} lux")
                    else:
                        print("\nError: Sensors not ready! Cannot read sensors.")
                elif command == 'q':
                    break
            
            # Read sensors if monitoring is active
            if controller.running:
                # Display readings
                if current_time - last_display_time >= controller.display_interval:
                    lux_values = controller.read_all_sensors()
                    timestamp = datetime.now()
                    
                    # Display status
                    status_parts = []
                    for i, lux in enumerate(lux_values):
                        status_parts.append(f"Ch{CHANNELS[i]}: {lux:6.2f}")
                    
                    sensor_status = " [SENSORS OK]" if controller.sensors_ready else " [SENSORS ERR]"
                    monitor_status = " [MONITORING]" if controller.running else " [STOPPED]"
                    log_status = " [LOGGING]" if controller.logging_enabled else ""
                    
                    status = (
                        f"\r{timestamp.strftime('%H:%M:%S')} | "
                        f"{' | '.join(status_parts)} lux{monitor_status}{sensor_status}{log_status}"
                    )
                    print(status, end='', flush=True)
                    
                    last_display_time = current_time
                
                # Log data if logging is enabled
                if controller.logging_enabled and current_time - last_log_time >= controller.log_interval:
                    lux_values = controller.read_all_sensors()
                    timestamp = datetime.now()
                    
                    log_entry = {
                        'timestamp': current_time,
                        'datetime': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
                        'channel_1_lux': lux_values[0],
                        'channel_2_lux': lux_values[1],
                        'channel_3_lux': lux_values[2]
                    }
                    controller.log_data.append(log_entry)
                    
                    last_log_time = current_time
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        # Restore terminal settings
        if old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass
        
        # Save any remaining log data
        if controller.logging_enabled:
            controller.stop_logging()
        
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
