# Save as plot_lux.py in the same folder as your CSV

import os
import pandas as pd
import matplotlib.pyplot as plt
import time
from collections import deque

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, 'lux_log.csv')

# Load data
df = pd.read_csv(csv_path)

# Convert timestamp to relative time (seconds since start)
df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

# Calculate sample interval (average)
intervals = df['time'].diff().dropna()
sample_interval = intervals.mean() if not intervals.empty else 0.05

# Set up plot
plt.ion()
fig, ax = plt.subplots(figsize=(12, 6))
lines = []
for ch in [1, 2, 3]:
    line, = ax.plot([], [], label=f'Channel {ch}')
    lines.append(line)
peak_lines = []

ax.set_xlabel('Time (s)')
ax.set_ylabel('Lux')
ax.set_title('Simulated Live Lux Sensor Data')
ax.legend()
ax.set_xlim(0, df['time'].iloc[-1])
ax.set_ylim(df[[f'ch{ch}' for ch in [1,2,3]]].min().min() * 0.9, df[[f'ch{ch}' for ch in [1,2,3]]].max().max() * 1.1)

# Prepare rolling windows for peak detection for each channel
peak_dots = [ [] for _ in range(3) ]  # Store scatter plot handles for each channel
windows = [deque(maxlen=3) for _ in range(3)]

# Simulate live plotting
for i in range(1, len(df)+1):
    for ch, line in enumerate(lines, 1):
        line.set_data(df['time'][:i], df[f'ch{ch}'][:i])
        # Update rolling window
        windows[ch-1].append((df['time'].iloc[i-1], df[f'ch{ch}'].iloc[i-1]))
        # Detect peak in the window
        if len(windows[ch-1]) == 3:
            t_prev, v_prev = windows[ch-1][0]
            t_curr, v_curr = windows[ch-1][1]
            t_next, v_next = windows[ch-1][2]
            if (v_curr - v_prev) > 0 and (v_next - v_curr) < 0:
                # Plot a dot at the peak
                dot = ax.plot(t_curr, v_curr, 'o', color=line.get_color(), markersize=8, label=f'Peak Ch{ch}' if i==3 else "")
                peak_dots[ch-1].append(dot)
    # Remove old peak lines
    for pl in peak_lines:
        pl.remove()
    peak_lines = []
    # Draw vertical lines for peaks up to this point (from CSV, optional)
    peaks = df.iloc[:i][df['peak'] != 0]
    for t in peaks['time']:
        pl = ax.axvline(x=t, color='red', linestyle='--', alpha=0.7)
        peak_lines.append(pl)
    ax.relim()
    ax.autoscale_view()
    plt.pause(sample_interval)  # Simulate real-time update

plt.ioff()
plt.show()

def detect_peaks_simple(data_stream):
    """
    Detects peaks by looking for a sign change in the difference (from + to -).
    Yields (timestamp, value) at each detected peak.
    data_stream: iterable of (timestamp, value)
    """
    prev = None
    curr = None
    for next_point in data_stream:
        if curr is not None and prev is not None:
            t_prev, v_prev = prev
            t_curr, v_curr = curr
            t_next, v_next = next_point
            # Detect peak: rising then falling
            if (v_curr - v_prev) > 0 and (v_next - v_curr) < 0:
                yield (t_curr, v_curr)
        prev = curr
        curr = next_point