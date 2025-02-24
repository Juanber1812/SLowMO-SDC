import cv2
import numpy as np
import pyapriltags
import time
from collections import deque
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QMainWindow, QPushButton
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from multiprocessing import Process, Queue
import threading
from scipy.spatial.transform import Rotation as R

# Load the calibration data
calibration_data = np.load('calibration_data.npz')
mtx = calibration_data['mtx']
dist = calibration_data['dist']

# Capture the video from camera
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
if not video_capture.isOpened():
    print(f"Error: Could not open video capture on camera index 0. Please check your camera connection.")
    exit()

#line color
line_color = (0, 255, 0)
#set time interval bewteen frames and graph update rate
time_interval = 10 #milliseconds
graphing_rate = 0.01 #seconds

# Create an AprilTag detector
detector = pyapriltags.Detector(families='tag25h9',
                                nthreads=4,
                                quad_decimate=1.0,  # Adjust this value based on your performance and accuracy requirements
                                quad_sigma=0.0,
                                refine_edges=1,
                                decode_sharpening=0.25)

# Set tag size in meters
tag_size = 0.055

# Define the 3D points of the AprilTag corners in the real world
object_points = np.array([
    [-tag_size / 2, -tag_size / 2, 0],
    [tag_size / 2, -tag_size / 2, 0],
    [tag_size / 2, tag_size / 2, 0],
    [-tag_size / 2, tag_size / 2, 0]
], dtype=np.float32)

def process_pose_data(pose_data):
    rvec, tvec, timestamp = pose_data
    rotation_matrix, _ = cv2.Rodrigues(rvec)

def calculate_relative_distance(pose_data):
    rvec, tvec, timestamp = pose_data
    distance = np.linalg.norm(tvec)
    return timestamp, distance

def calculate_velocity(pose_data, prev_pose_data):
    timestamp, distance = calculate_relative_distance(pose_data)
    prev_timestamp, prev_distance = calculate_relative_distance(prev_pose_data)
    velocity = (distance - prev_distance) / (timestamp - prev_timestamp)
    return timestamp, velocity

def calculate_relative_angle(pose_data):
    rvec, tvec, timestamp = pose_data
    angle = np.arctan2(tvec[0], tvec[2])
    return timestamp, np.degrees(angle)

def calculate_angular_position(pose_data):
    rvec, tvec, timestamp = pose_data
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    r = R.from_matrix(rotation_matrix)
    euler_angles = r.as_euler('xyz', degrees=True)
    angular_position = euler_angles[1]  # Yaw angle
    return timestamp, angular_position

# Add a shared start time variable
shared_start_time = None

class GraphWindow(QMainWindow):
    def __init__(self, title, xlabel, ylabel, color):
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

def update_distance_graph(queue, distance_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, distance = calculate_relative_distance(pose_data)
        distance_graph.update_graph(timestamp, distance)

def update_velocity_graph(queue, velocity_graph):
    prev_pose_data = None
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        if prev_pose_data is not None:
            timestamp, velocity = calculate_velocity(pose_data, prev_pose_data)
            velocity_graph.update_graph(timestamp, velocity)
        prev_pose_data = pose_data

def update_angle_graph(queue, angle_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, angle = calculate_relative_angle(pose_data)
        angle_graph.update_graph(timestamp, angle)

def update_angular_position_graph(queue, angular_position_graph):
    while True:
        pose_data = queue.get()
        if pose_data is None:
            break
        timestamp, angular_position = calculate_angular_position(pose_data)
        angular_position_graph.update_graph(timestamp, angular_position)

def graph_updater(queue):
    app = QApplication([])
    distance_graph = GraphWindow('Relative Distance', 'Time', 'Distance (m)', 'blue')
    velocity_graph = GraphWindow('Velocity', 'Time', 'Velocity (m/s)', 'green')
    angle_graph = GraphWindow('Relative Angle', 'Time', 'Angle (degrees)', 'red')
    angular_position_graph = GraphWindow('Angular Position', 'Time', 'Angular Position (degrees)', 'purple')
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

class AprilTagWindow(QWidget):
    def __init__(self, queue):
        super().__init__()
        self.initUI()
        self.last_time = time.time()
        self.frame_count = 0
        self.pose_data = deque(maxlen=250)  # Deque to store rvec, tvec, and timestamp
        self.prev_pose_data = None
        self.queue = queue
        self.tag_detected = False

    def initUI(self):
        self.setWindowTitle('AprilTag Detection')
        self.image_label = QLabel(self)
        self.fps_label = QLabel(self)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.fps_label)
        self.setLayout(self.layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(time_interval)  # Update frame every 33 ms

    def update_frame(self):
        ret, frame = video_capture.read()
        if not ret:
            return

        undistorted_frame = cv2.undistort(frame, mtx, dist)
        gray_frame = cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2GRAY)
        tags = detector.detect(gray_frame)

        self.tag_detected = len(tags) > 0

        # Draw the detected tags
        for tag in tags:
            corners = tag.corners
            pt1 = (int(corners[0][0]), int(corners[0][1]))
            pt2 = (int(corners[1][0]), int(corners[1][1]))
            pt3 = (int(corners[2][0]), int(corners[2][1]))
            pt4 = (int(corners[3][0]), int(corners[3][1]))

            cv2.line(undistorted_frame, pt1, pt2, (0, 255, 0), 2)
            cv2.line(undistorted_frame, pt2, pt3, (0, 255, 0), 2)
            cv2.line(undistorted_frame, pt3, pt4, (0, 255, 0), 2)
            cv2.line(undistorted_frame, pt4, pt1, (0, 255, 0), 2)

            # Estimate the pose of the AprilTag
            image_points = np.array(corners, dtype=np.float32)
            success, rvec, tvec = cv2.solvePnP(object_points, image_points, mtx, dist)
            if success:
                timestamp = time.time()
                self.pose_data.append((rvec, tvec, timestamp))
                # Process the pose data
                process_pose_data((rvec, tvec, timestamp))
                if self.prev_pose_data is not None:
                    self.update_graphs((rvec, tvec, timestamp), self.prev_pose_data)
                self.prev_pose_data = (rvec, tvec, timestamp)

                            # Project 3D points to image plane to draw cubes (10 cm x 10 cm)
                cube_size = 0.10  # 10 cm
                cube_points = np.array([
                    [-cube_size / 2, -cube_size / 2, 0],
                    [cube_size / 2, -cube_size / 2, 0],
                    [cube_size / 2, cube_size / 2, 0],
                    [-cube_size / 2, cube_size / 2, 0],
                    [-cube_size / 2, -cube_size / 2, -cube_size],
                    [cube_size / 2, -cube_size / 2, -cube_size],
                    [cube_size / 2, cube_size / 2, -cube_size],
                    [-cube_size / 2, cube_size / 2, -cube_size]
                ], dtype=np.float32)

                # Define the axis points (10 cm length) relative to the center of the cube
                axis_length = 0.10  # 10 cm
                axis_points = np.array([
                    [0, 0, 0],  # Origin (center of the cube)
                    [axis_length, 0, 0],  # X-axis
                    [0, axis_length, 0],  # Y-axis
                    [0, 0, axis_length]  # Z-axis
                ], dtype=np.float32)

                # Offset the axis points to the center of the cube
                cube_center_offset = np.array([0, 0, -cube_size / 2], dtype=np.float32)
                axis_points += cube_center_offset

                # Draw the main cube
                img_points, _ = cv2.projectPoints(cube_points, rvec, tvec, mtx, dist)
                img_points = img_points.reshape(-1, 2).astype(int)
                for i, j in zip(range(4), range(4, 8)):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), line_color, 2)
                for i in range(4):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), line_color, 2)
                    cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), line_color, 2)

                # Draw the top cube
                top_cube_points = cube_points + np.array([0, -cube_size, 0])
                img_points, _ = cv2.projectPoints(top_cube_points, rvec, tvec, mtx, dist)
                img_points = img_points.reshape(-1, 2).astype(int)
                for i, j in zip(range(4), range(4, 8)):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), line_color, 2)
                for i in range(4):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), line_color, 2)
                    cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), line_color, 2)

                # Draw the bottom cube
                bottom_cube_points = cube_points + np.array([0, cube_size, 0])
                img_points, _ = cv2.projectPoints(bottom_cube_points, rvec, tvec, mtx, dist)
                img_points = img_points.reshape(-1, 2).astype(int)
                for i, j in zip(range(4), range(4, 8)):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), line_color, 2)
                for i in range(4):
                    cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), line_color, 2)
                    cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), line_color, 2)

                # Project the axis points to the image plane
                axis_img_points, _ = cv2.projectPoints(axis_points, rvec, tvec, mtx, dist)
                axis_img_points = axis_img_points.reshape(-1, 2).astype(int)

                # Draw the axes with different colors and labels
                origin = tuple(axis_img_points[0])
                x_axis = tuple(axis_img_points[1])
                y_axis = tuple(axis_img_points[2])
                z_axis = tuple(axis_img_points[3])

                cv2.arrowedLine(undistorted_frame, origin, x_axis, (0, 0, 255), 2)  # X-axis in red
                cv2.arrowedLine(undistorted_frame, origin, y_axis, (0, 255, 0), 2)  # Y-axis in green
                cv2.arrowedLine(undistorted_frame, origin, z_axis, (255, 0, 0), 2)  # Z-axis in blue

                cv2.putText(undistorted_frame, 'X', x_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                cv2.putText(undistorted_frame, 'Y', y_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(undistorted_frame, 'Z', z_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Convert the frame to QImage and display it
        height, width, channel = undistorted_frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(undistorted_frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        self.image_label.setPixmap(QPixmap.fromImage(q_img))

        # Calculate and display FPS
        self.frame_count += 1
        current_time = time.time()
        elapsed_time = current_time - self.last_time
        if elapsed_time >= 1.0:
            fps = self.frame_count / elapsed_time
            self.fps_label.setText(f"FPS: {fps:.2f}")
            self.last_time = current_time
            self.frame_count = 0

    def update_graphs(self, pose_data, prev_pose_data):
        if self.tag_detected:
            self.queue.put(pose_data)
        else:
            self.queue.put(None)

    def closeEvent(self, event):
        video_capture.release()
        self.queue.put(None)
        event.accept()

if __name__ == '__main__':
    queue = Queue()
    graph_process = Process(target=graph_updater, args=(queue,))
    graph_process.start()

    app = QApplication([])
    window = AprilTagWindow(queue)
    window.show()
    app.exec()

    graph_process.join()

