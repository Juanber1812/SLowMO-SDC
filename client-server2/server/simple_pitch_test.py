#!/usr/bin/env python3
"""
Simple Yaw PD Controller Test (Primary Control Angle)
Tests bang-bang motor control with MPU6050 yaw feedback for horizontal stabilization
"""

import time
import sys
import threading
from mpu import MPU6050
from pd_bangbang import PDController, rotate_clockwise_dc, rotate_counterclockwise_dc, stop_motor_dc, cleanup

class SimpleYawController:
    def __init__(self):
        print("Initializing Simple Yaw Controller (Primary Control)...")
        
        # Initialize MPU6050
        self.mpu = MPU6050()
        
        # Set to GYRO-ONLY mode to disable accelerometer bias (same as mpu.py)
        self.mpu.set_control_mode(use_gyro_only=True, verbose=True)
        
        # Initialize PD Controller with much more conservative settings
        self.pd = PDController(kp=0.1, kd=0.01, deadband=2.0)
        
        # Control state
        self.running = False
        self.control_thread = None
        
        print("Simple Yaw Controller ready!")
    
    def live_data_display(self):
        """Live data display - SAME AS MPU.PY"""
        print("Starting live yaw data display (PURE GYRO MODE)")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        try:
            while True:
                # Use EXACT same data collection as mpu.py
                data = self.mpu.read_all_data()
                angles = data['angles']
                
                # Display ONLY yaw_pure angle (same as mpu.py live display)
                print(f"\rYaw_PURE: {angles['yaw_pure']:+7.2f}°", end='', flush=True)
                
                # Same timing as mpu.py
                time.sleep(0.01)  # 100Hz display update
                
        except KeyboardInterrupt:
            print("\nLive data display stopped.")
        self.pd = PDController(kp=0.1, kd=0.01, deadband=2.0)
        
        # Control state
        self.running = False
        self.control_thread = None
        
        print("Simple Yaw Controller ready!")
    
    def control_loop(self):
        """Simple control loop for yaw stabilization (horizontal control)"""
        print(f"Starting yaw control - Target: {self.pd.target_angle}° (horizontal)")
        print("Press Ctrl+C to stop")
        
        while self.running:
            try:
                # Get current yaw angle using PURE GYRO (same as mpu.py display)
                data = self.mpu.read_all_data()
                current_yaw = data['angles']['yaw_pure']  # Pure gyro integration (no accelerometer bias)
                
                # Update PD controller
                self.pd.update_current_angle(current_yaw)
                control_output, error, derivative = self.pd.calculate_control()
                
                # SAFETY: Limit control output to prevent runaway
                control_output = max(-10.0, min(10.0, control_output))
                
                # SAFETY: Stop if error is too large (system may be broken)
                if abs(error) > 90:
                    stop_motor_dc()
                    print(f"\nSAFETY STOP: Error too large ({error:.1f}°)")
                    break
                
                # Bang-bang control logic (REACTION WHEEL CORRECTED)
                if abs(error) < self.pd.deadband:
                    stop_motor_dc()
                    status = "STOP"
                elif control_output > 0:
                    # Positive error: need to rotate cube CW → Motor CCW (reaction wheel)
                    rotate_counterclockwise_dc()
                    status = "CCW"
                elif control_output < 0:
                    # Negative error: need to rotate cube CCW → Motor CW (reaction wheel)
                    rotate_clockwise_dc()
                    status = "CW"
                else:
                    stop_motor_dc()
                    status = "STOP"
                
                # Live display (using PURE GYRO data - same as mpu.py)
                print(f"\rYaw_PURE: {current_yaw:+6.2f}° | Target: {self.pd.target_angle:+6.2f}° | "
                      f"Error: {error:+5.2f}° | Control: {control_output:+6.2f} | Motor: {status:<4}", 
                      end='', flush=True)
                
                time.sleep(0.05)  # 20Hz control loop
                
            except Exception as e:
                print(f"\nControl error: {e}")
                stop_motor_dc()
                break
        
        stop_motor_dc()
        print("\nControl loop stopped")
    
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
        print(f"\nTarget changed to {angle}°")
    
    def tune_gains(self, kp, kd):
        """Tune PD gains"""
        self.pd.set_gains(kp, kd)
        print(f"\nGains updated: Kp={kp}, Kd={kd}")
    
    def calibrate_zero(self):
        """Set current position as zero reference"""
        self.mpu.calibrate_at_current_position()
        print("\nCurrent position set as 0° reference")

def main():
    """Test interface"""
    print("="*60)
    print("🎯 SIMPLE YAW PD CONTROLLER TEST (PURE GYRO MODE)")
    print("="*60)
    print("🚀 USING PURE GYRO DATA (no accelerometer bias)")
    print("Commands:")
    print("  live             - Live yaw data display (same as mpu.py)")
    print("  start <angle>    - Start control to target angle")
    print("  stop             - Stop control")
    print("  target <angle>   - Change target angle")
    print("  tune <kp> <kd>   - Tune PD gains (try: 0.1 0.01)")
    print("  deadband <deg>   - Set deadband (try: 3.0)")
    print("  zero             - Calibrate current position as 0°")
    print("  status           - Show current readings")
    print("  manual <cmd>     - Manual control (cw/ccw/stop)")
    print("  quit             - Exit")
    print("  ")
    print("🔧 TUNING TIPS:")
    print("  - Start with: tune 0.05 0.005")
    print("  - If oscillating: REDUCE Kp")
    print("  - If overshoot: INCREASE Kd")
    print("  - If slow: slightly increase Kp")
    print("="*60)
    
    controller = SimpleYawController()
    
    try:
        while True:
            cmd = input("\nYaw> ").strip().split()
            
            if not cmd:
                continue
            
            if cmd[0] == "quit" or cmd[0] == "q":
                break
            
            elif cmd[0] == "live":
                controller.live_data_display()
            
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
            
            elif cmd[0] == "deadband" and len(cmd) == 2:
                try:
                    deadband = float(cmd[1])
                    controller.pd.set_deadband(deadband)
                    print(f"\nDeadband set to {deadband}°")
                except ValueError:
                    print("Invalid deadband")
            
            elif cmd[0] == "zero":
                controller.calibrate_zero()
            
            elif cmd[0] == "status":
                data = controller.mpu.read_all_data()
                angles = data['angles']
                print(f"\nCurrent Status:")
                print(f"  Yaw_PURE: {angles['yaw_pure']:+6.2f}° (CONTROL - no accel bias)")
                print(f"  Yaw_Filt: {angles['yaw']:+6.2f}° (filtered)")
                print(f"  Roll:     {angles['roll']:+6.2f}°")
                print(f"  Pitch:    {angles['pitch']:+6.2f}°")
                print(f"  Target:   {controller.pd.target_angle:+6.2f}°")
                print(f"  PD Gains: Kp={controller.pd.kp:.3f}, Kd={controller.pd.kd:.3f}")
                print(f"  Deadband: {controller.pd.deadband:.1f}°")
                print(f"  Running:  {controller.running}")
            
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
        print("\nInterrupted...")
    
    finally:
        controller.stop_control()
        cleanup()
        print("Test complete!")

if __name__ == "__main__":
    main()
