import RPi.GPIO as GPIO
import time

TACHO_PIN = 0  # Changed to GPIO 0 as requested

def run_tachometer(report_func):
    """Continuously sample TACHO_PIN and call report_func(rpm)."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TACHO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    prev_ref         = False
    initial_time     = None
    last_pulse_time  = None
    rpm              = 0.0

    try:
        while True:
            level = GPIO.input(TACHO_PIN)
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

            # if we haven’t seen a pulse in ≥1 s, force rpm=0
            if last_pulse_time and (time.perf_counter() - last_pulse_time) > 1.0:
                rpm = 0.0

            report_func(rpm)
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    finally:
        GPIO.cleanup()


# ── MANUAL TEST REPL ─────────────────────────────────────────
if __name__ == "__main__":
    print(f"Tachometer test: reading RPM on GPIO {TACHO_PIN} (Ctrl-C to exit)")
    print("Connect your tachometer data line to GPIO 0")
    print("Raw signal and RPM will be displayed...")
    try:
        def display_rpm(rpm):
            # Show both raw signal level and calculated RPM
            level = GPIO.input(TACHO_PIN)
            print(f"GPIO {TACHO_PIN} Level: {level} | RPM: {rpm:.1f}")
        
        run_tachometer(display_rpm)
    except KeyboardInterrupt:
        print("\nExiting tachometer test.")
    finally:
        GPIO.cleanup()