import time
import threading
import heapq

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

class TrafficSignalController:
    def __init__(self, manager):
        self.manager = manager
        self.shutdown = False

    def start(self):
        print("🚦 Signal Controller Running")
        try:
            while not self.shutdown:
                req = self.manager.get_next()
                if req:
                    print(f"✅ GREEN: {req.ambulance_id} (Trauma {req.trauma_level})")
                    time.sleep(5)
                else:
                    print("🔁 Normal cycle")
                    time.sleep(2)
        except KeyboardInterrupt:
            print("🔌 Stopped")
