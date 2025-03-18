import calculate_graph_data

import time
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QPushButton
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

shared_start_time = None # Add a shared start time variable

class GraphUpdaterThread(QThread):
    new_data = pyqtSignal(float, float)  # Signal for updating the graph

    def __init__(self, queue, update_func, graph_widget):
        super().__init__()
        self.queue = queue
        self.update_func = update_func
        self.graph_widget = graph_widget
        self.running = True
        self.prev_pose_data = None

    def run(self):
        while self.running:
            try:
                pose_data = self.queue.get_nowait()  # Non-blocking queue read
                if pose_data is not None:
                    if self.update_func == calculate_graph_data.calculate_velocity:
                        if self.prev_pose_data is not None:
                            timestamp, value = self.update_func(pose_data, self.prev_pose_data)
                        self.prev_pose_data = pose_data # Update previous pose_data for next iteration
                    else:
                        timestamp, value = self.update_func(pose_data)
                    self.new_data.emit(timestamp, value)  # Send signal to GUI
                    
            except:
                pass  # No new data, continue loop
            time.sleep(0.1)  # Prevent CPU overload

    def stop(self):
        self.running = False



class GraphWidget(QWidget):
    def __init__(self, title, graphing_rate, xlabel, ylabel, color):
        super().__init__()

        # Setup matplotlib figure
        self.title = title
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.ax.set_title(self.title)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True)

        # Layout to contain the graph and button
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)

        # Add start/stop button
        self.button = QPushButton('Start')
        self.button.clicked.connect(self.toggle_plotting)
        self.button.setGeometry(10, 10, 80, 30)
        layout.addWidget(self.button)

        self.setLayout(layout)

        # Graph data
        self.data = deque(maxlen=50)
        self.time_data = deque(maxlen=50)
        self.plotting = False
        self.update_interval = graphing_rate  # Update graph every 0.1 seconds
        self.last_update_time = time.time()
        self.color = color

    def toggle_plotting(self):
        global shared_start_time
        self.plotting = not self.plotting
        self.button.setText('Stop' if self.plotting else 'Start')
        if self.plotting:
            self.clear_data()
            if shared_start_time is None:
                shared_start_time = time.time()
            print(f"Plotting started for {self.title}")
        else:
            print(f"Plotting stopped for {self.title}")

    def clear_data(self):
        self.data.clear()
        self.time_data.clear()

    def update_graph(self, timestamp, value):
        if not self.plotting:
            return

        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return

        self.last_update_time = current_time

        elapsed_time = timestamp - shared_start_time
        self.time_data.append(elapsed_time)
        self.data.append(value)
        self.ax.clear()
        self.ax.set_title(self.title)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel(self.ax.get_ylabel())
        self.ax.grid(True)
        self.ax.plot(self.time_data, self.data, color=self.color, linewidth=1)
        self.canvas.draw()