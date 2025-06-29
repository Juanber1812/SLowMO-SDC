#!/usr/bin/env python3
"""
Test script for communication monitoring module.
Tests the CommunicationMonitor class functionality.
"""

import sys
import os
import time

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

try:
    from communication import CommunicationMonitor
    print("✓ CommunicationMonitor imported successfully")
except ImportError as e:
    print(f"✗ Failed to import CommunicationMonitor: {e}")
    print("Make sure to install requirements: pip install speedtest-cli psutil")
    sys.exit(1)

def test_callback(data):
    """Test callback function to receive communication data"""
    print(f"\n[CALLBACK] Communication data received:")
    for key, value in data.items():
        print(f"  {key}: {value}")

def main():
    print("Testing Communication Monitor...")
    print("=" * 50)
    
    # Create communication monitor
    comm_monitor = CommunicationMonitor()
    
    # Set callback
    comm_monitor.set_update_callback(test_callback)
    
    # Test getting current data (should be empty/default)
    print("\n1. Initial data:")
    initial_data = comm_monitor.get_current_data()
    for key, value in initial_data.items():
        print(f"  {key}: {value}")
    
    # Test recording upload data
    print("\n2. Testing upload data recording...")
    for i in range(5):
        comm_monitor.record_upload_data(1024 * (i + 1))  # Simulate varying upload sizes
        time.sleep(0.2)
    
    # Get data after upload recording
    print("\n3. Data after upload recording:")
    updated_data = comm_monitor.get_current_data()
    for key, value in updated_data.items():
        print(f"  {key}: {value}")
    
    # Test signal strength update
    print("\n4. Testing signal strength update...")
    comm_monitor.update_client_signal_strength(-65)
    
    # Start monitoring for a short time
    print("\n5. Starting monitoring for 10 seconds...")
    if comm_monitor.start_monitoring():
        print("✓ Monitoring started successfully")
        time.sleep(10)
        comm_monitor.stop_monitoring()
        print("✓ Monitoring stopped")
    else:
        print("✗ Failed to start monitoring")
    
    print("\n6. Final data:")
    final_data = comm_monitor.get_current_data()
    for key, value in final_data.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 50)
    print("Communication Monitor test completed!")
    print("\nNote: WiFi speed test may take time and requires internet connection.")
    print("Signal strength detection depends on your operating system and WiFi setup.")

if __name__ == "__main__":
    main()
