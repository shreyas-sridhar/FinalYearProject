import RPi.GPIO as GPIO
from mfrc522 import MFRC522  # Use the lower-level MFRC522 class
import time
import threading
from datetime import datetime

# GPIO Setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# LED Pins (Physical Pin Numbers)
LEDs = {
    "Signal1": {
        "Red": 11,    # Pin 11 (GPIO17)
        "Yellow": 13, # Pin 13 (GPIO27)
        "Green": 15,  # Pin 15 (GPIO22)
        "White": 29   # Pin 29 (GPIO5)
    },
    "Signal2": {
        "Red": 31,    # Pin 31 (GPIO6)
        "Yellow": 33, # Pin 33 (GPIO13)
        "Green": 35,  # Pin 35 (GPIO19)
        "White": 37   # Pin 37 (GPIO26)
    }
}

# Initialize LEDs
for sig in LEDs.values():
    for pin in sig.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

# RFID Readers with Explicit SPI Device Selection
reader1 = MFRC522(bus=0, device=0)  # CE0
reader2 = MFRC522(bus=0, device=1)  # CE1

# Global Variables
paused = False
interrupted_signal = None
interrupted_time = 0
shutdown = False
lock = threading.Lock()

# RFID Thread Function
def rfid_listener(reader, signal_name):
    global paused, interrupted_signal, interrupted_time, shutdown
    try:
        while not shutdown:
            (status, _) = reader.MFRC522_Request(reader.PICC_REQIDL)
            if status == reader.MI_OK:
                (status, uid) = reader.MFRC522_Anticoll()
                if status == reader.MI_OK:
                    id = int.from_bytes(bytes(uid), "big")
                    with lock:
                        print(f"[{datetime.now()}] {signal_name} detected RFID: {id}")
                        paused = True
                        interrupted_signal = signal_name
                        interrupted_time = time.time()
                        for color in ["Red", "Yellow", "Green"]:
                            GPIO.output(LEDs["Signal1"][color], GPIO.LOW)
                            GPIO.output(LEDs["Signal2"][color], GPIO.LOW)
                        GPIO.output(LEDs[signal_name]["White"], GPIO.HIGH)
            time.sleep(0.1)
    except Exception as e:
        print(f"RFID Error on {signal_name}: {e}")

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
                        print(f"[{datetime.now()}] {sig}: {last_state[sig]} → {new_state[sig]}")
                        last_state[sig] = new_state[sig]
                for sig in ["Signal1", "Signal2"]:
                    GPIO.output(LEDs[sig]["Red"], GPIO.HIGH if new_state[sig] == "Red" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Green"], GPIO.HIGH if new_state[sig] == "Green" else GPIO.LOW)
                    GPIO.output(LEDs[sig]["Yellow"], GPIO.LOW)
                time.sleep(5)
                GPIO.output(LEDs[current_signal]["Green"], GPIO.LOW)
                GPIO.output(LEDs[current_signal]["Yellow"], GPIO.HIGH)
                time.sleep(2)
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
        pass

# Stop Listener
def stop_listener():
    global shutdown
    while True:
        cmd = input().strip()
        if cmd.lower() == "stop":
            shutdown = True
            break

# Start Threads
thread1 = threading.Thread(target=rfid_listener, args=(reader1, "Signal1"))
thread2 = threading.Thread(target=rfid_listener, args=(reader2, "Signal2"))
thread3 = threading.Thread(target=traffic_light_controller)
thread4 = threading.Thread(target=stop_listener)

thread1.start()
thread2.start()
thread3.start()
thread4.start()

try:
    while not shutdown:
        time.sleep(1)
finally:
    GPIO.cleanup()
    print("Program stopped. GPIO cleaned up.")
