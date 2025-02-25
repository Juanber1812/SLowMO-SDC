import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyapriltags
import threading
import time
from collections import deque
from scipy.spatial.transform import Rotation as R

# Load the calibration data
calibration_data = np.load('calibration_data.npz')
mtx = calibration_data['mtx']
dist = calibration_data['dist']

# Define the 3D points of the AprilTag corners in the real world
# Assuming the tag is 0.055 meters (5.5 cm) wide
tag_size = 0.055
object_points = np.array([
    [-tag_size / 2, -tag_size / 2, 0],
    [tag_size / 2, -tag_size / 2, 0],
    [tag_size / 2, tag_size / 2, 0],
    [-tag_size / 2, tag_size / 2, 0]
], dtype=np.float32)

# Initialize video capture from the default camera with lower resolution
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
if not video_capture.isOpened():
    print(f"Error: Could not open video capture on camera index 0. Please check your camera connection.")
    exit()

root = tk.Tk()
root.title("AprilTag Detection and Distance Estimation")

# Create an AprilTag detector with optimized parameters
detector = pyapriltags.Detector(
    families='tag25h9',
    nthreads=4,  # Number of threads to use
    quad_decimate=2.0,  # Increase decimation factor to improve FPS
    quad_sigma=0.0,  # Apply Gaussian blur to input image
    refine_edges=1,  # Spend more time to align edges of tags
    decode_sharpening=0.25  # Apply sharpening to decoded images
)
time_stamps = deque(maxlen=100)
rvec_y = deque(maxlen=100)
distance_values = []
velocity_values = []
time_values = []
angle_values = []
time_angle_values = []

# Define a variable for font size
font_size = 16

# Create separate figures for each graph
fig1, ax1 = plt.subplots(figsize=(6, 5))
fig2, ax2 = plt.subplots(figsize=(6, 5))
fig3, ax3 = plt.subplots(figsize=(6, 5))

line1, = ax1.plot([], [], 'r-', label='Distance')
line2, = ax2.plot([], [], 'b-', label='Velocity')
line3, = ax3.plot([], [], 'g-', label='Angle')

ax1.set_xlabel('Time (seconds)', fontsize=font_size)
ax1.set_ylabel('Distance (meters)', fontsize=font_size)
ax1.yaxis.set_label_position("left")
ax1.yaxis.tick_left()
ax1.grid(True)
ax1.legend(loc='upper left', fontsize=font_size)

ax2.set_ylim(-2, 2)  # Fixed y-axis range
ax2.set_xlabel('Time (seconds)', fontsize=font_size)
ax2.set_ylabel('Velocity (meters/second)', fontsize=font_size)
ax2.yaxis.set_label_position("left")
ax2.yaxis.tick_left()
ax2.grid(True)
ax2.legend(loc='upper left', fontsize=font_size)

ax3.set_xlabel('Time (seconds)', fontsize=font_size)
ax3.set_ylabel('Angle (degrees)', fontsize=font_size)
ax3.yaxis.set_label_position("left")
ax3.yaxis.tick_left()
ax3.grid(True)
ax3.legend(loc='upper left', fontsize=font_size)

# Create text annotations for current values
distance_text = ax1.text(0.95, 0.95, '', transform=ax1.transAxes, ha='right', va='top', fontsize=font_size)
velocity_text = ax2.text(0.95, 0.95, '', transform=ax2.transAxes, ha='right', va='top', fontsize=font_size)
angle_text = ax3.text(0.95, 0.95, '', transform=ax3.transAxes, ha='right', va='top', fontsize=font_size)
fps_text = fig1.text(0.95, 0.05, '', ha='right', va='bottom', fontsize=font_size)

# Create the main window for the live feed
video_label = ttk.Label(root)
video_label.grid(row=0, column=0, sticky="nsew")

# Create canvases to display the graphs
canvas1 = FigureCanvasTkAgg(fig1, master=root)
canvas1.get_tk_widget().grid(row=0, column=1, sticky="nsew")

canvas2 = FigureCanvasTkAgg(fig2, master=root)
canvas2.get_tk_widget().grid(row=0, column=2, sticky="nsew")

canvas3 = FigureCanvasTkAgg(fig3, master=root)
canvas3.get_tk_widget().grid(row=0, column=3, sticky="nsew")

# Create a new figure and axis for the Euler angles
fig4, ax4 = plt.subplots(figsize=(6, 5))
line4, = ax4.plot([], [], 'm-', label='Y Rotation')

ax4.set_xlabel('Time (seconds)', fontsize=font_size)
ax4.set_ylabel('Angle (degrees)', fontsize=font_size)
ax4.yaxis.set_label_position("left")
ax4.yaxis.tick_left()
ax4.grid(True)
ax4.legend(loc='upper left', fontsize=font_size)

# Create a canvas to display the Euler angles graph
canvas4 = FigureCanvasTkAgg(fig4, master=root)
canvas4.get_tk_widget().grid(row=0, column=4, sticky="nsew")

# Configure the grid to adjust the size of the video and graphs
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_columnconfigure(3, weight=1)
root.grid_columnconfigure(4, weight=1)
root.grid_rowconfigure(0, weight=1)

stop_event = threading.Event()

frame_timestamps = deque(maxlen=100)  # Store timestamps of the last 100 frames

def process_frame():
    start_time = time.perf_counter()
    while video_capture.isOpened() and not stop_event.is_set():
        ret, frame = video_capture.read()
        if not ret:
            continue

        current_time = time.perf_counter()
        frame_timestamps.append(current_time)

        # Calculate the current FPS over the past second
        one_second_ago = current_time - 1
        while frame_timestamps and frame_timestamps[0] < one_second_ago:
            frame_timestamps.popleft()
        current_fps = len(frame_timestamps)

        # Undistort the frame using the calibration data
        undistorted_frame = cv2.undistort(frame, mtx, dist)
        # Convert the frame to grayscale
        gray_frame = cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2GRAY)

        # Detect AprilTags in the frame
        tags = detector.detect(gray_frame)

        # Draw lines on the edges of the detected AprilTags and calculate distance
        for tag in tags:
            corners = tag.corners
            pt1 = (int(corners[0][0]), int(corners[0][1]))
            pt2 = (int(corners[1][0]), int(corners[1][1]))
            pt3 = (int(corners[2][0]), int(corners[2][1]))
            pt4 = (int(corners[3][0]), int(corners[3][1]))
            
            # Draw each line with the same color (e.g., green)
            line_color = (0, 255, 0)
            cv2.line(undistorted_frame, pt1, pt2, line_color, 2)
            cv2.line(undistorted_frame, pt2, pt3, line_color, 2)
            cv2.line(undistorted_frame, pt3, pt4, line_color, 2)
            cv2.line(undistorted_frame, pt4, pt1, line_color, 2)

            # Estimate the pose of the AprilTag
            image_points = np.array(corners, dtype=np.float32)
            success, rvec, tvec = cv2.solvePnP(object_points, image_points, mtx, dist)

            if success:
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

                # Calculate the distance to the camera
                distance = np.linalg.norm(tvec) - 0.02
                distance_values.append(distance)
                if len(distance_values) > 150:
                    distance_values.pop(0)

                # Calculate the velocity (derivative of distance with respect to time)
                if len(distance_values) > 1:
                    elapsed_time = current_time - frame_timestamps[-2]
                    velocity = (distance_values[-1] - distance_values[-2]) / elapsed_time
                    velocity_values.append(velocity)  # Velocity in meters/second
                    if len(velocity_values) > 150:
                        velocity_values.pop(0)
                else:
                    velocity_values.append(0)

                # Update time values
                total_elapsed_time = current_time - start_time
                time_values.append(total_elapsed_time)
                if len(time_values) > 150:
                    time_values.pop(0)

                # Calculate the angle in the X-axis relative to the center of the cube
                # Offset the translation vector to the center of the cube
                tvec_center = tvec.reshape(3, 1) + np.array([0, 0, -cube_size / 2]).reshape(3, 1)
                angle_x = np.arctan2(tvec_center[0], 1)  # Angle in radians, considering only the X-axis
                angle_x_degrees = np.degrees(angle_x)

                # Update the angle and time values for the line plot
                angle_values.append(angle_x_degrees)
                time_angle_values.append(total_elapsed_time)
                if len(angle_values) > 150:
                    angle_values.pop(0)
                    time_angle_values.pop(0)

                # Convert rvec to Euler angles
                rotation_matrix, _ = cv2.Rodrigues(rvec)
                r = R.from_matrix(rotation_matrix)
                euler_angles = r.as_euler('xyz', degrees=True)

                # Append the Euler angles to the deques
                rvec_y.append(euler_angles[1])
                time_stamps.append(total_elapsed_time)
                
        # Resize the frame to fit the desired size
        desired_width = int(16*50)  # Set your desired width
        desired_height = int(9*50)  # Set your desired height
        resized_frame = cv2.resize(undistorted_frame, (desired_width, desired_height))

        # Convert the resized frame to a format suitable for Tkinter
        resized_frame_rgb = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        resized_frame_pil = Image.fromarray(resized_frame_rgb)
        resized_frame_tk = ImageTk.PhotoImage(image=resized_frame_pil)

        # Update the label with the new frame
        video_label.config(image=resized_frame_tk)
        video_label.image = resized_frame_tk

        # Update the graphs
        if distance_values:
            line1.set_data(time_values, distance_values)
            ax1.relim()
            ax1.autoscale_view()
            ax1.set_xlim(max(0, time_values[-1] - 15), time_values[-1])  # Update x-axis limits to show last 15 seconds
            canvas1.draw()

        if velocity_values:
            line2.set_data(time_values, velocity_values)
            ax2.relim()
            ax2.autoscale_view()
            ax2.set_xlim(max(0, time_values[-1] - 15), time_values[-1])  # Update x-axis limits to show last 15 seconds
            canvas2.draw()

        if len(angle_values) > 1:
            line3.set_data(time_angle_values, angle_values)
            ax3.autoscale_view()
            ax3.set_xlim(max(0, time_angle_values[-1] - 15), time_angle_values[-1])  # Show last 15 seconds
            ax3.set_ylim(-45, 45)  # Set y-axis limits to -45 to 45 degrees
            canvas3.draw()  # Update the correct canvas        

        if rvec_y:
            line4.set_data(time_stamps, rvec_y)
            ax4.relim()
            ax4.autoscale_view()
            ax4.set_xlim(max(0, time_stamps[-1] - 15), time_stamps[-1])  # Update x-axis limits to show last 15 seconds
            canvas4.draw()

        # Update text annotations with current values
        if distance_values:
            distance_text.set_text(f'Distance: {distance_values[-1]:.2f} m')
        if velocity_values:
            velocity_text.set_text(f'Velocity: {velocity_values[-1]:.2f} m/s')
        if angle_values:
            angle_text.set_text(f'Angle: {angle_values[-1][0]:.2f}°')

        # Display the current FPS
        fps_text.set_text(f'FPS: {current_fps:.2f}')

# Start the frame processing in a separate thread
thread = threading.Thread(target=process_frame)
thread.daemon = True
thread.start()

# Function to handle window close event
def on_closing():
    stop_event.set()
    video_capture.release()
    cv2.destroyAllWindows()
    root.destroy()
root.protocol("WM_DELETE_WINDOW", on_closing)

# Function to plot the Euler angles over time
def plot_euler_angles():
    plt.figure(figsize=(12, 8))

    plt.subplot(3, 1, 1)
    plt.plot(time_stamps, rvec_y, label='Y Rotation')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (degrees)')
    plt.title('Y Rotation Over Time')
    plt.legend()

    plt.tight_layout()
    plt.show()

# Button to plot the Euler angles
plot_button = ttk.Button(root, text="Plot Euler Angles", command=plot_euler_angles)
plot_button.grid(row=1, column=0, sticky="nsew")

# Start the Tkinter main loop
root.mainloop()