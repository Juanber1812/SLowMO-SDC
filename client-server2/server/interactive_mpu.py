#!/usr/bin/env python3
"""
Interactive MPU6050 with CSV Logging Control
Allows live control of CSV logging while displaying real-time IMU data
"""

import threading
import sys
import select
import tty
import termios
from mpu import MPU6050

class InteractiveMPU:
    def __init__(self):
        self.mpu = MPU6050()
        self.running = True
        
    def get_char(self):
        """Get single character input (non-blocking on Unix)"""
        try:
            if sys.platform == 'win32':
                import msvcrt
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8').lower()
            else:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(sys.stdin.fileno())
                    if select.select([sys.stdin], [], [], 0.01) == ([sys.stdin], [], []):
                        ch = sys.stdin.read(1)
                        return ch.lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except:
            pass
        return None
    
    def print_help(self):
        """Print available commands"""
        print("\n" + "=" * 70)
        print("INTERACTIVE MPU6050 WITH CSV LOGGING")
        print("=" * 70)
        print("Commands:")
        print("  'l' - Start CSV logging (10Hz)")
        print("  's' - Stop CSV logging")
        print("  'z' - Zero pitch angle (secondary)")
        print("  'r' - Reset yaw to zero (primary control)")
        print("  'c' - Calibrate gyroscope")
        print("  'h' - Show this help")
        print("  'q' - Quit")
        print("=" * 70)
        
    def run(self):
        """Main interactive loop"""
        self.print_help()
        
        try:
            while self.running:
                # Handle keyboard input
                char = self.get_char()
                if char:
                    if char == 'q':
                        print("\nExiting...")
                        break
                    elif char == 'l':
                        print("\nStarting CSV logging...")
                        self.mpu.start_csv_logging()
                    elif char == 's':
                        print("\nStopping CSV logging...")
                        self.mpu.stop_csv_logging()
                    elif char == 'z':
                        print("\nZeroing pitch angle...")
                        self.mpu.reset_pitch()
                    elif char == 'r':
                        print("\nResetting yaw to zero (primary control)...")
                        self.mpu.calibrate_at_current_position()
                    elif char == 'c':
                        print("\nCalibrating gyroscope (keep sensor still)...")
                        self.mpu.calibrate_gyro()
                        print("Calibration complete!")
                    elif char == 'h':
                        self.print_help()
                
                # Read and display sensor data
                data = self.mpu.read_all_data()
                self.mpu.log_data_if_needed()
                
                # Extract data for display
                accel = data['accel']
                gyro = data['gyro']
                angles = data['angles']
                temp = data['temperature']
                
                # Live display with logging status (updated order: yaw first)
                log_status = " [LOGGING]" if self.mpu.enable_logging else ""
                live_display = (
                    f"\rYaw: {angles['yaw']:+6.1f}° | "      # Primary control (was pitch)
                    f"Roll: {angles['roll']:+6.1f}° | "
                    f"Pitch: {angles['pitch']:+6.1f}° | "   # Secondary (was yaw)
                    f"Accel: X={accel['x']:+5.2f}g Y={accel['y']:+5.2f}g Z={accel['z']:+5.2f}g | "
                    f"Gyro: X={gyro['x']:+5.1f} Y={gyro['y']:+5.1f} Z={gyro['z']:+5.1f} °/s | "
                    f"T: {temp:4.1f}°C{log_status} | Press 'h' for help"
                )
                
                print(live_display, end='', flush=True)
                
        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt received...")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.mpu.stop_csv_logging()
            print("\nCleanup complete.")

if __name__ == "__main__":
    interactive_mpu = InteractiveMPU()
    interactive_mpu.run()
