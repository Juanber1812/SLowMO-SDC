#!/usr/bin/env python3
"""
MPU Calibration Utility
Standalone script to perform MPU calibration and analysis
"""

import sys
import os
import numpy as np

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpu import MPULogger

def analyze_sample_data():
    """Analyze sample data like the user provided"""
    print("🔍 Sample Data Analysis")
    print("=" * 40)
    
    # Sample data from user's example
    print("Analyzing sample gyroscope data...")
    
    # Example data (user would replace with their actual readings)
    gx_samples = [-3.8, -3.8, -3.8, -3.9, -2.0, -3.7, -3.8, -3.9, -3.8, -3.8]
    gy_samples = [-0.9, -0.9, -1.0, -1.1, -1.0, -0.9, -1.0, -0.9, -1.0, -1.0]
    gz_samples = [-2.6, -2.7, -2.7, -2.5, -2.7, -2.6, -2.7, -2.6, -2.7, -2.7]
    
    # Calculate biases
    gx_bias = np.mean(gx_samples)
    gy_bias = np.mean(gy_samples)
    gz_bias = np.mean(gz_samples)
    
    # Calculate standard deviations
    gx_std = np.std(gx_samples)
    gy_std = np.std(gy_samples)
    gz_std = np.std(gz_samples)
    
    print(f"\n📊 CALCULATED BIASES:")
    print(f"   Gyro X Bias: {gx_bias:.3f} ± {gx_std:.3f} °/s")
    print(f"   Gyro Y Bias: {gy_bias:.3f} ± {gy_std:.3f} °/s")
    print(f"   Gyro Z Bias: {gz_bias:.3f} ± {gz_std:.3f} °/s")
    
    print(f"\n🎯 CORRECTED VALUES (Example):")
    print("   Original → Corrected")
    for i in range(min(5, len(gx_samples))):
        gx_corrected = gx_samples[i] - gx_bias
        gy_corrected = gy_samples[i] - gy_bias
        gz_corrected = gz_samples[i] - gz_bias
        print(f"   Sample {i+1}:")
        print(f"     X: {gx_samples[i]:6.1f} → {gx_corrected:6.1f}")
        print(f"     Y: {gy_samples[i]:6.1f} → {gy_corrected:6.1f}")
        print(f"     Z: {gz_samples[i]:6.1f} → {gz_corrected:6.1f}")
    
    return gx_bias, gy_bias, gz_bias

def quick_calibration_demo():
    """Demonstrate calibration with simulated data"""
    print("\n🧪 Quick Calibration Demo")
    print("=" * 40)
    
    logger = MPULogger(simulation_mode=True, log_to_file=False)
    
    # Perform a short calibration
    print("Performing 10-second calibration demo...")
    logger.perform_calibration(duration_seconds=10, sample_rate=20)
    
    print("\n✅ Demo calibration complete!")
    
    # Show some corrected readings
    print("\n📊 Testing calibrated readings:")
    for i in range(5):
        # Get simulated raw data
        ax, ay, az, gx, gy, gz = logger.read_mpu_simulation()
        
        # Apply calibration
        ax_cal, ay_cal, az_cal, gx_cal, gy_cal, gz_cal = logger.apply_calibration(ax, ay, az, gx, gy, gz)
        
        print(f"   Sample {i+1}:")
        print(f"     Raw Gyro:  X={gx:6.1f}, Y={gy:6.1f}, Z={gz:6.1f}")
        print(f"     Corrected: X={gx_cal:6.1f}, Y={gy_cal:6.1f}, Z={gz_cal:6.1f}")

def main():
    """Main calibration utility"""
    print("🎯 MPU Calibration Utility")
    print("=" * 35)
    print("1. Analyze sample data (like your examples)")
    print("2. Quick calibration demo")
    print("3. Full calibration procedure")
    print("4. View saved calibration")
    
    choice = input("Choose option (1-4): ").strip()
    
    if choice == "1":
        analyze_sample_data()
        
    elif choice == "2":
        quick_calibration_demo()
        
    elif choice == "3":
        print("\n🚀 Starting full calibration...")
        logger = MPULogger(simulation_mode=None, log_to_file=False)
        duration = input("Calibration duration in seconds [30]: ").strip()
        duration = int(duration) if duration.isdigit() else 30
        logger.perform_calibration(duration_seconds=duration)
        
    elif choice == "4":
        logger = MPULogger(simulation_mode=None, log_to_file=False)
        if logger.is_calibrated:
            print("✅ Current calibration data loaded and displayed")
        else:
            print("❌ No calibration file found")
    
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
