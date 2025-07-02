# Save as plot_lux.py in the same folder as your CSV

import os
import pandas as pd
import matplotlib.pyplot as plt

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, 'lux_log.csv')

# Load data
df = pd.read_csv(csv_path)

# Convert timestamp to relative time (seconds since start)
df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

# Metric analysis
num_samples = len(df)
duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
collection_rate = num_samples / duration if duration > 0 else float('nan')
num_peaks = df['peak'].sum()

print(f"Total samples: {num_samples}")
print(f"Total duration: {duration:.2f} seconds")
print(f"Data collection rate: {collection_rate:.2f} Hz")
print(f"Number of detected peaks: {int(num_peaks)}")

# Plot each channel
plt.figure(figsize=(12, 6))
for ch in [1, 2, 3]:
    plt.plot(df['time'], df[f'ch{ch}'], label=f'Channel {ch}')

# Plot vertical lines for peaks
for t in df[df['peak'] == 1]['time']:
    plt.axvline(x=t, color='red', linestyle='--', alpha=0.7)

plt.xlabel('Time (s)')
plt.ylabel('Lux')
plt.title('Lux Sensor Data with Peaks')
plt.legend()
plt.tight_layout()
plt.show()