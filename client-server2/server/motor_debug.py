import RPi.GPIO as GPIO
import time

# ── PIN SETUP ─────────────────────────────────────────────
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
    time.sleep(0.01)  # Small delay after direction change
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def rotate_counterclockwise_dc():
    """Full DC reverse."""
    print("[MOTOR] Starting counterclockwise rotation")
    GPIO.output(DIR_PIN, GPIO.HIGH)
    time.sleep(0.01)  # Small delay after direction change
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def stop_motor_dc():
    """Disable driver (0 V to motor) - Enhanced version."""
    print("[MOTOR] Stopping motor")
    
    # Method 1: Disable first, then reset direction
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    time.sleep(0.01)  # Small delay
    GPIO.output(DIR_PIN, GPIO.LOW)  # Reset direction to default
    
    print(f"[MOTOR] DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}")

def emergency_stop():
    """Emergency stop with full reset."""
    print("[MOTOR] EMERGENCY STOP - Full reset")
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(SLEEP_PIN, GPIO.LOW)  # Put driver to sleep
    time.sleep(0.1)
    GPIO.output(SLEEP_PIN, GPIO.HIGH)  # Wake up driver
    print(f"[MOTOR] After reset: DIR_PIN={GPIO.input(DIR_PIN)}, ENABLE_PIN={GPIO.input(ENABLE_PIN)}, SLEEP_PIN={GPIO.input(SLEEP_PIN)}")

def test_sequence():
    """Test sequence to identify the issue."""
    print("\n=== MOTOR DRIVER TEST SEQUENCE ===")
    
    print("\n1. Testing clockwise rotation...")
    rotate_clockwise_dc()
    time.sleep(2)
    stop_motor_dc()
    time.sleep(1)
    
    print("\n2. Testing counterclockwise rotation...")
    rotate_counterclockwise_dc()
    time.sleep(2)
    stop_motor_dc()
    time.sleep(1)
    
    print("\n3. Testing rapid direction changes...")
    for i in range(3):
        print(f"\nCycle {i+1}:")
        rotate_clockwise_dc()
        time.sleep(0.5)
        stop_motor_dc()
        time.sleep(0.1)
        rotate_counterclockwise_dc()
        time.sleep(0.5)
        stop_motor_dc()
        time.sleep(0.1)
    
    print("\n4. Final emergency stop...")
    emergency_stop()

def voltage_test():
    """Test GPIO voltage levels with multimeter."""
    print("\n=== GPIO VOLTAGE TEST ===")
    print("Use a multimeter to check these voltages:")
    
    print("\nTesting DIR_PIN (GPIO 19)...")
    GPIO.output(DIR_PIN, GPIO.LOW)
    print("DIR_PIN = LOW - Check voltage (should be ~0V)")
    input("Press Enter when measured...")
    
    GPIO.output(DIR_PIN, GPIO.HIGH)
    print("DIR_PIN = HIGH - Check voltage (should be ~3.3V)")
    input("Press Enter when measured...")
    
    print("\nTesting ENABLE_PIN (GPIO 13)...")
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    print("ENABLE_PIN = LOW - Check voltage (should be ~0V)")
    input("Press Enter when measured...")
    
    GPIO.output(ENABLE_PIN, GPIO.HIGH)
    print("ENABLE_PIN = HIGH - Check voltage (should be ~3.3V)")
    input("Press Enter when measured...")
    
    # Reset to safe state
    GPIO.output(ENABLE_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)

def cleanup():
    emergency_stop()
    GPIO.cleanup()

# ── ENHANCED MANUAL TEST REPL ────────────────────────────────────────
if __name__=="__main__":
    print("Enhanced Motor Test - Troubleshooting CCW Stop Issue")
    print("Commands:")
    print("  'cw'    - Clockwise rotation")
    print("  'ccw'   - Counterclockwise rotation") 
    print("  'stop'  - Normal stop")
    print("  'estop' - Emergency stop (full reset)")
    print("  'test'  - Run test sequence")
    print("  'volt'  - Voltage test (needs multimeter)")
    print("  'quit'  - Exit")
    
    try:
        while True:
            cmd = input("\ncmd> ").strip().lower()
            if cmd=="cw":
                rotate_clockwise_dc()
            elif cmd=="ccw":
                rotate_counterclockwise_dc()
            elif cmd=="stop":
                stop_motor_dc()
            elif cmd=="estop":
                emergency_stop()
            elif cmd=="test":
                test_sequence()
            elif cmd=="volt":
                voltage_test()
            elif cmd in ("q","quit","exit"):
                break
            else:
                print("Unknown command")
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cleanup()
        print("Cleanup complete")
