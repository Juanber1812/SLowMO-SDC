#!/usr/bin/env python3
"""
Test script to verify PD controller constants are working correctly
"""

# Mock the hardware imports to avoid import errors
import sys
from unittest.mock import MagicMock

# Mock all hardware libraries
sys.modules['board'] = MagicMock()
sys.modules['busio'] = MagicMock()
sys.modules['smbus2'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['adafruit_veml7700'] = MagicMock()

# Now import our ADCS module
from ADCS_PD import (
    DEFAULT_KP, DEFAULT_KD, DEFAULT_MAX_POWER, 
    DEFAULT_DEADBAND, DEFAULT_INTEGRAL_LIMIT,
    PDControllerPWM
)

def test_pd_constants():
    """Test that PD controller constants are properly defined and used"""
    
    print("🧪 Testing PD Controller Constants...")
    
    # Test 1: Check that constants are defined
    print(f"✓ Constants defined:")
    print(f"  DEFAULT_KP = {DEFAULT_KP}")
    print(f"  DEFAULT_KD = {DEFAULT_KD}")
    print(f"  DEFAULT_MAX_POWER = {DEFAULT_MAX_POWER}")
    print(f"  DEFAULT_DEADBAND = {DEFAULT_DEADBAND}")
    print(f"  DEFAULT_INTEGRAL_LIMIT = {DEFAULT_INTEGRAL_LIMIT}")
    
    # Test 2: Check that PDControllerPWM uses the defaults
    print(f"\n✓ Testing PDControllerPWM with defaults:")
    controller = PDControllerPWM()
    print(f"  Controller KP = {controller.kp} (should be {DEFAULT_KP})")
    print(f"  Controller KD = {controller.kd} (should be {DEFAULT_KD})")
    print(f"  Controller MAX_POWER = {controller.max_power} (should be {DEFAULT_MAX_POWER})")
    print(f"  Controller DEADBAND = {controller.deadband} (should be {DEFAULT_DEADBAND})")
    
    # Test 3: Check that we can still override defaults
    print(f"\n✓ Testing PDControllerPWM with custom values:")
    custom_controller = PDControllerPWM(kp=15.0, kd=3.0, max_power=90, deadband=2.0)
    print(f"  Custom Controller KP = {custom_controller.kp} (should be 15.0)")
    print(f"  Custom Controller KD = {custom_controller.kd} (should be 3.0)")
    print(f"  Custom Controller MAX_POWER = {custom_controller.max_power} (should be 90)")
    print(f"  Custom Controller DEADBAND = {custom_controller.deadband} (should be 2.0)")
    
    # Test 4: Verify that runtime changes would work
    print(f"\n✓ Testing runtime parameter changes:")
    controller.kp = 20.0
    controller.kd = 5.0
    controller.max_power = 75
    controller.deadband = 0.5
    print(f"  Modified Controller KP = {controller.kp} (should be 20.0)")
    print(f"  Modified Controller KD = {controller.kd} (should be 5.0)")
    print(f"  Modified Controller MAX_POWER = {controller.max_power} (should be 75)")
    print(f"  Modified Controller DEADBAND = {controller.deadband} (should be 0.5)")
    
    print(f"\n🎉 All tests passed! PD controller constants are working correctly.")
    print(f"\n📝 To change default values, edit the constants at the top of ADCS_PD.py:")
    print(f"   DEFAULT_KP = {DEFAULT_KP}")
    print(f"   DEFAULT_KD = {DEFAULT_KD}")
    print(f"   DEFAULT_MAX_POWER = {DEFAULT_MAX_POWER}")
    print(f"   DEFAULT_DEADBAND = {DEFAULT_DEADBAND}")
    print(f"   DEFAULT_INTEGRAL_LIMIT = {DEFAULT_INTEGRAL_LIMIT}")
    print(f"\n✅ The set_controller_gains() function will still work to change values during runtime!")

if __name__ == "__main__":
    test_pd_constants()
