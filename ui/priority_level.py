from flask import Flask, request, jsonify
import threading
import requests
import heapq
import time
from datetime import datetime
# import RPi.GPIO as GPIO
# from mfrc522 import MFRC522
import sqlite3

# ----------------- GPIO Setup ------------------
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

LEDs = {"Signal1": {"Red": 5, "Yellow": 12 ,"Green": 3, "White": 40},            
   "Signal2": {"Red": 13, "Yellow": 38,"Green": 15, "White": 16}           }
for signal in LEDs.values():
    for pin in signal.values():
         GPIO.setup(pin, GPIO.OUT)
         GPIO.output(pin, GPIO.LOW)

# ----------------- Priority Logic ------------------

class EmergencyRequest:
    def __init__(self, ambulance_id, trauma_level, patient_name=None, hospital_name=None):
        self.ambulance_id = ambulance_id
        self.trauma_level = trauma_level
        self.patient_name = patient_name
        self.hospital_name = hospital_name
        self.timestamp = time.time()

    def __lt__(self, other):
        # Higher trauma_level has higher priority; if equal, older request first
        return self.trauma_level > other.trauma_level or (
            self.trauma_level == other.trauma_level and self.timestamp < other.timestamp
        )

class EmergencyManager:
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()
        self.pending_cases = {}  # Store cases waiting for RFID scan

    def add_pending_case(self, case_id, patient_name, hospital_name, trauma_level):
        """Store case details waiting for RFID scan"""
        with self.lock:
            self.pending_cases[case_id] = {
                'patient_name': patient_name,
                'hospital_name': hospital_name,
                'trauma_level': trauma_level,
                'timestamp': time.time()
            }
            print(f"📋 Pending case {case_id}: {patient_name} -> {hospital_name} (Trauma {trauma_level})")

    def link_rfid_to_case(self, case_id, rfid_number):
        """Link RFID to pending case and add to priority queue"""
        with self.lock:
            if case_id in self.pending_cases:
                case_data = self.pending_cases[case_id]
                req = EmergencyRequest(
                    ambulance_id=rfid_number,
                    trauma_level=case_data['trauma_level'],
                    patient_name=case_data['patient_name'],
                    hospital_name=case_data['hospital_name']
                )
                heapq.heappush(self.queue, req)
                del self.pending_cases[case_id]
                print(f"🔗 Linked RFID {rfid_number} to case {case_id}")
                return True
            return False

    def add_emergency(self, ambulance_id, trauma_level):
        """Direct emergency addition (for backward compatibility)"""
        with self.lock:
            req = EmergencyRequest(ambulance_id, trauma_level)
            heapq.heappush(self.queue, req)
            print(f"🆕 Added: {ambulance_id} (Trauma {trauma_level})")

    def get_next(self):
        with self.lock:
            return heapq.heappop(self.queue) if self.queue else None

    def get_pending_cases(self):
        """Return list of cases waiting for RFID scan"""
        with self.lock:
            return list(self.pending_cases.items())

# ----------------- Traffic Controller ------------------

class TrafficSignalController:
    def __init__(self, manager):
        self.manager = manager
        self.shutdown = False
        self.current_request = None
        self.current_priority = None
        self.lock = threading.Lock()

    def start(self):
        print("🚦 Signal Controller Started")
        try:
            while not self.shutdown:
                with self.lock:
                    req = self.manager.get_next()
                    if req:
                        # If a higher priority comes in during the window, preempt
                        self.current_request = req
                        self.current_priority = req.trauma_level
                        self.activate_priority(req)
                        start_time = time.time()
                        preempted = False
                        while time.time() - start_time < 10:
                            # Check for higher priority in the queue
                            with self.manager.lock:
                                if self.manager.queue:
                                    highest = self.manager.queue[0]
                                    if highest.trauma_level > self.current_priority:
                                        print(f"⚠️ Higher priority detected: Trauma {highest.trauma_level} preempts Trauma {self.current_priority}. Granting access to higher priority.")
                                        # Put current back in queue
                                        heapq.heappush(self.manager.queue, self.current_request)
                                        # Pop and process the higher priority
                                        self.current_request = heapq.heappop(self.manager.queue)
                                        self.current_priority = self.current_request.trauma_level
                                        self.activate_priority(self.current_request)
                                        start_time = time.time()
                                        preempted = True
                                        continue
                                    elif highest.trauma_level < self.current_priority:
                                        print(f"❌ Lower priority ambulance (Trauma {highest.trauma_level}) denied green corridor. Waiting for Trauma {self.current_priority} window to finish.")
                                # else: no higher or lower, continue
                            time.sleep(0.5)
                        print(f"[INFO] Trauma {self.current_priority} window complete.")
                        self.reset_signals()
                        if preempted:
                            print(f"[INFO] Trauma {self.current_priority} was prioritized over lower priority.")
                    else:
                        self.normal_cycle()
        except KeyboardInterrupt:
            print("🔌 Stopping")
        finally:
            GPIO.cleanup()
            pass

    def activate_priority(self, req):
        patient_info = f" - {req.patient_name}" if req.patient_name else ""
        print(f"[{datetime.now()}] ✅ GREEN: {req.ambulance_id} (Trauma {req.trauma_level}){patient_info}")

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

@app.route('/pending_case', methods=['POST'])
def add_pending_case():
    """API endpoint to add case waiting for RFID scan"""
    data = request.get_json()
    case_id = data.get("case_id")
    patient_name = data.get("patient_name")
    hospital_name = data.get("hospital_name")
    trauma_level = data.get("trauma_level")

    if not all([case_id, patient_name, hospital_name, trauma_level]):
        return jsonify({"error": "Missing required data"}), 400

    manager.add_pending_case(case_id, patient_name, hospital_name, int(trauma_level))
    return jsonify({"status": "pending_case_added", "case_id": case_id}), 200

@app.route('/link_rfid', methods=['POST'])
def link_rfid():
    """API endpoint to link RFID to pending case"""
    data = request.get_json()
    case_id = data.get("case_id")
    rfid_number = data.get("rfid_number")

    if not case_id or not rfid_number:
        return jsonify({"error": "Missing case_id or rfid_number"}), 400

    success = manager.link_rfid_to_case(case_id, rfid_number)
    if success:
        return jsonify({"status": "linked_successfully"}), 200
    else:
        return jsonify({"error": "Case not found"}), 404

@app.route('/pending_cases', methods=['GET'])
def get_pending_cases():
    """Get list of cases waiting for RFID scan"""
    cases = manager.get_pending_cases()
    return jsonify({"pending_cases": [{"case_id": k, **v} for k, v in cases]})

# ----------------- Database Functions ------------------

def log_to_database(rfid_number, severity, patient_name=None, hospital_name=None, case_id=None):
    conn = sqlite3.connect("emergency_log.db")
    c = conn.cursor()
    
    # Create enhanced table structure
    c.execute('''CREATE TABLE IF NOT EXISTS emergency_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        rfid_number TEXT NOT NULL,
        patient_name TEXT,
        hospital_name TEXT,
        trauma_level INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute("""INSERT INTO emergency_log 
                 (case_id, rfid_number, patient_name, hospital_name, trauma_level) 
                 VALUES (?, ?, ?, ?, ?)""",
              (case_id, rfid_number, patient_name, hospital_name, severity))
    conn.commit()
    conn.close()

# ----------------- RFID Listener ------------------

def rfid_listener():
    print("🟢 RFID Listener Ready")
    # reader = MFRC522()  # Commented out for non-Raspberry Pi testing

    try:
        while True:
            # Check for pending cases
            pending_cases = manager.get_pending_cases()
            if pending_cases:
                print(f"\n📋 {len(pending_cases)} case(s) waiting for RFID scan:")
                for case_id, case_data in pending_cases:
                    print(f"  - Case {case_id}: {case_data['patient_name']} (Trauma {case_data['trauma_level']})")
                print("🏷️  Please scan RFID tag...\n")

            # RFID-related code commented out for non-Raspberry Pi testing
            (status, tag_type) = reader.MFRC522_Request(reader.PICC_REQIDL)
            if status == reader.MI_OK:
                (status, uid) = reader.MFRC522_Anticoll()
                if status == reader.MI_OK:
                    rfid_number = str(int.from_bytes(bytes(uid), "big"))
                    print(f"🔍 RFID Detected: {rfid_number}")
            #         # Check if there are pending cases to link
                    pending_cases = manager.get_pending_cases()
                    if pending_cases:
                        print("📋 Available cases to link:")
                        for i, (case_id, case_data) in enumerate(pending_cases, 1):
                            print(f"  {i}. Case {case_id}: {case_data['patient_name']} -> {case_data['hospital_name']} (Trauma {case_data['trauma_level']})")
                        try:
                            choice = int(input(f"Choose case number (1-{len(pending_cases)}): ")) - 1
                            if 0 <= choice < len(pending_cases):
                                case_id, case_data = pending_cases[choice]
                                # Link RFID to case
                                success = manager.link_rfid_to_case(case_id, rfid_number)
                                if success:
                                    # Log to database with full details
                                    log_to_database(
                                        rfid_number, 
                                        case_data['trauma_level'],
                                        case_data['patient_name'],
                                        case_data['hospital_name'],
                                        case_id
                                    )
                                    print("✅ RFID linked to case and added to priority queue!")
                                else:
                                     print("❌ Failed to link RFID to case")
                            else:
                                print("⚠️ Invalid choice")
                        except ValueError:
                            print("❌ Invalid input")
                    else:
                        # No pending cases - manual entry (backward compatibility)
                        try:
            

                       severity = int(input("💥 Enter trauma level (1-5): "))
                         if 1 <= severity <= 5:
                              log_to_database(rfid_number, severity)
            #                     manager.add_emergency(rfid_number, severity)
            #                     print("✅ Emergency added to queue")
            #                 else:
            #                     print("⚠️ Enter a number between 1 and 5.")
            #             except ValueError:
            #                 print("❌ Invalid input. Please enter a number.")

            time.sleep(2)  # Simulate wait for RFID

    except KeyboardInterrupt:
        print("🔌 RFID Listener stopped")
    finally:
        # GPIO.cleanup()
        pass

# ----------------- Case Processing ------------------

def process_case(case_id, severity_level):
    """Simulate signal routing for a submitted case. This is a placeholder for integration with app.py."""
    print(f"[process_case] Routing started for case_id={case_id}, severity_level={severity_level}")
    # Here you could add logic to interact with EmergencyManager or TrafficSignalController if needed
    # For now, just simulate a delay
    time.sleep(2)
    print(f"[process_case] Routing complete for case_id={case_id}")

# ----------------- Main ------------------

if __name__ == "__main__":
    try:
        rfid_thread = threading.Thread(target=rfid_listener, daemon=True)
        rfid_thread.start()

        signal_thread = threading.Thread(target=controller.start, daemon=True)
        signal_thread.start()

        app.run(host="127.0.0.1", port=5001)
    except KeyboardInterrupt:
        print("🛑 Graceful shutdown")
    finally:
        controller.shutdown = True
        GPIO.cleanup()
        pass
