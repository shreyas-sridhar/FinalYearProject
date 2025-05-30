import serial
import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import time
import threading
from datetime import datetime

# GPIO Setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# LED Pins (Physical Pin Numbers)
LEDs = {
    "Signal1": {
        "Red": 5,    # GPIO3
        "Yellow": 12, # GPIO18
        "Green": 3,  # GPIO2
        "White": 40   # GPIO21
    },
    "Signal2": {
        "Red": 13,    # GPIO27
        "Yellow": 38, # GPIO20
        "Green": 15,  # GPIO22
        "White": 16   # GPIO23
    }
}

# Initialize LEDs
for sig in LEDs.values():
    for pin in sig.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

# RFID Readers
reader2 = MFRC522(bus=0, device=1)  # CE1 for MFRC522

# Serial setup for Arduino (RFID1)
arduino_serial = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
time.sleep(2)

# Global Variables
paused = False
interrupted_signal = None
interrupted_time = 0
shutdown = False
lock = threading.Lock()

# RFID Listener for Arduino Serial
def rfid_listener_arduino():
    global paused, interrupted_signal, interrupted_time, shutdown
    try:
        while not shutdown:
            if arduino_serial.in_waiting > 0:
                data = arduino_serial.readline().decode('utf-8').strip()
                if data:
                    with lock:
                        print("[",datetime.now()," Signal1 detected RFID from Arduino:",data)
                        paused = True
                        interrupted_signal = "Signal1"
                        interrupted_time = time.time()
                        for color in ["Red", "Yellow", "Green"]:
                            GPIO.output(LEDs["Signal1"][color], GPIO.LOW)
                            GPIO.output(LEDs["Signal2"][color], GPIO.LOW)
                        GPIO.output(LEDs["Signal1"]["White"], GPIO.HIGH)
            time.sleep(0.1)
    except Exception as e:
        print("Arduino RFID Error: ",e)

# RFID Listener for MFRC522
def rfid_listener_mfrc():
    global paused, interrupted_signal, interrupted_time, shutdown
    try:
        while not shutdown:
            (status, _) = reader2.MFRC522_Request(reader2.PICC_REQIDL)
            if status == reader2.MI_OK:
                (status, uid) = reader2.MFRC522_Anticoll()
                if status == reader2.MI_OK:
                    id = int.from_bytes(bytes(uid), "big")
                    with lock:
                        print("[",datetime.now(), " Signal2 detected RFID: ", id)
                        paused = True
                        interrupted_signal = "Signal2"
                        interrupted_time = time.time()
                        for color in ["Red", "Yellow", "Green"]:
                            GPIO.output(LEDs["Signal1"][color], GPIO.LOW)
                            GPIO.output(LEDs["Signal2"][color], GPIO.LOW)
                        GPIO.output(LEDs["Signal2"]["White"], GPIO.HIGH)
            time.sleep(0.1)
    except Exception as e:
        print("MFRC522 RFID Error: ",e)

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
                        print("[",datetime.now(), ' ',sig , ': ',last_state[sig], ' ->', new_state[sig])
                        last_state[sig] = new_state[sig]
                for sig in ["Signal1", "Signal2"]:
                    GPIO.output(LEDs[sig]["Red"], GPIO.HIGH if new_state[sig] == "Red" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Green"], GPIO.HIGH if new_state[sig] == "Green" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Yellow"], GPIO.LOW)
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
                        GPIO.output(LEDs["Signal1"]["White"], GPIO.LOW)
                        GPIO.output(LEDs["Signal2"]["White"], GPIO.LOW)
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
