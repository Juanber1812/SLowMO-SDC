#!/usr/bin/env python3
"""
SLowMO-SDC Server Dependency Checker
Verifies all required packages and hardware interfaces are available
"""

import sys
import importlib
import subprocess
import os
from pathlib import Path

def check_color(success):
    """Return colored status indicators"""
    if success:
        return "✅"
    else:
        return "❌"

def check_import(module_name, optional=False):
    """Check if a module can be imported"""
    try:
        importlib.import_module(module_name)
        status = check_color(True)
        print(f"{status} {module_name}")
        return True
    except ImportError as e:
        status = check_color(False)
        optional_text = " (optional)" if optional else ""
        print(f"{status} {module_name}{optional_text} - {e}")
        return False

def check_system_command(command, description):
    """Check if a system command is available"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        success = result.returncode == 0
        status = check_color(success)
        print(f"{status} {description}")
        if not success and result.stderr:
            print(f"    Error: {result.stderr.strip()}")
        return success
    except Exception as e:
        status = check_color(False)
        print(f"{status} {description} - {e}")
        return False

def check_file_exists(filepath, description):
    """Check if a file or device exists"""
    exists = Path(filepath).exists()
    status = check_color(exists)
    print(f"{status} {description} ({filepath})")
    return exists

def main():
    print("🔍 SLowMO-SDC Server Dependency Checker")
    print("=" * 60)
    
    # Track overall success
    all_critical_ok = True
    
    print("\n📦 CORE WEB SERVER & COMMUNICATION")
    print("-" * 40)
    critical_web = [
        check_import("flask"),
        check_import("flask_socketio"),
        check_import("gevent"),
        check_import("socketio"),
    ]
    all_critical_ok &= all(critical_web)
    
    print("\n🔌 RASPBERRY PI HARDWARE INTERFACES")
    print("-" * 40)
    try:
        import platform
        is_raspberry_pi = "raspberry" in platform.platform().lower() or "arm" in platform.machine().lower()
        if is_raspberry_pi:
            critical_hw = [
                check_import("RPi.GPIO"),
                check_import("smbus"),
                check_import("smbus2"),
                check_import("picamera2"),
            ]
        else:
            print("⚠️  Not running on Raspberry Pi - hardware libraries will be simulated")
            critical_hw = [
                check_import("RPi.GPIO", optional=True),
                check_import("smbus", optional=True),
                check_import("smbus2", optional=True),
                check_import("picamera2", optional=True),
            ]
        all_critical_ok &= all(critical_hw) if is_raspberry_pi else True
    except Exception:
        is_raspberry_pi = False
        print("⚠️  Platform detection failed - assuming development environment")
    
    print("\n🌟 ADAFRUIT SENSOR LIBRARIES")
    print("-" * 40)
    adafruit_libs = [
        check_import("adafruit_veml7700", optional=True),
        check_import("adafruit_busdevice", optional=True),
        check_import("adafruit_tca9548a", optional=True),
        check_import("adafruit_blinka", optional=True),
        check_import("adafruit_ina228", optional=True),
    ]
    
    print("\n🌡️ TEMPERATURE MONITORING")
    print("-" * 40)
    temp_libs = [
        check_import("w1thermsensor", optional=True),
    ]
    
    print("\n📷 COMPUTER VISION & IMAGE PROCESSING")
    print("-" * 40)
    vision_libs = [
        check_import("cv2"),
        check_import("numpy"),
    ]
    all_critical_ok &= all(vision_libs)
    
    print("\n📊 DATA PROCESSING & ANALYSIS")
    print("-" * 40)
    data_libs = [
        check_import("pandas"),
        check_import("scipy", optional=True),
        check_import("matplotlib", optional=True),
    ]
    all_critical_ok &= check_import("pandas")  # Only pandas is critical
    
    print("\n💻 SYSTEM MONITORING")
    print("-" * 40)
    system_libs = [
        check_import("psutil"),
    ]
    all_critical_ok &= all(system_libs)
    
    print("\n🔧 SYSTEM COMMANDS & TOOLS")
    print("-" * 40)
    if is_raspberry_pi:
        system_commands = [
            check_system_command("i2cdetect -l", "I2C tools"),
            check_system_command("vcgencmd version", "VideoCore GPU commands"),
            check_system_command("gpio -v", "WiringPi GPIO tools (optional)"),
        ]
    else:
        print("⚠️  Skipping Raspberry Pi specific commands")
    
    print("\n📁 HARDWARE INTERFACES")
    print("-" * 40)
    if is_raspberry_pi:
        hardware_files = [
            check_file_exists("/dev/i2c-1", "I2C Bus 1"),
            check_file_exists("/sys/class/thermal/thermal_zone0/temp", "CPU Temperature"),
            check_file_exists("/sys/bus/w1/devices/", "1-Wire Bus"),
        ]
    else:
        print("⚠️  Skipping hardware interface checks (not on Raspberry Pi)")
    
    print("\n📋 PROJECT FILES")
    print("-" * 40)
    project_files = [
        check_file_exists("server2.py", "Main server"),
        check_file_exists("camera.py", "Camera module"),
        check_file_exists("mpu.py", "MPU sensor module"),
        check_file_exists("requirements.txt", "Requirements file"),
    ]
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if all_critical_ok:
        print("✅ All critical dependencies are satisfied!")
        print("🚀 Server should be ready to run.")
        
        print("\n🔧 Quick start commands:")
        print("   python3 server2.py              # Start main server")
        print("   python3 mpu.py                  # Test MPU sensor")
        print("   python3 -m pytest              # Run tests (if available)")
        
    else:
        print("❌ Some critical dependencies are missing!")
        print("📦 Install missing packages with:")
        print("   pip install -r requirements.txt")
        
        if is_raspberry_pi:
            print("\n🔧 Enable hardware interfaces:")
            print("   sudo raspi-config")
            print("   # Enable I2C, SPI, Camera, 1-Wire")
    
    print("\n📚 Additional setup:")
    print("   See SETUP_GUIDE.md for complete installation instructions")
    
    print("\n🐛 Troubleshooting:")
    print("   • Ensure you're running on Raspberry Pi for full functionality")
    print("   • Check hardware connections if sensors fail")
    print("   • Verify permissions for GPIO and I2C access")
    print("   • Update system packages: sudo apt update && sudo apt upgrade")
    
    return 0 if all_critical_ok else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
