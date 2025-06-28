#!/usr/bin/env python3
"""
Advanced MPU Accelerometer Calibration Demo
Demonstrates the enhanced accelerometer calibration features
"""

import sys
import os
import numpy as np

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpu import MPULogger

def demo_accelerometer_corrections():
    """Demonstrate different types of accelerometer corrections"""
    print("📐 Accelerometer Correction Demo")
    print("=" * 50)
    
    # Create logger in simulation mode
    logger = MPULogger(simulation_mode=True, log_to_file=False)
    
    print("\n🧪 Testing different correction methods:")
    print("-" * 50)
    
    # Simulate some typical accelerometer errors
    test_cases = [
        ("Perfect 1g on Z-axis", [0.0, 0.0, 1.0]),
        ("Biased readings", [0.05, -0.03, 0.98]),
        ("Scale error", [0.0, 0.0, 1.1]),
        ("Combined errors", [0.04, -0.02, 1.08]),
    ]
    
    for case_name, (ax, ay, az) in test_cases:
        print(f"\n📊 {case_name}:")
        print(f"   Raw:     [{ax:6.3f}, {ay:6.3f}, {az:6.3f}]")
        
        # Apply basic correction (bias only)
        logger.accel_bias = {'x': 0.04, 'y': -0.02, 'z': 0.08}
        logger.accel_scale = {'x': 1.0, 'y': 1.0, 'z': 1.0}
        logger.is_accel_calibrated = False
        
        ax_basic, ay_basic, az_basic = logger.apply_accel_calibration(ax, ay, az)
        print(f"   Basic:   [{ax_basic:6.3f}, {ay_basic:6.3f}, {az_basic:6.3f}]")
        
        # Apply advanced correction (bias + scale)
        logger.accel_scale = {'x': 1.0, 'y': 1.0, 'z': 0.91}  # Z-axis needs correction
        logger.is_accel_calibrated = True
        
        ax_advanced, ay_advanced, az_advanced = logger.apply_accel_calibration(ax, ay, az)
        print(f"   Advanced:[{ax_advanced:6.3f}, {ay_advanced:6.3f}, {az_advanced:6.3f}]")
        
        # Calculate magnitude
        mag_raw = np.sqrt(ax**2 + ay**2 + az**2)
        mag_basic = np.sqrt(ax_basic**2 + ay_basic**2 + az_basic**2)
        mag_advanced = np.sqrt(ax_advanced**2 + ay_advanced**2 + az_advanced**2)
        
        print(f"   Magnitude: Raw={mag_raw:.3f}, Basic={mag_basic:.3f}, Advanced={mag_advanced:.3f}")

def demo_6_position_calibration():
    """Demonstrate the 6-position calibration concept"""
    print("\n\n🔄 6-Position Calibration Concept Demo")
    print("=" * 50)
    
    print("📋 The 6-position method measures gravity in all orientations:")
    
    positions = [
        ("+X up", [1.0, 0.0, 0.0], "Device rotated 90° left"),
        ("-X up", [-1.0, 0.0, 0.0], "Device rotated 90° right"),
        ("+Y up", [0.0, 1.0, 0.0], "Device rotated 90° forward"),
        ("-Y up", [0.0, -1.0, 0.0], "Device rotated 90° backward"),
        ("+Z up", [0.0, 0.0, 1.0], "Device flat, normal position"),
        ("-Z up", [0.0, 0.0, -1.0], "Device upside down")
    ]
    
    print("\n📍 Required positions:")
    for i, (name, expected, description) in enumerate(positions, 1):
        print(f"   {i}. {name:6} - Expected: [{expected[0]:4.1f}, {expected[1]:4.1f}, {expected[2]:4.1f}] - {description}")
    
    print("\n🧮 What the calibration calculates:")
    print("   • Bias: Average offset when reading should be 0")
    print("   • Scale: Correction factor when reading should be ±1g")
    print("   • Formula: corrected = (raw - bias) × scale")
    
    # Simulate some calibration calculations
    print("\n🔬 Example calculation:")
    print("   If +Z position reads 1.08g and -Z position reads -0.94g:")
    bias_z = (1.08 + (-0.94)) / 2
    scale_z = 2.0 / (1.08 - (-0.94))
    print(f"   • Z-axis bias = {bias_z:.3f}g")
    print(f"   • Z-axis scale = {scale_z:.3f}")
    print(f"   • Result: 1.08g → {(1.08 - bias_z) * scale_z:.3f}g")
    print(f"   • Result: -0.94g → {(-0.94 - bias_z) * scale_z:.3f}g")

def main():
    """Main demo function"""
    print("🎯 Advanced MPU Accelerometer Calibration Demo")
    print("=" * 60)
    print("1. Basic vs Advanced correction comparison")
    print("2. 6-position calibration concept")
    print("3. Run actual accelerometer calibration")
    
    choice = input("Choose demo (1-3): ").strip()
    
    if choice == "1":
        demo_accelerometer_corrections()
    elif choice == "2":
        demo_6_position_calibration()
    elif choice == "3":
        print("\n🚀 Starting actual accelerometer calibration...")
        logger = MPULogger(simulation_mode=True, log_to_file=False)
        logger.perform_accelerometer_calibration()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
