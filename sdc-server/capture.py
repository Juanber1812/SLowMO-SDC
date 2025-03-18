import cv2
import base64
import numpy as np
import pyapriltags
import time
from collections import deque
from gevent import monkey

monkey.patch_all()

class AprilTagCaptureObject():
    def __init__(self):
        self.latest_frame_data = None

        self.last_time = time.time()
        self.frame_count = 0
        self.pose_data = deque(maxlen=100)  # Deque to store rvec, tvec, and timestamp
        self.prev_pose_data = None
        self.tag_detected = False
        
        self.pose_data_list = [self.pose_data, self.prev_pose_data, self.tag_detected]

        # Load the calibration data
        self.calibration_data = np.load('calibration_data.npz')
        self.mtx = self.calibration_data['mtx']
        self.dist = self.calibration_data['dist']

        self.flip_state = False
        self.invert_state = False

        # OpenCV Video Capture (0 = default webcam)
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1000)  # Width
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1000)  # Height

        if not self.cap.isOpened():
            print(f"Error: Could not open video capture on camera index 0. Please check your camera connection.")
            exit()

        # Line color
        self.line_color = (0, 255, 0)

        # Create an AprilTag detector
        self.detector = pyapriltags.Detector(families='tag25h9',
                                        nthreads=4,
                                        quad_decimate=1.0,  # Adjust this value based on your performance and accuracy requirements
                                        quad_sigma=0.0,
                                        refine_edges=1,
                                        decode_sharpening=0.25)

        # Set tag size in meters
        self.tag_size = 0.055

        # Define the 3D points of the AprilTag corners in the real world
        self.object_points = np.array([
            [-self.tag_size / 2, -self.tag_size / 2, 0],
            [self.tag_size / 2, -self.tag_size / 2, 0],
            [self.tag_size / 2, self.tag_size / 2, 0],
            [-self.tag_size / 2, self.tag_size / 2, 0]
        ], dtype=np.float32)

    def process_pose_data(self, pose_data):
        rvec, tvec, timestamp = pose_data
        self.rotation_matrix, _ = cv2.Rodrigues(rvec)

    def capture_frame(self):
        """ Capture a frame from the webcam and encode it as base64 """
        ret, frame = self.cap.read()
        if ret:
            undistorted_frame = cv2.undistort(frame, self.mtx, self.dist)
            gray_frame = cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2GRAY)
            tags = self.detector.detect(gray_frame)

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
                success, rvec, tvec = cv2.solvePnP(self.object_points, image_points, self.mtx, self.dist)
                if success:
                    timestamp = time.time()
                    self.pose_data.append((rvec, tvec, timestamp))
                    # Process the pose data
                    self.process_pose_data((rvec, tvec, timestamp))
                    if self.prev_pose_data is not None:
                        self.pose_data_list = [(rvec, tvec, timestamp), self.prev_pose_data]
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

                    #if np.any(np.isnan(img_points)):
                     #   print("Warning: img_points contains NaN values.")
                        # You can either skip this operation, set defaults, or handle as needed.
                        # For example, replace NaN values with a default value:
                        #img_points = np.nan_to_num(img_points, nan=0)

                    # Draw the main cube
                    img_points, _ = cv2.projectPoints(cube_points, rvec, tvec, self.mtx, self.dist)
                    img_points = img_points.reshape(-1, 2).astype(int)
                    for i, j in zip(range(4), range(4, 8)):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), self.line_color, 2)
                    for i in range(4):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), self.line_color, 2)
                        cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), self.line_color, 2)

                    # Draw the top cube
                    top_cube_points = cube_points + np.array([0, -cube_size, 0])
                    img_points, _ = cv2.projectPoints(top_cube_points, rvec, tvec, self.mtx, self.dist)
                    img_points = img_points.reshape(-1, 2).astype(int)
                    for i, j in zip(range(4), range(4, 8)):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), self.line_color, 2)
                    for i in range(4):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), self.line_color, 2)
                        cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), self.line_color, 2)

                    # Draw the bottom cube
                    bottom_cube_points = cube_points + np.array([0, cube_size, 0])
                    img_points, _ = cv2.projectPoints(bottom_cube_points, rvec, tvec, self.mtx, self.dist)
                    img_points = img_points.reshape(-1, 2).astype(int)
                    for i, j in zip(range(4), range(4, 8)):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[j]), self.line_color, 2)
                    for i in range(4):
                        cv2.line(undistorted_frame, tuple(img_points[i]), tuple(img_points[(i+1)%4]), self.line_color, 2)
                        cv2.line(undistorted_frame, tuple(img_points[i+4]), tuple(img_points[(i+1)%4+4]), self.line_color, 2)

                    # Project the axis points to the image plane
                    axis_img_points, _ = cv2.projectPoints(axis_points, rvec, tvec, self.mtx, self.dist)
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

            if self.flip_state:
                undistorted_frame = cv2.flip(undistorted_frame, 1)
            if self.invert_state:
                undistorted_frame = cv2.bitwise_not(undistorted_frame)

            _, buffer = cv2.imencode('.jpg', undistorted_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])  # Compress
            self.latest_frame_data = base64.b64encode(buffer).decode('utf-8')
    
    def get_fps(self):
        # Calculate and display FPS
        self.frame_count += 1
        current_time = time.time()
        elapsed_time = current_time - self.last_time
        if elapsed_time >= 1.0:
            fps = self.frame_count / elapsed_time
            self.last_time = current_time
            self.frame_count = 0
            return fps