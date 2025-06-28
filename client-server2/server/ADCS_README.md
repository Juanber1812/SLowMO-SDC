# Integrated ADCS Control System - Single Axis Yaw Control

This directory contains a complete Attitude Determination and Control System (ADCS) for satellite control using a Raspberry Pi, MPU-6050 motion sensor, VEML7700 light sensor, and a single reaction wheel motor for yaw axis control.

**Note:** This system is designed for a cube satellite hanging from the ceiling, rotating in the horizontal plane around the vertical (Z) axis.

## Files Overview

### Core ADCS Files
- **`adcs_integrated.py`** - Main integrated ADCS system with sensor reading, orientation calculation, and PD control
- **`adcs_network.py`** - Network interface for remote control via Flask-SocketIO
- **`adcs_example.py`** - Simple example showing how to use the ADCS system
- **`adcs_requirements.txt`** - Python package requirements

### Legacy/Development Files
- **`pd_motor_control.py`** - Original PD controller (now integrated into `adcs_integrated.py`)
- **`lux+motion.py`** - Original sensor test script
- **`motor_test.py`** - Basic motor control test

## Hardware Setup

### Required Components
1. **Raspberry Pi** (3B+ or 4 recommended)
2. **MPU-6050** - 6-axis motion sensor (accelerometer + gyroscope)
3. **VEML7700** - Ambient light sensor
4. **Motor Driver** - Compatible with GPIO control (e.g., MP6550)
5. **Reaction Wheel Motor** - DC motor for attitude control

### Wiring Connections

#### Motor Driver (GPIO)
```
GPIO Pin 19  → DIR_PIN    (Direction control)
GPIO Pin 13  → ENABLE_PIN (Enable/PWM control)
GPIO Pin 26  → SLEEP_PIN  (Standby control)
```

#### I2C Sensors
```
GPIO Pin 2   → SDA (I2C Data)
GPIO Pin 3   → SCL (I2C Clock)
3.3V         → VCC (Both sensors)
GND          → GND (Both sensors)
```

## Installation

1. **Install system dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv i2c-tools
   sudo raspi-config  # Enable I2C interface
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv adcs_env
   source adcs_env/bin/activate
   ```

3. **Install Python packages:**
   ```bash
   pip install -r adcs_requirements.txt
   ```

4. **Verify I2C devices:**
   ```bash
   i2cdetect -y 1
   # Should show MPU-6050 at 0x68 and VEML7700 at 0x10
   ```

## Usage

### Quick Start
```bash
# Run the integrated ADCS system
python3 adcs_integrated.py

# Or run the example script
python3 adcs_example.py
```

### Interactive Commands

When running `adcs_integrated.py`, you can use these commands:

#### Basic Control
- `start [yaw]` - Start ADCS control (yaw angle in degrees, default: 0°)
- `stop` - Stop ADCS control
- `target <yaw>` - Set new target yaw angle
- `status` - Show system status
- `sensors` - Show current sensor readings

#### Tuning
- `tune <kp> <kd>` - Adjust PD controller gains
- `deadband <degrees>` - Set deadband threshold

#### Data Logging
- `log [filename]` - Save sensor data to CSV file

#### Manual Control
- `manual` - Enter manual motor control mode
  - `cw` - Rotate clockwise
  - `ccw` - Rotate counterclockwise  
  - `stop` - Stop motor
  - `auto` - Return to ADCS mode

### Programming Interface

```python
from adcs_integrated import start_adcs_control, stop_adcs_control, set_target, get_adcs_status

# Start ADCS with target yaw angle
start_adcs_control(target_yaw=45.0)

# Change target during operation
set_target(yaw=-30.0)

# Get current status
status = get_adcs_status()
print(f"Current yaw: {status['current_yaw']:.1f}°")
print(f"Yaw error: {status['yaw_error']:.1f}°")

# Stop ADCS
stop_adcs_control()
```

## System Architecture

### Sensor Reading Thread
- Reads MPU-6050 accelerometer and gyroscope data at 20 Hz
- Reads VEML7700 light sensor data
- Calculates yaw angle from horizontal accelerometer components
- Stores data in circular buffer for logging

### Control Thread  
- Runs PD controller at 10 Hz
- Computes control output based on yaw error
- Applies bang-bang (on/off) motor control
- Uses deadband to prevent oscillation around target

### Orientation Calculation
For a hanging cube rotating in horizontal plane:
```python
yaw = atan2(ay, ax) * 180/π
```

This calculates the rotation around the vertical Z-axis using the horizontal accelerometer components (X and Y). When the cube is hanging, gravity acts primarily in the Z direction, so the X,Y components indicate horizontal orientation.

## PD Controller Parameters

### Default Values
- **Kp (Proportional Gain):** 2.0 - Controls response to current error
- **Kd (Derivative Gain):** 0.5 - Controls response to error rate of change  
- **Deadband:** 2.0° - Prevents oscillation around target

### Tuning Guidelines
- **Higher Kp:** Faster response, may cause overshoot
- **Higher Kd:** Better damping, smoother approach to target
- **Larger Deadband:** More stable but less precise
- **Start conservative** and increase gains gradually

## Network Integration

To integrate with the Flask-SocketIO server for remote control:

```python
# In server2.py
from adcs_network import setup_adcs_routes, start_adcs_status_broadcast, adcs_cleanup

# Add routes
setup_adcs_routes(app, socketio)

# Start status broadcasting
start_adcs_status_broadcast(socketio)

# Cleanup on shutdown
adcs_cleanup()
```

## Data Logging

The system automatically logs sensor data including:
- Timestamp
- Accelerometer readings (ax, ay, az in g)
- Gyroscope readings (gx, gy, gz in °/s)
- Light sensor reading (lux)
- Calculated yaw angle (degrees)

Save logs with:
```python
adcs.save_log("my_experiment.csv")
```

## Troubleshooting

### Common Issues

1. **"No I2C device found"**
   - Check wiring connections
   - Ensure I2C is enabled: `sudo raspi-config`
   - Test with: `i2cdetect -y 1`

2. **Motor doesn't respond**
   - Verify GPIO connections
   - Check motor driver power supply
   - Test with manual commands first

3. **Orientation readings seem wrong**
   - Ensure MPU-6050 is mounted correctly
   - Check that yaw=0° corresponds to your reference direction
   - For hanging cube, ensure X,Y axes are horizontal
   - Consider sensor calibration for better accuracy  

4. **Control oscillates around target**
   - Increase deadband value
   - Reduce Kp gain
   - Increase Kd gain for better damping

5. **Permission denied on GPIO**
   - Add user to gpio group: `sudo usermod -a -G gpio $USER`
   - Or run with sudo (not recommended for development)

### Debug Tips
- Use `sensors` command to verify sensor readings
- Use `manual` mode to test motor control directly
- Check status frequently with `status` command
- Save logs to analyze system behavior offline

## Future Enhancements

1. **Improved Orientation Estimation**
   - Implement complementary or Kalman filter
   - Integrate gyroscope data for dynamic conditions
   - Add magnetometer for absolute heading reference

2. **Multi-Axis Control**  
   - Add more reaction wheels for 3-axis control
   - Implement momentum wheel management
   - Add attitude determination from star tracker

3. **Advanced Control**
   - PID controller with integral term
   - Adaptive control for varying conditions  
   - Predictive control for faster response

4. **System Health**
   - Motor current monitoring
   - Temperature monitoring
   - Automatic fault detection and recovery

## Safety Notes

- Always test in manual mode first
- Monitor motor temperature during extended operation  
- Use appropriate current limiting for motor protection
- Ensure proper mechanical mounting to prevent vibration
- Keep emergency stop readily available during testing
