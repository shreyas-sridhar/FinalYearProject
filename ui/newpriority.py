import RPi.GPIO as GPIO
import time
import sqlite3

# Setup GPIO mode
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Signal 1 (Top) Pins
SIGNAL1 = {'red': 5, 'yellow': 12, 'green': 3, 'white': 40}

# Signal 2 (Bottom) Pins
SIGNAL2 = {'red': 13, 'yellow': 38, 'green': 15, 'white': 16}

# Setup all pins as output
for pin in list(SIGNAL1.values()) + list(SIGNAL2.values()):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

DB_PATH = "rfid_logs.db"

def get_latest_severity():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rfid_scans ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        #if row:
            #return int(row[0]) if row[0].isdigit() else 0
        return 0
    except Exception as e:
        print("DB Error:", e)
        return 0

def all_off():
    for pin in list(SIGNAL1.values()) + list(SIGNAL2.values()):
        GPIO.output(pin, GPIO.LOW)

def priority_signal_cycle():
    print("⚠️ Emergency Detected: Prioritizing Signal 1")
    all_off()
    GPIO.output(SIGNAL1['white'], GPIO.HIGH)
    GPIO.output(SIGNAL2['red'], GPIO.HIGH)
    time.sleep(1)

def normal_cycle():
    print("🚦 Running Normal Cycle")
    # Signal 1 Green, Signal 2 Red
    GPIO.output(SIGNAL1['green'], GPIO.HIGH)
    GPIO.output(SIGNAL2['red'], GPIO.HIGH)
    time.sleep(2)
    GPIO.output(SIGNAL1['green'], GPIO.LOW)

    GPIO.output(SIGNAL1['yellow'], GPIO.HIGH)
    time.sleep(2)
    GPIO.output(SIGNAL1['yellow'], GPIO.LOW)

    # Signal 1 Red, Signal 2 Green
    GPIO.output(SIGNAL1['red'], GPIO.HIGH)
    GPIO.output(SIGNAL2['green'], GPIO.HIGH)
    time.sleep(5)
    GPIO.output(SIGNAL2['green'], GPIO.LOW)

    GPIO.output(SIGNAL2['yellow'], GPIO.HIGH)
    time.sleep(2)
    GPIO.output(SIGNAL2['yellow'], GPIO.LOW)

    GPIO.output(SIGNAL1['red'], GPIO.LOW)
    GPIO.output(SIGNAL2['red'], GPIO.LOW)

def main():
    try:
        while True:
            id = get_latest_severity()
            if id >= 3:
                priority_signal_cycle()
            else:
                all_off()
                normal_cycle()
    except KeyboardInterrupt:
        print("🔴 Exiting...")
    finally:
        all_off()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
