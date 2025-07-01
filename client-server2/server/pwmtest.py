import time

# --- GPIO SETUP ---
# Attempt to import the RPi.GPIO library. If it fails, create a mock object.
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    print("⚠️ WARNING: RPi.GPIO library not found. Using a mock library for testing.")
    GPIO_AVAILABLE = False
    # Create a mock GPIO object to allow the script to run on a non-Pi machine
    class MockGPIO:
        BCM = 11
        OUT = 1
        LOW = 0
        HIGH = 1
        def setmode(self, mode): print(f"[MOCK] GPIO mode set to {mode}")
        def setwarnings(self, state): print(f"[MOCK] GPIO warnings set to {state}")
        def setup(self, pins, mode, initial): print(f"[MOCK] Pins {pins} setup as OUT")
        def output(self, pin, state): print(f"[MOCK] Pin {pin} set to {state}")
        def cleanup(self): print("[MOCK] GPIO cleaned up")
        class PWM:
            def __init__(self, pin, freq): self.pin, self.freq = pin, freq; print(f"[MOCK] PWM created on pin {pin} at {freq}Hz")
            def start(self, duty_cycle): print(f"[MOCK] PWM on pin {self.pin} started at {duty_cycle}% duty cycle")
            def ChangeDutyCycle(self, dc): print(f"[MOCK] PWM on pin {self.pin} changed to {dc}% duty cycle")
            def stop(self): print(f"[MOCK] PWM on pin {self.pin} stopped")
    GPIO = MockGPIO()

# --- PIN CONFIGURATION ---
# These pins correspond to the motor driver inputs
IN1_PIN = 13    # Clockwise control pin
IN2_PIN = 19    # Counter-clockwise control pin
SLEEP_PIN = 26  # Motor driver enable/sleep pin
PWM_FREQUENCY = 1000 # Hz (1kHz for smoother motor control)

# Global PWM object variables
motor_cw_pwm = None
motor_ccw_pwm = None

def setup_gpio():
    """Initializes GPIO pins and creates PWM objects."""
    global motor_cw_pwm, motor_ccw_pwm
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup([IN1_PIN, IN2_PIN, SLEEP_PIN], GPIO.OUT, initial=GPIO.LOW)
    
    # Create PWM instances for each direction
    motor_cw_pwm = GPIO.PWM(IN1_PIN, PWM_FREQUENCY)
    motor_ccw_pwm = GPIO.PWM(IN2_PIN, PWM_FREQUENCY)
    
    # Start PWM with 0% duty cycle (motor is off)
    motor_cw_pwm.start(0)
    motor_ccw_pwm.start(0)
    
    # Enable the motor driver
    GPIO.output(SLEEP_PIN, GPIO.HIGH)
    print("✅ GPIO and PWM initialized. Motor driver is active.")

def set_motor_power(power):
    """
    Sets the motor power and direction using PWM.
    - power: A value from -100 (full CCW) to 100 (full CW).
    """
    # Clamp the power value to be within the -100 to 100 range
    power = max(-100, min(100, power))

    if power > 0:  # Clockwise
        motor_ccw_pwm.ChangeDutyCycle(0)
        motor_cw_pwm.ChangeDutyCycle(power)
        print(f"🔄 Rotating Clockwise at {power}% power.")
    elif power < 0:  # Counter-clockwise
        motor_cw_pwm.ChangeDutyCycle(0)
        motor_ccw_pwm.ChangeDutyCycle(abs(power))
        print(f"🔄 Rotating Counter-Clockwise at {abs(power)}% power.")
    else:  # Stop
        motor_cw_pwm.ChangeDutyCycle(0)
        motor_ccw_pwm.ChangeDutyCycle(0)
        print("⏹️ Motor stopped.")

def cleanup_gpio():
    """Stops PWM and cleans up GPIO resources."""
    try:
        if motor_cw_pwm:
            motor_cw_pwm.stop()
        if motor_ccw_pwm:
            motor_ccw_pwm.stop()
        GPIO.output(SLEEP_PIN, GPIO.LOW)  # Disable motor driver
        GPIO.cleanup()
        print("✅ GPIO cleaned up and motor driver disabled.")
    except:
        pass

def run_motor_test():
    """Run automatic motor test sequence."""
    print("\n🔄 Running automatic motor test...")
    
    # Test clockwise at different speeds
    for speed in [25, 50, 75, 100]:
        print(f"Testing CW at {speed}%...")
        set_motor_power(speed)
        time.sleep(2)
    
    # Stop
    set_motor_power(0)
    time.sleep(1)
    
    # Test counter-clockwise at different speeds
    for speed in [-25, -50, -75, -100]:
        print(f"Testing CCW at {abs(speed)}%...")
        set_motor_power(speed)
        time.sleep(2)
    
    # Stop
    set_motor_power(0)
    print("✅ Automatic test complete!")

def main():
    """Main loop to get user input and control the motor."""
    print("\n=== PWM Motor Test ===")
    print("Commands:")
    print("  Enter power: -100 to 100 (negative = CCW, positive = CW)")
    print("  'test' or 't' = Run automatic test sequence")
    print("  'quit' or 'q' = Exit program")
    print("  '0' = Stop motor")
    
    while True:
        try:
            user_input = input("\nEnter command: ").strip().lower()
            
            if user_input in ['q', 'quit', 'exit']:
                break
            elif user_input in ['test', 't']:
                run_motor_test()
            else:
                power_level = int(user_input)
                if -100 <= power_level <= 100:
                    set_motor_power(power_level)
                else:
                    print("❌ Power must be between -100 and 100")
                
        except ValueError:
            print("❌ Invalid input. Enter a number, 'test', or 'quit'")
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            break

if __name__ == "__main__":
    try:
        setup_gpio()
        main()
    except Exception as e:
        print(f"❌ Setup error: {e}")
    finally:
        print("\n🔄 Cleaning up...")
        cleanup_gpio()
        print("👋 Program ended")