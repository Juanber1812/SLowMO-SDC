# MPU-6050 Yaw Angle Reference Guide

## Expected Behavior for Hanging Cube

### Yaw Angle Range
- **Range**: -180° to +180° (NOT 0° to 360°)
- **Calculation**: `atan2(ay, ax) * 180/π`
- **Zero Reference**: Initial orientation when starting the test

### Rotation Direction
```
Looking down at cube from above:

Counterclockwise rotation → Positive yaw angles
     ↑ +90°
     |
-180°/+180° ← → 0°
     |
     ↓ -90°
Clockwise rotation → Negative yaw angles
```

### What You Should Observe

#### 1. Stationary Cube
- Yaw angle should be stable (±1-2° fluctuation is normal)
- Z acceleration should be close to -1g (hanging down) or +1g (upside up)
- Gyroscope readings should be low (<10°/s)

#### 2. Slow Manual Rotation
- Yaw should change smoothly as you rotate
- No sudden jumps except at ±180° boundary
- Gyroscope Z should show rotation rate

#### 3. Full 360° Rotation
- Starting at 0°, rotating CCW: 0° → +90° → +180° → -180° → -90° → 0°
- Starting at 0°, rotating CW: 0° → -90° → -180° → +180° → +90° → 0°

### Troubleshooting

#### If yaw doesn't change when rotating:
- Check I2C connections (SDA, SCL, VCC, GND)
- Verify MPU-6050 address (0x68)
- Ensure cube can rotate freely

#### If yaw jumps erratically:
- Cube might be tilted (check Z acceleration)
- Vibrations or unstable mounting
- I2C communication issues

#### If readings are always zero:
- MPU-6050 not initialized properly
- Wrong I2C address or wiring
- Power supply issues

### Integration with ADCS

For your reaction wheel control:
- Use yaw angle directly: `target_yaw - current_yaw = error`
- Handle ±180° wraparound in your control logic
- Consider using `math.atan2(sin(error), cos(error))` for error calculation
