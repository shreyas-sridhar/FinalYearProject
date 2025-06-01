import RPi.GPIO as GPIO
import time
import sqlite3
from datetime import datetime, timedelta
import threading

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

class PriorityTrafficController:
    def __init__(self):
        self.current_priority_signal = None  # 1 or 2
        self.current_priority_level = None   # 1-5 (1 = highest)
        self.priority_start_time = None
        self.priority_duration = 10  # seconds
        self.last_processed_id = 0
        
    def get_latest_rfid_scans(self):
        """Get new RFID scans that haven't been processed yet"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get latest scans after last processed ID
            cursor.execute("""
                SELECT rs.id, rs.data, rs.source, rs.timestamp, ec.severity_level
                FROM rfid_scans rs
                LEFT JOIN emergency_case ec ON (rs.data = ec.rfid1_number OR rs.data = ec.rfid2_number)
                WHERE rs.id > ? 
                ORDER BY rs.timestamp DESC
            """, (self.last_processed_id,))
            
            scans = cursor.fetchall()
            conn.close()
            return scans
            
        except Exception as e:
            print(f"DB Error: {e}")
            return []
    
    def get_signal_number(self, source):
        """Convert source string to signal number"""
        if source.lower() == "signal 1":
            return 1
        elif source.lower() == "signal 2":
            return 2
        return None
    
    def all_off(self):
        """Turn off all lights"""
        for pin in list(SIGNAL1.values()) + list(SIGNAL2.values()):
            GPIO.output(pin, GPIO.LOW)
    
    def flash_red_denial(self, signal_num):
        """Flash red light rapidly for 2 seconds to indicate access denied"""
        print(f"🚫 Access Denied - Signal {signal_num}")
        
        signal = SIGNAL1 if signal_num == 1 else SIGNAL2
        
        # Flash red rapidly for 2 seconds
        for _ in range(8):  # 8 flashes in 2 seconds
            GPIO.output(signal['red'], GPIO.HIGH)
            time.sleep(0.125)
            GPIO.output(signal['red'], GPIO.LOW)
            time.sleep(0.125)
    
    def activate_priority_signal(self, signal_num, priority_level):
        """Activate white light for priority signal"""
        print(f"🚨 Priority Activated - Signal {signal_num}, Priority Level {priority_level}")
        
        self.all_off()
        
        if signal_num == 1:
            GPIO.output(SIGNAL1['white'], GPIO.HIGH)
            GPIO.output(SIGNAL2['red'], GPIO.HIGH)
        else:
            GPIO.output(SIGNAL2['white'], GPIO.HIGH) 
            GPIO.output(SIGNAL1['red'], GPIO.HIGH)
        
        self.current_priority_signal = signal_num
        self.current_priority_level = priority_level
        self.priority_start_time = datetime.now()
    
    def process_rfid_scan(self, scan_id, rfid_data, source, timestamp, severity_level):
        """Process individual RFID scan and determine action"""
        signal_num = self.get_signal_number(source)
        
        if signal_num is None:
            print(f"⚠️ Unknown source: {source}")
            return
        
        if severity_level is None:
            print(f"⚠️ No emergency case found for RFID: {rfid_data}")
            self.flash_red_denial(signal_num)
            return
        
        print(f"📍 RFID Scan - Signal: {signal_num}, Priority: {severity_level}, Time: {timestamp}")
        
        # If no current priority session
        if self.current_priority_signal is None:
            self.activate_priority_signal(signal_num, severity_level)
            return
        
        # If same signal is scanning again
        if self.current_priority_signal == signal_num:
            if severity_level <= self.current_priority_level:  # Same or higher priority
                self.activate_priority_signal(signal_num, severity_level)
            else:  # Lower priority
                self.flash_red_denial(signal_num)
            return
        
        # Different signal is scanning
        if severity_level < self.current_priority_level:  # Higher priority (lower number)
            self.activate_priority_signal(signal_num, severity_level)
        elif severity_level > self.current_priority_level:  # Lower priority
            self.flash_red_denial(signal_num)
        else:  # Same priority - check timestamp
            # Get current priority signal's timestamp
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT rs.timestamp FROM rfid_scans rs
                    LEFT JOIN emergency_case ec ON (rs.data = ec.rfid1_number OR rs.data = ec.rfid2_number)
                    WHERE rs.source = ? AND ec.severity_level = ?
                    ORDER BY rs.timestamp DESC LIMIT 1
                """, (f"Signal {self.current_priority_signal}", self.current_priority_level))
                
                current_time = cursor.fetchone()
                conn.close()
                
                if current_time and timestamp > current_time[0]:
                    # New scan is more recent
                    self.activate_priority_signal(signal_num, severity_level)
                else:
                    self.flash_red_denial(signal_num)
                    
            except Exception as e:
                print(f"Timestamp comparison error: {e}")
                self.flash_red_denial(signal_num)
    
    def check_priority_timeout(self):
        """Check if current priority session has expired"""
        if (self.current_priority_signal is not None and 
            self.priority_start_time is not None):
            
            elapsed = (datetime.now() - self.priority_start_time).total_seconds()
            if elapsed >= self.priority_duration:
                print(f"⏰ Priority timeout - Signal {self.current_priority_signal}")
                self.current_priority_signal = None
                self.current_priority_level = None
                self.priority_start_time = None
                return True
        return False
    
    def normal_cycle(self):
        """Run normal traffic light cycle"""
        print("🚦 Running Normal Cycle")
        
        # Signal 1 Green, Signal 2 Red
        self.all_off()
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
    
    def run(self):
        """Main control loop"""
        try:
            while True:
                # Check for new RFID scans
                new_scans = self.get_latest_rfid_scans()
                
                for scan in new_scans:
                    scan_id, rfid_data, source, timestamp, severity_level = scan
                    self.process_rfid_scan(scan_id, rfid_data, source, timestamp, severity_level)
                    self.last_processed_id = max(self.last_processed_id, scan_id)
                
                # Check if priority session has expired
                priority_expired = self.check_priority_timeout()
                
                # Run appropriate cycle
                if self.current_priority_signal is not None and not priority_expired:
                    # Maintain priority state
                    time.sleep(0.5)
                else:
                    # Run normal cycle
                    self.all_off()
                    self.normal_cycle()
                
        except KeyboardInterrupt:
            print("🔴 Exiting...")
        finally:
            self.all_off()
            GPIO.cleanup()

def main():
    controller = PriorityTrafficController()
    controller.run()

if __name__ == "__main__":
    main()
