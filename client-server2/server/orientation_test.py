#!/usr/bin/env python3
"""
Orientation Test for MPU6050 - Verify which angle represents "horizontal"

This script helps you determine which angle (pitch or roll) corresponds to 
your testbed being horizontal (parallel to gravity).

Usage:
1. Place your testbed/MPU6050 perfectly horizontal
2. Run this script and note the angle values
3. Tilt the testbed in the direction you want to control
4. The angle that changes the most is your control angle

Author: Attitude Control System
"""

import time
import sys
from mpu import MPU6050

def orientation_test():
    """Test to determine which angle represents horizontal orientation"""
    
    print("=" * 80)
    print("MPU6050 ORIENTATION TEST")
    print("=" * 80)
    print("This test helps determine which angle represents 'horizontal'")
    print()
    print("INSTRUCTIONS:")
    print("1. Place your testbed/MPU6050 as HORIZONTAL as possible")
    print("2. Press Enter to record the 'horizontal' reference")
    print("3. Tilt the testbed in the direction you want to control")
    print("4. The angle that changes the most is your control angle")
    print()
    print("Press Ctrl+C to exit at any time")
    print("-" * 80)
    
    try:
        # Initialize MPU6050
        print("Initializing MPU6050...")
        mpu = MPU6050()
        time.sleep(1)
        
        # Step 1: Record horizontal reference
        input("Step 1: Place testbed HORIZONTAL, then press Enter...")
        
        # Take several readings for average
        pitch_samples = []
        roll_samples = []
        yaw_samples = []
        
        print("Recording horizontal reference (5 samples)...")
        for i in range(5):
            data = mpu.read_all_data()
            pitch_samples.append(data['angles']['pitch'])
            roll_samples.append(data['angles']['roll'])
            yaw_samples.append(data['angles']['yaw'])
            time.sleep(0.2)
        
        # Calculate averages
        ref_pitch = sum(pitch_samples) / len(pitch_samples)
        ref_roll = sum(roll_samples) / len(roll_samples)
        ref_yaw = sum(yaw_samples) / len(yaw_samples)
        
        print(f"\nHORIZONTAL REFERENCE RECORDED:")
        print(f"  Pitch: {ref_pitch:+6.2f}°")
        print(f"  Roll:  {ref_roll:+6.2f}°")
        print(f"  Yaw:   {ref_yaw:+6.2f}°")
        print()
        
        # Step 2: Live angle monitoring with deviations
        print("Step 2: Now TILT the testbed in your control direction...")
        print("(Watch which angle changes the most - that's your control angle)")
        print()
        print("Live angles (deviations from horizontal reference):")
        print("Format: Angle = Current (Δ from horizontal)")
        print("-" * 80)
        
        while True:
            data = mpu.read_all_data()
            
            # Calculate deviations from horizontal reference
            pitch_current = data['angles']['pitch']
            roll_current = data['angles']['roll']
            yaw_current = data['angles']['yaw']
            
            pitch_delta = pitch_current - ref_pitch
            roll_delta = roll_current - ref_roll
            yaw_delta = yaw_current - ref_yaw
            
            # Determine which angle has the largest deviation
            max_deviation = max(abs(pitch_delta), abs(roll_delta), abs(yaw_delta))
            control_angle = "PITCH" if abs(pitch_delta) == max_deviation else \
                           "ROLL" if abs(roll_delta) == max_deviation else "YAW"
            
            # Live display with highlighting
            display = (
                f"\rPitch = {pitch_current:+6.2f}° (Δ{pitch_delta:+6.2f}°) | "
                f"Roll = {roll_current:+6.2f}° (Δ{roll_delta:+6.2f}°) | "
                f"Yaw = {yaw_current:+6.2f}° (Δ{yaw_delta:+6.2f}°) | "
                f"Control: {control_angle}"
            )
            
            print(display, end='', flush=True)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("ORIENTATION TEST SUMMARY:")
        print("=" * 80)
        print("The angle that changed the most when you tilted the testbed")
        print("is your CONTROL ANGLE for keeping the testbed horizontal.")
        print()
        print("RECOMMENDED CONTROL ANGLE:")
        print("- If PITCH changed the most → Use PITCH for control")
        print("- If ROLL changed the most → Use ROLL for control")
        print("- If YAW changed the most → Check your mounting orientation")
        print()
        print("Update your PD controller to use the identified control angle.")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError during orientation test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    orientation_test()
