## As it stands, this code can be run directly on the pi with a monitor, and the adcs can be controlled with inputs to the pi. This needs to be changed so that inputs to another laptop call functions to be ran on the pi.


# Required libraries
import time
import RPi.GPIO as GPIO
import board
import busio
import adafruit_tca9548a  # Multiplexer library
import adafruit_veml7700
import smbus
from tkinter import *
import tkinter.messagebox as box

# Setting up motor
GPIO.setmode(GPIO.BOARD)
Motor1A = 16 #Change for actual pin used
Motor1B = 18 #Change for actual pin used
Motor1E = 22 #Change for actual pin used
GPIO.setup(Motor1A,GPIO.OUT)
GPIO.setup(Motor1B,GPIO.OUT)
GPIO.setup(Motor1E,GPIO.OUT)
pwm = GPIO.PWM(Motor1E, 100)  # Set PWM frequency to 100Hz
pwm.start(100)  # Start PWM with 0% duty cycle
def motor_forward(speed):
    GPIO.output(Motor1A, GPIO.HIGH)
    GPIO.output(Motor1B, GPIO.LOW)
    pwm.ChangeDutyCycle(speed)  # Adjust speed (0-100%)
def motor_backward(speed):
    GPIO.output(Motor1A, GPIO.LOW)
    GPIO.output(Motor1B, GPIO.HIGH)
    pwm.ChangeDutyCycle(speed)
def stop_motor():
    pwm.ChangeDutyCycle(0)  # Stop motor

# Setting up rpm sensor
GPIO.setmode(GPIO.BCM)  #Use Broadcom pin numbering
GPIO.setup(17, GPIO.IN)  #Change for pin number used
###set variable showing whether sensor is high or low###

#Initialising I2C bus and multiplexer for light sensor
i2c = busio.I2C(board.SCL, board.SDA)
tca = adafruit_tca9548a.TCA9548A(i2c)

# Assigning light sensors to different channels
veml7700_1 = adafruit_veml7700.VEML7700(tca[0])  
veml7700_2 = adafruit_veml7700.VEML7700(tca[1])  
veml7700_3 = adafruit_veml7700.VEML7700(tca[2])

# Setting I2C protocol and device address used in motion sensor functions
bus = smbus.SMBus(1) 	
Device_Address = 0x68

# Setting motion sensor registers and addresses
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
GYRO_CONFIG  = 0x1B
INT_ENABLE   = 0x38
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H  = 0x43
GYRO_YOUT_H  = 0x45
GYRO_ZOUT_H  = 0x47

# Creating function to initialise motion sensor
def MPU_Init():
	bus.write_byte_data(Device_Address, SMPLRT_DIV, 7)
	bus.write_byte_data(Device_Address, PWR_MGMT_1, 1)
	bus.write_byte_data(Device_Address, CONFIG, 0)
	bus.write_byte_data(Device_Address, GYRO_CONFIG, 24)
	bus.write_byte_data(Device_Address, INT_ENABLE, 1)

# Creating function to read motion sensor's raw data
def read_raw_data(addr):
        high = bus.read_byte_data(Device_Address, addr)
        low = bus.read_byte_data(Device_Address, addr+1)
        value = ((high << 8) | low)
        if(value > 32768):
                value = value - 65536
        return value

# Setting PD controller
class PDController:
    def __init__(self, Kp, Kd):
        self.Kp = Kp
        self.Kd = Kd
        self.previous_error = 0
    
    def compute(self, desired_orientation, actual_orientation, dt):
        error = desired_orientation - actual_orientation
        derivative = (error - self.previous_error) / dt if dt > 0 else 0
        control_output = self.Kp * error + self.Kd * derivative
        self.previous_error = error
        return control_output

# Beginning initialisation of motion sensor
MPU_Init()

# Initial orientation
orientation = 0

# Orientation tracking
start_time = time.perf_counter()
intial_time = None
prev_ref = False
while True:
        elapsed = time.time() - start_time
        acc_x = read_raw_data(ACCEL_XOUT_H)
        acc_y = read_raw_data(ACCEL_YOUT_H)
        acc_z = read_raw_data(ACCEL_ZOUT_H)
        gyro_x = read_raw_data(GYRO_XOUT_H)
        gyro_y = read_raw_data(GYRO_YOUT_H)
        gyro_z = read_raw_data(GYRO_ZOUT_H)
        Ax = acc_x/16384.0
        Ay = acc_y/16384.0
        Az = acc_z/16384.0
        Gx = gyro_x/131.0
        Gy = gyro_y/131.0
        Gz = gyro_z/131.0
        velocity = Gz
        dt = 0.1
        orientation += velocity * dt
	#RPM sensing
	if GPIO.input(Motor1E) == GPIO.HIGH:
	    if GPIO.input(17) == GPIO.HIGH and prev_ref == False: 
            	if initial_time is None:  
           		initial_time = time.perf_counter()
           		prev_ref = True
        	else:
                	current_time = time.perf_counter()
                        period = current_time - initial_time
			rpm = 60/period 
                        initial_time = current_time
                        prev_ref = True
            if GPIO.input(17) == GPIO.LOW:
                prev_ref = False
	else:
		rpm = 0

# Creating environmental calibration mode function
def environmental_calibration_mode():
	#Setting reference light readings
	light_intensity_1 = []
	light_intensity_2 = []
	light_intensity_3 = []
	motor_forward(100)
	pd_controller = PDController(Kp=1600, Kd=80)
	calibration = False
	dt = 0.1
	while calibration == False:
        	# Checking for light maximum
        	light1 = veml7700_1.light
        	light2 = veml7700_2.light
		light3 = veml7700_3.light
        	light_intensity_1.append(light1)
        	light_intensity_2.append(light2)
        	light_intensity_3.append(light3)
        	timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        	if len(light_intensity_1) > 2 or len(light_intensity_2) > 2 or len(light_intensity_3) > 2:
			stop_motor()
                	if np.sign(light_intensity_1[-2]-light_intensity_1[-3]) == -np.sign(light_intensity_1[-1]-light_intensity_1[-2]):
                		orientation = 0
                		orientation += velocity * dt
                		desired_orientation = 0
                		actual_orientation = orientation
				calibration = True
			elif np.sign(light_intensity_2[-2]-light_intensity_2[-3]) == -np.sign(light_intensity_2[-1]-light_intensity_2[-2]):
                		orientation = -60
                		orientation += velocity * dt
                		desired_orientation = -60
                		actual_orientation = orientation
				calibration = True
			elif np.sign(light_intensity_3[-2]-light_intensity_3[-3]) == -np.sign(light_intensity_3[-1]-light_intensity_3[-2]):
                		orientation = -120
                		orientation += velocity * dt
                		desired_orientation = -120
                		actual_orientation = orientation
				calibration = True
	while calibration == True and abs(desired_orientation - orientation) > 0.01:
       		control_signal = pd_controller.compute(desired_orientation, actual_orientation, dt)
		# Mapping PD output to motor speed (ensure values are within valid range)
        	motor_speed = max(min(abs(control_signal), 1000), 0)  # Limiting to realistic values
		#Adjust motor direction based on control signal sign
		if control_signal > 0:
			motor_forward(motor_speed)
			orientation += velocity * dt
        		actual_orientation = orientation  # Update actual orientation in real-time
		else:
			motor_backward(motor_speed)
			orientation += velocity * dt
        		actual_orientation = orientation  # Update actual orientation in real-time
	else:
        	stop_motor()
        	orientation += velocity * dt
        	return		
        time.sleep(0.1)

# Creating manual orientation mode function
def manual_orientation_mode():
    #Creating commands for motor
    def startstop_cw():
        GPIO.output(Motor1A,GPIO.HIGH)
        GPIO.output(Motor1B,GPIO.LOW)
        if GPIO.input(Motor1E) == GPIO.HIGH:
            GPIO.output(Motor1E,GPIO.LOW)
        elif GPIO.input(Motor1E) == GPIO.LOW:
            GPIO.output(Motor1E,GPIO.HIGH)
    def startstop_ccw():
        GPIO.output(Motor1A,GPIO.LOW)
        GPIO.output(Motor1B,GPIO.HIGH)
        if GPIO.input(Motor1E) == GPIO.HIGH:
            GPIO.output(Motor1E,GPIO.LOW)
        elif GPIO.input(Motor1E) == GPIO.LOW:
            GPIO.output(Motor1E,GPIO.HIGH)
    #Setting up interface
    window_mom = Tk()
    window_mom.title('Manual Orientation Mode')
    def close_program():
            GPIO.cleanup()
            window_mom.destroy()
    btn_mom_end = Button(window_mom, text = 'Close', command=close_program)
    btn_cw = Button(window_mom, text = 'CW', command=startstop_cw)
    btn_ccw = Button(window_mom, text = 'CCW', command=startstop_ccw)
    btn_cw.pack(padx = 120, pady = 20)
    btn_ccw.pack(padx = 120, pady = 20)
    btn_mom_end.pack(padx = 120, pady = 20)
    window_mom.mainloop()

# Creating automatic orientation mode function
def automatic_orientation_mode():
        def rotation():
                # Parameter setting
                desired_orientation = float(entry.get())
                actual_orientation = orientation
                pd_controller = PDController(Kp=1600, Kd=80)
                # Running controller
                while abs(actual_orientation - desired_orientation) > 0.1:  # Stop condition
                        control_signal = pd_controller.compute(desired_orientation, actual_orientation, dt)
                        GPIO.output(Motor1A,GPIO.HIGH)
                        GPIO.output(Motor1B,GPIO.LOW)
                        GPIO.output(Motor1E,GPIO.HIGH)
                        actual_orientation = orientation
                else:
                        GPIO.output(Motor1E,GPIO.LOW)
                        GPIO.cleanup()
        def start_rotation():
                rotation(float(entry.get()))
        #Setting up interface
        window_aom = Tk()
        window_aom.title('Automatic Orientation Mode')
        frame = Frame(window_aom)
        entry = Entry(frame)
        btn = Button(frame, text = 'Enter Desired Orientation', command=start_rotation)
        btn.pack(side = RIGHT, padx=5)
        entry.pack(side=LEFT)
        frame.pack(padx=20, pady=20)
        window_aom.mainloop()

# Creating detumbling mode function
def detumbling_mode():
    desired_orientation = 0  
    actual_orientation = orientation
    dt = 0.1
    pd_controller = PDController(Kp=1600, Kd=80)
    while abs(actual_orientation - desired_orientation) > 0.1:
        control_signal = pd_controller.compute(desired_orientation, actual_orientation, dt)
        GPIO.output(Motor1A,GPIO.HIGH)
        GPIO.output(Motor1B,GPIO.LOW)
        GPIO.output(Motor1E,GPIO.HIGH)
        actual_orientation = orientation
    else:
        GPIO.output(Motor1E,GPIO.LOW)
        GPIO.cleanup()  
    
# Intefacing
window_adcs = Tk()
window_adcs.title('ADCS Control Inteface')
btn_ecm = Button(window_adcs, text = 'Environmental Calibration', command=environmental_calibration_mode())
btn_mom = Button(window_adcs, text = 'Manual Orientation', command=manual_orientation_mode())
btn_aom = Button(window_adcs, text = 'Automatic Orientation', command=automatic_orientation_mode())
btn_dm = Button(window_adcs, text = 'Detumble', command=detumbling_mode())
btn_adcs_end = Button(window_adcs, text = 'Close', command=exit)

btn_ecm.pack(padx = 120, pady = 20)
btn_mom.pack(padx = 120, pady = 20)
btn_aom.pack(padx = 120, pady = 20)
btn_dm.pack(padx = 120, pady = 20)
btn_adcs_end.pack(padx = 120, pady = 20)

window_adcs.mainloop()
