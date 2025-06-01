from flask import Flask, request, jsonify
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
    "Signal1": {"Red": 11, "Green": 15, "White": 29},
    "Signal2": {"Red": 31, "Green": 35, "White": 37}
}

for signal in LEDs.values():
    for pin in signal.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

# ----------------- Priority Logic ------------------

class EmergencyRequest:
    def __init__(self, ambulance_id, trauma_level):
        self.ambulance_id = ambulance_id
        self.trauma_level = trauma_level
        self.timestamp = time.time()

    def __lt__(self, other):
        return self.trauma_level > other.trauma_level or (
            self.trauma_level == other.trauma_level and self.timestamp < other.timestamp
        )

class EmergencyManager:
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()

    def add_emergency(self, ambulance_id, trauma_level):
        with self.lock:
            req = EmergencyRequest(ambulance_id, trauma_level)
            heapq.heappush(self.queue, req)
            print(f"🆕 Added: {ambulance_id} (Trauma {trauma_level})")

    def get_next(self):
        with self.lock:
            return heapq.heappop(self.queue) if self.queue else None

# ----------------- Traffic Controller ------------------

class TrafficSignalController:
    def __init__(self, manager):
        self.manager = manager
        self.shutdown = False

    def start(self):
        print("🚦 Signal Controller Started")
        try:
            while not self.shutdown:
                req = self.manager.get_next()
                if req:
                    self.activate_priority(req)
                    time.sleep(5)
                    self.reset_signals()
                else:
                    self.normal_cycle()
        except KeyboardInterrupt:
            print("🔌 Stopping")
        finally:
            GPIO.cleanup()

    def activate_priority(self, req):
        print(f"[{datetime.now()}] ✅ GREEN: {req.ambulance_id} (Trauma {req.trauma_level})")
        # Example: always use Signal2 for emergency passage
        GPIO.output(LEDs["Signal1"]["Red"], GPIO.HIGH)
        GPIO.output(LEDs["Signal2"]["Green"], GPIO.HIGH)
        GPIO.output(LEDs["Signal2"]["White"], GPIO.HIGH)

    def reset_signals(self):
        print(f"[{datetime.now()}] ⛔ Back to RED")
        for signal in LEDs:
            for pin in LEDs[signal].values():
                GPIO.output(pin, GPIO.LOW)

    def normal_cycle(self):
        print("🔁 Normal cycle")
        GPIO.output(LEDs["Signal1"]["Green"], GPIO.HIGH)
        GPIO.output(LEDs["Signal2"]["Red"], GPIO.HIGH)
        time.sleep(3)
        self.reset_signals()
        GPIO.output(LEDs["Signal2"]["Green"], GPIO.HIGH)
        GPIO.output(LEDs["Signal1"]["Red"], GPIO.HIGH)
        time.sleep(3)
        self.reset_signals()

# ----------------- Flask API ------------------

app = Flask(__name__)
manager = EmergencyManager()
controller = TrafficSignalController(manager)

@app.route('/emergency', methods=['POST'])
def handle_emergency():
    data = request.get_json()
    ambulance_id = data.get("ambulance_id")
    severity = data.get("severity")

    if not ambulance_id or severity is None:
        return jsonify({"error": "Missing data"}), 400

    manager.add_emergency(ambulance_id, int(severity))
    return jsonify({"status": "received"}), 200

# ----------------- RFID Listener ------------------
def log_to_database(ambulance_id, severity):
    conn = sqlite3.connect("emergency_log.db")
    c = conn.cursor()

    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS emergency_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ambulance_id TEXT NOT NULL,
        trauma_level INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Insert the data
    c.execute("INSERT INTO emergency_log (ambulance_id, trauma_level) VALUES (?, ?)",
              (ambulance_id, severity))

    conn.commit()
    conn.close()

def rfid_listener():
    print("🟢 RFID Listener Ready")
    reader = MFRC522()

    try:
        while True:
            (status, tag_type) = reader.MFRC522_Request(reader.PICC_REQIDL)
            if status == reader.MI_OK:
                (status, uid) = reader.MFRC522_Anticoll()
                if status == reader.MI_OK:
                    ambulance_id = str(int.from_bytes(bytes(uid), "big"))
                    print(f"🔍 RFID Detected: {ambulance_id}")
                    try:
                        severity = int(input("💥 Enter trauma level (1-5): "))
                    except ValueError:
                        print("❌ Invalid input. Please enter a number between 1 and 5.")
                        continue
                if 1 <= severity <= 5:
                    try:
                        log_to_database(ambulance_id, severity)
                        requests.post("http://127.0.0.1:5001/emergency", json={
                            "ambulance_id": ambulance_id,
                            "severity": severity
                        })
                        print("✅ Submitted")
                    except requests.exceptions.ConnectionError:
                        print("❌ ERROR: Could not connect to Flask server.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    try:
        # Start RFID listener in a separate thread
        rfid_thread = threading.Thread(target=rfid_listener, daemon=True)
        rfid_thread.start()

        # Start Traffic Signal Controller in a separate thread
        signal_thread = threading.Thread(target=controller.start, daemon=True)
        signal_thread.start()

        # Start Flask server
        app.run(host="127.0.0.1", port=5001)

    except KeyboardInterrupt:
        print("🛑 Graceful shutdown")
    finally:
        controller.shutdown = True
        GPIO.cleanup()
