import time
from adcs import motor

class PDBangBangController:
    """
    A PD controller that drives the motor in bang-bang mode
    with minimum pulse time and deadband support.
    """

    def __init__(self, kp=1.5, kd=0.3, deadband=1.0, min_pulse_time=0.2):
        """
        Parameters:
            kp (float): Proportional gain
            kd (float): Derivative gain
            deadband (float): Acceptable error range in degrees
            min_pulse_time (float): Minimum motor on-time in seconds
        """
        self.kp = kp
        self.kd = kd
        self.deadband = deadband
        self.min_pulse_time = min_pulse_time
        self.last_error = 0.0
        self.last_time = time.time()

    def set_gains(self, kp, kd):
        """Set new proportional and derivative gains."""
        self.kp = kp
        self.kd = kd

    def set_deadband(self, db):
        """Set a new deadband in degrees."""
        self.deadband = db

    def compute_correction(self, current_angle, target_angle):
        """
        Compute PD correction based on angle error and rate of change.
        Returns a signed correction value (not used directly in bang-bang).
        """
        now = time.time()
        dt = now - self.last_time if (now - self.last_time) > 0 else 1e-3

        error = target_angle - current_angle
        d_error = (error - self.last_error) / dt

        output = self.kp * error + self.kd * d_error

        self.last_error = error
        self.last_time = now

        return output

    def control(self, current_angle, target_angle):
        """
        Apply bang-bang control based on PD error calculation.
        Rotates the motor in the required direction for a fixed pulse time.
        """
        error = target_angle - current_angle
        abs_error = abs(error)

        if abs_error < self.deadband:
            motor.stop_motor()
            return

        if error > 0:
            motor.rotate_clockwise()
        else:
            motor.rotate_counterclockwise()

        time.sleep(self.min_pulse_time)
        motor.stop_motor()
