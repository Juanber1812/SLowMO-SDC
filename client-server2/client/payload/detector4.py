import cv2
import numpy as np
import pyapriltags
import os
import time
import logging # <<< ADD THIS IMPORT

class AprilTagDetector:
    def __init__(self, calibration_file=None):
        """Initialize detector with calibration file."""
        # 1) store config in a dict
        self.config = {
            'families':   'tag25h9',
            'nthreads':   4,
            'quad_decimate':    0.5,
            'quad_sigma':       0,
            'refine_edges':     4,
            'decode_sharpening':0.25
        }
        
        # 2) pass it into the real detector
        self.detector = pyapriltags.Detector(**self.config)

        self.tag_size = 0.055  # meters
        self.line_color = (0, 255, 0)
        self.line_thickness = 8
        
        # Load initial calibration
        self.mtx = None
        self.dist = None
        if calibration_file:
            self.load_calibration(calibration_file)
        else:
            # Fallback to default
            default_calib = os.path.join(os.path.dirname(__file__), "calibration_data.npz")
            if os.path.exists(default_calib):
                self.load_calibration(default_calib)
    
    def load_calibration(self, calibration_file):
        """Load calibration data from file."""
        try:
            # Handle relative paths for legacy calibration
            abs_calibration_file = calibration_file # Store original for logging if needed
            if not os.path.isabs(calibration_file):
                # If it's a relative path, make it relative to the current file's directory
                # This path logic assumes calibration_file is like "payload/file.npz" or "calibrations/file.npz"
                # and this script (detector4.py) is in client/payload
                base_path = os.path.join(os.path.dirname(__file__), "..") # up to client/
                abs_calibration_file = os.path.join(base_path, calibration_file)
                abs_calibration_file = os.path.normpath(abs_calibration_file)
        
            if not os.path.exists(abs_calibration_file):
                print(f"[WARNING] Calibration file not found: {abs_calibration_file} (original path: {calibration_file})")
                return False
                
            calibration = np.load(abs_calibration_file)
            self.mtx = calibration['mtx']
            self.dist = calibration['dist']

            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to load calibration {calibration_file} (resolved: {abs_calibration_file if 'abs_calibration_file' in locals() else 'N/A'}): {e}")
            self.mtx = None # Clear on failure
            self.dist = None # Clear on failure
            return False
    
    def update_calibration(self, calibration_file):
        """Update calibration file - thread-safe method."""
        return self.load_calibration(calibration_file)
    
    def detect_and_draw(self, frame: np.ndarray, return_pose=False, is_cropped=False, original_height=None):
        """Detect AprilTags and draw cubes."""
        if self.mtx is None or self.dist is None:
            print("[WARNING] No calibration data - skipping detection")
            return (frame, None) if return_pose else frame
        
        start_time = time.time()

        # Adjust camera matrix for cropped images
        mtx = self.mtx.copy() # self.mtx is the original calibration matrix
        if is_cropped and original_height is not None:
            current_height = frame.shape[0] # Height of the cropped image
            
            
            # Calculate how many rows were removed from the top (center crop)
            total_removed = original_height - current_height
            crop_offset_from_top = total_removed // 2  # Half removed from top, half from bottom
            

            # Adjust principal point Y (cy) for the crop offset from top
            mtx[1, 2] -= crop_offset_from_top 
            

            # Sanity check - where should cy be proportionally?
            original_cy_ratio = self.mtx[1,2] / original_height
            expected_new_cy = original_cy_ratio * current_height

        
        frame = cv2.undistort(frame, mtx, self.dist)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tags = self.detector.detect(gray, estimate_tag_pose=True,
                               camera_params=(mtx[0, 0], mtx[1, 1], mtx[0, 2], mtx[1, 2]),
                               tag_size=self.tag_size)

        for tag in tags:
            corners = tag.corners.astype(int)
            for i in range(4):
                pt1 = tuple(corners[i])
                pt2 = tuple(corners[(i + 1) % 4])
                cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

            rvec, _ = cv2.Rodrigues(tag.pose_R)
            tvec = tag.pose_t.reshape(3, 1)
            cube_size = 0.10

            # Use adjusted camera matrix for cube drawing
            self.draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, 0, 0], dtype=np.float32), mtx=mtx)
            self.draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, -cube_size, 0], dtype=np.float32), mtx=mtx)
            self.draw_cube_manual(frame, rvec, tvec, cube_size, offset=np.array([0, cube_size, 0], dtype=np.float32), mtx=mtx)
        
        end_time= time.time()
        latency_ms = (end_time - start_time) * 1000.0

        if return_pose and tags:
            rvec, _ = cv2.Rodrigues(tags[0].pose_R)
            tvec = tags[0].pose_t.reshape(3, 1)
            return frame, (rvec, tvec), latency_ms

        if return_pose:
            return frame, None, latency_ms

        return frame

    def draw_cube_manual(self, img, rvec, tvec, size, offset, mtx=None):
        """Draw a 3D cube on the image."""
        if mtx is None:
            mtx = self.mtx
            
        if mtx is None or self.dist is None:
            print("[WARNING] No calibration data loaded")
            return
            
        cube_points = np.array([
            [-size / 2, -size / 2, 0],
            [ size / 2, -size / 2, 0],
            [ size / 2,  size / 2, 0],
            [-size / 2,  size / 2, 0],
            [-size / 2, -size / 2, size],
            [ size / 2, -size / 2, size],
            [ size / 2,  size / 2, size],
            [-size / 2,  size / 2, size],
        ], dtype=np.float32)

        cube_points += offset
        img_points, _ = cv2.projectPoints(cube_points, rvec, tvec, mtx, self.dist)
        pts = img_points.reshape(-1, 2).astype(int)

        # Manually draw all cube edges
        cv2.line(img, tuple(pts[0]), tuple(pts[1]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[1]), tuple(pts[2]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[2]), tuple(pts[3]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[3]), tuple(pts[0]), self.line_color, self.line_thickness)

        cv2.line(img, tuple(pts[4]), tuple(pts[5]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[5]), tuple(pts[6]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[6]), tuple(pts[7]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[7]), tuple(pts[4]), self.line_color, self.line_thickness)

        cv2.line(img, tuple(pts[0]), tuple(pts[4]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[1]), tuple(pts[5]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[2]), tuple(pts[6]), self.line_color, self.line_thickness)
        cv2.line(img, tuple(pts[3]), tuple(pts[7]), self.line_color, self.line_thickness)

    def get_config(self) -> dict:
        """Return the current detector parameters."""
        return self.config.copy()

    def update_params(self, **kwargs):
        """Reconfigure detector on the fly."""
        # merge new settings
        self.config.update(kwargs)
        # re-create the underlying detector
        self.detector = pyapriltags.Detector(**self.config)
        return self.config

    def update_tag_size(self, new_size):
        """Update the AprilTag size."""
        self.tag_size = new_size


# Create global detector instance
try:
    detector_instance = AprilTagDetector()
    print("[INFO] AprilTag detector initialized successfully")
except Exception as e:
    print(f"[ERROR] Failed to initialize AprilTag detector: {e}")
    detector_instance = None

# Backward compatibility functions
def detect_and_draw(frame: np.ndarray, return_pose=False):
    """Backward compatible function."""
    try:
        if detector_instance:
            return detector_instance.detect_and_draw(frame, return_pose)
        else:
            print("[WARNING] Detector instance not available")
            return (frame, None) if return_pose else frame
    except Exception as e:
        print(f"[ERROR] detect_and_draw failed: {e}")
        return (frame, None) if return_pose else frame

def update_calibration(calibration_file):
    """Update calibration file."""
    try:
        if detector_instance:
            return detector_instance.update_calibration(calibration_file)
        else:
            print("[WARNING] Detector instance not available for calibration update")
            return False
    except Exception as e:
        print(f"[ERROR] update_calibration failed: {e}")
        return False

def get_detector_config():
    """Global helper for backward compatibility."""
    if detector_instance:
        return detector_instance.get_config()
    return None

def update_tag_size(new_size):
    """Update AprilTag size globally."""
    if detector_instance:
        detector_instance.update_tag_size(new_size)
    else:
        print("[WARNING] Detector instance not available")

