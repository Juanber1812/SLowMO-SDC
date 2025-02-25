import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

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
    rotation = R.from_matrix(rotation_matrix)
    euler_angles = rotation.as_euler('xyz', degrees=True)
    angular_position = euler_angles[1]  # Yaw angle
    return timestamp, angular_position