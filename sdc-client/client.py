import data_handler
import main_window

import sys
from multiprocessing import Queue
from PyQt6.QtWidgets import QApplication

cleanup_printed = False

# Cleanup function to ensure a proper shutdown
def cleanup():
    global cleanup_printed
    if not cleanup_printed: # Ensure cleanup print only runs once
        print("Cleaning up before exit...")
        cleanup_printed = True  # Mark cleanup print as done

    if data_handler.sio.connected:
        data_handler.sio.disconnect()
        print("SocketIO disconnected.")

    QApplication.quit()

if __name__ == "__main__":
    # Set time interval bewteen frames and graph update rate
    time_interval = 100 #milliseconds
    graphing_rate = 0.01 #seconds

    # Queue for graph windows
    queue = Queue()

    # Setup PyQt6
    app = QApplication(sys.argv)
    data_handler.window = main_window.MainWindow(time_interval, graphing_rate)
    
    # Connect to the server
    try:
        data_handler.sio.connect('http://127.0.0.1:5000', wait_timeout=5)
        print("Connected to server.")
    except Exception as e:
        print(f"Connection error: {e}")

    # Connect the cleanup function to the aboutToQuit signal
    app.aboutToQuit.connect(cleanup)

    # Show the main window and run the event loop
    data_handler.window.show()
    sys.exit(app.exec())