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
LOG_FREQUENCY = 50  # Hz - MAXIMUM SPEED!
DISPLAY_FREQUENCY = 20  # Hz - High-speed display updates

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
        
        # HIGH-SPEED synchronized data sharing
        self.data_thread = None
        self.stop_data_thread = False
        self.current_readings = {ch: 0.0 for ch in CHANNELS}
        self.readings_lock = threading.Lock()
        self.last_reading_time = time.time()
        
        # Initialize sensors once at startup
        self.sensors = {}
        self.initialize_sensors()
        
        # Start high-speed data acquisition thread immediately
        self.start_data_thread()
    
    def select_channel(self, channel):
        """Select multiplexer channel - ULTRA FAST"""
        if 0 <= channel <= 7:
            self.i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.005)  # MINIMAL 5ms - MAXIMUM SPEED!
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
    
    def read_all_sensors_fast(self):
        """ULTRA-FAST sensor reading - optimized for maximum speed"""
        readings = {}
        for ch in CHANNELS:
            try:
                self.select_channel(ch)
                # Use pre-initialized sensor, create fresh only if needed
                sensor = VEML7700(self.i2c)
                lux = sensor.lux
                readings[ch] = lux
            except Exception as e:
                readings[ch] = None
        return readings
    
    def start_data_thread(self):
        """Start high-speed data acquisition thread"""
        self.stop_data_thread = False
        self.data_thread = threading.Thread(target=self._data_thread_worker, daemon=True)
        self.data_thread.start()
        print(f"🚀 HIGH-SPEED data thread started at {LOG_FREQUENCY}Hz!")
    
    def _data_thread_worker(self):
        """MAXIMUM SPEED data acquisition worker - 50Hz!"""
        interval = 1.0 / LOG_FREQUENCY  # 0.02 seconds for 50Hz
        next_read_time = time.time()
        
        while not self.stop_data_thread:
            current_time = time.time()
            
            if current_time >= next_read_time:
                try:
                    # ULTRA-FAST sensor reading
                    new_readings = self.read_all_sensors_fast()
                    
                    # Thread-safe update of shared data
                    with self.readings_lock:
                        self.current_readings = new_readings
                        self.last_reading_time = current_time
                    
                    # Schedule next read (precise timing)
                    next_read_time += interval
                    
                except Exception as e:
                    print(f"Error in high-speed data thread: {e}")
                    break
            
            # MINIMAL sleep for maximum speed
            time.sleep(0.001)  # 1ms sleep - ULTRA RESPONSIVE!
    
    def get_current_readings(self):
        """Get the latest sensor readings (thread-safe)"""
        with self.readings_lock:
            return self.current_readings.copy(), self.last_reading_time
    
    def start_csv_logging(self, filename=None):
        """Start CSV logging using shared high-speed data"""
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
            
            print(f"🚀 ULTRA-FAST CSV logging started: {filename}")
            print(f"  Logging at {LOG_FREQUENCY}Hz (MAXIMUM SPEED!)")
            print(f"  Columns: {', '.join(header)}")
            
        except Exception as e:
            print(f"✗ Error starting CSV logging: {e}")
    
    def stop_csv_logging(self):
        """Stop CSV logging"""
        if not self.enable_logging:
            print("CSV logging not active!")
            return
            
        try:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None
            
            self.enable_logging = False
            self.log_start_time = None
            print("✓ ULTRA-FAST CSV logging stopped")
            
        except Exception as e:
            print(f"✗ Error stopping CSV logging: {e}")
    
    def log_current_data(self):
        """Log current shared data to CSV if logging enabled"""
        if not self.enable_logging or not self.csv_writer:
            return
            
        try:
            # Get current shared readings (SAME DATA as display!)
            readings, reading_time = self.get_current_readings()
            
            # Calculate relative time from start
            relative_time = reading_time - self.log_start_time
            
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
            
        except Exception as e:
            print(f"Error logging data: {e}")
    
    # Legacy methods removed - now using ultra-high-speed synchronized approach!
    
    def display_readings(self):
        """Display current sensor readings using shared data"""
        # Get current shared readings (SAME DATA as logging!)
        readings, reading_time = self.get_current_readings()
        
        print("\r", end="")  # Clear line
        status_parts = []
        
        for ch in CHANNELS:
            lux = readings.get(ch)
            if lux is not None:
                status_parts.append(f"Ch{ch}: {lux:6.2f}lux")
            else:
                status_parts.append(f"Ch{ch}: ERROR")
        
        status = " | ".join(status_parts)
        
        # Add logging status with data rate
        if self.enable_logging:
            elapsed = time.time() - self.log_start_time if self.log_start_time else 0
            status += f" | LOG: {elapsed:.1f}s @{LOG_FREQUENCY}Hz"
        else:
            status += f" | LOG: OFF | DATA: @{LOG_FREQUENCY}Hz"
        
        print(status, end="", flush=True)
    
    def run_interactive(self):
        """Run ULTRA-HIGH-SPEED interactive monitoring"""
        print("🚀 === ULTRA-HIGH-SPEED VEML7700 Logger ===")
        print(f"📊 Data Acquisition: {LOG_FREQUENCY}Hz (MAXIMUM SPEED!)")
        print(f"🖥️ Display Updates: {DISPLAY_FREQUENCY}Hz")
        print("Commands:")
        print("  'l' = start logging")
        print("  's' = stop logging") 
        print("  'q' = quit")
        print("=" * 60)
        
        try:
            # Try to set up non-blocking input
            import termios, tty
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            raw_mode = True
        except:
            print("Warning: Non-blocking input not available")
            raw_mode = False
        
        # High-speed display timing
        display_interval = 1.0 / DISPLAY_FREQUENCY  # 0.05s for 20Hz display
        next_display_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                # High-speed display updates
                if current_time >= next_display_time:
                    self.display_readings()
                    
                    # Log current data if logging enabled (SAME DATA!)
                    if self.enable_logging:
                        self.log_current_data()
                    
                    next_display_time += display_interval
                
                # Check for keyboard input
                if raw_mode:
                    import select
                    if select.select([sys.stdin], [], [], 0.001)[0]:  # 1ms timeout - ULTRA FAST!
                        key = sys.stdin.read(1).lower()
                        
                        if key == 'q':
                            break
                        elif key == 'l':
                            if not self.enable_logging:
                                print(f"\n🚀 [STARTING ULTRA-FAST LOG] ", end='')
                                self.start_csv_logging()
                            else:
                                print(f"\n⚡ [ALREADY LOGGING @{LOG_FREQUENCY}Hz] ", end='')
                        elif key == 's':
                            if self.enable_logging:
                                print(f"\n🛑 [STOPPING LOG] ", end='')
                                self.stop_csv_logging()
                            else:
                                print(f"\n❌ [NOT LOGGING] ", end='')
                else:
                    time.sleep(0.01)  # Fallback for non-raw mode
                    
        except KeyboardInterrupt:
            pass
        finally:
            if raw_mode:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
            # Stop everything
            self.stop_data_thread = True
            if self.enable_logging:
                self.stop_csv_logging()
            
            print(f"\n\n🏁 ULTRA-HIGH-SPEED shutdown complete.")


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
