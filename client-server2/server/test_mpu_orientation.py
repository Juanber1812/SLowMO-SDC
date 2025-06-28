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

# Simple moving average filter for yaw
yaw_history = []
FILTER_SIZE = 5  # Average over last 5 readings

# Calibration offsets (will be set during calibration)
gyro_offset = [0.0, 0.0, 0.0]  # [gx, gy, gz] bias
accel_offset = [0.0, 0.0, 0.0]  # [ax, ay, az] bias

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
    """Read accelerometer and gyroscope data with calibration applied"""
    try:
        # Read accelerometer data (raw)
        ax_raw = read_raw_data(0x3B)
        ay_raw = read_raw_data(0x3D)
        az_raw = read_raw_data(0x3F)
        
        # Read gyroscope data (raw)
        gx_raw = read_raw_data(0x43)
        gy_raw = read_raw_data(0x45)
        gz_raw = read_raw_data(0x47)
        
        # Apply calibration offsets
        ax_cal = ax_raw - accel_offset[0]
        ay_cal = ay_raw - accel_offset[1]
        az_cal = az_raw - accel_offset[2]
        gx_cal = gx_raw - gyro_offset[0]
        gy_cal = gy_raw - gyro_offset[1]
        gz_cal = gz_raw - gyro_offset[2]
        
        # Convert to g (±2g range, 16-bit resolution)
        ax = ax_cal / 16384.0
        ay = ay_cal / 16384.0
        az = az_cal / 16384.0
        
        # Convert to degrees/sec (±250°/s range, 16-bit resolution)
        gx = gx_cal / 131.0
        gy = gy_cal / 131.0
        gz = gz_cal / 131.0
        
        return ax, ay, az, gx, gy, gz
    except Exception as e:
        print(f"Error reading MPU data: {e}")
        return 0, 0, 0, 0, 0, 0

def calculate_yaw_angle(ax, ay, az):
    """
    Calculate yaw angle for hanging cube with noise filtering
    
    For a cube hanging from ceiling, gravity acts in Z direction,
    so X,Y components show horizontal orientation
    """
    try:
        # Check if we have reasonable gravity reading
        total_g = math.sqrt(ax*ax + ay*ay + az*az)
        if total_g < 0.5:  # Too low, sensor might be faulty
            return 0.0
            
        # Normalize the horizontal components by total gravity
        # This helps reduce the effect of gravity magnitude variations
        ax_norm = ax / total_g
        ay_norm = ay / total_g
        
        # Only calculate yaw if horizontal components are significant enough
        horizontal_mag = math.sqrt(ax_norm*ax_norm + ay_norm*ay_norm)
        if horizontal_mag < 0.02:  # Less than ~1.1 degrees of tilt
            return 0.0  # Essentially vertical, yaw undefined
        
        # Calculate yaw (rotation around vertical Z-axis)
        yaw_rad = math.atan2(ay_norm, ax_norm)
        yaw_deg = yaw_rad * 180.0 / math.pi
        
        return yaw_deg
    except Exception as e:
        print(f"Error calculating yaw: {e}")
        return 0.0

def calculate_filtered_yaw(ax, ay, az):
    """Calculate yaw with moving average filter"""
    global yaw_history
    
    # Get raw yaw
    raw_yaw = calculate_yaw_angle(ax, ay, az)
    
    # Add to history
    yaw_history.append(raw_yaw)
    
    # Keep only last FILTER_SIZE readings
    if len(yaw_history) > FILTER_SIZE:
        yaw_history.pop(0)
    
    # Return filtered average
    if len(yaw_history) > 0:
        return sum(yaw_history) / len(yaw_history)
    else:
        return raw_yaw

def calculate_gravity_magnitude(ax, ay, az):
    """Calculate total acceleration magnitude (should be ~1g when stationary)"""
    return math.sqrt(ax*ax + ay*ay + az*az)

def print_header():
    """Print column headers"""
    print("\n" + "="*110)
    print("MPU-6050 Enhanced Orientation Test - Hanging Cube Setup")
    print("="*110)
    print("Time     | Accelerometer (g)        | Gyroscope (°/s)        | Yaw(Raw) | Yaw(Filt) | |G|   | Status")
    print("(sec)    |   X      Y      Z       |   X      Y      Z      |   (°)    |    (°)    | (g)   |")
    print("-"*110)

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
    print("\nCalibration Results:")
    print(f"• Gyro offsets: [{gyro_offset[0]:.1f}, {gyro_offset[1]:.1f}, {gyro_offset[2]:.1f}]")
    print(f"• Accel offsets: [{accel_offset[0]:.1f}, {accel_offset[1]:.1f}, {accel_offset[2]:.1f}]")
    print("\nTips for your hanging cube setup:")
    print("• Calibrated yaw angle should be much more stable now")
    print("• Z acceleration should be close to -1g or +1g when hanging")
    print("• X,Y accelerations show horizontal tilt")
    print("• Use filtered yaw angle for your reaction wheel control")
    print("="*90)
    sys.exit(0)

def calibrate_mpu(samples=200):
    """
    Calibrate MPU-6050 by measuring bias when stationary
    Returns True if calibration successful
    """
    print("\n" + "="*60)
    print("🧭 MPU-6050 CALIBRATION")
    print("="*60)
    print("⚠️  IMPORTANT: Keep the cube PERFECTLY STILL during calibration!")
    print("   Place it on a stable surface and don't touch it.")
    print(f"   Taking {samples} samples over {samples*0.01:.1f} seconds...")
    print()
    
    global gyro_offset, accel_offset
    gyro_sum = [0.0, 0.0, 0.0]
    accel_sum = [0.0, 0.0, 0.0]
    
    try:
        # Collect samples
        for i in range(samples):
            # Read raw data
            ax_raw = read_raw_data(0x3B)
            ay_raw = read_raw_data(0x3D)
            az_raw = read_raw_data(0x3F)
            gx_raw = read_raw_data(0x43)
            gy_raw = read_raw_data(0x45)
            gz_raw = read_raw_data(0x47)
            
            # Accumulate for averaging
            accel_sum[0] += ax_raw
            accel_sum[1] += ay_raw
            accel_sum[2] += az_raw
            gyro_sum[0] += gx_raw
            gyro_sum[1] += gy_raw
            gyro_sum[2] += gz_raw
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                progress = (i + 1) / samples * 100
                print(f"   Progress: {progress:.0f}% ({i+1}/{samples})")
            
            time.sleep(0.01)  # 10ms between samples
        
        # Calculate average offsets
        gyro_offset[0] = gyro_sum[0] / samples
        gyro_offset[1] = gyro_sum[1] / samples  
        gyro_offset[2] = gyro_sum[2] / samples
        
        accel_offset[0] = accel_sum[0] / samples
        accel_offset[1] = accel_sum[1] / samples
        # For Z-axis, subtract expected gravity (16384 for ±2g range)
        # Assuming cube is sitting flat (Z-axis pointing up = +1g)
        accel_offset[2] = accel_sum[2] / samples - 16384
        
        print("\n✅ Calibration Complete!")
        print("-" * 40)
        print("Gyroscope Offsets (raw):")
        print(f"   X: {gyro_offset[0]:8.1f}")
        print(f"   Y: {gyro_offset[1]:8.1f}")
        print(f"   Z: {gyro_offset[2]:8.1f}")
        print()
        print("Accelerometer Offsets (raw):")
        print(f"   X: {accel_offset[0]:8.1f}")
        print(f"   Y: {accel_offset[1]:8.1f}")
        print(f"   Z: {accel_offset[2]:8.1f}")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Calibration failed: {e}")
        return False

def main():
    """Main test loop"""
    print("MPU-6050 Enhanced Orientation Test with Calibration")
    print("Press Ctrl+C to stop")
    
    # Setup signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize MPU-6050
    if not setup_mpu():
        print("Failed to initialize MPU-6050. Check I2C connection.")
        return
    
    print("\nWaiting 2 seconds for sensor to stabilize...")
    time.sleep(2)
    
    # Calibrate the sensor
    print("\n🧭 Starting calibration process...")
    if not calibrate_mpu(samples=200):
        print("❌ Calibration failed. Exiting.")
        return
    
    input("\n✅ Calibration complete! Press ENTER to start testing...")
    
    print_header()
    
    start_time = time.time()
    sample_count = 0
    
    try:
        while True:
            # Read sensor data
            ax, ay, az, gx, gy, gz = read_mpu_data()
            
            # Calculate orientation
            yaw_raw = calculate_yaw_angle(ax, ay, az)
            yaw_filtered = calculate_filtered_yaw(ax, ay, az)
            gravity_mag = calculate_gravity_magnitude(ax, ay, az)
            
            # Analyze readings
            status = analyze_readings(ax, ay, az, gx, gy, gz, yaw_filtered, gravity_mag)
            
            # Calculate elapsed time
            elapsed = time.time() - start_time
            
            # Print data row
            print(f"{elapsed:6.1f}   |"
                  f"{ax:7.3f} {ay:7.3f} {az:7.3f}  |"
                  f"{gx:7.1f} {gy:7.1f} {gz:7.1f}   |"
                  f"{yaw_raw:8.1f}  |"
                  f"{yaw_filtered:9.1f}  |"
                  f"{gravity_mag:6.3f} |"
                  f" {status}")
            
            sample_count += 1
            
            # Print summary every 50 samples
            if sample_count % 50 == 0:
                yaw_variation = max(yaw_history) - min(yaw_history) if len(yaw_history) > 1 else 0
                print(f"\n[Sample #{sample_count}] Filtered yaw: {yaw_filtered:.1f}° | Variation: {yaw_variation:.1f}°")
                print("Try rotating the cube to see yaw angle change...")
                print("-"*110)
            
            time.sleep(0.1)  # 10 Hz sampling rate
            
    except Exception as e:
        print(f"\nError in main loop: {e}")

if __name__ == "__main__":
    main()
