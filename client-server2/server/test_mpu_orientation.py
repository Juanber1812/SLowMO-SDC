#!/usr/bin/env python3
"""
MPU-6050 Orientation Test Script
Simple test to verify sensor readings and yaw angle calculation
for a hanging cube rotating in horizontal plane
"""

import time
import math
import smbus
import signal
import sys

# MPU-6050 configuration
MPU_ADDR = 0x68
bus = smbus.SMBus(1)

def setup_mpu():
    """Initialize MPU-6050 sensor"""
    try:
        # Wake up MPU-6050 (exit sleep mode)
        bus.write_byte_data(MPU_ADDR, 0x6B, 0)
        
        # Configure accelerometer range (±2g)
        bus.write_byte_data(MPU_ADDR, 0x1C, 0x00)
        
        # Configure gyroscope range (±250°/s)
        bus.write_byte_data(MPU_ADDR, 0x1B, 0x00)
        
        print("✓ MPU-6050 initialized successfully")
        return True
    except Exception as e:
        print(f"✗ MPU-6050 initialization failed: {e}")
        return False

def read_raw_data(addr):
    """Read 16-bit raw data from MPU-6050 register"""
    try:
        high = bus.read_byte_data(MPU_ADDR, addr)
        low = bus.read_byte_data(MPU_ADDR, addr + 1)
        value = (high << 8) | low
        
        # Convert to signed integer
        if value > 32767:
            value = value - 65536
        return value
    except Exception as e:
        print(f"Error reading register {addr:02X}: {e}")
        return 0

def read_mpu_data():
    """Read accelerometer and gyroscope data"""
    try:
        # Read accelerometer data (convert to g)
        ax_raw = read_raw_data(0x3B)
        ay_raw = read_raw_data(0x3D)
        az_raw = read_raw_data(0x3F)
        
        # Convert to g (±2g range, 16-bit resolution)
        ax = ax_raw / 16384.0
        ay = ay_raw / 16384.0
        az = az_raw / 16384.0
        
        # Read gyroscope data (convert to degrees/sec)
        gx_raw = read_raw_data(0x43)
        gy_raw = read_raw_data(0x45)
        gz_raw = read_raw_data(0x47)
        
        # Convert to degrees/sec (±250°/s range, 16-bit resolution)
        gx = gx_raw / 131.0
        gy = gy_raw / 131.0
        gz = gz_raw / 131.0
        
        return ax, ay, az, gx, gy, gz
    except Exception as e:
        print(f"Error reading MPU data: {e}")
        return 0, 0, 0, 0, 0, 0

def calculate_yaw_angle(ax, ay, az):
    """
    Calculate yaw angle for hanging cube
    
    For a cube hanging from ceiling, gravity acts in Z direction,
    so X,Y components show horizontal orientation
    """
    try:
        # Calculate yaw (rotation around vertical Z-axis)
        yaw_rad = math.atan2(ay, ax)
        yaw_deg = yaw_rad * 180.0 / math.pi
        
        return yaw_deg
    except Exception as e:
        print(f"Error calculating yaw: {e}")
        return 0.0

def calculate_gravity_magnitude(ax, ay, az):
    """Calculate total acceleration magnitude (should be ~1g when stationary)"""
    return math.sqrt(ax*ax + ay*ay + az*az)

def print_header():
    """Print column headers"""
    print("\n" + "="*90)
    print("MPU-6050 Orientation Test - Hanging Cube Setup")
    print("="*90)
    print("Time     | Accelerometer (g)        | Gyroscope (°/s)        | Yaw   | |G|   | Status")
    print("(sec)    |   X      Y      Z       |   X      Y      Z      | (°)   | (g)   |")
    print("-"*90)

def analyze_readings(ax, ay, az, gx, gy, gz, yaw, gravity_mag):
    """Analyze readings and provide status feedback"""
    status_flags = []
    
    # Check if cube is hanging properly (Z should be close to -1g or +1g)
    if abs(abs(az) - 1.0) < 0.2:
        if az < -0.8:
            status_flags.append("Hanging↓")
        elif az > 0.8:
            status_flags.append("Upside↑")
    else:
        status_flags.append("Tilted")
    
    # Check if stationary (low gyroscope readings)
    gyro_total = math.sqrt(gx*gx + gy*gy + gz*gz)
    if gyro_total < 10:
        status_flags.append("Still")
    else:
        status_flags.append("Moving")
    
    # Check gravity magnitude (should be close to 1g)
    if abs(gravity_mag - 1.0) < 0.1:
        status_flags.append("1g✓")
    else:
        status_flags.append("?g")
    
    return " ".join(status_flags)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n\n{'='*90}")
    print("Test stopped by user")
    print("Tips for your hanging cube setup:")
    print("• Yaw angle should change smoothly when you rotate the cube")
    print("• Z acceleration should be close to -1g or +1g when hanging")
    print("• X,Y accelerations show horizontal tilt")
    print("• Use yaw angle for your reaction wheel control")
    print("="*90)
    sys.exit(0)

def main():
    """Main test loop"""
    print("MPU-6050 Orientation Test for Hanging Cube")
    print("Press Ctrl+C to stop")
    
    # Setup signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize MPU-6050
    if not setup_mpu():
        print("Failed to initialize MPU-6050. Check I2C connection.")
        return
    
    print("\nWaiting 2 seconds for sensor to stabilize...")
    time.sleep(2)
    
    print_header()
    
    start_time = time.time()
    sample_count = 0
    
    try:
        while True:
            # Read sensor data
            ax, ay, az, gx, gy, gz = read_mpu_data()
            
            # Calculate orientation
            yaw = calculate_yaw_angle(ax, ay, az)
            gravity_mag = calculate_gravity_magnitude(ax, ay, az)
            
            # Analyze readings
            status = analyze_readings(ax, ay, az, gx, gy, gz, yaw, gravity_mag)
            
            # Calculate elapsed time
            elapsed = time.time() - start_time
            
            # Print data row
            print(f"{elapsed:6.1f}   |"
                  f"{ax:7.3f} {ay:7.3f} {az:7.3f}  |"
                  f"{gx:7.1f} {gy:7.1f} {gz:7.1f}   |"
                  f"{yaw:6.1f} |"
                  f"{gravity_mag:6.3f} |"
                  f" {status}")
            
            sample_count += 1
            
            # Print summary every 50 samples
            if sample_count % 50 == 0:
                print(f"\n[Sample #{sample_count}] Current yaw: {yaw:.1f}°")
                print("Try rotating the cube to see yaw angle change...")
                print("-"*90)
            
            time.sleep(0.1)  # 10 Hz sampling rate
            
    except Exception as e:
        print(f"\nError in main loop: {e}")

if __name__ == "__main__":
    main()
