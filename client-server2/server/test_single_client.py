# test_single_client.py

"""
Test script to verify single-client functionality
"""

import socketio
import time
import threading

def test_single_client_limit():
    """Test that only one client can connect at a time"""
    
    print("Testing single client connection limit...")
    
    # Create first client
    client1 = socketio.Client()
    client2 = socketio.Client()
    
    # Event handlers for client1
    @client1.event
    def connect():
        print("✅ Client 1: Connected successfully")
    
    @client1.event
    def connection_accepted(data):
        print(f"✅ Client 1: Connection accepted - {data}")
    
    @client1.event
    def connection_rejected(data):
        print(f"❌ Client 1: Connection rejected - {data}")
    
    @client1.event
    def disconnect():
        print("🔌 Client 1: Disconnected")
    
    # Event handlers for client2
    @client2.event
    def connect():
        print("✅ Client 2: Connected successfully")
    
    @client2.event
    def connection_accepted(data):
        print(f"✅ Client 2: Connection accepted - {data}")
    
    @client2.event
    def connection_rejected(data):
        print(f"❌ Client 2: Connection rejected - {data}")
    
    @client2.event
    def disconnect():
        print("🔌 Client 2: Disconnected")
    
    try:
        # Connect first client
        print("\n1. Connecting first client...")
        client1.connect('http://localhost:5000')
        time.sleep(2)
        
        # Try to connect second client (should be rejected)
        print("\n2. Attempting to connect second client (should be rejected)...")
        try:
            client2.connect('http://localhost:5000')
            time.sleep(2)
        except Exception as e:
            print(f"Client 2 connection failed as expected: {e}")
        
        # Test client status
        print("\n3. Getting client status...")
        client1.emit('get_client_status')
        time.sleep(1)
        
        # Test data transmission rate
        print("\n4. Getting data transmission rate...")
        client1.emit('get_data_transmission_rate')
        time.sleep(1)
        
        # Disconnect first client
        print("\n5. Disconnecting first client...")
        client1.disconnect()
        time.sleep(2)
        
        # Now try connecting second client (should succeed)
        print("\n6. Connecting second client after first disconnected...")
        client2.connect('http://localhost:5000')
        time.sleep(2)
        
        print("\n✅ Single client test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    finally:
        # Cleanup
        try:
            if client1.connected:
                client1.disconnect()
            if client2.connected:
                client2.disconnect()
        except:
            pass

if __name__ == "__main__":
    print("🧪 Single Client Connection Test")
    print("Make sure the server is running on localhost:5000")
    print("-" * 50)
    
    test_single_client_limit()
