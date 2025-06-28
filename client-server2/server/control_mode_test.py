#!/usr/bin/env python3
"""
Control Mode Comparison Test
Demonstrates the difference between normal filtering and control-optimized filtering
"""

import time
from mpu import MPU6050

def compare_control_modes():
    """Compare different control modes and their behavior"""
    
    print("=" * 80)
    print("🎯 CONTROL MODE COMPARISON TEST")
    print("=" * 80)
    print("This test shows how different filtering modes affect control performance.")
    print("Watch how the angles behave when tilted away from horizontal.")
    print()
    
    mpu = MPU6050()
    
    print("MODES:")
    print("1. NORMAL    - Standard complementary filter (biased towards 0°)")
    print("2. REDUCED   - Reduced accelerometer influence")  
    print("3. GYRO ONLY - Pure gyro integration (no accelerometer bias)")
    print()
    
    mode = input("Select mode (1/2/3) or press Enter for comparison: ").strip()
    
    if mode == "1":
        mpu.set_control_mode(use_gyro_only=False, disable_accel_correction=False)
        run_single_mode(mpu, "NORMAL")
    elif mode == "2":
        mpu.set_control_mode(use_gyro_only=False, disable_accel_correction=True)
        run_single_mode(mpu, "REDUCED ACCEL")
    elif mode == "3":
        mpu.set_control_mode(use_gyro_only=True, disable_accel_correction=False)
        run_single_mode(mpu, "GYRO ONLY")
    else:
        run_comparison_mode(mpu)

def run_single_mode(mpu, mode_name):
    """Run a single control mode"""
    print(f"\\nRunning {mode_name} mode...")
    print("Tilt the sensor and watch the angle behavior.")
    print("Press Ctrl+C to exit")
    print("-" * 60)
    
    try:
        while True:
            data = mpu.read_all_data()
            angles = data['angles']
            
            control_yaw = mpu.get_yaw_for_control()
            
            print(f"\\rYaw (filtered): {angles['yaw']:+7.2f}° | " +
                  f"Yaw (control): {control_yaw:+7.2f}° | " +
                  f"Pure: {angles.get('yaw_pure', 0):+7.2f}° | " +
                  f"Mode: {mode_name}", end='', flush=True)
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print(f"\\n{mode_name} mode test complete.")

def run_comparison_mode(mpu):
    """Run comparison between all modes"""
    print("\\nCOMPARISON MODE")
    print("All three angles will be shown side by side:")
    print("- Normal: Standard complementary filter")
    print("- Reduced: Weak accelerometer correction") 
    print("- Pure: Pure gyro integration")
    print()
    print("Tilt the sensor and observe the differences.")
    print("Press Ctrl+C to exit")
    print("-" * 80)
    
    try:
        while True:
            # Get normal mode
            mpu.set_control_mode(use_gyro_only=False, disable_accel_correction=False)
            data1 = mpu.read_all_data()
            normal_yaw = data1['angles']['yaw']
            
            # Get reduced mode 
            mpu.set_control_mode(use_gyro_only=False, disable_accel_correction=True)
            data2 = mpu.read_all_data()
            reduced_yaw = data2['angles']['yaw']
            
            # Get pure gyro mode
            mpu.set_control_mode(use_gyro_only=True, disable_accel_correction=False)
            data3 = mpu.read_all_data()
            pure_yaw = data3['angles']['yaw_pure']
            
            print(f"\\rNormal: {normal_yaw:+7.2f}° | " +
                  f"Reduced: {reduced_yaw:+7.2f}° | " +
                  f"Pure: {pure_yaw:+7.2f}° | " +
                  f"Drift difference: {abs(pure_yaw - normal_yaw):5.2f}°", 
                  end='', flush=True)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\\nComparison test complete.")
        print("\\n" + "=" * 80)
        print("🎯 RECOMMENDATIONS:")
        print("=" * 80)
        print("For PD CONTROL:")
        print("- Use GYRO ONLY mode for best setpoint tracking")
        print("- Use REDUCED mode for compromise between stability and control")
        print("- NORMAL mode will always drift towards 0° (not good for control)")
        print()
        print("For MONITORING:")
        print("- Use NORMAL mode for stable, long-term attitude reference")
        print("- Accelerometer correction prevents long-term drift")
        print("=" * 80)

if __name__ == "__main__":
    compare_control_modes()
