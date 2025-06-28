#!/usr/bin/env python3
"""
Integrated MPU6050 + PD Controller + Motor System
Combines pitch feedback with lux sensor drift compensation and AprilTag reference correction
For spacecraft attitude control testing
"""

import time
import threading
import numpy as np
from datetime import datetime
import queue
import RPi.GPIO as GPIO
import board
import busio
import adafruit_veml7700

# Import our custom modules
from mpu import MPU6050
from pd_bangbang import PDController, rotate_clockwise_dc, rotate_counterclockwise_dc, stop_motor_dc, cleanup

class IntegratedAttitudeController:
    def __init__(self):
        """Initialize the integrated attitude control system"""
        
        # ── SENSOR INITIALIZATION ─────────────────────────────
        print("Initializing sensors...")
        
        # MPU6050 for attitude feedback
        self.mpu = MPU6050()
        
        # VEML7700 lux sensor for drift compensation
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.veml = adafruit_veml7700.VEML7700(i2c)
            self.lux_enabled = True
            print("VEML7700 lux sensor initialized")
        except Exception as e:
            print(f"Warning: Lux sensor not available: {e}")
            self.lux_enabled = False
        
        # ── CONTROLLER INITIALIZATION ─────────────────────────
        self.pd_controller = PDController(kp=1.0, kd=0.1, deadband=2.0)
        
        # ── CONTROL MODES ─────────────────────────────────────
        self.control_mode = "pitch"  # "pitch", "yaw", "manual"
        self.reference_source = "internal"  # "internal", "lux", "apriltag"
        
        # ── STATE VARIABLES ───────────────────────────────────
        self.current_pitch = 0.0
        self.current_yaw = 0.0
        self.target_angle = 0.0
        self.running = False
        
        # ── DRIFT COMPENSATION ────────────────────────────────
        self.lux_reference_angle = None
        self.lux_max_history = []
        self.lux_scan_active = False
        self.apriltag_reference = None
        self.drift_compensation_active = True
        
        # ── DATA LOGGING ──────────────────────────────────────
        self.data_queue = queue.Queue(maxsize=1000)
        self.logging_enabled = True
        
        # ── THREADING ─────────────────────────────────────────
        self.main_thread = None
        self.lux_thread = None
        
        print("Integrated attitude controller initialized!")
    
    def set_control_mode(self, mode):
        """Set control mode: 'pitch', 'yaw', or 'manual'"""
        valid_modes = ["pitch", "yaw", "manual"]
        if mode in valid_modes:
            self.control_mode = mode
            print(f"Control mode set to: {mode}")
        else:
            print(f"Invalid mode. Use: {valid_modes}")
    
    def set_reference_source(self, source):
        """Set reference source: 'internal', 'lux', or 'apriltag'"""
        valid_sources = ["internal", "lux", "apriltag"]
        if source in valid_sources:
            self.reference_source = source
            print(f"Reference source set to: {source}")
        else:
            print(f"Invalid source. Use: {valid_sources}")
    
    def start_lux_maxima_scan(self, scan_duration=30.0):
        """Start scanning for lux maxima to establish reference"""
        if not self.lux_enabled:
            print("Lux sensor not available!")
            return
        
        self.lux_scan_active = True
        self.lux_max_history.clear()
        
        def lux_scan_worker():
            print(f"Starting lux maxima scan for {scan_duration} seconds...")
            start_time = time.time()
            max_lux = 0
            max_angle = 0
            
            while self.lux_scan_active and (time.time() - start_time) < scan_duration:
                try:
                    # Read current sensors
                    mpu_data = self.mpu.read_all_data()
                    current_angle = mpu_data['angles']['pitch']
                    current_lux = self.veml.lux
                    
                    # Track maximum
                    if current_lux > max_lux:
                        max_lux = current_lux
                        max_angle = current_angle
                        self.lux_max_history.append({
                            'timestamp': time.time(),
                            'angle': current_angle,
                            'lux': current_lux
                        })
                    
                    print(f"\\rLux scan: {current_lux:.1f} lux @ {current_angle:.1f}° (max: {max_lux:.1f} @ {max_angle:.1f}°)", 
                          end='', flush=True)
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"\\nLux scan error: {e}")
                    break
            
            if self.lux_max_history:
                # Set reference to maximum lux angle
                self.lux_reference_angle = max_angle
                print(f"\\nLux reference established: {max_angle:.2f}° at {max_lux:.1f} lux")
            else:
                print("\\nNo lux maxima found during scan")
            
            self.lux_scan_active = False
        
        self.lux_thread = threading.Thread(target=lux_scan_worker, daemon=True)
        self.lux_thread.start()
    
    def set_apriltag_reference(self, relative_angle):
        """Set reference from AprilTag detection"""
        self.apriltag_reference = relative_angle
        print(f"AprilTag reference set: {relative_angle:.2f}°")
    
    def apply_drift_compensation(self, measured_angle):
        """Apply drift compensation based on reference source"""
        compensated_angle = measured_angle
        
        if not self.drift_compensation_active:
            return compensated_angle
        
        if self.reference_source == "lux" and self.lux_reference_angle is not None:
            # Compensate based on lux reference
            current_lux = self.veml.lux if self.lux_enabled else 0
            if current_lux > 50:  # Only compensate in good light
                drift_error = measured_angle - self.lux_reference_angle
                compensated_angle = measured_angle - (drift_error * 0.1)  # 10% compensation
                
        elif self.reference_source == "apriltag" and self.apriltag_reference is not None:
            # Compensate based on AprilTag reference
            drift_error = measured_angle - self.apriltag_reference
            compensated_angle = measured_angle - (drift_error * 0.2)  # 20% compensation
        
        return compensated_angle
    
    def control_loop(self):
        """Main control loop"""
        print(f"Starting control loop - Mode: {self.control_mode}, Reference: {self.reference_source}")
        
        loop_count = 0
        start_time = time.time()
        
        while self.running:
            try:
                # Read MPU6050 data
                mpu_data = self.mpu.read_all_data()
                angles = mpu_data['angles']
                
                # Select angle based on control mode
                if self.control_mode == "pitch":
                    current_angle = angles['pitch']
                elif self.control_mode == "yaw":
                    current_angle = angles['yaw']
                else:  # manual mode
                    time.sleep(0.1)
                    continue
                
                # Apply drift compensation
                compensated_angle = self.apply_drift_compensation(current_angle)
                
                # Update controller
                self.pd_controller.update_current_angle(compensated_angle)
                
                # Calculate control output
                control_output, error, derivative = self.pd_controller.calculate_control()
                
                # Apply bang-bang control
                if abs(error) < self.pd_controller.deadband:
                    stop_motor_dc()
                elif control_output > 0:
                    rotate_clockwise_dc()
                elif control_output < 0:
                    rotate_counterclockwise_dc()
                else:
                    stop_motor_dc()
                
                # Data logging
                if self.logging_enabled and loop_count % 10 == 0:  # Log every 10th iteration
                    log_data = {
                        'timestamp': datetime.now().isoformat(),
                        'mode': self.control_mode,
                        'reference': self.reference_source,
                        'raw_angle': current_angle,
                        'compensated_angle': compensated_angle,
                        'target_angle': self.pd_controller.target_angle,
                        'error': error,
                        'control_output': control_output,
                        'gyro': mpu_data['gyro'],
                        'accel': mpu_data['accel'],
                        'dt': mpu_data['dt']
                    }
                    
                    if self.lux_enabled:
                        log_data['lux'] = self.veml.lux
                    
                    try:
                        self.data_queue.put_nowait(log_data)
                    except queue.Full:
                        pass  # Skip if queue is full
                
                # Live display every 5th iteration
                if loop_count % 5 == 0:
                    lux_str = f" | Lux: {self.veml.lux:.1f}" if self.lux_enabled else ""
                    print(f"\\r{self.control_mode.upper()}: {compensated_angle:+6.1f}° → {self.pd_controller.target_angle:+6.1f}° | "
                          f"Err: {error:+5.1f}° | Out: {control_output:+6.2f}{lux_str}", 
                          end='', flush=True)
                
                loop_count += 1
                time.sleep(0.02)  # 50Hz control loop
                
            except Exception as e:
                print(f"\\nControl loop error: {e}")
                stop_motor_dc()
                break
        
        # Final cleanup
        stop_motor_dc()
        print("\\nControl loop stopped")
    
    def start_control(self, target_angle=0.0):
        """Start the integrated control system"""
        if self.running:
            print("Control already running!")
            return
        
        self.target_angle = target_angle
        self.pd_controller.set_target(target_angle)
        self.running = True
        
        self.main_thread = threading.Thread(target=self.control_loop, daemon=True)
        self.main_thread.start()
        print(f"Control started - Target: {target_angle}°")
    
    def stop_control(self):
        """Stop the control system"""
        self.running = False
        self.lux_scan_active = False
        
        if self.main_thread:
            self.main_thread.join(timeout=2.0)
        
        stop_motor_dc()
        print("Control stopped")
    
    def tune_controller(self, kp=None, kd=None, deadband=None):
        """Tune PD controller parameters"""
        if kp is not None:
            self.pd_controller.kp = kp
        if kd is not None:
            self.pd_controller.kd = kd
        if deadband is not None:
            self.pd_controller.deadband = deadband
        
        print(f"Controller tuned: Kp={self.pd_controller.kp:.3f}, Kd={self.pd_controller.kd:.3f}, "
              f"Deadband={self.pd_controller.deadband:.1f}°")
    
    def get_status(self):
        """Get comprehensive system status"""
        mpu_data = self.mpu.read_all_data()
        
        status = {
            'running': self.running,
            'control_mode': self.control_mode,
            'reference_source': self.reference_source,
            'angles': mpu_data['angles'],
            'target_angle': self.pd_controller.target_angle,
            'error': self.pd_controller.target_angle - mpu_data['angles']['pitch'],
            'controller': self.pd_controller.get_status(),
            'lux_enabled': self.lux_enabled,
            'drift_compensation': self.drift_compensation_active
        }
        
        if self.lux_enabled:
            status['lux'] = self.veml.lux
            status['lux_reference'] = self.lux_reference_angle
        
        if self.apriltag_reference is not None:
            status['apriltag_reference'] = self.apriltag_reference
        
        return status
    
    def save_log_data(self, filename=None):
        """Save logged data to CSV file"""
        if filename is None:
            filename = f"attitude_control_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        import csv
        data_list = []
        
        while not self.data_queue.empty():
            try:
                data_list.append(self.data_queue.get_nowait())
            except queue.Empty:
                break
        
        if data_list:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=data_list[0].keys())
                writer.writeheader()
                writer.writerows(data_list)
            print(f"Logged {len(data_list)} data points to {filename}")
        else:
            print("No data to save")

# ── GLOBAL CONTROLLER INSTANCE ───────────────────────────────────────
attitude_controller = IntegratedAttitudeController()

# ── COMMAND LINE INTERFACE ───────────────────────────────────────────
def main():
    """Interactive command line interface"""
    print("\\n" + "="*70)
    print("🚀 INTEGRATED ATTITUDE CONTROL SYSTEM")
    print("="*70)
    print("Commands:")
    print("  start <angle>     - Start control to target angle")
    print("  stop              - Stop control")
    print("  mode <pitch/yaw>  - Set control mode")
    print("  ref <source>      - Set reference source (internal/lux/apriltag)")
    print("  lux_scan <sec>    - Scan for lux maxima reference")
    print("  apriltag <angle>  - Set AprilTag reference angle")
    print("  tune <kp> <kd>    - Tune PD parameters")
    print("  status            - Show system status")
    print("  log               - Save log data")
    print("  manual <cmd>      - Manual motor control (cw/ccw/stop)")
    print("  quit              - Exit")
    print("="*70)
    
    try:
        while True:
            cmd = input("\\nAttitude> ").strip().split()
            
            if not cmd:
                continue
            
            if cmd[0] == "quit" or cmd[0] == "q":
                break
            
            elif cmd[0] == "start" and len(cmd) == 2:
                try:
                    target = float(cmd[1])
                    attitude_controller.start_control(target)
                except ValueError:
                    print("Invalid target angle")
            
            elif cmd[0] == "stop":
                attitude_controller.stop_control()
            
            elif cmd[0] == "mode" and len(cmd) == 2:
                attitude_controller.set_control_mode(cmd[1])
            
            elif cmd[0] == "ref" and len(cmd) == 2:
                attitude_controller.set_reference_source(cmd[1])
            
            elif cmd[0] == "lux_scan":
                duration = 30.0
                if len(cmd) == 2:
                    try:
                        duration = float(cmd[1])
                    except ValueError:
                        pass
                attitude_controller.start_lux_maxima_scan(duration)
            
            elif cmd[0] == "apriltag" and len(cmd) == 2:
                try:
                    angle = float(cmd[1])
                    attitude_controller.set_apriltag_reference(angle)
                except ValueError:
                    print("Invalid angle")
            
            elif cmd[0] == "tune" and len(cmd) == 3:
                try:
                    kp = float(cmd[1])
                    kd = float(cmd[2])
                    attitude_controller.tune_controller(kp=kp, kd=kd)
                except ValueError:
                    print("Invalid parameters")
            
            elif cmd[0] == "status":
                status = attitude_controller.get_status()
                print(f"\\nSystem Status:")
                print(f"  Running: {status['running']}")
                print(f"  Mode: {status['control_mode']}")
                print(f"  Reference: {status['reference_source']}")
                print(f"  Pitch: {status['angles']['pitch']:+6.2f}°")
                print(f"  Yaw: {status['angles']['yaw']:+6.2f}°")
                print(f"  Target: {status['target_angle']:+6.2f}°")
                print(f"  Error: {status['error']:+6.2f}°")
                if 'lux' in status:
                    print(f"  Lux: {status['lux']:.1f}")
            
            elif cmd[0] == "log":
                attitude_controller.save_log_data()
            
            elif cmd[0] == "manual" and len(cmd) == 2:
                attitude_controller.set_control_mode("manual")
                if cmd[1] == "cw":
                    rotate_clockwise_dc()
                elif cmd[1] == "ccw":
                    rotate_counterclockwise_dc()
                elif cmd[1] == "stop":
                    stop_motor_dc()
            
            else:
                print("Unknown command or wrong parameters")
    
    except KeyboardInterrupt:
        print("\\nInterrupted...")
    
    finally:
        attitude_controller.stop_control()
        cleanup()
        print("System shutdown complete.")

if __name__ == "__main__":
    main()
