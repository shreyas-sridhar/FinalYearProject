import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
reader = SimpleMFRC522()
while True:
    try:
        print("Place your RFID tag near the reader...")
        id, text = reader.read()
        print(id)
        f=open('rfid2.txt','w')
        f.write(str(id))
        f.close()
    finally:
        GPIO.cleanup()
    time.sleep(1)
