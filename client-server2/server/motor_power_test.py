#!/usr/bin/env python3
"""
🔧 MOTOR POWER OUTPUT TEST
Simple script to test and monitor motor power output in real-time
Logs motor power values to console and CSV file
"""

import time
import csv
import os
import sys
from datetime import datetime

# Add the server directory to path to import ADCS_PD
sys.path.append(os.path.dirname(__file__))

try:
    from ADCS_PD import (
        ADCSController, 
        rotate_clockwise, 
        rotate_counterclockwise, 
        stop_motor,
        set_motor_power
    )
    print("✓ Motor control functions imported successfully")
except ImportError as e:
    print(f"❌ Failed to import motor functions: {e}")
    sys.exit(1)

class MotorPowerLogger:
    """Simple motor power monitoring and logging"""
    
    def __init__(self):
        self.log_data = []
        self.start_time = time.time()
        self.controller = None
        
    def start_controller(self):
        """Initialize ADCS controller for motor power monitoring"""
        try:
            print("🛰️ Initializing ADCS controller for motor power testing...")
            self.controller = ADCSController()
            time.sleep(2.0)  # Wait for initialization
            print("✓ Controller initialized")
            return True
        except Exception as e:
            print(f"❌ Controller initialization failed: {e}")
            return False
    
    def log_motor_power(self, test_name="", manual_power=None):
        """Log current motor power and system state"""
        current_time = time.time()
        relative_time = current_time - self.start_time
        
        if self.controller:
            data, _ = self.controller.get_current_data()
            controller_power = data['controller']['motor_power']
            controller_enabled = data['controller']['enabled']
            current_yaw = data['mpu']['yaw']
            target_yaw = data['controller']['target_yaw']
            error = data['controller']['error']
        else:
            controller_power = 0
            controller_enabled = False
            current_yaw = 0
            target_yaw = 0
            error = 0
        
        # Use manual power if provided (for manual control tests)
        actual_power = manual_power if manual_power is not None else controller_power
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'relative_time': relative_time,
            'test_name': test_name,
            'motor_power': actual_power,
            'controller_enabled': controller_enabled,
            'current_yaw': current_yaw,
            'target_yaw': target_yaw,
            'error': error
        }
        
        self.log_data.append(entry)
        
        # Print to console
        print(f"[{relative_time:6.1f}s] {test_name:15s} | Power: {actual_power:+4.0f}% | Yaw: {current_yaw:+7.1f}° | Target: {target_yaw:+7.1f}° | Error: {error:+6.1f}°")
        
        return entry
    
    def save_log(self, filename=None):
        """Save logged data to CSV file"""
        if not self.log_data:
            print("No data to save")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"motor_power_test_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'relative_time', 'test_name', 'motor_power', 
                             'controller_enabled', 'current_yaw', 'target_yaw', 'error']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for entry in self.log_data:
                    writer.writerow(entry)
            
            print(f"✓ Saved {len(self.log_data)} entries to {filename}")
            
            # Print summary stats
            powers = [entry['motor_power'] for entry in self.log_data]
            print(f"📊 Motor Power Stats:")
            print(f"   Min: {min(powers):+4.0f}%")
            print(f"   Max: {max(powers):+4.0f}%")
            print(f"   Avg: {sum(powers)/len(powers):+4.1f}%")
            
        except Exception as e:
            print(f"❌ Error saving log: {e}")
    
    def shutdown(self):
        """Clean shutdown"""
        if self.controller:
            self.controller.shutdown()

def manual_power_test(logger, duration=5.0):
    """Test manual motor commands (CW, CCW, Stop)"""
    print(f"\n🔧 MANUAL POWER TEST ({duration}s each)")
    print("=" * 50)
    
    # Test Manual CW (100% power)
    print("Testing Manual CW (100% power)...")
    rotate_clockwise()
    test_start = time.time()
    while time.time() - test_start < duration:
        logger.log_motor_power("Manual_CW", 100)
        time.sleep(0.1)
    
    # Test Manual CCW (-100% power)  
    print("Testing Manual CCW (-100% power)...")
    rotate_counterclockwise()
    test_start = time.time()
    while time.time() - test_start < duration:
        logger.log_motor_power("Manual_CCW", -100)
        time.sleep(0.1)
    
    # Test Stop (0% power)
    print("Testing Stop (0% power)...")
    stop_motor()
    test_start = time.time()
    while time.time() - test_start < duration:
        logger.log_motor_power("Manual_Stop", 0)
        time.sleep(0.1)

def pd_controller_test(logger, duration=10.0):
    """Test PD controller motor output"""
    print(f"\n🎮 PD CONTROLLER TEST ({duration}s)")
    print("=" * 50)
    
    if not logger.controller:
        print("❌ Controller not available")
        return
    
    # Start PD controller
    logger.controller.set_target_yaw(45.0)  # Target 45 degrees
    logger.controller.start_auto_control('Test')
    
    test_start = time.time()
    while time.time() - test_start < duration:
        logger.log_motor_power("PD_Control")
        time.sleep(0.1)
    
    # Stop PD controller
    logger.controller.stop_auto_control()

def power_step_test(logger):
    """Test different power levels manually"""
    print(f"\n⚡ POWER STEP TEST")
    print("=" * 50)
    
    power_levels = [10, 25, 50, 75, 100, -10, -25, -50, -75, -100, 0]
    
    for power in power_levels:
        print(f"Testing {power:+4d}% power...")
        set_motor_power(power)
        
        # Log for 2 seconds at this power level
        test_start = time.time()
        while time.time() - test_start < 2.0:
            logger.log_motor_power(f"Power_{power:+d}", power)
            time.sleep(0.1)
    
    stop_motor()

def main():
    """Main test function"""
    print("🔧 MOTOR POWER OUTPUT TEST")
    print("=" * 60)
    print("This script will test and log motor power output")
    print("Tests: Manual CW/CCW, PD Controller, Power Steps")
    print("=" * 60)
    
    logger = MotorPowerLogger()
    
    try:
        # Initialize controller
        if not logger.start_controller():
            print("❌ Cannot proceed without controller")
            return
        
        print(f"\n🚀 Starting motor power tests...")
        
        # Test 1: Manual commands (CW, CCW, Stop)
        manual_power_test(logger, duration=3.0)
        
        # Test 2: Power step test  
        power_step_test(logger)
        
        # Test 3: PD Controller
        pd_controller_test(logger, duration=8.0)
        
        print(f"\n✅ All tests completed!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        # Always save log and shutdown
        print(f"\n💾 Saving test results...")
        logger.save_log()
        
        print(f"\n🛠️ Shutting down...")
        logger.shutdown()
        
        print(f"✅ Test complete!")

if __name__ == "__main__":
    main()
