import time
import datetime
from collections import deque

from dash import Dash, dcc, html, Output, Input
import plotly.graph_objs as go

import smbus2

# Multiplexer and sensor settings
MUX_ADDR = 0x70  # TCA9548A default address
MUX_CHANNELS = [1, 2, 3]  # Channels for your sensors (1-indexed)
SENSOR_ADDR = 0x23  # BH1750 default address
I2C_BUS = 1  # Usually 1 on Raspberry Pi

bus = smbus2.SMBus(I2C_BUS)

def select_mux_channel(channel):
    """Select a channel on the TCA9548A multiplexer."""
    if 1 <= channel <= 8:
        bus.write_byte(MUX_ADDR, 1 << (channel - 1))
        time.sleep(0.002)  # Small delay for channel switching

def read_bh1750():
    """Read lux value from BH1750 sensor."""
    try:
        bus.write_byte(SENSOR_ADDR, 0x10)  # 0x10 = Continuously H-Resolution Mode
        time.sleep(0.18)  # Wait for measurement
        data = bus.read_i2c_block_data(SENSOR_ADDR, 0x00, 2)
        lux = ((data[0] << 8) | data[1]) / 1.2
        return lux
    except Exception as e:
        print(f"Error reading BH1750: {e}")
        return 0.0

def read_lux_sensor(sensor_id):
    """Read from the correct channel and return the lux value."""
    select_mux_channel(MUX_CHANNELS[sensor_id])
    return read_bh1750()

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

tracker = LuxTracker()

app = Dash(__name__)
app.layout = html.Div([
    html.H2("Live Lux Sensor Readings and Maxima"),
    dcc.Graph(id='lux-graph'),
    dcc.Interval(id='interval', interval=500, n_intervals=0)
])

@app.callback(
    Output('lux-graph', 'figure'),
    Input('interval', 'n_intervals')
)
def update_graph(n):
    tracker.update()
    times = [datetime.datetime.fromtimestamp(ts) for ts in tracker.timestamps]
    if not times:
        return go.Figure()
    t0 = times[0]
    x = [(t-t0).total_seconds() for t in times]
    colors = ['red', 'green', 'blue']
    data = []
    for i in range(3):
        y = list(tracker.values[i])
        data.append(go.Scatter(
            x=x, y=y, mode='lines', name=f"Lux {i+1} (now: {y[-1]:.1f})", line=dict(color=colors[i])
        ))
        max_val, max_ts = tracker.maxima[i]
        if max_ts:
            max_x = (datetime.datetime.fromtimestamp(max_ts)-t0).total_seconds()
            data.append(go.Scatter(
                x=[max_x], y=[max_val], mode='markers+text', marker=dict(color=colors[i], size=12),
                text=[f"max {max_val:.1f}"], textposition="top center", name=f"Max {i+1}"
            ))
    fig = go.Figure(data=data)
    fig.update_layout(
        xaxis_title="Time (s)",
        yaxis_title="Lux Value",
        legend_title="Sensor",
        margin=dict(l=40, r=20, t=40, b=40)
    )
    return fig

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)