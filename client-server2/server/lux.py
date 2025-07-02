import time
import datetime
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# Dummy I2C read function (replace with your actual sensor reading logic)
def read_lux_sensor(sensor_id):
    # Replace this with actual I2C read code for your sensors
    # For demo, return a fluctuating value
    import random
    return 100 + 50 * random.random() + 50 * (sensor_id + 1) * (0.5 - random.random())

class LuxTracker:
    def __init__(self, history_len=300):
        self.history_len = history_len
        self.timestamps = deque(maxlen=history_len)
        self.values = [deque(maxlen=history_len) for _ in range(3)]
        self.maxima = [(-float('inf'), None) for _ in range(3)]  # (max_value, timestamp)

    def update(self):
        now = time.time()
        self.timestamps.append(now)
        for i in range(3):
            val = read_lux_sensor(i)
            self.values[i].append(val)
            if val > self.maxima[i][0]:
                self.maxima[i] = (val, now)

    def get_current(self):
        return [v[-1] if v else None for v in self.values]

    def get_maxima(self):
        return self.maxima

lux_tracker = LuxTracker()

def animate(frame):
    lux_tracker.update()
    plt.clf()
    times = [datetime.datetime.fromtimestamp(ts) for ts in lux_tracker.timestamps]
    for i, color in zip(range(3), ['r', 'g', 'b']):
        plt.plot(times, lux_tracker.values[i], color, label=f"Lux {i+1} (now: {lux_tracker.get_current()[i]:.1f})")
        max_val, max_ts = lux_tracker.maxima[i]
        if max_ts:
            plt.scatter([datetime.datetime.fromtimestamp(max_ts)], [max_val], color=color, marker='o', s=80, label=f"Max {i+1}: {max_val:.1f} @ {datetime.datetime.fromtimestamp(max_ts).strftime('%H:%M:%S')}")
    plt.legend(loc='upper left')
    plt.xlabel("Time")
    plt.ylabel("Lux Value")
    plt.title("Live Lux Sensor Readings and Maxima")
    plt.tight_layout()

if __name__ == "__main__":
    fig = plt.figure(figsize=(10, 6))
    anim = animation.FuncAnimation(fig, animate, interval=500, cache_frame_data=False)
    plt.show()