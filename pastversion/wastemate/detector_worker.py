# detector_worker.py

import threading
import queue
import time
import logging
from bridge import bridge
from payload import detector4

class DetectorWorker:
    """
    Background worker for running the detector on frames.
    Feeds analysed frames to the UI via bridge.analysed_frame.
    Optionally updates a graph widget with pose data.
    """
    def __init__(self):
        self.active = False
        self.thread = None
        self.frame_queue = queue.Queue()
        self.graph_widget = None  # Set externally by the UI

    def start(self):
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        self.active = False
        self._clear_queue()

    def feed_frame(self, frame):
        self._clear_queue()
        self.frame_queue.put(frame)

    def _clear_queue(self):
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    def _run(self):
        while self.active:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                analysed, pose = detector4.detect_and_draw(frame, return_pose=True)
                bridge.analysed_frame.emit(analysed)

                if self.graph_widget is not None and pose:
                    rvec, tvec = pose
                    timestamp = time.time()
                    self.graph_widget.update(rvec, tvec, timestamp)

            except queue.Empty:
                continue
            except Exception as e:
                logging.exception("DetectorWorker encountered an error")
        self.active = False  # Ensure flag is reset when thread exits
