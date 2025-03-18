import data_handler
import calculate_graph_data
from graphs import GraphWidget, GraphUpdaterThread

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QMainWindow, QPushButton, QWidget, QGridLayout, QVBoxLayout
import cv2

class MainWindow(QMainWindow):
    def __init__(self, updateFreq, graphing_rate):
        super().__init__()
        self.queue = data_handler.queue
        self.setWindowTitle("Camera Feed")
        self.setGeometry(100, 100, 750, 530) # Set window size

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (2x1 grid)
        main_layout = QGridLayout()

        # ** Left Side: Image Label, FPS Label, Flip Button, Invert Button **
        left_layout = QVBoxLayout()

        self.image_label = QLabel(self)
        self.image_label.setFixedSize(620, 460)  # Fix size

        self.fps_label = QLabel("FPS: -1", self)
        self.fps_label.setStyleSheet("color: white;")

        self.sensor_text = QLabel('Temperature: -1\nHumidity: -1', self)
        self.sensor_text.setGeometry(640, 480, 140, 40)
        
        self.flip_button = QPushButton('Flip', self) # Create a "Flip" button
        self.flip_button.setGeometry(150, 480, 140, 40)
        self.flip_button.clicked.connect(self.flip_video)  # Connect to the flip function on click

        self.invert_button = QPushButton('Invert', self) # Create an "Invert" button
        self.invert_button.setGeometry(350, 480, 140, 40)
        self.invert_button.clicked.connect(self.invert_video)  # Connect to the invert function on click
        

        left_layout.addWidget(self.image_label)
        left_layout.addWidget(self.fps_label)
        left_layout.addWidget(self.sensor_text)
        left_layout.addWidget(self.invert_button)
        left_layout.addWidget(self.flip_button)

        # ** Right Side: 2x2 Grid for Graphs **
        self.graph_grid = QGridLayout()
        self.distance_graph = GraphWidget('Relative Distance', graphing_rate, 'Time', 'Distance (m)', 'blue')
        self.velocity_graph = GraphWidget('Velocity', graphing_rate, 'Time', 'Velocity (m/s)', 'green')
        self.angle_graph = GraphWidget('Relative Angle', graphing_rate, 'Time', 'Angle (degrees)', 'red')
        self.angular_position_graph = GraphWidget('Angular Position', graphing_rate, 'Time', 'Angular Position (degrees)', 'purple')

        # ** Start Graph Threads **
        self.distance_thread = GraphUpdaterThread(self.queue, calculate_graph_data.calculate_relative_distance, self.distance_graph)
        self.velocity_thread = GraphUpdaterThread(self.queue, calculate_graph_data.calculate_velocity, self.velocity_graph)
        self.angle_thread = GraphUpdaterThread(self.queue, calculate_graph_data.calculate_relative_angle, self.angle_graph)
        self.angular_position_thread = GraphUpdaterThread(self.queue, calculate_graph_data.calculate_angular_position, self.angular_position_graph)

        self.distance_thread.new_data.connect(self.distance_graph.update_graph)
        self.velocity_thread.new_data.connect(self.velocity_graph.update_graph)
        self.angle_thread.new_data.connect(self.angle_graph.update_graph)
        self.angular_position_thread.new_data.connect(self.angular_position_graph.update_graph)

        self.distance_thread.start()
        self.velocity_thread.start()
        self.angle_thread.start()
        self.angular_position_thread.start()

        self.graph_grid.addWidget(self.distance_graph, 0, 0)
        self.graph_grid.addWidget(self.velocity_graph, 0, 1)
        self.graph_grid.addWidget(self.angle_graph, 1, 0)
        self.graph_grid.addWidget(self.angular_position_graph, 1, 1)

        # Add the 2x2 grid layout to the right side of the main layout
        main_layout.addLayout(left_layout, 0, 0, 2, 1)  # Span 2 rows, 1 column
        main_layout.addLayout(self.graph_grid, 0, 1, 2, 1)  # Span 2 rows, 1 column

        # Set the layout for the central widget
        central_widget.setLayout(main_layout)

        self.showMaximized()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.request_data)  # Request data and update graphs
        self.timer.start(updateFreq)  # Update every time_interval ms

    def request_data(self): # Request a new frame from the server
        data_handler.sio.emit('request_data')  # Send request to the server for a new frame

    def update_data(self):
        self.update_frame()  # Update frame
        self.update_fps_data()   # Update fps data
        self.update_sensor_data()   # Update sensor data

    def update_frame(self):
        if data_handler.frame is not None:
            # Convert the frame to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(data_handler.frame, cv2.COLOR_BGR2RGB)

            # Create QImage from the frame
            height, width, channels = rgb_frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(rgb_frame.data, width, height, width * channels, QImage.Format.Format_RGB888)

            # Display the image in the QLabel
            self.image_label.setPixmap(QPixmap.fromImage(q_img))

    def update_fps_data(self):
        if data_handler.fps is not None:
            self.fps_label.setText(f"FPS: {data_handler.fps:.2f}")

    def update_sensor_data(self):
        if data_handler.sensor is not None:
            self.sensor_text.setText('Temperature: {temperature}\nHumidity: {humidity}'.format(**data_handler.sensor))

    def flip_video(self): # Send signal to server to toggle the flip state.
        print(f"Client: Image is flipped")
        data_handler.sio.emit('flip')

    def invert_video(self): # Send signal to server to toggle the invert state.
        print(f"Client: Image is inverted")
        data_handler.sio.emit('invert')

    def closeEvent(self, event): # Ensure all threads are stopped before close
        self.distance_thread.stop()
        self.velocity_thread.stop()
        self.angle_thread.stop()
        self.angular_position_thread.stop()
        print("Graph threads terminated")
        event.accept()