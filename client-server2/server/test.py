#!/usr/bin/env python3
import smbus2, time

BUS = 1
ADDR = 0x62

# LiDAR-Lite v4 registers
ACQ_CMD  = 0x00
ACQ_VAL  = 0x04
STATUS   = 0x01
DIST_LO  = 0x10
DIST_HI  = 0x11

def read_distance(bus):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 1) Trigger measurement
            bus.write_byte_data(ADDR, ACQ_CMD, ACQ_VAL)
            
            # 2) Wait for measurement to complete (with timeout)
            timeout = 100  # 100 iterations max
            while timeout > 0:
                status = bus.read_byte_data(ADDR, STATUS)
                if not (status & 0x01):  # Bit 0 clear means ready
                    break
                time.sleep(0.005)
                timeout -= 1
            
            if timeout == 0:
                raise OSError("Measurement timeout")
            
            # 3) Read distance
            lo = bus.read_byte_data(ADDR, DIST_LO)
            hi = bus.read_byte_data(ADDR, DIST_HI)
            distance = (hi << 8) | lo
            
            # Validate reading (LiDAR-Lite v4 range is typically 5-4000 cm)
            if 5 <= distance <= 4000:
                return distance
            else:
                raise OSError(f"Invalid distance reading: {distance}")
                
        except OSError as e:
            if attempt == max_retries - 1:  # Last attempt
                raise e
            time.sleep(0.1)  # Wait before retry
    
    return None

def main():
    bus = smbus2.SMBus(BUS)
    try:
        print("Testing LiDAR sensor...")
        print("If you see I2C errors, try:")
        print("1. Check wiring connections")
        print("2. Reduce I2C bus speed: sudo nano /boot/config.txt")
        print("   Add: dtparam=i2c_arm_baudrate=50000")
        print("3. Check power supply to sensor")
        print()
        
        while True:
            try:
                d = read_distance(bus)
                print(f"✅ Distance: {d} cm")
            except OSError as e:
                print(f"❌ I2C error: {e}")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()

# Alternative register values for different LiDAR-Lite versions
def test_alternative_registers():
    """Test with alternative register addresses"""
    bus = smbus2.SMBus(BUS)
    try:
        print("🔧 Testing alternative register addresses...")
        
        # Alternative addresses for different LiDAR-Lite versions
        ALT_DIST_LO = 0x0f  # Some use 0x0f instead of 0x10
        ALT_DIST_HI = 0x10  # Some use 0x10 instead of 0x11
        
        # Trigger measurement
        bus.write_byte_data(ADDR, ACQ_CMD, ACQ_VAL)
        time.sleep(0.02)  # Wait for measurement
        
        # Try alternative registers
        try:
            lo = bus.read_byte_data(ADDR, ALT_DIST_LO)
            hi = bus.read_byte_data(ADDR, ALT_DIST_HI)
            distance = (hi << 8) | lo
            print(f"Alternative registers: {distance} cm")
        except Exception as e:
            print(f"Alternative registers failed: {e}")
            
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        bus.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "alt":
        test_alternative_registers()
    else:
        main()
