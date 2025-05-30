import serial
import RPi.GPIO as GPIO

import time
import threading
from datetime import datetime

# GPIO Setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# LED Pins (Physical Pin Numbers)
LEDs = {
    "Signal1": {
        "Red": 5,
        "Yellow": 12,
        "Green": 3,
        "White": 40
    },
    "Signal2": {
        "Red": 13,
        "Yellow": 38,
        "Green": 15,
        "White": 16
    }
}

# Initialize LEDs
for sig in LEDs.values():
    for pin in sig.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)




# Global Variables
paused = False
interrupted_signal = None
interrupted_time = 0
shutdown = False
lock = threading.Lock()

# RFID Listener for Arduino Serial (RFID1)
def rfid_listener_arduino():
    global paused, interrupted_signal, interrupted_time, shutdown
    try:
        while not shutdown:
            #print('check nano ')
            f=open('rfid1.txt','r')
            data=f.read()
            f.close()
            #print('rfid_id 1', data)
            
            with lock:
                if data:
                    print("[", datetime.now(), "] Signal1 detected RFID from Arduino: " + str(data))
                    print("(" + str(data) + " scanned giving green corridor)")
                    paused = True
                    interrupted_signal = "Signal1"
                    interrupted_time = time.time()

                    for color in ["Red", "Yellow", "Green", "White"]:
                        GPIO.output(LEDs["Signal1"][color], GPIO.LOW)
                        GPIO.output(LEDs["Signal2"][color], GPIO.LOW)

                        GPIO.output(LEDs["Signal1"]["White"], GPIO.HIGH)
                    f=open('rfid1.txt','w')
                    f.write('')
                    f.close()
                    
            time.sleep(0.1)
    except Exception as e:
        print("Arduino RFID Error: " + str(e))

# RFID Listener for MFRC522 (RFID2)
def rfid_listener_mfrc():
    global paused, interrupted_signal, interrupted_time, shutdown
    try:
        while not shutdown:
            
            f=open('rfid2.txt','r')
            rfid_id=f.read()
            f.close()
            #print('rfid_id 2', rfid_id)
            with lock:
                if rfid_id!='':
                    print("[", datetime.now(), "] Signal2 detected RFID: " + str(rfid_id))
                    print("(" + str(rfid_id) + " scanned giving green corridor)")
                    paused = True
                    interrupted_signal = "Signal2"
                    interrupted_time = time.time()
                    for color in ["Red", "Yellow", "Green", "White"]:
                        GPIO.output(LEDs["Signal1"][color], GPIO.LOW)
                        GPIO.output(LEDs["Signal2"][color], GPIO.LOW)

                        GPIO.output(LEDs["Signal2"]["White"], GPIO.HIGH)
                    f=open('rfid2.txt','w')
                    f.write('')
                    f.close()
                    
            time.sleep(0.1)
    except Exception as e:
        print("MFRC522 RFID Error: " + str(e))

# Traffic Light Controller
def traffic_light_controller():
    global paused, interrupted_signal, interrupted_time, shutdown
    current_signal = "Signal1"
    last_state = {"Signal1": "Red", "Signal2": "Red"}
    try:
        while not shutdown:
            if not paused:
                new_state = {"Signal1": "Red", "Signal2": "Red"}
                new_state[current_signal] = "Green"

                for sig in ["Signal1", "Signal2"]:
                    if new_state[sig] != last_state[sig]:
                        print("[", datetime.now(), "] " + sig + ": " + last_state[sig] + " -> " + new_state[sig])
                        last_state[sig] = new_state[sig]

                for sig in ["Signal1", "Signal2"]:
                    GPIO.output(LEDs[sig]["Red"], GPIO.HIGH if new_state[sig] == "Red" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Green"], GPIO.HIGH if new_state[sig] == "Green" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Yellow"], GPIO.LOW)
                    GPIO.output(LEDs[sig]["White"], GPIO.LOW)

                time.sleep(5)
                GPIO.output(LEDs[current_signal]["Green"], GPIO.LOW)
                GPIO.output(LEDs[current_signal]["Yellow"], GPIO.HIGH)
                time.sleep(2)
                GPIO.output(LEDs[current_signal]["Yellow"], GPIO.LOW)
                current_signal = "Signal2" if current_signal == "Signal1" else "Signal1"
            else:
                with lock:
                    if time.time() - interrupted_time >= 10:
                        paused = False
                        for sig in ["Signal1", "Signal2"]:
                            for color in ["Red", "Yellow", "Green", "White"]:
                                GPIO.output(LEDs[sig][color], GPIO.LOW)
                        GPIO.output(LEDs["Signal1"]["Red"], GPIO.HIGH)
                        GPIO.output(LEDs["Signal2"]["Red"], GPIO.HIGH)
                        last_state = {"Signal1": "Red", "Signal2": "Red"}
            time.sleep(0.1)
    except KeyboardInterrupt:
        shutdown = True

# Start Threads
thread1 = threading.Thread(target=rfid_listener_arduino)
thread2 = threading.Thread(target=rfid_listener_mfrc)
thread3 = threading.Thread(target=traffic_light_controller)

thread1.start()
thread2.start()
thread3.start()

try:
    while not shutdown:
        time.sleep(1)
except KeyboardInterrupt:
    shutdown = True
finally:
    GPIO.cleanup()
    arduino_serial.close()
    print("Program stopped. GPIO and Serial cleaned up.")
