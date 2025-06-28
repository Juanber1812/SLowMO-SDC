#!/usr/bin/env python3
"""
Super Simple Bias Test
Just one line every second - no spam at all
"""

import time
from mpu import MPU6050

def simple_bias_test():
    """Super simple test - one reading per second"""
    
    print("🎯 SIMPLE BIAS TEST")
    print("One reading per second - no spam!")
    print("Tilt sensor to see the bias effect...")
    print("Press Ctrl+C to exit")
    print()
    
    mpu = MPU6050()
    mpu.set_control_mode(verbose=False)  # Silent mode
    
    sample = 0
    try:
        while True:
            sample += 1
            data = mpu.read_all_data()
            angles = data['angles']
            
            filtered = angles['yaw']
            pure = angles.get('yaw_pure', 0)
            bias = pure - filtered
            
            print(f"Sample {sample:3d}: Filtered={filtered:+6.1f}° | Pure={pure:+6.1f}° | Bias={bias:+5.1f}°")
            
            time.sleep(1.0)  # One second between readings
            
    except KeyboardInterrupt:
        print("\nTest complete!")
        print(f"The bias shows how much the filter interferes with control.")
        print(f"Use mpu.get_yaw_for_control_pure() for no bias in your PD controller.")

if __name__ == "__main__":
    simple_bias_test()
