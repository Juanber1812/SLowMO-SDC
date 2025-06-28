#!/usr/bin/env python3
"""
MPU Logger Test Runner
Quick test script to run the MPU logger with different configurations
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpu import MPULogger

def test_quick_simulation():
    """Run a quick 30-second simulation test"""
    print("🧪 Quick Simulation Test (30 seconds)")
    print("=" * 50)
    
    logger = MPULogger(
        simulation_mode=True,
        log_to_file=False,
        update_rate=5  # 5 Hz for demo
    )
    
    import time
    start_time = time.time()
    
    try:
        while time.time() - start_time < 30:  # Run for 30 seconds
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Read simulated data
            ax, ay, az, gx, gy, gz = logger.read_mpu_simulation()
            yaw = logger.calculate_yaw(ax, ay)
            gravity_mag = logger.calculate_gravity_magnitude(ax, ay, az)
            
            # Display
            display_line = logger.format_display_line(elapsed, ax, ay, az, gx, gy, gz, yaw, gravity_mag)
            print(display_line)
            
            time.sleep(0.2)  # 5 Hz
            
    except KeyboardInterrupt:
        pass
    
    print("\n✅ Test completed!")

def test_high_frequency():
    """Test high-frequency logging"""
    print("⚡ High-Frequency Test (20 Hz for 15 seconds)")
    print("=" * 50)
    
    logger = MPULogger(
        simulation_mode=True,
        log_to_file=True,
        update_rate=20  # 20 Hz
    )
    
    import time
    start_time = time.time()
    sample_count = 0
    
    try:
        while time.time() - start_time < 15:  # Run for 15 seconds
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Read simulated data
            ax, ay, az, gx, gy, gz = logger.read_mpu_simulation()
            yaw = logger.calculate_yaw(ax, ay)
            gravity_mag = logger.calculate_gravity_magnitude(ax, ay, az)
            
            # Display every 10th sample to avoid spam
            if sample_count % 10 == 0:
                display_line = logger.format_display_line(elapsed, ax, ay, az, gx, gy, gz, yaw, gravity_mag)
                print(display_line)
            
            sample_count += 1
            time.sleep(0.05)  # 20 Hz
            
    except KeyboardInterrupt:
        pass
    
    print(f"\n✅ Test completed! Processed {sample_count} samples")
    print(f"📊 Average rate: {sample_count/15:.1f} Hz")

def main():
    """Main test runner"""
    print("🔬 MPU Logger Test Suite")
    print("=" * 40)
    print("1. Quick simulation (30s, 5Hz)")
    print("2. High-frequency test (15s, 20Hz)")
    print("3. Full interactive logger")
    
    choice = input("Choose test (1-3): ").strip()
    
    if choice == "1":
        test_quick_simulation()
    elif choice == "2":
        test_high_frequency()
    elif choice == "3":
        # Import and run the main MPU logger
        from mpu import main as mpu_main
        mpu_main()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
