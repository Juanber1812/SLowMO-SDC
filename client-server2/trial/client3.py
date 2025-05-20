# mjpeg_client.py

import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

class MJPEGViewer(QWidget):
    def __init__(self, stream_url):
        super().__init__()
        self.setWindowTitle("MJPEG Stream Viewer")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        self.label = QLabel("Streaming from: " + stream_url)
        layout.addWidget(self.label)

        self.webview = QWebEngineView()
        self.webview.load(QUrl(stream_url))
        layout.addWidget(self.webview)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Change this to your actual Raspberry Pi IP if needed
    stream_url = "http://localhost:8080/video_feed"

    viewer = MJPEGViewer(stream_url)
    viewer.show()

    sys.exit(app.exec())
