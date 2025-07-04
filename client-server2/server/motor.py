#!/usr/bin/env python3
"""
🔧 MINIMAL MOTOR POWER CONTROL
Direct motor power control script - no ADCS controller needed
Send commands to set specific motor power levels
"""

import time
import sys

# Try to import GPIO directly
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("✓ GPIO available")
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ GPIO not available (simulation mode)")

# Motor control pins (from ADCS_PD.py)
IN1_PIN = 13    # Clockwise control
IN2_PIN = 19    # Counterclockwise control  
SLEEP_PIN = 26  # Motor driver enable
PWM_FREQUENCY = 1000  # Hz

class SimpleMotorController:
    """Minimal motor controller - direct GPIO control"""
    
    def __init__(self):
        self.motor_cw_pwm = None
        self.motor_ccw_pwm = None
        self.current_power = 0
        self.setup_motor()
    
    def setup_motor(self):
        """Initialize GPIO and PWM for motor control"""
        if not GPIO_AVAILABLE:
            print("🔧 Motor setup (simulation mode)")
            return True
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(IN1_PIN, GPIO.OUT)
            GPIO.setup(IN2_PIN, GPIO.OUT)
            GPIO.setup(SLEEP_PIN, GPIO.OUT)
            
            # Enable motor driver
            GPIO.output(SLEEP_PIN, GPIO.HIGH)
            
            # Initialize PWM
            self.motor_cw_pwm = GPIO.PWM(IN1_PIN, PWM_FREQUENCY)
            self.motor_ccw_pwm = GPIO.PWM(IN2_PIN, PWM_FREQUENCY)
            
            self.motor_cw_pwm.start(0)
            self.motor_ccw_pwm.start(0)
            
            print("✓ Motor hardware initialized")
            return True
            
        except Exception as e:
            print(f"❌ Motor setup failed: {e}")
            return False
    
    def set_power(self, power):
        """
        Set motor power directly
        Args:
            power: -100 to +100 (negative = CCW, positive = CW)
        """
        # Clamp power to valid range
        power = max(-100, min(100, power))
        self.current_power = power
        
        if not GPIO_AVAILABLE:
            print(f"🔧 Motor power set to: {power:+4d}% (simulation)")
            return
        
        try:
            if power > 0:
                # Clockwise rotation
                self.motor_ccw_pwm.ChangeDutyCycle(0)  # Stop CCW
                self.motor_cw_pwm.ChangeDutyCycle(abs(power))  # Set CW power
                direction = "CW"
            elif power < 0:
                # Counterclockwise rotation  
                self.motor_cw_pwm.ChangeDutyCycle(0)  # Stop CW
                self.motor_ccw_pwm.ChangeDutyCycle(abs(power))  # Set CCW power
                direction = "CCW"
            else:
                # Stop motor
                self.motor_cw_pwm.ChangeDutyCycle(0)
                self.motor_ccw_pwm.ChangeDutyCycle(0)
                direction = "STOP"
            
            print(f"🔧 Motor: {power:+4d}% ({direction})")
            
        except Exception as e:
            print(f"❌ Motor control error: {e}")
    
    def stop(self):
        """Stop motor and cleanup"""
        self.set_power(0)
        
        if GPIO_AVAILABLE and self.motor_cw_pwm and self.motor_ccw_pwm:
            try:
                self.motor_cw_pwm.stop()
                self.motor_ccw_pwm.stop()
                GPIO.output(SLEEP_PIN, GPIO.LOW)  # Disable motor driver
                GPIO.cleanup()
                print("✓ Motor stopped and GPIO cleaned up")
            except:
                pass

def show_commands():
    """Display available commands"""
    print("\n📋 MOTOR POWER COMMANDS:")
    print("  Direct power: Enter number -100 to +100")
    print("    Examples: 100, -50, 0, 75")
    print("  Quick commands:")
    print("    'max' or 'm'  = 100% CW")
    print("    'min' or 'n'  = 100% CCW") 
    print("    'stop' or 's' = 0% (stop)")
    print("    'help' or 'h' = Show commands")
    print("    'quit' or 'q' = Exit")
    print("=" * 40)

def main():
    """Minimal motor control interface"""
    print("🔧 MINIMAL MOTOR POWER CONTROL")
    print("=" * 40)
    print("Direct motor power control")
    print("No ADCS controller - just raw motor commands")
    print("=" * 40)
    
    # Initialize motor
    motor = SimpleMotorController()
    
    show_commands()
    
    try:
        while True:
            try:
                # Get user input
                cmd = input(f"\nMotor[{motor.current_power:+4d}%]> ").strip().lower()
                
                if cmd in ['quit', 'q', 'exit']:
                    print("👋 Exiting...")
                    break
                elif cmd in ['help', 'h', '?']:
                    show_commands()
                elif cmd in ['stop', 's']:
                    motor.set_power(0)
                elif cmd in ['max', 'm']:
                    motor.set_power(100)
                elif cmd in ['min', 'n']:
                    motor.set_power(-100)
                else:
                    # Try to parse as number
                    try:
                        power = int(cmd)
                        if -100 <= power <= 100:
                            motor.set_power(power)
                        else:
                            print(f"❌ Power must be -100 to +100, got: {power}")
                    except ValueError:
                        print(f"❌ Unknown command: '{cmd}' (type 'help' for commands)")
                        
            except EOFError:
                print("\n👋 EOF received, exiting...")
                break
                
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    finally:
        print("\n🛠️ Stopping motor...")
        motor.stop()
        print("✅ Done!")

if __name__ == "__main__":
    main()
