import cv2
import base64
import json
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

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

def read_sensor_data():
    """ Example function to read sensor data (replace with real sensors) """
    return {"temperature": 22.5, "humidity": 55.3}

@app.route('/')
def home():
    return "Server is running"

@socketio.on('connect')  
def handle_connect():
    print("Client connected successfully!")

@socketio.on('disconnect')  
def handle_connect():
    print("Client disconnected.")

@socketio.on('request_data')
def send_data():
    """ Send video frame and sensor data """
    frame_data = capture_frame()
    if frame_data:
        sensor_data = read_sensor_data()
        socketio.emit('response_data', json.dumps({
            "image": frame_data,
            "sensors": sensor_data
        }))

@socketio.on('flip')
def flip():
    global flip_state
    flip_state = not flip_state

@socketio.on('invert')
def invert():
    global invert_state
    invert_state = not invert_state

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

    # Release the camera when the server stops
    cap.release()
