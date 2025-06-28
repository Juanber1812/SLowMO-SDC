import time
import board
import busio
import csv
import os
import sys
import threading
from datetime import datetime
from adafruit_veml7700 import VEML7700

# Constants
MUX_ADDRESS = 0x70  # I2C address of the multiplexer
CHANNELS = [1, 2, 3]  # Channels where VEML7700s are connected
LOG_FREQUENCY = 10  # Hz

class LuxLogger:
    def __init__(self):
        # Setup I2C
        self.i2c = busio.I2C(board.SCL, board.SDA)
        
        # Logging variables
        self.log_file = None
        self.csv_writer = None
        self.enable_logging = False
        self.log_start_time = None
        self.last_log_time = time.time()
        
        # Threading for precise 10Hz logging
        self.logging_thread = None
        self.stop_logging_thread = False
        
        # Initialize sensors once at startup
        self.sensors = {}
        self.initialize_sensors()
    
    def select_channel(self, channel):
        """Select multiplexer channel"""
        if 0 <= channel <= 7:
            self.i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.01)  # Reduced to 10ms - faster I2C settling
        else:
            raise ValueError("Invalid channel: must be 0-7")
    
    def initialize_sensors(self):
        """Initialize all sensors on startup"""
        print("Initializing VEML7700 sensors...")
        for ch in CHANNELS:
            try:
                self.select_channel(ch)
                # Create a fresh sensor instance for each channel
                sensor = VEML7700(self.i2c)
                self.sensors[ch] = sensor
                print(f"✓ Channel {ch} initialized")
            except Exception as e:
                print(f"✗ Channel {ch} failed: {e}")
                self.sensors[ch] = None
        print(f"Initialized {len([s for s in self.sensors.values() if s is not None])}/{len(CHANNELS)} sensors")
    
    def read_sensor(self, channel):
        """Read lux value from a specific channel"""
        if channel not in self.sensors or self.sensors[channel] is None:
            return None
        
        try:
            self.select_channel(channel)
            # Always create a fresh sensor instance for reliable readings
            sensor = VEML7700(self.i2c)
            lux = sensor.lux
            return lux
        except Exception as e:
            print(f"Error reading channel {channel}: {e}")
            return None
    
    def read_all_sensors(self):
        """Read all sensor values"""
        readings = {}
        for ch in CHANNELS:
            lux = self.read_sensor(ch)
            readings[ch] = lux
        return readings
    
    def start_csv_logging(self, filename=None):
        """Start CSV logging of lux data at precise 10Hz using dedicated thread"""
        if self.enable_logging:
            print("CSV logging already active!")
            return
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lux_data_{timestamp}.csv"
        
        try:
            self.log_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.log_file)
            
            # Write header: time, channel1, channel2, channel3
            header = ['time'] + [f'channel_{ch}' for ch in CHANNELS]
            self.csv_writer.writerow(header)
            self.log_file.flush()
            
            # Initialize logging state
            self.enable_logging = True
            self.log_start_time = time.time()
            self.last_log_time = self.log_start_time
            self.stop_logging_thread = False
            
            # Start dedicated logging thread for precise 10Hz timing
            self.logging_thread = threading.Thread(target=self._logging_thread_worker, daemon=True)
            self.logging_thread.start()
            
            print(f"✓ CSV logging started: {filename}")
            print(f"  Logging at {LOG_FREQUENCY}Hz with dedicated thread")
            print(f"  Columns: {', '.join(header)}")
            
        except Exception as e:
            print(f"✗ Error starting CSV logging: {e}")
    
    def stop_csv_logging(self):
        """Stop CSV logging and close file"""
        if not self.enable_logging:
            print("CSV logging not active!")
            return
            
        try:
            # Stop the logging thread
            self.stop_logging_thread = True
            if self.logging_thread and self.logging_thread.is_alive():
                self.logging_thread.join(timeout=1.0)  # Wait up to 1 second
            
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None
            
            self.enable_logging = False
            self.log_start_time = None
            print("✓ CSV logging stopped")
            
        except Exception as e:
            print(f"✗ Error stopping CSV logging: {e}")
    
    def _logging_thread_worker(self):
        """Dedicated thread worker for precise 10Hz logging"""
        interval = 1.0 / LOG_FREQUENCY  # 0.1 seconds for 10Hz
        next_log_time = time.time()
        
        while not self.stop_logging_thread and self.enable_logging:
            current_time = time.time()
            
            if current_time >= next_log_time:
                try:
                    # Read all sensor values
                    readings = self.read_all_sensors()
                    
                    # Calculate relative time from start
                    relative_time = current_time - self.log_start_time
                    
                    # Prepare CSV row: time, channel1, channel2, channel3
                    row = [f"{relative_time:.6f}"]
                    for ch in CHANNELS:
                        lux_value = readings.get(ch)
                        if lux_value is not None:
                            row.append(f"{lux_value:.2f}")
                        else:
                            row.append("ERROR")
                    
                    # Write to CSV
                    if self.csv_writer:
                        self.csv_writer.writerow(row)
                        self.log_file.flush()
                    
                    # Schedule next log time (precise 10Hz timing)
                    next_log_time += interval
                    
                except Exception as e:
                    print(f"Error in logging thread: {e}")
                    break
            
            # Small sleep to prevent busy waiting
            time.sleep(0.01)  # 10ms sleep
    
    def log_data_if_needed(self):
        """Log data to CSV if logging is enabled and enough time has passed"""
        if not self.enable_logging or self.csv_writer is None:
            return
            
        current_time = time.time()
        time_since_last_log = current_time - self.last_log_time
        
        # Check if it's time to log (10Hz = 0.1 second intervals)
        if time_since_last_log >= (1.0 / LOG_FREQUENCY):
            try:
                # Read all sensor values BEFORE calculating timing
                readings = self.read_all_sensors()
                
                # Calculate relative time from start (use current time, not after sensor read)
                relative_time = current_time - self.log_start_time
                
                # Prepare CSV row: time, channel1, channel2, channel3
                row = [f"{relative_time:.6f}"]
                for ch in CHANNELS:
                    lux_value = readings.get(ch)
                    if lux_value is not None:
                        row.append(f"{lux_value:.2f}")
                    else:
                        row.append("ERROR")
                
                # Write to CSV
                self.csv_writer.writerow(row)
                self.log_file.flush()
                
                # Update last log time to maintain consistent 10Hz timing
                self.last_log_time = current_time
                
            except Exception as e:
                print(f"Error logging data: {e}")
    
    def display_readings(self):
        """Display current sensor readings"""
        readings = self.read_all_sensors()
        
        print("\r", end="")  # Clear line
        status_parts = []
        
        for ch in CHANNELS:
            lux = readings.get(ch)
            if lux is not None:
                status_parts.append(f"Ch{ch}: {lux:6.2f}lux")
            else:
                status_parts.append(f"Ch{ch}: ERROR")
        
        status = " | ".join(status_parts)
        
        # Add logging status
        if self.enable_logging:
            elapsed = time.time() - self.log_start_time if self.log_start_time else 0
            status += f" | LOG: {elapsed:.1f}s"
        else:
            status += " | LOG: OFF"
        
        print(status, end="", flush=True)
    
    def run_interactive(self):
        """Run interactive monitoring with keyboard commands"""
        print("=== VEML7700 Lux Sensor Logger ===")
        print("Commands:")
        print("  'l' = start logging")
        print("  's' = stop logging") 
        print("  'q' = quit")
        print("  Any other key = refresh display")
        print("=" * 50)
        
        try:
            # Try to set up non-blocking input
            import termios, tty
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            raw_mode = True
        except:
            print("Warning: Non-blocking input not available")
            raw_mode = False
        
        try:
            while True:
                # Display current readings
                self.display_readings()
                
                # Note: Logging is now handled by dedicated thread for precise 10Hz
                
                # Check for keyboard input
                if raw_mode:
                    import select
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1).lower()
                        
                        if key == 'q':
                            break
                        elif key == 'l':
                            if not self.enable_logging:
                                print(f"\n[STARTING LOG] ", end='')
                                self.start_csv_logging()
                            else:
                                print(f"\n[ALREADY LOGGING] ", end='')
                        elif key == 's':
                            if self.enable_logging:
                                print(f"\n[STOPPING LOG] ", end='')
                                self.stop_csv_logging()
                            else:
                                print(f"\n[NOT LOGGING] ", end='')
                else:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            pass
        finally:
            if raw_mode:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
            # Stop logging if active
            if self.enable_logging:
                self.stop_csv_logging()
            
            print(f"\n\nShutdown complete.")


# Simple function-based interface (for backward compatibility)
def select_channel(channel):
    if 0 <= channel <= 7:
        i2c = busio.I2C(board.SCL, board.SDA)
        i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
        time.sleep(0.05)
    else:
        raise ValueError("Invalid channel: must be 0-7")


def main():
    """Main function - choose between simple display or interactive logging"""
    if len(sys.argv) > 1 and sys.argv[1] == '--simple':
        # Simple display mode (original behavior)
        simple_display()
    else:
        # Interactive logging mode
        logger = LuxLogger()
        logger.run_interactive()


def simple_display():
    """Simple display mode (original behavior)"""
    # Setup I2C
    i2c = busio.I2C(board.SCL, board.SDA)
    
    # Initialize sensors
    sensors = []
    for ch in CHANNELS:
        select_channel(ch)
        time.sleep(0.1)  # allow I2C bus to settle
        sensor = VEML7700(i2c)
        sensors.append(sensor)

    # Read loop
    print("Reading lux values from channels (simple mode):")
    try:
        while True:
            for idx, ch in enumerate(CHANNELS):
                select_channel(ch)
                time.sleep(0.05)
                lux = sensors[idx].lux
                print(f"Channel {ch}: {lux:.2f} lux")
            print("-" * 30)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
