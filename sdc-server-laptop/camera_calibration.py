# take 10 pictures of calibration chess board by pressing spacebar so that camera_data.npz can be formed properly

import cv2
import numpy as np

# Define the chessboard size
chessboard_size = (9, 6)

# Prepare object points (0,0,0), (1,0,0), (2,0,0), ..., (8,5,0)
objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)

# Arrays to store object points and image points from all the images
objpoints = []  # 3d point in real world space
imgpoints = []  # 2d points in image plane

# Capture calibration images
video_capture = cv2.VideoCapture(0)
cv2.namedWindow('Calibration', cv2.WINDOW_NORMAL)  # Create a named window

while True:
    ret, frame = video_capture.read()
    if not ret:
        print("Failed to capture image")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, chessboard_size, None)

    if ret:
        # Draw and display the corners
        cv2.drawChessboardCorners(frame, chessboard_size, corners, ret)

    # Display the frame
    cv2.imshow('Calibration', frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord(' '):  # Spacebar to capture the image
        if ret:
            objpoints.append(objp)
            imgpoints.append(corners)
            print(f"Chessboard detected and corners added. Total images: {len(objpoints)}")

video_capture.release()
cv2.destroyAllWindows()

# Check if enough images were captured for calibration
print(f"Total images captured: {len(objpoints)}")
if len(objpoints) < 10:
    print("Not enough calibration images were captured. Please capture more images.")
else:
    # Calibrate the camera
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    if ret:
        # Save the calibration results
        np.savez('calibration_data.npz', mtx=mtx, dist=dist, rvecs=rvecs, tvecs=tvecs)
        print("Calibration successful. Calibration data saved to 'calibration_data.npz'.")
        
        # Print the calibration values for easy copying
        print("Camera matrix (mtx):")
        print(mtx)
        print("Distortion coefficients (dist):")
        print(dist)
        print("Rotation vectors (rvecs):")
        print(rvecs)
        print("Translation vectors (tvecs):")
        print(tvecs)
    else:
        print("Calibration failed.")