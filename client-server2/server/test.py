#!/usr/bin/env python3
"""
tachometer_test.py

A simple test script for reading RPM from a tachometer sensor on a Raspberry Pi GPIO pin.
Usage:
    python tachometer_test.py --pin <GPIO_PIN>

Connect your tachometer signal line to the specified GPIO pin.
"""
import RPi.GPIO as GPIO
import time
import argparse

def run_tachometer(pin, report_func, sample_interval=0.1):
    """Continuously sample TACHO_PIN and call report_func(rpm)."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    prev_ref         = False
    initial_time     = None
    last_pulse_time  = None
    rpm              = 0.0

    try:
        while True:
            level = GPIO.input(pin)
            if level == GPIO.HIGH and not prev_ref:
                now = time.perf_counter()
                last_pulse_time = now
                if initial_time is None:
                    initial_time = now
                else:
                    period = now - initial_time
                    rpm    = 60.0 / period if period > 0 else 0.0
                    initial_time = now
                prev_ref = True
            elif level == GPIO.LOW:
                prev_ref = False

            # if we haven’t seen a pulse in ≥1s, force rpm=0
            if last_pulse_time and (time.perf_counter() - last_pulse_time) > 1.0:
                rpm = 0.0

            report_func(level, rpm)
            time.sleep(sample_interval)

    except KeyboardInterrupt:
        pass

    finally:
        GPIO.cleanup()


def display_rpm(level, rpm):
    """Default reporting function: prints the raw level and RPM."""
    print(f"Level: {level} | RPM: {rpm:.1f}", end='\r')


def main():
    parser = argparse.ArgumentParser(description="Tachometer test on Raspberry Pi GPIO")
    parser.add_argument("--pin", type=int, default=0,
                        help="BCM GPIO pin number where the tachometer is connected (default: 0)")
    parser.add_argument("--interval", type=float, default=0.1,
                        help="Sampling interval in seconds (default: 0.1)")
    args = parser.parse_args()

    print(f"Tachometer test: reading RPM on GPIO {args.pin} (Ctrl-C to exit)")
    print("Connect your tachometer data line to that pin.")

    run_tachometer(args.pin, display_rpm, sample_interval=args.interval)
    print("\nExiting tachometer test.")

if __name__ == "__main__":
    main()
