import RPi.GPIO as GPIO
import time

# ── PIN SETUP ─────────────────────────────────────────────
# adjust these to match your wiring
IN1_PIN = 19  # Was DIR_PIN
IN2_PIN = 13  # Was ENABLE_PIN
SLEEP_PIN  = 26   # standby (if your MP6550 uses it)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(IN1_PIN,    GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(IN2_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(SLEEP_PIN,  GPIO.OUT, initial=GPIO.HIGH)

# Clockwise: IN1=HIGH, IN2=LOW
def rotate_clockwise_dc():
    """Full DC forward."""
    print("[MOTOR] Starting clockwise rotation")
    GPIO.output(IN1_PIN, GPIO.HIGH)
    GPIO.output(IN2_PIN, GPIO.LOW)
    print(f"[MOTOR] IN1_PIN={GPIO.input(IN1_PIN)}, IN2_PIN={GPIO.input(IN2_PIN)}")

# Counterclockwise: IN1=LOW, IN2=HIGH  
def rotate_counterclockwise_dc():
    """Full DC reverse."""
    print("[MOTOR] Starting counterclockwise rotation")
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.HIGH)
    print(f"[MOTOR] IN1_PIN={GPIO.input(IN1_PIN)}, IN2_PIN={GPIO.input(IN2_PIN)}")

# Stop: IN1=LOW, IN2=LOW
def stop_motor_dc():
    """Disable driver (0 V to motor)."""
    print("[MOTOR] Stopping motor")
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.LOW)
    print(f"[MOTOR] IN1_PIN={GPIO.input(IN1_PIN)}, IN2_PIN={GPIO.input(IN2_PIN)}")

def cleanup():
    stop_motor_dc()
    GPIO.cleanup()

# ── MANUAL TEST REPL ────────────────────────────────────────
if __name__=="__main__":
    print("cmd> 'cw','ccw','stop','quit'")
    try:
        while True:
            cmd = input("cmd> ").strip().lower()
            if cmd=="cw":
                rotate_clockwise_dc()
            elif cmd=="ccw":
                rotate_counterclockwise_dc()
            elif cmd=="stop":
                stop_motor_dc()
            elif cmd in ("q","quit","exit"):
                break
            else:
                print("Unknown")
    finally:
        cleanup()