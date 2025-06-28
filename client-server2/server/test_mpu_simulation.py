#!/usr/bin/env python3
"""
Simple MPU-6050 Test with Simulated Data
Test script to understand orientation calculation without hardware dependencies
"""

import time
import math
import random

def simulate_hanging_cube_data(rotation_angle):
    """
    Simulate MPU-6050 data for a hanging cube at different rotation angles
    
    Args:
        rotation_angle: Current rotation angle in degrees
    
    Returns:
        ax, ay, az, gx, gy, gz: Simulated sensor readings
    """
    # Convert angle to radians
    angle_rad = math.radians(rotation_angle)
    
    # For a hanging cube, gravity acts downward (Z = -1g approximately)
    # X,Y components depend on any slight tilt from rotation
    ax = 0.05 * math.sin(angle_rad) + random.uniform(-0.02, 0.02)  # Small tilt
    ay = 0.05 * math.cos(angle_rad) + random.uniform(-0.02, 0.02)  # Small tilt  
    az = -0.98 + random.uniform(-0.05, 0.05)  # Mostly -1g (hanging down)
    
    # Gyroscope data (rotation rates)
    gx = random.uniform(-2, 2)   # Small random motion
    gy = random.uniform(-2, 2)   # Small random motion
    gz = random.uniform(-5, 5)   # Z-axis rotation (what we care about)
    
    return ax, ay, az, gx, gy, gz

def calculate_yaw_from_accelerometer(ax, ay, az):
    """
    Calculate yaw angle from accelerometer data
    
    For hanging cube: yaw = atan2(ay, ax)
    This gives rotation around the vertical (Z) axis
    """
    yaw_rad = math.atan2(ay, ax)
    yaw_deg = yaw_rad * 180.0 / math.pi
    return yaw_deg

def calculate_gravity_magnitude(ax, ay, az):
    """Calculate total gravity magnitude (should be ~1g)"""
    return math.sqrt(ax*ax + ay*ay + az*az)

def normalize_angle(angle):
    """Normalize angle to -180 to +180 degrees"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle

def main():
    print("="*70)
    print("MPU-6050 Orientation Test - Simulated Hanging Cube")
    print("="*70)
    print("This simulates how your hanging cube would behave")
    print("Press Ctrl+C to stop")
    print("-"*70)
    print("Time  | Accel (g)         | Gyro (°/s)      | Calc  | True | Error")
    print("(sec) |  X     Y     Z    |  X    Y    Z    | Yaw   | Yaw  | (°)")
    print("-"*70)
    
    start_time = time.time()
    true_angle = 0.0  # Simulated actual angle
    angle_rate = 10.0  # Rotation rate (degrees/second)
    
    try:
        while True:
            elapsed = time.time() - start_time
            
            # Simulate cube rotating at constant rate
            true_angle = (elapsed * angle_rate) % 360
            if true_angle > 180:
                true_angle -= 360
            
            # Get simulated sensor data
            ax, ay, az, gx, gy, gz = simulate_hanging_cube_data(true_angle)
            
            # Calculate yaw from accelerometer
            calculated_yaw = calculate_yaw_from_accelerometer(ax, ay, az)
            
            # Calculate error
            error = normalize_angle(calculated_yaw - true_angle)
            
            # Calculate gravity magnitude
            gravity_mag = calculate_gravity_magnitude(ax, ay, az)
            
            # Print results
            print(f"{elapsed:5.1f} |"
                  f"{ax:6.3f} {ay:6.3f} {az:6.3f} |"
                  f"{gx:5.1f} {gy:5.1f} {gz:5.1f} |"
                  f"{calculated_yaw:6.1f} |"
                  f"{true_angle:5.1f} |"
                  f"{error:6.1f}")
            
            # Status updates
            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"\n[{elapsed:.0f}s] Gravity magnitude: {gravity_mag:.3f}g")
                print("For real hanging cube:")
                print("• Z should be close to -1g (hanging down)")
                print("• X,Y should be small (minimal tilt)")
                print("• Calculated yaw tracks actual rotation")
                print("-"*70)
            
            time.sleep(0.1)  # 10 Hz update rate
            
    except KeyboardInterrupt:
        print(f"\n\n{'='*70}")
        print("UNDERSTANDING YOUR SETUP:")
        print("="*70)
        print("1. HANGING CUBE PHYSICS:")
        print("   • Gravity pulls down → Z ≈ -1g")
        print("   • Horizontal plane → X,Y ≈ 0g (when level)")
        print("   • Rotation changes X,Y slightly due to centrifugal effects")
        print("")
        print("2. YAW CALCULATION:")
        print("   • yaw = atan2(ay, ax) * 180/π")
        print("   • Uses horizontal components (X,Y)")
        print("   • Gives rotation around vertical axis")
        print("   • Range: -180° to +180°")
        print("")
        print("3. FOR YOUR REACTION WHEEL:")
        print("   • Target yaw = desired orientation")
        print("   • Current yaw = calculated from MPU")
        print("   • Error = target - current")
        print("   • PD controller → motor CW/CCW/STOP")
        print("="*70)

if __name__ == "__main__":
    main()
