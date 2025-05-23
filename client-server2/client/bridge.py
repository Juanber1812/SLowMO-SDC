# bridge.py

from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np

class Bridge(QObject):
    frame_received = pyqtSignal(np.ndarray)
    analysed_frame = pyqtSignal(np.ndarray)

    update_system_info = pyqtSignal(float, float)  # temp, cpu
    update_camera_status = pyqtSignal(str)         # camera status string

bridge = Bridge()
