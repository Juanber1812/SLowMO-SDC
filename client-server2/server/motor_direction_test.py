#!/usr/bin/env python3
"""
Quick Motor Direction Test for MP6550
Verify clockwise/counterclockwise directions are correct
"""

import RPi.GPIO as GPIO
import time

# ── PIN SETUP ─────────────────────────────────────────────
IN1_PIN = 19  # Motor direction control 1
IN2_PIN = 13  # Motor direction control 2
SLEEP_PIN = 26  # Sleep/standby pin

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(IN1_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(IN2_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(SLEEP_PIN, GPIO.OUT, initial=GPIO.HIGH)

def rotate_clockwise():
    """Clockwise: IN1=HIGH, IN2=LOW"""
    print("🔄 Clockwise rotation (IN1=HIGH, IN2=LOW)")
    GPIO.output(IN1_PIN, GPIO.HIGH)
    GPIO.output(IN2_PIN, GPIO.LOW)

def rotate_counterclockwise():
    """Counterclockwise: IN1=LOW, IN2=HIGH"""
    print("🔄 Counterclockwise rotation (IN1=LOW, IN2=HIGH)")
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.HIGH)

def stop_motor():
    """Stop: IN1=LOW, IN2=LOW"""
    print("⏹️  Motor stopped (IN1=LOW, IN2=LOW)")
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.LOW)

def cleanup():
    stop_motor()
    GPIO.cleanup()
    print("🧹 GPIO cleanup complete")

def main():
    """Test motor directions"""
    print("🔧 MP6550 Motor Direction Test")
    print("=" * 40)
    print("Commands:")
    print("  cw    - Clockwise rotation")
    print("  ccw   - Counterclockwise rotation") 
    print("  stop  - Stop motor")
    print("  test  - Auto test sequence")
    print("  quit  - Exit")
    print("=" * 40)
    
    try:
        while True:
            cmd = input("\\nMotor> ").strip().lower()
            
            if cmd == "quit" or cmd == "q":
                break
            elif cmd == "cw":
                rotate_clockwise()
            elif cmd == "ccw":
                rotate_counterclockwise()
            elif cmd == "stop":
                stop_motor()
            elif cmd == "test":
                print("\\n🧪 Starting auto test sequence...")
                
                print("1. Clockwise for 2 seconds")
                rotate_clockwise()
                time.sleep(2)
                
                print("2. Stop for 1 second")
                stop_motor()
                time.sleep(1)
                
                print("3. Counterclockwise for 2 seconds")
                rotate_counterclockwise()
                time.sleep(2)
                
                print("4. Stop")
                stop_motor()
                print("✅ Test sequence complete!")
                
            elif cmd == "status":
                in1_state = GPIO.input(IN1_PIN)
                in2_state = GPIO.input(IN2_PIN)
                print(f"\\n📊 Pin Status:")
                print(f"  IN1_PIN (19): {in1_state}")
                print(f"  IN2_PIN (13): {in2_state}")
                
                if in1_state == 1 and in2_state == 0:
                    print("  Direction: Clockwise")
                elif in1_state == 0 and in2_state == 1:
                    print("  Direction: Counterclockwise")
                elif in1_state == 0 and in2_state == 0:
                    print("  Direction: Stopped")
                else:
                    print("  Direction: ⚠️  INVALID (both pins high!)")
                    
            else:
                print("Unknown command. Use: cw, ccw, stop, test, quit")
                
    except KeyboardInterrupt:
        print("\\n\\nInterrupted...")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
