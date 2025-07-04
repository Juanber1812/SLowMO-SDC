# sensors_simple.py

"""
Simple, non-threaded sensor functions that can be called directly
from the unified monitoring system.
"""

import time
import psutil

def get_temp():
    """Get Pi temperature"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read()) / 1000.0
    except:
        return None

def get_memory_usage():
    """Get memory usage statistics."""
    try:
        memory = psutil.virtual_memory()
        return {
            'percent': round(memory.percent, 1),
            'used_gb': round(memory.used / (1024**3), 2),
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2)
        }
    except:
        return None

def get_uptime(start_time):
    """Calculate uptime since start_time."""
    current_time = time.time()
    uptime_seconds = current_time - start_time
    
    # Convert to days, hours, minutes, seconds
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    else:
        return f"{minutes}m {seconds}s"

def get_system_status(cpu_percent, memory_percent):
    """Generate smart status based on CPU and memory usage."""
    try:
        # Define thresholds
        cpu_high = 80
        cpu_critical = 95
        memory_high = 85
        memory_critical = 95
        
        # Check for critical conditions first
        if cpu_percent >= cpu_critical or memory_percent >= memory_critical:
            return "Critical"
        elif cpu_percent >= cpu_high or memory_percent >= memory_high:
            return "High Load"
        elif cpu_percent >= 50 or memory_percent >= 70:
            return "Moderate Load"
        elif cpu_percent <= 20 and memory_percent <= 50:
            return "Optimal"
        else:
            return "Normal"
            
    except Exception:
        return "Unknown"

def get_sensor_data(start_time):
    """Get all sensor data in a single call"""
    temp = get_temp()
    cpu = psutil.cpu_percent(interval=None)
    memory = get_memory_usage()
    uptime = get_uptime(start_time)
    
    # Get memory percentage for status calculation
    memory_percent = memory.get('percent', 0) if memory else 0
    
    # Generate smart status based on CPU and memory usage
    system_status = get_system_status(cpu, memory_percent)
    
    return {
        "temperature": temp,
        "cpu_percent": cpu,
        "memory": memory,
        "uptime": uptime,
        "status": system_status,
        "memory_percent": memory_percent
    }
