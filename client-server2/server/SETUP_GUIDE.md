# SLowMO-SDC Server Setup Guide

## 📋 **System Requirements**

### **Hardware Requirements**
- **Raspberry Pi 4B** (4GB+ RAM recommended)
- **MicroSD Card** (32GB+ Class 10)
- **Raspberry Pi Camera Module** (v2 or v3)
- **Connected Sensors:**
  - MPU-6050 6-axis IMU
  - VEML7700 light sensor
  - TCA9548A I2C multiplexer
  - INA228 power monitoring sensor
  - DS18B20 temperature sensors
  - LiDAR sensor (I2C)
  - Motor drivers and control hardware

### **Software Requirements**
- **Raspberry Pi OS** (Bullseye or newer)
- **Python 3.9+** (included with Raspberry Pi OS)
- **Git** for version control

## 🚀 **Quick Installation**

### **1. System Preparation**
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-dev build-essential
sudo apt install -y i2c-tools python3-smbus git
sudo apt install -y libcamera-dev python3-picamera2
sudo apt install -y python3-opencv

# Enable hardware interfaces
sudo raspi-config
# Navigate to Interface Options and enable:
# - I2C
# - SPI  
# - Camera
# - 1-Wire
```

### **2. Install Python Dependencies**
```bash
# Navigate to server directory
cd /path/to/SLowMO-SDC/client-server2/server

# Install all requirements
pip install -r requirements.txt

# Verify critical imports
python3 -c "import cv2, numpy, flask, RPi.GPIO; print('✅ Core imports successful')"
```

### **3. Hardware Verification**
```bash
# Check I2C devices
i2cdetect -y 1

# Test camera
libcamera-still --list-cameras

# Check 1-Wire temperature sensors
ls /sys/bus/w1/devices/
```

## 📁 **Project Structure**

```
server/
├── requirements.txt              # Main dependencies file
├── adcs_requirements.txt         # ADCS-specific requirements  
├── server2.py                   # Main Flask server
├── camera.py                    # Camera streaming
├── sensors.py                   # System monitoring
├── lidar.py                     # Distance measurement
├── mpu.py                       # IMU data & calibration
├── power.py                     # Power monitoring
├── temperature.py               # Temperature sensors
├── tachometer.py                # Motor speed measurement
├── motor_test.py                # Motor control
├── pd_bangbang.py               # Control algorithms
├── adcs_*.py                    # ADCS system files
├── calibrate_mpu.py             # MPU calibration utility
├── demo_accel_calibration.py    # Calibration demos
└── test_*.py                    # Testing utilities
```

## 🔧 **Configuration**

### **Hardware Interface Setup**

#### **I2C Configuration**
```bash
# Add to /boot/config.txt
dtparam=i2c_arm=on
dtparam=i2c1=on

# Set I2C speed (optional)
dtparam=i2c_arm_baudrate=400000
```

#### **1-Wire Temperature Sensors**
```bash
# Add to /boot/config.txt
dtoverlay=w1-gpio
```

#### **Camera Configuration**
```bash
# Add to /boot/config.txt
camera_auto_detect=1
dtoverlay=ov5647  # For Camera Module v1
# or
dtoverlay=imx219  # For Camera Module v2
# or  
dtoverlay=imx477  # For HQ Camera
```

### **Software Configuration**

#### **System Services (Optional)**
Create systemd service for auto-start:

```bash
# Create service file
sudo nano /etc/systemd/system/slowmo-sdc.service
```

```ini
[Unit]
Description=SLowMO-SDC Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/SLowMO-SDC/client-server2/server
ExecStart=/usr/bin/python3 server2.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable slowmo-sdc.service
sudo systemctl start slowmo-sdc.service
```

## 🧪 **Testing & Verification**

### **1. Individual Module Tests**
```bash
# Test MPU sensor
python3 mpu.py

# Test camera streaming  
python3 camera.py

# Test power monitoring
python3 power.py

# Test temperature sensors
python3 temperature.py
```

### **2. Full System Test**
```bash
# Start main server
python3 server2.py

# Check server status
curl http://localhost:5000/health
```

### **3. Hardware Diagnostics**
```bash
# I2C device scan
i2cdetect -y 1

# GPIO state check
gpio readall

# Camera test
libcamera-still -o test.jpg

# System resources
htop
```

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Import Errors**
```bash
# Missing RPi.GPIO
pip install RPi.GPIO

# Missing OpenCV
sudo apt install python3-opencv
pip install opencv-python

# Missing Adafruit libraries
pip install adafruit-circuitpython-veml7700
```

#### **Permission Issues**
```bash
# Add user to required groups
sudo usermod -a -G i2c,spi,gpio pi

# Set permissions for GPIO access
sudo chmod 666 /dev/gpiomem
```

#### **Hardware Detection Issues**
```bash
# Enable I2C and check
sudo raspi-config
i2cdetect -y 1

# Camera not detected
sudo raspi-config  # Enable camera
vcgencmd get_camera

# 1-Wire sensors not found
sudo modprobe w1-gpio
sudo modprobe w1-therm
ls /sys/bus/w1/devices/
```

#### **Performance Issues**
```bash
# Increase GPU memory split
sudo raspi-config  # Advanced Options > Memory Split > 128

# Monitor system resources
htop
iostat -x 1

# Check for thermal throttling
vcgencmd measure_temp
vcgencmd get_throttled
```

## 📊 **Usage Examples**

### **Basic Server Operation**
```bash
# Start server with default settings
python3 server2.py

# Server will start on http://localhost:5000
# WebSocket available for real-time communication
```

### **MPU Calibration**
```bash
# Quick calibration
python3 calibrate_mpu.py

# Full calibration with logging
python3 mpu.py
# Choose option 3: "Perform full calibration"
```

### **Camera Streaming**
```bash
# Test camera independently
python3 camera.py

# Access stream at http://localhost:5000/video_feed
```

## 🔐 **Security Considerations**

### **Network Security**
- Change default passwords
- Use VPN for remote access
- Implement authentication for web interface
- Limit network exposure

### **File System Security**
```bash
# Secure log directories
chmod 750 /var/log/slowmo-sdc/
chown pi:pi /var/log/slowmo-sdc/

# Protect configuration files
chmod 600 *.json
```

## 📈 **Monitoring & Maintenance**

### **Log Management**
```bash
# View system logs
journalctl -u slowmo-sdc.service -f

# Rotate log files
sudo logrotate /etc/logrotate.conf
```

### **System Health Monitoring**
```bash
# Check system status
systemctl status slowmo-sdc.service

# Monitor resources
htop
iotop

# Check hardware health
vcgencmd measure_temp
vcgencmd measure_volts
```

### **Updates & Maintenance**
```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Update Python packages
pip install --upgrade -r requirements.txt

# Backup configuration
tar -czf slowmo-backup-$(date +%Y%m%d).tar.gz *.json *.csv *.log
```

## 📞 **Support & Documentation**

- **Project Repository**: GitHub SLowMO-SDC
- **Hardware Documentation**: See individual sensor datasheets
- **Raspberry Pi Documentation**: https://www.raspberrypi.org/documentation/
- **Python Library Documentation**: Links in requirements.txt comments

---

*Last Updated: June 28, 2025*
*Compatible with: Raspberry Pi OS Bullseye, Python 3.9+*
