#!/usr/bin/env python3
"""
🔧 SIMPLE MOTOR POWER MONITOR
Lightweight script to quickly test and display motor power output
"""

import time
import sys
import os
from datetime import datetime

# Add the server directory to path
sys.path.append(os.path.dirname(__file__))

try:
    from ADCS_PD import ADCSController, rotate_clockwise, rotate_counterclockwise, stop_motor
    print("✓ Motor functions imported")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def display_motor_status(controller):
    """Display live motor power and system status"""
    if not controller:
        print("No controller available")
        return
    
    data, _ = controller.get_current_data()
    
    current_yaw = data['mpu']['yaw']
    target_yaw = data['controller']['target_yaw']
    error = data['controller']['error']
    motor_power = data['controller']['motor_power']
    ctrl_enabled = data['controller']['enabled']
    
    # Status indicators
    ctrl_status = "ON " if ctrl_enabled else "OFF"
    direction = "CW " if motor_power > 0 else "CCW" if motor_power < 0 else "---"
    
    # Create status line
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = (
        f"[{timestamp}] 🔧 MOTOR: {motor_power:+4.0f}% ({direction}) | "
        f"Controller: {ctrl_status} | "
        f"Yaw: {current_yaw:+7.1f}° → {target_yaw:+7.1f}° | "
        f"Error: {error:+6.1f}°"
    )
    
    print(f"\r{status:<100}", end="", flush=True)

def main():
    """Simple motor power monitor"""
    print("🔧 SIMPLE MOTOR POWER MONITOR")
    print("=" * 50)
    print("Commands:")
    print("  'a' = Manual CW (100%)")
    print("  'f' = Manual CCW (-100%)")  
    print("  'x' = Stop motor (0%)")
    print("  'g' = Start PD controller")
    print("  's' = Stop PD controller")
    print("  't' = Set target angle")
    print("  'q' = Quit")
    print("=" * 50)
    
    # Initialize controller
    print("Initializing controller...")
    controller = ADCSController()
    time.sleep(2.0)
    print("✓ Ready! Live motor power display:")
    print("-" * 50)
    
    try:
        import select  # For non-blocking input on Unix-like systems
        
        while True:
            # Display live status
            display_motor_status(controller)
            
            # Check for user input (non-blocking)
            if select.select([sys.stdin], [], [], 0.1)[0]:
                command = sys.stdin.read(1).lower().strip()
                print()  # New line after status
                
                if command == 'q':
                    print("Shutting down...")
                    break
                elif command == 'a':
                    print("🔄 Manual CW (100% power)")
                    rotate_clockwise()
                elif command == 'f':
                    print("🔄 Manual CCW (-100% power)")
                    rotate_counterclockwise()
                elif command == 'x':
                    print("⏹️ Stop motor (0% power)")
                    stop_motor()
                elif command == 'g':
                    print("▶️ Start PD controller")
                    controller.start_auto_control('Test')
                elif command == 's':
                    print("⏹️ Stop PD controller")
                    controller.stop_auto_control()
                elif command == 't':
                    try:
                        target = float(input("Enter target angle: "))
                        controller.set_target_yaw(target)
                        print(f"🎯 Target set to {target}°")
                    except:
                        print("❌ Invalid angle")
                else:
                    print(f"Unknown command: '{command}'")
            
            time.sleep(0.05)  # 20Hz update rate
                
    except ImportError:
        # Fallback for Windows (no select module)
        print("Windows detected - using simple input mode")
        print("Enter commands and press Enter:")
        
        while True:
            display_motor_status(controller)
            time.sleep(0.2)
            
            # Simple blocking input for Windows
            try:
                command = input("\nCommand: ").lower().strip()
                
                if command == 'q':
                    break
                elif command == 'a':
                    print("🔄 Manual CW")
                    rotate_clockwise()
                elif command == 'f':
                    print("🔄 Manual CCW")
                    rotate_counterclockwise()
                elif command == 'x':
                    print("⏹️ Stop")
                    stop_motor()
                elif command == 'g':
                    print("▶️ Start PD")
                    controller.start_auto_control('Test')
                elif command == 's':
                    print("⏹️ Stop PD")
                    controller.stop_auto_control()
                elif command == 't':
                    try:
                        target = float(input("Target angle: "))
                        controller.set_target_yaw(target)
                        print(f"🎯 Target: {target}°")
                    except:
                        print("❌ Invalid")
            except KeyboardInterrupt:
                break
                
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
    finally:
        print("\n🛠️ Shutting down...")
        controller.shutdown()
        print("✅ Done!")

if __name__ == "__main__":
    main()
