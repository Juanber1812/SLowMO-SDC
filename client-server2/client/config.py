# config.py

import logging

# === Server Configuration ===
SERVER_URL = "http://192.168.1.146:5000"

# === Resolution Presets ===
RES_PRESETS = [
    ("192x108", (192, 108)),
    ("256x144", (256, 144)),
    ("384x216", (384, 216)),
    ("768x432", (768, 432)),
    ("1024x576", (1024, 576)),
    ("1536x864", (1536, 864)),
]

# === Graph Modes ===
GRAPH_MODES = ["Relative Distance", "Relative Angle", "Angular Position"]

# === Logging Configuration ===
logging.basicConfig(filename='client_log.txt', level=logging.DEBUG)
