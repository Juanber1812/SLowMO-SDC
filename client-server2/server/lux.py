import time
from collections import deque
import numpy as np

# Hardware/library imports
try:
    import board
    import busio
    from adafruit_veml7700 import VEML7700
    LUX_AVAILABLE = True
except ImportError:
    print("Warning: VEML7700 or board/busio not available - lux sensors disabled")
    LUX_AVAILABLE = False

# Constants
MUX_ADDRESS = 0x70
LUX_CHANNELS = [1, 2, 3]

class LuxSensorManager:
    """Manages VEML7700 lux sensors with multiplexer"""
    
    def __init__(self):
        self.lux_i2c = None
        self.lux_sensors = {}
        self.sensors_ready = False
        self.history = {ch: deque(maxlen=500) for ch in LUX_CHANNELS}  # Store (timestamp, value)
        self.last_maxima = {ch: None for ch in LUX_CHANNELS}
        self.detected_maxima = []  # List of (timestamp, channel, value)
        if LUX_AVAILABLE:
            self.initialize_lux_sensors()
    
    def initialize_lux_sensors(self):
        """Initialize VEML7700 lux sensors"""
        try:
            self.lux_i2c = busio.I2C(board.SCL, board.SDA)
            self.lux_sensors = {}
            
            print("🔧 Initializing VEML7700 lux sensors...")
            for ch in LUX_CHANNELS:
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    sensor = VEML7700(self.lux_i2c)
                    # Test sensor
                    test_read = sensor.lux
                    self.lux_sensors[ch] = sensor
                    print(f"✓ Lux channel {ch} initialized (test: {test_read:.1f} lux)")
                except Exception as e:
                    print(f"✗ Lux channel {ch} failed: {e}")
                    self.lux_sensors[ch] = None
            
            active_sensors = len([s for s in self.lux_sensors.values() if s is not None])
            print(f"✓ {active_sensors}/{len(LUX_CHANNELS)} lux sensors ready")
            self.sensors_ready = active_sensors > 0
            
        except Exception as e:
            print(f"✗ Lux sensor initialization failed: {e}")
            self.sensors_ready = False
    
    def select_lux_channel(self, channel):
        """Select multiplexer channel for lux sensors"""
        if 0 <= channel <= 7 and self.lux_i2c:
            self.lux_i2c.writeto(MUX_ADDRESS, bytes([1 << channel]))
            time.sleep(0.002)
    
    def read_lux_sensors(self):
        """Read all lux sensors and record timestamped values"""
        lux_data = {ch: 0.0 for ch in LUX_CHANNELS}
        now = time.time()
        if not self.sensors_ready:
            return lux_data

        for ch in LUX_CHANNELS:
            try:
                if ch in self.lux_sensors and self.lux_sensors[ch] is not None:
                    self.select_lux_channel(ch)
                    value = self.lux_sensors[ch].lux
                    lux_data[ch] = value
                else:
                    value = 0.0
                    lux_data[ch] = 0.0
            except Exception as e:
                try:
                    self.select_lux_channel(ch)
                    time.sleep(0.01)
                    self.lux_sensors[ch] = VEML7700(self.lux_i2c)
                    value = self.lux_sensors[ch].lux
                    lux_data[ch] = value
                except:
                    value = 0.0
                    lux_data[ch] = 0.0
                    self.lux_sensors[ch] = None
            # Store (timestamp, value) for analysis
            self.history[ch].append((now, value))
        return lux_data

    def analyse_and_log_maxima(self, min_distance=10, threshold=5.0):
        """
        Analyse each lux sensor stream for maxima (peaks).
        Only log a peak if it's a true local maximum and separated by min_distance samples.
        threshold: minimum difference from neighbors to be considered a peak.
        """
        for ch in LUX_CHANNELS:
            data = list(self.history[ch])
            if len(data) < 3:
                continue  # Not enough data for peak detection
            # Only check the latest point
            t_prev, v_prev = data[-3]
            t_curr, v_curr = data[-2]
            t_next, v_next = data[-1]
            # Check for local maximum
            if v_curr > v_prev and v_curr > v_next and (v_curr - v_prev) > threshold and (v_curr - v_next) > threshold:
                # Check min_distance from last maxima
                last_max = self.last_maxima[ch]
                if last_max is None or (data[-2][0] - last_max[0]) > min_distance * 0.01:  # 0.01s per sample
                    self.last_maxima[ch] = data[-2]
                    self.detected_maxima.append((t_curr, ch, v_curr))
                    # Print log with timestamp and channel
                    print(f"\n[PEAK LOG] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_curr))} | Channel: {ch} | Value: {v_curr:.2f}")

    def analyse_peaks_gradient(self, threshold=10.0, min_time_between_peaks=0.2):
        """
        Simple peak detection: look for sign flip in difference and apply threshold.
        """
        for ch in LUX_CHANNELS:
            data = list(self.history[ch])
            if len(data) < 3:
                continue

            for i in range(1, len(data) - 1):
                t_prev, v_prev = data[i - 1]
                t_curr, v_curr = data[i]
                t_next, v_next = data[i + 1]

                # Sign flip: up then down
                if (v_curr - v_prev) > 0 and (v_next - v_curr) < 0:
                    # Threshold: value must drop by at least threshold after peak
                    if (v_curr - v_next) >= threshold:
                        last_max = self.last_maxima[ch]
                        if last_max is None or (t_curr - last_max[0]) > min_time_between_peaks:
                            self.last_maxima[ch] = (t_curr, v_curr)
                            self.detected_maxima.append((t_curr, ch, v_curr))
                            print(f"\n[PEAK-SIMPLE] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_curr))} | Channel: {ch} | Value: {v_curr:.2f}")

def print_hello():
    print("Hello")

if __name__ == "__main__":
    print_hello()  # Call the hello function
    manager = LuxSensorManager()
    try:
        while True:
            readings = manager.read_lux_sensors()
            print_hello()  # Call the hello function

            manager.analyse_and_log_maxima(min_distance=10, threshold=5.0)
            lux_str = " | ".join([f"Lux{ch}: {readings[ch]:7.2f}" for ch in LUX_CHANNELS])
            print(f"\r{lux_str}  {time.strftime('%H:%M:%S')}", end="", flush=True)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting lux sensor live display.")