
#!/usr/bin/env python3
"""
tachometer_raw.py

Continuously read the raw digital output from a tachometer connected to a Raspberry Pi GPIO pin and print timestamped logic levels.
Usage:
    python tachometer_raw.py --pin <GPIO_PIN> [--interval <seconds>]
"""
import RPi.GPIO as GPIO
import time
import argparse

def run_raw_reader(pin, interval=0.1):
    """Read and print raw GPIO input at fixed intervals."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    try:
        while True:
            level = GPIO.input(pin)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            print(f"{timestamp} | GPIO {pin} Level: {level}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping raw output reader.")
    finally:
        GPIO.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Tachometer Raw Output Reader")
    parser.add_argument("--pin", type=int, default=0,
                        help="BCM GPIO pin number where the tachometer signal is connected")
    parser.add_argument("--interval", type=float, default=0.1,
                        help="Sampling interval in seconds (default: 0.1)")
    args = parser.parse_args()

    print(f"Starting raw reader on GPIO {args.pin} at {args.interval}s intervals. Ctrl+C to exit.")
    run_raw_reader(args.pin, args.interval)

if __name__ == "__main__":
    main()
