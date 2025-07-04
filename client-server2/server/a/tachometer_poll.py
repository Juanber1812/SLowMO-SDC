import RPi.GPIO as GPIO
import time

def get_rpm_from_tachometer(pin=0, sample_time=0.1):
    """Poll the tachometer pin for one sample period and return the measured RPM."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    prev_ref = False
    initial_time = None
    last_pulse_time = None
    rpm = 0.0
    start = time.perf_counter()
    end = start + sample_time
    while time.perf_counter() < end:
        level = GPIO.input(pin)
        if level == GPIO.HIGH and not prev_ref:
            now = time.perf_counter()
            last_pulse_time = now
            if initial_time is None:
                initial_time = now
            else:
                period = now - initial_time
                rpm = 60.0 / period if period > 0 else 0.0
                initial_time = now
            prev_ref = True
        elif level == GPIO.LOW:
            prev_ref = False
        if last_pulse_time and (time.perf_counter() - last_pulse_time) > 1.0:
            rpm = 0.0
        time.sleep(0.001)
    GPIO.cleanup()
    return rpm
