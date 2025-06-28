#!/usr/bin/env python3
"""
Simple Drift Analysis Tool
Clean, no-spam comparison of filter behavior
"""

import time
import sys
from mpu import MPU6050

def clean_drift_test():
    """Clean test to analyze the drift behavior you observed"""
    
    print("🎯 DRIFT ANALYSIS TEST")
    print("=" * 50)
    print("This will show the bias effect you discovered.")
    print("Tilt the sensor and watch the difference between:")
    print("- Filtered angle (biased towards 0°)")
    print("- Pure gyro angle (no bias)")
    print()
    
    mpu = MPU6050()
    
    # Set up for clean comparison - no spam
    mpu.set_control_mode(use_gyro_only=False, disable_accel_correction=False, verbose=False)
    
    print("Hold sensor at an angle and watch the bias...")
    print("Press Ctrl+C to exit")
    print("-" * 50)
    
    try:
        counter = 0
        while True:
            data = mpu.read_all_data()
            angles = data['angles']
            
            filtered_yaw = angles['yaw']
            pure_yaw = angles.get('yaw_pure', 0)
            bias = pure_yaw - filtered_yaw
            
            # Clear the line and print new data
            counter += 1
            sys.stdout.write(f"\rSample {counter:4d} | Filtered: {filtered_yaw:+6.1f}° | Pure: {pure_yaw:+6.1f}° | Bias: {bias:+5.1f}°")
            sys.stdout.flush()
            
            time.sleep(0.2)  # Slower updates = less spam
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 50)
        print("🎯 ANALYSIS COMPLETE")
        print("=" * 50)
        print("What you just saw:")
        print("- Filtered angle: Always pulls towards 0° (accelerometer)")
        print("- Pure gyro: Tracks actual rotation (no bias)")
        print("- Bias: The difference = control interference")
        print()
        print("For PD control, use: mpu.get_yaw_for_control_pure()")
        print("This gives you the pure gyro angle with no bias!")
        print("=" * 50)

if __name__ == "__main__":
    clean_drift_test()
