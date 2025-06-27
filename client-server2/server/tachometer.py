import RPi.GPIO as GPIO
import time

TACHO_PIN = 17

def run_tachometer(report_func):
    """Continuously sample TACHO_PIN and call report_func(rpm)."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TACHO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    prev_ref     = False
    initial_time = None
    rpm          = 0.0

    try:
        while True:
            level = GPIO.input(TACHO_PIN)
            if level == GPIO.HIGH and not prev_ref:
                now = time.perf_counter()
                if initial_time is None:
                    initial_time = now
                else:
                    period = now - initial_time
                    rpm    = 60.0 / period if period>0 else 0.0
                    initial_time = now
                prev_ref = True
            elif level == GPIO.LOW:
                prev_ref = False

            report_func(rpm)
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    # standalone mode just prints
    run_tachometer(lambda r: print(f"RPM: {r:.1f}"))