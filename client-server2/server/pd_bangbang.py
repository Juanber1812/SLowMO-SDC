import RPi.GPIO as GPIO
import time
import threading

# ── PIN SETUP ─────────────────────────────────────────────
# adjust these to match your wiring
DIR_PIN    = 19   # direction select
ENABLE_PIN = 13   # digital enable instead of PWM
SLEEP_PIN  = 26   # standby (if your MP6550 uses it)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(DIR_PIN,    GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ENABLE_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(SLEEP_PIN,  GPIO.OUT, initial=GPIO.HIGH)

# ── BASIC MOTOR CONTROL FUNCTIONS ─────────────────────────
def rotate_clockwise_dc():
    """Full DC forward."""
    print("[MOTOR] Starting clockwise rotation")
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def rotate_counterclockwise_dc():
    """Full DC reverse."""
    print("[MOTOR] Starting counterclockwise rotation")
    GPIO.output(DIR_PIN, GPIO.HIGH)
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def stop_motor_dc():
    """Disable driver (0 V to motor)."""
    print("[MOTOR] Stopping motor")
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def cleanup():
    stop_motor_dc()
    GPIO.cleanup()

# ── PD CONTROLLER CLASS ───────────────────────────────────
class PDController:
    def __init__(self, kp=1.0, kd=0.1, deadband=2.0):
        self.kp = kp                    # Proportional gain
        self.kd = kd                    # Derivative gain
        self.deadband = deadband        # Don't move if error < this (degrees)
        self.target_angle = 0.0         # Desired orientation
        self.current_angle = 0.0        # Current orientation
        self.previous_error = 0.0       # For derivative calculation
        self.previous_time = time.time()
        self.running = False
        self.control_thread = None
        self.control_frequency = 10     # Hz (10 times per second)
        
    def set_target(self, target):
        """Set the target orientation angle"""
        self.target_angle = target
        print(f"[PD] Target set to {target}°")
        
    def update_current_angle(self, angle):
        """Update current orientation from sensors"""
        self.current_angle = angle
        
    def set_gains(self, kp, kd):
        """Update PD gains"""
        self.kp = kp
        self.kd = kd
        print(f"[PD] Gains updated: Kp={kp}, Kd={kd}")
        
    def set_deadband(self, deadband):
        """Update deadband threshold"""
        self.deadband = deadband
        print(f"[PD] Deadband set to {deadband}°")
        
    def calculate_control(self):
        """Calculate PD control output"""
        current_time = time.time()
        dt = current_time - self.previous_time
        
        if dt <= 0:
            dt = 0.01  # Prevent division by zero
        
        # Calculate error
        error = self.target_angle - self.current_angle
        
        # Handle angle wraparound (if using 0-360° system)
        if error > 180:
            error -= 360
        elif error < -180:
            error += 360
            
        # Calculate derivative
        derivative = (error - self.previous_error) / dt
            
        # PD control output
        control_output = self.kp * error + self.kd * derivative
        
        # Update for next iteration
        self.previous_error = error
        self.previous_time = current_time
        
        return control_output, error, derivative
        
    def control_loop(self):
        """Main control loop - runs in separate thread"""
        print(f"[PD] Control loop started (Kp={self.kp}, Kd={self.kd}, deadband={self.deadband}°)")
        
        while self.running:
            try:
                control_output, error, derivative = self.calculate_control()
                
                # Apply deadband - don't move for small errors
                if abs(error) < self.deadband:
                    stop_motor_dc()
                    if abs(error) > 0.1:  # Only print if there's some error
                        print(f"[PD] In deadband: error={error:.1f}° (target reached)")
                    
                # Bang-bang control logic based on PD output
                elif control_output > 0:
                    # Need to rotate clockwise
                    rotate_clockwise_dc()
                    print(f"[PD] CW: error={error:.1f}°, derivative={derivative:.2f}, output={control_output:.2f}")
                    
                elif control_output < 0:
                    # Need to rotate counterclockwise  
                    rotate_counterclockwise_dc()
                    print(f"[PD] CCW: error={error:.1f}°, derivative={derivative:.2f}, output={control_output:.2f}")
                    
                else:
                    stop_motor_dc()
                    
                # Control loop timing
                time.sleep(1.0 / self.control_frequency)
                
            except Exception as e:
                print(f"[PD] Control loop error: {e}")
                stop_motor_dc()
                break
                
        print("[PD] Control loop stopped")
        
    def start_control(self):
        """Start the PD control loop"""
        if not self.running:
            self.running = True
            self.previous_time = time.time()  # Reset timing
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            print("[PD] Control started")
        else:
            print("[PD] Control already running")
            
    def stop_control(self):
        """Stop the PD control loop"""
        if self.running:
            self.running = False
            if self.control_thread:
                self.control_thread.join(timeout=2.0)
            stop_motor_dc()
            print("[PD] Control stopped")
        else:
            print("[PD] Control already stopped")
            
    def get_status(self):
        """Get current controller status"""
        return {
            "running": self.running,
            "target_angle": self.target_angle,
            "current_angle": self.current_angle,
            "error": self.target_angle - self.current_angle,
            "kp": self.kp,
            "kd": self.kd,
            "deadband": self.deadband
        }

# ── GLOBAL PD CONTROLLER INSTANCE ─────────────────────────
pd_controller = PDController(kp=1.0, kd=0.1, deadband=2.0)

# ── CONVENIENCE FUNCTIONS FOR EXTERNAL USE ────────────────
def start_pd_control(target_angle=0.0):
    """Start PD control to reach target angle"""
    pd_controller.set_target(target_angle)
    pd_controller.start_control()

def stop_pd_control():
    """Stop PD control"""
    pd_controller.stop_control()

def set_target_angle(angle):
    """Set new target angle"""
    pd_controller.set_target(angle)

def update_current_orientation(angle):
    """Update current orientation from sensors"""
    pd_controller.update_current_angle(angle)

def tune_controller(kp, kd, deadband=None):
    """Tune PD controller parameters"""
    pd_controller.set_gains(kp, kd)
    if deadband is not None:
        pd_controller.set_deadband(deadband)

def get_controller_status():
    """Get controller status"""
    return pd_controller.get_status()

# ── MANUAL TEST INTERFACE ─────────────────────────────────
if __name__ == "__main__":
    print("PD Motor Control Test Interface")
    print("Commands:")
    print("  manual           - Enter manual mode (cw/ccw/stop)")
    print("  pd <target>      - Start PD control to target angle")
    print("  stop             - Stop PD control")
    print("  angle <current>  - Update current angle")
    print("  tune <kp> <kd>   - Tune PD gains")
    print("  status           - Show controller status")
    print("  quit             - Exit")
    
    manual_mode = False
    
    try:
        while True:
            if manual_mode:
                cmd = input("manual> ").strip().lower().split()
            else:
                cmd = input("pd> ").strip().lower().split()
                
            if not cmd:
                continue
                
            if cmd[0] == "quit" or cmd[0] == "q":
                break
                
            elif cmd[0] == "manual":
                manual_mode = True
                pd_controller.stop_control()
                print("Entered manual mode. Use 'cw', 'ccw', 'stop', 'auto' to return")
                
            elif cmd[0] == "auto" and manual_mode:
                manual_mode = False
                print("Returned to PD control mode")
                
            elif manual_mode:
                # Manual control commands
                if cmd[0] == "cw":
                    rotate_clockwise_dc()
                elif cmd[0] == "ccw":
                    rotate_counterclockwise_dc()
                elif cmd[0] == "stop":
                    stop_motor_dc()
                else:
                    print("Manual commands: cw, ccw, stop, auto")
                    
            else:
                # PD control commands
                if cmd[0] == "pd" and len(cmd) == 2:
                    try:
                        target = float(cmd[1])
                        start_pd_control(target)
                    except ValueError:
                        print("Invalid target angle")
                        
                elif cmd[0] == "stop":
                    stop_pd_control()
                    
                elif cmd[0] == "angle" and len(cmd) == 2:
                    try:
                        current = float(cmd[1])
                        update_current_orientation(current)
                        print(f"Current angle updated to {current}°")
                    except ValueError:
                        print("Invalid angle")
                        
                elif cmd[0] == "tune" and len(cmd) == 3:
                    try:
                        kp = float(cmd[1])
                        kd = float(cmd[2])
                        tune_controller(kp, kd)
                    except ValueError:
                        print("Invalid gains")
                        
                elif cmd[0] == "status":
                    status = get_controller_status()
                    print(f"Running: {status['running']}")
                    print(f"Target: {status['target_angle']:.1f}°")
                    print(f"Current: {status['current_angle']:.1f}°")
                    print(f"Error: {status['error']:.1f}°")
                    print(f"Gains: Kp={status['kp']:.2f}, Kd={status['kd']:.2f}")
                    print(f"Deadband: {status['deadband']:.1f}°")
                    
                else:
                    print("Unknown command. Type 'quit' to exit.")
                    
    except KeyboardInterrupt:
        print("\nStopping...")
        
    finally:
        pd_controller.stop_control()
        cleanup()
        print("Cleanup complete.")
