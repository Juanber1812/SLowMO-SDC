#!/usr/bin/env python3
"""
Simple Pitch PD Controller Test
Tests bang-bang motor control with MPU6050 pitch feedback
"""

import time
import sys
import threading
from mpu import MPU6050
from pd_bangbang import PDController, rotate_clockwise_dc, rotate_counterclockwise_dc, stop_motor_dc, cleanup

class SimplePitchController:
    def __init__(self):
        print("Initializing Simple Pitch Controller...")
        
        # Initialize MPU6050
        self.mpu = MPU6050()
        
        # Initialize PD Controller with conservative settings for testing
        self.pd = PDController(kp=0.5, kd=0.05, deadband=1.0)
        
        # Control state
        self.running = False
        self.control_thread = None
        
        print("Simple Pitch Controller ready!")
    
    def control_loop(self):
        """Simple control loop for pitch stabilization"""
        print(f"Starting pitch control - Target: {self.pd.target_angle}°")
        print("Press Ctrl+C to stop")
        
        while self.running:
            try:
                # Get current pitch angle
                data = self.mpu.read_all_data()
                current_pitch = data['angles']['pitch']
                
                # Update PD controller
                self.pd.update_current_angle(current_pitch)
                control_output, error, derivative = self.pd.calculate_control()
                
                # Bang-bang control logic
                if abs(error) < self.pd.deadband:
                    stop_motor_dc()
                    status = "STOP"
                elif control_output > 0:
                    rotate_clockwise_dc()
                    status = "CW"
                elif control_output < 0:
                    rotate_counterclockwise_dc()
                    status = "CCW"
                else:
                    stop_motor_dc()
                    status = "STOP"
                
                # Live display
                print(f"\\rPitch: {current_pitch:+6.2f}° | Target: {self.pd.target_angle:+6.2f}° | "
                      f"Error: {error:+5.2f}° | Control: {control_output:+6.2f} | Motor: {status:<4}", 
                      end='', flush=True)
                
                time.sleep(0.05)  # 20Hz control loop
                
            except Exception as e:
                print(f"\\nControl error: {e}")
                stop_motor_dc()
                break
        
        stop_motor_dc()
        print("\\nControl loop stopped")
    
    def start_control(self, target_angle=0.0):
        """Start pitch control"""
        if self.running:
            print("Control already running!")
            return
        
        self.pd.set_target(target_angle)
        self.running = True
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
        self.control_thread.start()
    
    def stop_control(self):
        """Stop control"""
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=2.0)
        stop_motor_dc()
    
    def set_target(self, angle):
        """Change target angle"""
        self.pd.set_target(angle)
        print(f"\\nTarget changed to {angle}°")
    
    def tune_gains(self, kp, kd):
        """Tune PD gains"""
        self.pd.set_gains(kp, kd)
        print(f"\\nGains updated: Kp={kp}, Kd={kd}")
    
    def calibrate_zero(self):
        """Set current position as zero reference"""
        self.mpu.calibrate_at_current_position()
        print("\\nCurrent position set as 0° reference")

def main():
    """Test interface"""
    print("="*60)
    print("🎯 SIMPLE PITCH PD CONTROLLER TEST")
    print("="*60)
    print("Commands:")
    print("  start <angle>    - Start control to target angle")
    print("  stop             - Stop control")
    print("  target <angle>   - Change target angle")
    print("  tune <kp> <kd>   - Tune PD gains")
    print("  zero             - Calibrate current position as 0°")
    print("  status           - Show current readings")
    print("  manual <cmd>     - Manual control (cw/ccw/stop)")
    print("  quit             - Exit")
    print("="*60)
    
    controller = SimplePitchController()
    
    try:
        while True:
            cmd = input("\\nPitch> ").strip().split()
            
            if not cmd:
                continue
            
            if cmd[0] == "quit" or cmd[0] == "q":
                break
            
            elif cmd[0] == "start":
                target = 0.0
                if len(cmd) == 2:
                    try:
                        target = float(cmd[1])
                    except ValueError:
                        print("Invalid angle")
                        continue
                controller.start_control(target)
            
            elif cmd[0] == "stop":
                controller.stop_control()
            
            elif cmd[0] == "target" and len(cmd) == 2:
                try:
                    angle = float(cmd[1])
                    controller.set_target(angle)
                except ValueError:
                    print("Invalid angle")
            
            elif cmd[0] == "tune" and len(cmd) == 3:
                try:
                    kp = float(cmd[1])
                    kd = float(cmd[2])
                    controller.tune_gains(kp, kd)
                except ValueError:
                    print("Invalid gains")
            
            elif cmd[0] == "zero":
                controller.calibrate_zero()
            
            elif cmd[0] == "status":
                data = controller.mpu.read_all_data()
                angles = data['angles']
                print(f"\\nCurrent Status:")
                print(f"  Pitch: {angles['pitch']:+6.2f}°")
                print(f"  Roll:  {angles['roll']:+6.2f}°")
                print(f"  Yaw:   {angles['yaw']:+6.2f}°")
                print(f"  Target: {controller.pd.target_angle:+6.2f}°")
                print(f"  PD Gains: Kp={controller.pd.kp:.3f}, Kd={controller.pd.kd:.3f}")
                print(f"  Deadband: {controller.pd.deadband:.1f}°")
                print(f"  Running: {controller.running}")
            
            elif cmd[0] == "manual" and len(cmd) == 2:
                controller.stop_control()
                if cmd[1] == "cw":
                    rotate_clockwise_dc()
                    print("Manual CW rotation")
                elif cmd[1] == "ccw":
                    rotate_counterclockwise_dc()
                    print("Manual CCW rotation")
                elif cmd[1] == "stop":
                    stop_motor_dc()
                    print("Manual stop")
                else:
                    print("Manual commands: cw, ccw, stop")
            
            else:
                print("Unknown command")
    
    except KeyboardInterrupt:
        print("\\nInterrupted...")
    
    finally:
        controller.stop_control()
        cleanup()
        print("Test complete!")

if __name__ == "__main__":
    main()
