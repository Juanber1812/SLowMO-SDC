import time
from collections import deque
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QMainWindow, QPushButton
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import threading

# Add a shared start time variable
shared_start_time = None

def update_distance_graph(queue, distance_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, distance = 0,0 #calculate_relative_distance(pose_data)
        distance_graph.update_graph(timestamp, distance)

def update_velocity_graph(queue, velocity_graph):
    prev_pose_data = None
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        if prev_pose_data is not None:
            timestamp, velocity = 0,0 #calculate_velocity(pose_data, prev_pose_data)
            velocity_graph.update_graph(timestamp, velocity)
        prev_pose_data = pose_data

def update_angle_graph(queue, angle_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, angle = 0,0 #calculate_relative_angle(pose_data)
        angle_graph.update_graph(timestamp, angle)

def update_angular_position_graph(queue, angular_position_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, angular_position = 0,0 #calculate_angular_position(pose_data)
        angular_position_graph.update_graph(timestamp, angular_position)

def graph_updater(queue, graphing_rate):
    app = QApplication([])
    distance_graph = GraphWindow('Relative Distance', graphing_rate, 'Time', 'Distance (m)', 'blue')
    velocity_graph = GraphWindow('Velocity', graphing_rate, 'Time', 'Velocity (m/s)', 'green')
    angle_graph = GraphWindow('Relative Angle', graphing_rate, 'Time', 'Angle (degrees)', 'red')
    angular_position_graph = GraphWindow('Angular Position', graphing_rate, 'Time', 'Angular Position (degrees)', 'purple')
    distance_graph.show()
    velocity_graph.show()
    angle_graph.show()
    angular_position_graph.show()

    distance_thread = threading.Thread(target=update_distance_graph, args=(queue, distance_graph))
    velocity_thread = threading.Thread(target=update_velocity_graph, args=(queue, velocity_graph))
    angle_thread = threading.Thread(target=update_angle_graph, args=(queue, angle_graph))
    angular_position_thread = threading.Thread(target=update_angular_position_graph, args=(queue, angular_position_graph))

    distance_thread.start()
    velocity_thread.start()
    angle_thread.start()
    angular_position_thread.start()

    app.exec()

    distance_thread.join()
    velocity_thread.join()
    angle_thread.join()
    angular_position_thread.join()

class GraphWindow(QMainWindow):
    def __init__(self, title, graphing_rate, xlabel, ylabel, color):
        super().__init__()
        self.setWindowTitle(title)
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.ax.set_title(title)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True)
        self.setCentralWidget(self.canvas)
        self.data = deque(maxlen=200)
        self.time_data = deque(maxlen=200)
        self.plotting = False
        self.update_interval = graphing_rate  # Update graph every 0.1 seconds
        self.last_update_time = time.time()
        self.color = color

        # Add start/stop button
        self.button = QPushButton('Start', self)
        self.button.clicked.connect(self.toggle_plotting)
        self.button.setGeometry(10, 10, 80, 30)

    def toggle_plotting(self):
        global shared_start_time
        self.plotting = not self.plotting
        self.button.setText('Stop' if self.plotting else 'Start')
        if self.plotting:
            self.clear_data()
            if shared_start_time is None:
                shared_start_time = time.time()
            print(f"Plotting started for {self.windowTitle()}")
        else:
            print(f"Plotting stopped for {self.windowTitle()}")

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
        self.ax.set_title(self.windowTitle())
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel(self.ax.get_ylabel())
        self.ax.grid(True)
        self.ax.plot(self.time_data, self.data, color=self.color, linewidth=1)
        self.canvas.draw()