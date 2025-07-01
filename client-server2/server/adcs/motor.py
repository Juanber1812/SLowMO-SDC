import time

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: RPi.GPIO not available — motor control disabled")
    GPIO_AVAILABLE = False

# GPIO pin definitions (BCM mode)
IN1_PIN = 13    # Clockwise
IN2_PIN = 19    # Counterclockwise
SLEEP_PIN = 26  # Motor driver enable

def setup_motor_control():
    """Initializes GPIO pins for motor control."""
    if not GPIO_AVAILABLE:
        return False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup([IN1_PIN, IN2_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
        enable_driver()
        print("✓ Motor control GPIO initialized")
        return True
    except Exception as e:
        print(f"✗ Motor control GPIO initialization failed: {e}")
        return False

def enable_driver():
    """Enable the motor driver by setting SLEEP_PIN high."""
    if GPIO_AVAILABLE:
        GPIO.output(SLEEP_PIN, GPIO.HIGH)

def disable_driver():
    """Disable the motor driver by setting SLEEP_PIN low."""
    if GPIO_AVAILABLE:
        GPIO.output(SLEEP_PIN, GPIO.LOW)

def rotate_clockwise():
    """Rotates motor clockwise."""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.HIGH)
        GPIO.output(IN2_PIN, GPIO.LOW)
        time.sleep(0.001)

def rotate_counterclockwise():
    """Rotates motor counterclockwise."""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.HIGH)
        time.sleep(0.001)

def stop_motor():
    """Stops the motor."""
    if GPIO_AVAILABLE:
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.LOW)
        time.sleep(0.001)

def cleanup_motor_control():
    """Cleans up GPIO resources."""
    if GPIO_AVAILABLE:
        stop_motor()
        disable_driver()
        GPIO.cleanup()
