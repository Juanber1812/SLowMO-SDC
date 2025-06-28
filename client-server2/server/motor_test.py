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
    time.sleep(0.01)  # Small delay after direction change
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")
    
    # Check if pins are actually set correctly
    dir_state = GPIO.input(DIR_PIN)
    enable_state = GPIO.input(ENABLE_PIN)
    if dir_state != 1 or enable_state != 1:
        print(f"[WARNING] Expected DIR=1, ENABLE=1 but got DIR={dir_state}, ENABLE={enable_state}")

def test_ccw_hold():
    """Test holding CCW for extended time to see what happens."""
    print("[TEST] Testing CCW hold for 5 seconds...")
    rotate_counterclockwise_dc()
    
    for i in range(50):  # Check every 0.1 seconds for 5 seconds
        time.sleep(0.1)
        dir_state = GPIO.input(DIR_PIN)
        enable_state = GPIO.input(ENABLE_PIN)
        print(f"[{i*0.1:.1f}s] DIR={dir_state}, ENABLE={enable_state}", end='\r')
        
        if dir_state != 1 or enable_state != 1:
            print(f"\n[ERROR] Pin states changed unexpectedly at {i*0.1:.1f}s!")
            break
    
    print(f"\n[TEST] CCW hold test complete")
    stop_motor_dc()

def test_pin_toggling():
    """Test rapid pin toggling to check for hardware issues."""
    print("[TEST] Testing rapid pin toggling...")
    
    # Test DIR pin
    print("Testing DIR pin...")
    for i in range(10):
        GPIO.output(DIR_PIN, GPIO.HIGH)
        time.sleep(0.1)
        print(f"DIR HIGH: {GPIO.input(DIR_PIN)}")
        GPIO.output(DIR_PIN, GPIO.LOW)
        time.sleep(0.1)
        print(f"DIR LOW: {GPIO.input(DIR_PIN)}")
    
    # Test ENABLE pin
    print("Testing ENABLE pin...")
    for i in range(10):
        GPIO.output(ENABLE_PIN, GPIO.HIGH)
        time.sleep(0.1)
        print(f"ENABLE HIGH: {GPIO.input(ENABLE_PIN)}")
        GPIO.output(ENABLE_PIN, GPIO.LOW)
        time.sleep(0.1)
        print(f"ENABLE LOW: {GPIO.input(ENABLE_PIN)}")
    
    # Reset to safe state
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    print("[TEST] Pin toggling test complete")

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
    print("Motor Test - Commands:")
    print("  'cw'     - Clockwise rotation")
    print("  'ccw'    - Counterclockwise rotation")
    print("  'stop'   - Stop motor")
    print("  'estop'  - Emergency stop")
    print("  'hold'   - Test CCW hold for 5 seconds")
    print("  'pins'   - Test pin toggling")
    print("  'quit'   - Exit")
    
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
            elif cmd=="hold":
                test_ccw_hold()
            elif cmd=="pins":
                test_pin_toggling()
            elif cmd in ("q","quit","exit"):
                break
            else:
                print("Unknown command")
    finally:
        cleanup()