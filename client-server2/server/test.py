import pigpio
import time

PWM_GPIO = 18  # GPIO pin where LIDAR PWM is connected
pi = pigpio.pi()

if not pi.connected:
    print("❌ Cannot connect to pigpio daemon")
    exit(1)

def cb_func(gpio, level, tick):
    global start_tick, pulse_width_us
    if level == 1:  # Rising edge
        start_tick = tick
    elif level == 0:  # Falling edge
        if start_tick is not None:
            pulse_width_us = pigpio.tickDiff(start_tick, tick)
            distance_cm = pulse_width_us / 10.0
            print(f"📏 Distance: {distance_cm:.2f} cm")

start_tick = None
pulse_width_us = 0

# Set up callback
pi.set_mode(PWM_GPIO, pigpio.INPUT)
pi.set_pull_up_down(PWM_GPIO, pigpio.PUD_DOWN)
cb = pi.callback(PWM_GPIO, pigpio.EITHER_EDGE, cb_func)

print("📡 Listening for PWM pulses from LIDAR...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[EXIT] Stopping PWM listener")
    cb.cancel()
    pi.stop()
