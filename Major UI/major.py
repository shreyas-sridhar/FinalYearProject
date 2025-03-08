import time
import heapq
import json
import threading

# File to store user accounts
USER_DB_FILE = "users.json"

# ----------------------------
# User Account Management
# ----------------------------

def load_users():
    """Load user accounts from a file."""
    try:
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    """Save user accounts to a file."""
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f)

def create_account():
    """Create a new ambulance user account."""
    users = load_users()
    username = input("Enter new ambulance ID (username): ")
    if username in users:
        print("🚨 This ambulance ID already exists! Try logging in.")
        return None

    password = input("Enter a password: ")
    users[username] = {"password": password}
    save_users(users)
    print("✅ Account created successfully!")
    return username

def login():
    """Log in an ambulance user."""
    users = load_users()
    username = input("Enter ambulance ID (username): ")
    if username not in users:
        print("🚨 Ambulance ID not found! Create an account first.")
        return None

    password = input("Enter password: ")
    if users[username]["password"] != password:
        print("🚨 Wrong password! Try again.")
        return None

    print(f"✅ Welcome, {username}!")
    return username

# ----------------------------
# Priority Queue for Ambulances
# ----------------------------

class EmergencyRequest:
    """Represents an ambulance's emergency request."""
    def _init_(self, ambulance_id, trauma_level):
        self.ambulance_id = ambulance_id
        self.trauma_level = trauma_level  # Higher = More Critical
        self.timestamp = time.time()      # Helps resolve ties

    def _lt_(self, other):
        """Higher trauma level gets priority. If equal, earlier request wins."""
        if self.trauma_level != other.trauma_level:
            return self.trauma_level > other.trauma_level
        return self.timestamp < other.timestamp

class EmergencyManager:
    """Manages priority queue for ambulances."""
    def _init_(self):
        self.emergency_queue = []
        self.lock = threading.Lock()

    def add_emergency(self, ambulance_id, trauma_level):
        """Add a new ambulance priority request."""
        with self.lock:
            req = EmergencyRequest(ambulance_id, trauma_level)
            heapq.heappush(self.emergency_queue, req)
            print(f"🚑 {ambulance_id} added with trauma level {trauma_level}")

    def get_highest_priority(self):
        """Check the highest priority ambulance."""
        with self.lock:
            return self.emergency_queue[0] if self.emergency_queue else None

    def pop_highest_priority(self):
        """Remove the highest priority ambulance."""
        with self.lock:
            return heapq.heappop(self.emergency_queue) if self.emergency_queue else None

# ----------------------------
# Traffic Signal Control
# ----------------------------

class TrafficSignalController:
    """Controls traffic signal based on ambulance priority."""
    def _init_(self):
        self.emergency_manager = EmergencyManager()
        self.current_emergency = None

    def check_for_emergency(self):
        """Continuously checks for priority ambulances."""
        while True:
            highest_priority = self.emergency_manager.get_highest_priority()
            if highest_priority:
                if (self.current_emergency is None or
                    highest_priority.trauma_level > self.current_emergency.trauma_level):
                    self.current_emergency = self.emergency_manager.pop_highest_priority()
                    self.override_signal(self.current_emergency)
            else:
                if self.current_emergency:
                    self.restore_normal_signal()
                    self.current_emergency = None
            time.sleep(0.5)

    def override_signal(self, emergency_request):
        """Turn traffic light green for the priority ambulance."""
        print(f"🚦 GREEN LIGHT for {emergency_request.ambulance_id} (Trauma Level {emergency_request.trauma_level})")

    def restore_normal_signal(self):
        """Restore normal signal when no emergencies are left."""
        print("🚦 Restoring normal signal")

# ----------------------------
# User Interface (CLI)
# ----------------------------

def main():
    controller = TrafficSignalController()
    threading.Thread(target=controller.check_for_emergency, daemon=True).start()

    print("\n🚑🚦 *TRAFFIC SIGNAL SYSTEM* 🚦🚑")
    
    while True:
        print("\n1️⃣ Create New Ambulance Account")
        print("2️⃣ Login & Set Priority")
        print("3️⃣ Exit")
        
        choice = input("Choose an option: ")
        
        if choice == "1":
            create_account()
        
        elif choice == "2":
            user = login()
            if user:
                trauma_level = int(input(f"{user}, enter trauma level (1-5): "))
                if 1 <= trauma_level <= 5:
                    controller.emergency_manager.add_emergency(user, trauma_level)
                else:
                    print("🚨 Invalid trauma level! Must be between 1 and 5.")
        
        elif choice == "3":
            print("👋 Exiting...")
            break
        
        else:
            print("🚨 Invalid choice! Please try again.")

if __name__ == "__main__":
    main()