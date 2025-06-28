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
        print("  'f' - Show current CSV file path")
        print("  'z' - Zero pitch angle (secondary)")
        print("  'r' - Reset yaw to zero (primary control)")
        print("  'c' - Calibrate gyroscope")
        print("  'h' - Show this help")
        print("  'q' - Quit")
        print("=" * 70)
        
    def show_csv_file_info(self):
        """Show information about CSV files and current logging status"""
        import os
        import glob
        from datetime import datetime
        
        print("\n" + "=" * 70)
        print("CSV FILE INFORMATION")
        print("=" * 70)
        
        # Show current working directory
        current_dir = os.getcwd()
        print(f"Current directory: {current_dir}")
        
        # Show current logging status
        if self.mpu.enable_logging and hasattr(self.mpu, 'log_file') and self.mpu.log_file:
            print(f"Currently logging to: {self.mpu.log_file.name}")
            print(f"Logging status: ACTIVE")
        else:
            print("Logging status: INACTIVE")
        
        # Find all CSV files in current directory
        csv_files = glob.glob("*.csv")
        imu_csv_files = glob.glob("imu_data_*.csv")
        
        if imu_csv_files:
            print(f"\nFound {len(imu_csv_files)} IMU CSV files:")
            # Sort by modification time (newest first)
            imu_csv_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            for i, file in enumerate(imu_csv_files[:5]):  # Show last 5 files
                file_path = os.path.abspath(file)
                file_size = os.path.getsize(file)
                mod_time = datetime.fromtimestamp(os.path.getmtime(file))
                
                print(f"  {i+1}. {file}")
                print(f"     Path: {file_path}")
                print(f"     Size: {file_size} bytes")
                print(f"     Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
            if len(imu_csv_files) > 5:
                print(f"     ... and {len(imu_csv_files) - 5} more files")
        else:
            print("\nNo IMU CSV files found in current directory")
            if csv_files:
                print(f"Other CSV files found: {len(csv_files)}")
        
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
                    elif char == 'f':
                        self.show_csv_file_info()
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
