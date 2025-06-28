#!/usr/bin/env python3
"""
Tachometer Explanation and Test Script
Understanding how the reaction wheel RPM measurement works
"""

import time

def explain_tachometer():
    """Explain how the tachometer works"""
    print("="*80)
    print("REACTION WHEEL TACHOMETER - How It Works")
    print("="*80)
    print()
    
    print("🔧 HARDWARE SETUP:")
    print("   • GPIO Pin 17 connected to tachometer sensor")
    print("   • Sensor detects magnetic field, hall effect, or optical pulse")
    print("   • One pulse per revolution of the reaction wheel")
    print("   • Pull-down resistor ensures clean LOW when no pulse")
    print()
    
    print("⚡ SIGNAL PATTERN:")
    print("   HIGH ┐     ┐     ┐     ┐")
    print("        │     │     │     │  ← Each pulse = 1 revolution")
    print("   LOW  └─────┘─────┘─────┘")
    print("        ←─T─→")
    print("        Period T between pulses")
    print()
    
    print("🧮 RPM CALCULATION:")
    print("   • Period T = time between rising edges")
    print("   • Frequency = 1/T (revolutions per second)")
    print("   • RPM = (1/T) × 60 (revolutions per minute)")
    print("   • Example: T=0.1s → RPM = 600")
    print()
    
    print("💻 SOFTWARE LOGIC:")
    print("   1. Continuously poll GPIO Pin 17")
    print("   2. Detect rising edge (LOW → HIGH transition)")
    print("   3. Measure time since last rising edge")
    print("   4. Calculate RPM = 60/period")
    print("   5. If no pulse for >1 second → RPM = 0")
    print()
    
    print("🔍 CODE BREAKDOWN:")
    print("   • prev_ref: Tracks previous GPIO state")
    print("   • initial_time: Time of current pulse")
    print("   • period: Time between consecutive pulses")
    print("   • Timeout: Reset RPM to 0 if wheel stops")
    print()

def simulate_tachometer_readings():
    """Simulate tachometer readings for different wheel speeds"""
    print("="*80)
    print("SIMULATED TACHOMETER READINGS")
    print("="*80)
    print("Time | Period | RPM   | Wheel Status")
    print("(s)  | (ms)   |       |")
    print("-"*40)
    
    scenarios = [
        (0.0, 100, "Accelerating"),
        (2.0, 50, "Higher speed"),
        (4.0, 25, "Maximum speed"),
        (6.0, 50, "Decelerating"), 
        (8.0, 100, "Slower"),
        (10.0, None, "Stopped"),
        (12.0, 200, "Slow restart"),
        (14.0, 75, "Normal operation")
    ]
    
    for time_point, period_ms, status in scenarios:
        if period_ms is None:
            rpm = 0.0
            period_str = "∞"
        else:
            period_s = period_ms / 1000.0
            rpm = 60.0 / period_s
            period_str = f"{period_ms:3.0f}"
        
        print(f"{time_point:4.1f} | {period_str:>6} | {rpm:5.0f} | {status}")
        time.sleep(0.5)

def analyze_your_tachometer_code():
    """Analyze the actual tachometer code"""
    print("\n" + "="*80)
    print("YOUR TACHOMETER CODE ANALYSIS")
    print("="*80)
    
    code_explanation = """
def run_tachometer(report_func):
    GPIO.setup(TACHO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # ↑ Pin 17 as input with pull-down resistor
    
    prev_ref = False          # Previous GPIO state
    initial_time = None       # Time of current pulse  
    last_pulse_time = None    # Time of last pulse (for timeout)
    rpm = 0.0                # Current RPM reading
    
    while True:
        level = GPIO.input(TACHO_PIN)  # Read current GPIO state
        
        # RISING EDGE DETECTION
        if level == GPIO.HIGH and not prev_ref:
            now = time.perf_counter()
            last_pulse_time = now
            
            if initial_time is None:
                initial_time = now  # First pulse - start timing
            else:
                period = now - initial_time  # Time since last pulse
                rpm = 60.0 / period if period > 0 else 0.0
                initial_time = now   # Reset for next period
            prev_ref = True
            
        elif level == GPIO.LOW:
            prev_ref = False  # Reset edge detection
        
        # TIMEOUT HANDLING
        if last_pulse_time and (time.perf_counter() - last_pulse_time) > 1.0:
            rpm = 0.0  # No pulse for 1 second = stopped
        
        report_func(rpm)  # Send RPM to callback
        time.sleep(0.1)   # 10 Hz polling rate
"""
    
    print("KEY FEATURES:")
    print("✓ Rising edge detection (LOW → HIGH)")
    print("✓ Period measurement between pulses")
    print("✓ Timeout detection (wheel stopped)")
    print("✓ Real-time RPM calculation")
    print("✓ Callback function for data reporting")
    print()
    print("INTEGRATION WITH ADCS:")
    print("• RPM data sent via SocketIO to client")
    print("• Can be used for wheel momentum monitoring")
    print("• Helps verify motor commands are working")
    print("• Useful for PD controller tuning")

def main():
    """Main test function"""
    try:
        explain_tachometer()
        input("\nPress Enter to see simulated readings...")
        simulate_tachometer_readings()
        input("\nPress Enter for code analysis...")
        analyze_your_tachometer_code()
        
        print("\n" + "="*80)
        print("NEXT STEPS FOR YOUR ADCS:")
        print("="*80)
        print("1. Test tachometer with: python3 tachometer.py")
        print("2. Verify RPM readings when motor runs")
        print("3. Check RPM goes to 0 when motor stops")
        print("4. Monitor RPM in your PyQt client GUI")
        print("5. Use RPM data to verify ADCS control effectiveness")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\nTest completed.")

if __name__ == "__main__":
    main()
