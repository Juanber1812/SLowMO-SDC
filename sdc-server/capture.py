import cv2
import base64

flip_state = False
invert_state = False

# OpenCV Video Capture (0 = default webcam)
cap = cv2.VideoCapture(0)
cap.set(3, 640)  # Width
cap.set(4, 480)  # Height

def capture_frame():
    """ Capture a frame from the webcam and encode it as base64 """
    ret, frame = cap.read()
    if flip_state:
        frame = cv2.flip(frame, 1)
    if invert_state:
        frame = cv2.bitwise_not(frame)
    if ret:
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
    return None