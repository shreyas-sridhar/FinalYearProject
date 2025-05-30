import serial
import time

# Set up the serial connection
ser = serial.Serial(
    port='/dev/ttyUSB0',  # Change to '/dev/ttyAMA0' or '/dev/serial0' if using GPIO UART
    baudrate=9600,
    timeout=1
)

time.sleep(2)  # Give time for connection to establish

print("Reading data from serial...")

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8').strip()
            print(f"Received: {data}")
            f=open('rfid1.txt','w')
            f.write(str(id))
            f.close()
except KeyboardInterrupt:
    print("Stopped by user")
finally:
    ser.close()
