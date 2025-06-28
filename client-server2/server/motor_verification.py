#!/usr/bin/env python3
"""
MP6550 Motor Driver Verification Script
Systematic test to verify correct motor operation and driver logic
"""

import RPi.GPIO as GPIO
import time
import sys

# Pin configuration - update these to match your wiring
IN1_PIN = 19    # MP6550 IN1
IN2_PIN = 13    # MP6550 IN2
SLEEP_PIN = 26  # MP6550 SLEEP/STBY (optional)

class MotorTester:
    def __init__(self):
        self.setup_gpio()
        
    def setup_gpio(self):
        """Initialize GPIO pins"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        GPIO.setup(IN1_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(IN2_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(SLEEP_PIN, GPIO.OUT, initial=GPIO.HIGH)  # Enable driver
        
        print("✓ GPIO initialized")
        print(f"  IN1 (Pin {IN1_PIN}): {GPIO.input(IN1_PIN)}")
        print(f"  IN2 (Pin {IN2_PIN}): {GPIO.input(IN2_PIN)}")
        print(f"  SLEEP (Pin {SLEEP_PIN}): {GPIO.input(SLEEP_PIN)}")
    
    def clockwise(self):
        """Rotate clockwise: IN1=HIGH, IN2=LOW"""
        print("\n[TEST] Clockwise rotation")
        GPIO.output(IN1_PIN, GPIO.HIGH)
        GPIO.output(IN2_PIN, GPIO.LOW)
        print(f"  IN1={GPIO.input(IN1_PIN)}, IN2={GPIO.input(IN2_PIN)}")
        print("  Expected: Motor spins clockwise")
    
    def counterclockwise(self):
        """Rotate counterclockwise: IN1=LOW, IN2=HIGH"""
        print("\n[TEST] Counterclockwise rotation")
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.HIGH)
        print(f"  IN1={GPIO.input(IN1_PIN)}, IN2={GPIO.input(IN2_PIN)}")
        print("  Expected: Motor spins counterclockwise")
    
    def stop(self):
        """Stop motor: IN1=LOW, IN2=LOW"""
        print("\n[TEST] Stop motor")
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.LOW)
        print(f"  IN1={GPIO.input(IN1_PIN)}, IN2={GPIO.input(IN2_PIN)}")
        print("  Expected: Motor stops")
    
    def brake(self):
        """Brake motor: IN1=HIGH, IN2=HIGH"""
        print("\n[TEST] Brake motor")
        GPIO.output(IN1_PIN, GPIO.HIGH)
        GPIO.output(IN2_PIN, GPIO.HIGH)
        print(f"  IN1={GPIO.input(IN1_PIN)}, IN2={GPIO.input(IN2_PIN)}")
        print("  Expected: Motor brakes (high resistance)")
    
    def sleep_mode(self, enable):
        """Enable/disable driver sleep mode"""
        state = GPIO.HIGH if enable else GPIO.LOW
        GPIO.output(SLEEP_PIN, state)
        print(f"\n[TEST] Driver {'enabled' if enable else 'disabled'}")
        print(f"  SLEEP={GPIO.input(SLEEP_PIN)}")
    
    def systematic_test(self):
        """Run systematic motor test sequence"""
        print("\n" + "="*60)
        print("MP6550 SYSTEMATIC MOTOR TEST")
        print("="*60)
        print("This will test all motor states systematically.")
        print("Observe the motor and verify expected behavior.")
        print("Press Ctrl+C to stop at any time.")
        
        input("\nPress Enter to start test...")
        
        try:
            # Test 1: Ensure driver is enabled
            print(f"\n{'='*40}")
            print("TEST 1: Driver Enable")
            print("="*40)
            self.sleep_mode(True)
            time.sleep(1)
            
            # Test 2: Clockwise rotation
            print(f"\n{'='*40}")
            print("TEST 2: Clockwise Rotation")
            print("="*40)
            self.clockwise()
            input("Press Enter after observing motor direction...")
            
            # Test 3: Stop
            print(f"\n{'='*40}")
            print("TEST 3: Stop")
            print("="*40)
            self.stop()
            time.sleep(2)
            
            # Test 4: Counterclockwise rotation
            print(f"\n{'='*40}")
            print("TEST 4: Counterclockwise Rotation")
            print("="*40)
            self.counterclockwise()
            input("Press Enter after observing motor direction...")
            
            # Test 5: Brake
            print(f"\n{'='*40}")
            print("TEST 5: Brake")
            print("="*40)
            self.brake()
            time.sleep(2)
            
            # Test 6: Stop again
            print(f"\n{'='*40}")
            print("TEST 6: Final Stop")
            print("="*40)
            self.stop()
            
            # Test 7: Driver disable
            print(f"\n{'='*40}")
            print("TEST 7: Driver Disable")
            print("="*40)
            self.sleep_mode(False)
            time.sleep(1)
            self.sleep_mode(True)  # Re-enable for cleanup
            
            print(f"\n{'='*60}")
            print("SYSTEMATIC TEST COMPLETE")
            print("="*60)
            print("Expected results:")
            print("• Test 2: Motor spins clockwise")
            print("• Test 3: Motor stops freely")
            print("• Test 4: Motor spins counterclockwise")
            print("• Test 5: Motor stops with resistance (brake)")
            print("• Test 6: Motor stops freely")
            print("• Test 7: Motor disabled, then re-enabled")
            
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
        finally:
            self.cleanup()
    
    def interactive_test(self):
        """Interactive motor test"""
        print("\n" + "="*60)
        print("MP6550 INTERACTIVE MOTOR TEST")
        print("="*60)
        print("Commands:")
        print("  cw    - Clockwise rotation")
        print("  ccw   - Counterclockwise rotation") 
        print("  stop  - Stop motor")
        print("  brake - Brake motor")
        print("  sleep - Toggle driver enable")
        print("  quit  - Exit")
        print("="*60)
        
        try:
            while True:
                cmd = input("\nmotor> ").strip().lower()
                
                if cmd == "cw":
                    self.clockwise()
                elif cmd == "ccw":
                    self.counterclockwise()
                elif cmd == "stop":
                    self.stop()
                elif cmd == "brake":
                    self.brake()
                elif cmd == "sleep":
                    current = GPIO.input(SLEEP_PIN)
                    self.sleep_mode(not current)
                elif cmd in ("q", "quit", "exit"):
                    break
                elif cmd == "help":
                    print("Commands: cw, ccw, stop, brake, sleep, quit")
                else:
                    print("Unknown command. Type 'help' for commands.")
                    
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean shutdown"""
        print("\n[CLEANUP] Stopping motor and cleaning up GPIO")
        self.stop()
        time.sleep(0.5)
        GPIO.cleanup()
        print("✓ GPIO cleaned up")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Automatic systematic test
        tester = MotorTester()
        tester.systematic_test()
    else:
        # Interactive test
        tester = MotorTester()
        tester.interactive_test()

if __name__ == "__main__":
    main()
