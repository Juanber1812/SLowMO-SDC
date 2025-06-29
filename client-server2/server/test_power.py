#!/usr/bin/env python3
"""
Test script for the PowerMonitor integration
"""

import sys
import os
import time

# Add server directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

from server.power import PowerMonitor

def test_power_monitor():
    """Test the PowerMonitor class functionality"""
    print("🔋 Testing PowerMonitor...")
    
    # Initialize power monitor - will try to connect to real hardware
    monitor = PowerMonitor(update_interval=1.0)
    
    def power_callback(data):
        if data.get('status') == 'Disconnected':
            print("📊 Power Monitor: Disconnected - No hardware detected")
        else:
            print(f"📊 Power Data: "
                  f"Current: {data['current_ma']:.1f}mA, "
                  f"Voltage: {data['voltage_v']:.2f}V, "
                  f"Power: {data['power_mw']:.1f}mW, "
                  f"Energy: {data['energy_j']:.2f}J, "
                  f"Temp: {data['temperature_c']:.1f}°C, "
                  f"Battery: {data['battery_percentage']}%")
    
    # Set callback
    monitor.set_update_callback(power_callback)
    
    print("Starting power monitoring...")
    if monitor.start_monitoring():
        try:
            # Let it run for a few iterations
            time.sleep(5)
            
            # Test getting latest data
            latest = monitor.get_latest_data()
            print(f"\n📋 Latest Data: {latest}")
            
            # Test status
            status = monitor.get_status()
            print(f"📈 Status: {status}")
            
            print("\n✅ PowerMonitor test completed successfully!")
            
        except KeyboardInterrupt:
            print("\n⏹️  Test interrupted by user")
        finally:
            monitor.stop_monitoring()
    else:
        print("❌ Failed to start power monitoring")

if __name__ == "__main__":
    test_power_monitor()
