import RPi.GPIO as GPIO
import time

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
    """Disable driver (0 V to motor) - Enhanced for CCW stop issue."""
    print("[MOTOR] Stopping motor")
    
    # Enhanced stop sequence for better CCW stopping
    GPIO.output(ENABLE_PIN, GPIO.LOW)    # Disable motor first
    time.sleep(0.01)                     # Small delay
    GPIO.output(DIR_PIN, GPIO.LOW)       # Reset direction to default
    
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def emergency_stop():
    """Emergency stop with full driver reset."""
    print("[MOTOR] EMERGENCY STOP")
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(SLEEP_PIN, GPIO.LOW)     # Sleep the driver
    time.sleep(0.05)
    GPIO.output(SLEEP_PIN, GPIO.HIGH)    # Wake up driver
    print(f"[MOTOR] Reset complete: DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def cleanup():
    emergency_stop()  # Use emergency stop for cleanup
    GPIO.cleanup()

# ── MANUAL TEST REPL ────────────────────────────────────────
if __name__=="__main__":
    print("Motor Test - Commands: 'cw','ccw','stop','estop','quit'")
    try:
        while True:
            cmd = input("cmd> ").strip().lower()
            if cmd=="cw":
                rotate_clockwise_dc()
            elif cmd=="ccw":
                rotate_counterclockwise_dc()
            elif cmd=="stop":
                stop_motor_dc()
            elif cmd=="estop":
                emergency_stop()
            elif cmd in ("q","quit","exit"):
                break
            else:
                print("Unknown command")
    finally:
        cleanup()