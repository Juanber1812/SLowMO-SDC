# Simulated Lux Sensor Live Plot with Peak Detection (custom range, random peaks, unique for each channel)
import time
import numpy as np
from collections import deque
import matplotlib.pyplot as plt

LUX_CHANNELS = [1, 2, 3]
SIM_FREQ = [0.18, 0.23, 0.27]
SAMPLE_RATE = 25
HISTORY_LEN = 100

class SimulatedLuxSensorManager:
    def __init__(self):
        self.history = {ch: deque(maxlen=HISTORY_LEN) for ch in LUX_CHANNELS}
        self.last_maxima = {ch: None for ch in LUX_CHANNELS}
        self.detected_maxima = []
        self.start_time = time.time()
        self.phase = {1: 0, 2: np.pi/3, 3: 2*np.pi/3}
        self.peak_locs = {ch: np.random.uniform(5, 20) for ch in LUX_CHANNELS}
        self.peak_heights = {ch: np.random.uniform(800, 1200) for ch in LUX_CHANNELS}

    def read_lux_sensors(self):
        now = time.time() - self.start_time
        lux_data = {}
        for idx, ch in enumerate(LUX_CHANNELS):
            # Base signal: random low frequency, random phase, less noise
            base = 200 + 150 * np.abs(np.sin(2 * np.pi * SIM_FREQ[idx] * now + self.phase[ch]))**2.5
            # Add a sharp random peak at a random time (simulate a "flash" event)
            peak = 0
            peak_time = self.peak_locs[ch]
            peak_height = self.peak_heights[ch]
            peak += peak_height * np.exp(-((now - peak_time) ** 2) / (2 * 0.5 ** 2))
            # Add less random noise
            noise = np.random.normal(0, 5)
            # Clamp to [50, 1200]
            value = np.clip(base + peak + noise, 50, 1200)
            lux_data[ch] = value
            self.history[ch].append((now, value))
        return lux_data

    def analyse_peaks_gradient(self, window_size=30, min_time_between_peaks=0.2):
        for ch in LUX_CHANNELS:
            data = list(self.history[ch])
            if len(data) < window_size + 1:
                continue
            gradients = []
            times = []
            for i in range(len(data) - window_size):
                window = data[i:i+window_size]
                t_vals = np.array([t for t, v in window])
                v_vals = np.array([v for t, v in window])
                A = np.vstack([t_vals, np.ones(len(t_vals))]).T
                m, c = np.linalg.lstsq(A, v_vals, rcond=None)[0]
                gradients.append(m)
                times.append(t_vals[-1])
            for i in range(1, len(gradients)):
                # Only detect high peaks (not troughs): gradient must go from positive to negative
                if gradients[i-1] > 0 and gradients[i] <= 0:
                    t1, t2 = times[i-1], times[i]
                    g1, g2 = gradients[i-1], gradients[i]
                    if g2 - g1 != 0:
                        t_peak = t1 + (0 - g1) * (t2 - t1) / (g2 - g1)
                    else:
                        t_peak = t2
                    v_peak = [v for t, v in data if abs(t - t_peak) == min([abs(t - t_peak) for t, v in data])][0]
                    last_max = self.last_maxima[ch]
                    if last_max is None or (t_peak - last_max[0]) > min_time_between_peaks:
                        self.last_maxima[ch] = (t_peak, v_peak)
                        self.detected_maxima.append((t_peak, ch, v_peak))
                        print(f"\n[PEAK-GRAD] {time.strftime('%H:%M:%S', time.localtime(self.start_time + t_peak))} | Channel: {ch} | Value: {v_peak:.2f}")

if __name__ == "__main__":
    manager = SimulatedLuxSensorManager()
    plt.ion()
    fig, ax = plt.subplots()
    lines = {ch: ax.plot([], [], label=f"Lux{ch}")[0] for ch in LUX_CHANNELS}
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Lux Value")
    ax.set_ylim(0, 1250)
    ax.legend()
    plt.title("Simulated Lux Sensor Data (Live)")

    try:
        while True:
            manager.read_lux_sensors()
            manager.analyse_peaks_gradient(window_size=30, min_time_between_peaks=0.2)
            for ch in LUX_CHANNELS:
                t_vals = [t for t, v in manager.history[ch]]
                v_vals = [v for t, v in manager.history[ch]]
                lines[ch].set_data(t_vals, v_vals)
            ax.relim()
            ax.autoscale_view(scalex=True, scaley=False)
            plt.pause(1.0 / SAMPLE_RATE)
    except KeyboardInterrupt:
        print("\nExiting simulated lux sensor live display.")