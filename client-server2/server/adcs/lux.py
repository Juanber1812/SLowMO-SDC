import time

# Try to import hardware libraries
try:
    import board
    import busio
    from adafruit_veml7700 import VEML7700
    LUX_AVAILABLE = True
except ImportError:
    print("Warning: VEML7700 library not available — lux sensors disabled")
    LUX_AVAILABLE = False

# Constants
MUX_ADDRESS = 0x70
LUX_CHANNELS = [1, 2, 3]

class LuxSensorManager:
    """Manages VEML7700 lux sensors using an I²C multiplexer."""

    def __init__(self):
        self.lux_i2c = None
        self.lux_sensors = {}
        self.sensors_ready = False

        if LUX_AVAILABLE:
            self.initialize_lux_sensors()

    def initialize_lux_sensors(self):
        """Initialize VEML7700 lux sensors across defined channels."""
        try:
            self.lux_i2c = busio.I2C(board.SCL, board.SDA)
            print("🔧 Initializing VEML7700 lux sensors...")

            for ch in LUX_CHANNELS:
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    sensor = VEML7700(self.lux_i2c)
                    _ = sensor.lux  # Trigger test read
                    self.lux_sensors[ch] = sensor
                    print(f"✓ Lux channel {ch} initialized")
                except Exception as e:
                    print(f"✗ Lux channel {ch} failed: {e}")
                    self.lux_sensors[ch] = None

            active = sum(1 for s in self.lux_sensors.values() if s is not None)
            self.sensors_ready = active > 0
            print(f"✓ {active}/{len(LUX_CHANNELS)} lux sensors ready")

        except Exception as e:
            print(f"✗ Lux sensor initialization failed: {e}")
            self.sensors_ready = False

    def select_lux_channel(self, channel):
        """Select a specific TCA9548A I²C multiplexer channel."""
        if 0 <= channel <= 7 and self.lux_i2c:
            self.lux_i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.002)

    def read_lux_sensors(self):
        """Read lux values from all available channels."""
        lux_data = {ch: 0.0 for ch in LUX_CHANNELS}

        if not self.sensors_ready:
            return lux_data

        for ch in LUX_CHANNELS:
            try:
                if ch in self.lux_sensors and self.lux_sensors[ch]:
                    self.select_lux_channel(ch)
                    lux_data[ch] = self.lux_sensors[ch].lux
                else:
                    lux_data[ch] = 0.0
            except Exception:
                # Try to reinitialize failed sensor once
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    self.lux_sensors[ch] = VEML7700(self.lux_i2c)
                    lux_data[ch] = self.lux_sensors[ch].lux
                except:
                    lux_data[ch] = 0.0
                    self.lux_sensors[ch] = None

        return lux_data
