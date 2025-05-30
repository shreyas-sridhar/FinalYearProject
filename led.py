import threading
import requests
import heapq
import time
from datetime import datetime
import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import sqlite3
# ----------------- GPIO Setup ------------------
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

LEDs = {
    "Signal1": {"Red": 5, "Yellow": 12, "Green": 3, "White": 40},
    "Signal2": {"Red": 13, "Yellow": 38, "Green": 15, "White": 16}
}
for signal in LEDs.values():
    for pin in signal.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
def reset_signals():
        print(f"[{datetime.now()}] ⛔ Back to RED")
        for signal in LEDs:
            for pin in LEDs[signal].values():
                GPIO.output(pin, GPIO.LOW)
def normal_cycle():
    global LEDs
    print("normal cycle")
    GPIO.output(LEDs["Signal1"]["Green"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["Green"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["Red"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["Red"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["White"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal1"]["White"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Red"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Red"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.LOW)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Green"],GPIO.HIGH)
    time.sleep(2)
    GPIO.output(LEDs["Signal2"]["Green"],GPIO.LOW)
    time.sleep(2)
normal_cycle()
'''
GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.HIGH)
time.sleep(2)
GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.LOW)
time.sleep(2)




    GPIO.output(LEDs["Signal1"]["Green"],GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.HIGH)
    GPIO.output(LEDs["Signal1"]["Red"],GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Green"],GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Red"],GPIO.LOW)
    time.sleep(1)
    
    GPIO.output(LEDs["Signal1"]["Green"],GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Red"],GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Green"],GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Red"],GPIO.LOW)
    time.sleep(3)
    GPIO.output(LEDs["Signal1"]["Green"],GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.HIGH)
    GPIO.output(LEDs["Signal1"]["Red"],GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Green"],GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Red"],GPIO.LOW)
    time.sleep(3)
    

normal_cycle()

reset_signals()

    GPIO.output(LEDs["Signal2"]["Green"], GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Red"], GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Red"], GPIO.HIGH)
    GPIO.output(LEDs["Signal1"]["Yellow"], GPIO.LOW)
    GPIO.output(LEDs["Signal1"]["Green"], GPIO.LOW)
    time.sleep(3)

    GPIO.output(LEDs["Signal2"]["Green"], GPIO.LOW)
    GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.HIGH)
    GPIO.output(LEDs["Signal2"]["Red"], GPIO.LOW)
    time.sleep(1)
    GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.LOW)
    reset_signals()
print("normal cycle")
GPIO.output(LEDs["Signal1"]["Green"],GPIO.HIGH)
GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.LOW)
GPIO.output(LEDs["Signal1"]["Red"],GPIO.LOW)
GPIO.output(LEDs["Signal2"]["Red"],GPIO.HIGH)
GPIO.output(LEDs["Signal2"]["Yellow"],GPIO.LOW)
GPIO.output(LEDs["Signal2"]["Green"],GPIO.LOW)
time.sleep(3)

GPIO.output(LEDs["Signal1"]["Green"],GPIO.LOW)
GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.HIGH)
GPIO.output(LEDs["Signal1"]["Red"],GPIO.LOW)
time.sleep(1)
GPIO.output(LEDs["Signal1"]["Yellow"],GPIO.LOW)
    


GPIO.output(LEDs["Signal2"]["Green"], GPIO.HIGH)
GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.LOW)
GPIO.output(LEDs["Signal2"]["Red"], GPIO.LOW)
GPIO.output(LEDs["Signal1"]["Red"], GPIO.HIGH)
GPIO.output(LEDs["Signal1"]["Yellow"], GPIO.LOW)
GPIO.output(LEDs["Signal1"]["Green"], GPIO.LOW)
time.sleep(3)

GPIO.output(LEDs["Signal2"]["Green"], GPIO.LOW)
GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.HIGH)
GPIO.output(LEDs["Signal2"]["Red"], GPIO.LOW)
time.sleep(1)
GPIO.output(LEDs["Signal2"]["Yellow"], GPIO.LOW)
'''
#reset_signals()



