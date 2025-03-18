import socketio
import base64
import json
import cv2
import numpy as np
from collections import deque
from multiprocessing import Queue

# Create a socketio client instance
sio = socketio.Client()

queue = Queue()
window = None

frame = None
fps = None
sensor = None

# Socket.IO events
@sio.event
def connect():
    print("Connected to server.")

@sio.event
def disconnect():
    print("Disconnected from server.")

@sio.event
def response_data(data): # Receive frames from the server
    global frame, fps, sensor

    # Parse the incoming JSON data
    json_data = json.loads(data, object_hook=custom_decoder)  # Decode the JSON string

    # Retrieve 'image' (frame_data) and 'sensors' from the parsed JSON
    frame_data = json_data.get('image')
    pose_data = json_data.get('pose')
    tag_detected_data = json_data.get('tag')
    fps_data = json_data.get('fps')
    sensor_data = json_data.get('sensors')

    update_queue(pose_data, tag_detected_data)
    fps = fps_data
    sensor = sensor_data

    try:
        nparr = np.frombuffer(base64.b64decode(frame_data), np.uint8)  # Decode the base64 data to NumPy array
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # Decode the frame
        window.update_data()  # Update window data
    except Exception as e:
        print(f"Error decoding frame: {e}")
        frame = None  # If an error occurs, set frame to None



# Decoder for data received from server
def custom_decoder(obj):
    if "__deque__" in obj:
        return deque(obj["data"])  # Convert list back to deque
    elif "__ndarray__" in obj:
        return np.array(obj["data"])  # Convert list back to ndarray
    return obj

# Update queue data if tag detected 
def update_queue(pose_data, tag_detected):
    if tag_detected:
        queue.put(pose_data)
    else:
        queue.put(None)