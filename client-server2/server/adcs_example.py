#!/usr/bin/env python3
"""
ADCS Quick Start Example - Single Axis Yaw Control
Simple example showing how to use the integrated ADCS system
for a hanging cube rotating in the horizontal plane
"""

import time
from adcs_integrated import start_adcs_control, stop_adcs_control, set_target, get_adcs_status, adcs

def main():
    print("=" * 50)
    print("ADCS Quick Start Example - Yaw Control")
    print("=" * 50)
    
    try:
        # Example 1: Start ADCS with default target (0°)
        print("\n1. Starting ADCS system...")
        start_adcs_control()
        time.sleep(2)
        
        # Check status
        status = get_adcs_status()
        print(f"   Current yaw: {status['current_yaw']:.1f}°")
        print(f"   Target yaw: {status['target_yaw']:.1f}°")
        
        # Example 2: Change target orientation
        print("\n2. Setting new target: Yaw=45°")
        set_target(45.0)
        
        # Let it run for a while
        print("   Running for 10 seconds...")
        for i in range(10):
            time.sleep(1)
            status = get_adcs_status()
            print(f"   [{i+1:2d}s] Yaw={status['current_yaw']:6.1f}° (error: {status['yaw_error']:6.1f}°)")
        
        # Example 3: Change target again
        print("\n3. Setting new target: Yaw=-30°")
        set_target(-30.0)
        
        # Run for another period
        print("   Running for 10 seconds...")
        for i in range(10):
            time.sleep(1)
            status = get_adcs_status()
            print(f"   [{i+1:2d}s] Yaw={status['current_yaw']:6.1f}° (error: {status['yaw_error']:6.1f}°)")
        
        # Example 4: Show sensor data
        print("\n4. Current sensor readings:")
        sensor_data = status['sensor_data']
        print(f"   Accelerometer (g): X={sensor_data['ax']:6.3f}, Y={sensor_data['ay']:6.3f}, Z={sensor_data['az']:6.3f}")
        print(f"   Gyroscope (°/s):   X={sensor_data['gx']:6.1f}, Y={sensor_data['gy']:6.1f}, Z={sensor_data['gz']:6.1f}")
        print(f"   Light (lux):       {sensor_data['lux']:6.1f}")
        print(f"   Calculated Yaw:    {sensor_data['yaw']:6.1f}°")
        
        # Example 5: Save data log
        print("\n5. Saving data log...")
        log_file = adcs.save_log("quickstart_yaw_example.csv")
        if log_file:
            print(f"   Data saved to: {log_file}")
        
        print("\n6. Stopping ADCS system...")
        stop_adcs_control()
        
        print("\nExample completed successfully!")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        stop_adcs_control()
        
    except Exception as e:
        print(f"\nError: {e}")
        stop_adcs_control()

if __name__ == "__main__":
    main()
