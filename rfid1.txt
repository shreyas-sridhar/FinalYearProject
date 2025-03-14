import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import time

# GPIO Setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Initialize RFID Reader 1 (CE0)
reader1 = MFRC522(bus=0, device=0)

print("RFID Reader 1 Ready. Scan a tag...")

try:
    while True:
        (status, _) = reader1.MFRC522_Request(reader1.PICC_REQIDL)
        if status == reader1.MI_OK:
            (status, uid) = reader1.MFRC522_Anticoll()
            if status == reader1.MI_OK:
                id = int.from_bytes(bytes(uid), "big")
                print(f"Tag Detected on Reader 1: {id}")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    GPIO.cleanup()
