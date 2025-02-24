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

# Initialize video capture from the default camera
video_capture = cv2.VideoCapture(0)
if not video_capture.isOpened():
    print(f"Error: Could not open video capture on camera index 0. Please check your camera connection.")
    exit()

root = tk.Tk()
root.title("AprilTag Detection and Pose Estimation")
# Create the main window for the live feed
video_label = ttk.Label(root)
video_label.grid(row=0, column=0, sticky="nsew")
# Create an AprilTag detector with tuned parameters for better recognition at a distance
detector = pyapriltags.Detector(
    families='tag25h9',
    nthreads=4,  # Number of threads to use
    quad_decimate=1,  # Decimate input image by this factor (increase to improve FPS)
    quad_sigma=0.0,  # Apply Gaussian blur to input image
    refine_edges=1,  # Spend more time to align edges of tags
    decode_sharpening=0.25  # Apply sharpening to decoded images
)

stop_event = threading.Event()

# Deques to store rvec values over time
rvec_x = deque(maxlen=100)
rvec_y = deque(maxlen=100)
rvec_z = deque(maxlen=100)
time_stamps = deque(maxlen=100)

def process_frame():
    start_time = time.time()
    while video_capture.isOpened() and not stop_event.is_set():
        ret, frame = video_capture.read()
        if not ret:
            continue

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
                # Convert rvec to Euler angles
                rotation_matrix, _ = cv2.Rodrigues(rvec)
                r = R.from_matrix(rotation_matrix)
                euler_angles = r.as_euler('xyz', degrees=True)

                # Append the Euler angles to the deques
                current_time = time.time() - start_time
                rvec_x.append(euler_angles[0])
                rvec_y.append(euler_angles[1])
                rvec_z.append(euler_angles[2])
                time_stamps.append(current_time)

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
                    [0, 0, axis_length],  # Z-axis
                ], dtype=np.float32)

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
           
        # Resize the frame to fit the desired size
        desired_width = int(640 * 1.5)  # Set your desired width
        desired_height = int(480 * 1.5)  # Set your desired height
        resized_frame = cv2.resize(undistorted_frame, (desired_width, desired_height))

        # Convert the resized frame to a format suitable for Tkinter
        resized_frame_rgb = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        resized_frame_pil = Image.fromarray(resized_frame_rgb)
        resized_frame_tk = ImageTk.PhotoImage(image=resized_frame_pil)

        # Update the label with the new frame
        video_label.config(image=resized_frame_tk)
        video_label.image = resized_frame_tk
    
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
    plt.plot(time_stamps, rvec_x, label='X Rotation')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (degrees)')
    plt.title('X Rotation Over Time')
    plt.legend()

    plt.subplot(3, 1, 2)
    plt.plot(time_stamps, rvec_y, label='Y Rotation')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (degrees)')
    plt.title('Y Rotation Over Time')
    plt.legend()

    plt.subplot(3, 1, 3)
    plt.plot(time_stamps, rvec_z, label='Z Rotation')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (degrees)')
    plt.title('Z Rotation Over Time')
    plt.legend()

    plt.tight_layout()
    plt.show()

# Button to plot the Euler angles
plot_button = ttk.Button(root, text="Plot Euler Angles", command=plot_euler_angles)
plot_button.grid(row=1, column=0, sticky="nsew")

# Start the Tkinter main loop
root.mainloop()