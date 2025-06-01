from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
import threading
import time
import sqlite3
from datetime import datetime

# RFID imports - with fallback for testing
try:
    import serial
    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO
    RFID_AVAILABLE = True
except ImportError:
    print("RFID libraries not available - running in simulation mode")
    RFID_AVAILABLE = False

DB_PATH = "rfid_logs.db"

def init_db():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create rfid_scans table (already exists but ensure it's there)
    c.execute('''
        CREATE TABLE IF NOT EXISTS rfid_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            source TEXT NOT NULL,
            severity INTEGER,
            patient_name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create emergency_cases table for SQLAlchemy
    c.execute('''
        CREATE TABLE IF NOT EXISTS emergency_case (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            severity_level INTEGER NOT NULL,
            driver_id TEXT NOT NULL,
            rfid1_number TEXT,
            rfid2_number TEXT,
            rfid_linked BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create drivers table for SQLAlchemy
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT
        )
    ''')
    
    # Create rfid_reading table for SQLAlchemy
    c.execute('''
        CREATE TABLE IF NOT EXISTS rfid_reading (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfid_number TEXT NOT NULL,
            reader_type TEXT NOT NULL,
            case_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0,
            FOREIGN KEY (case_id) REFERENCES emergency_case (id)
        )
    ''')
    
    # Insert test driver if not exists
    c.execute("SELECT COUNT(*) FROM driver WHERE driver_id = ?", ('driver123',))
    if c.fetchone()[0] == 0:
        password_hash = pbkdf2_sha256.hash('password123')
        c.execute("INSERT INTO driver (driver_id, password_hash, name) VALUES (?, ?, ?)",
                 ('driver123', password_hash, 'Test Driver'))
        print("Test driver created")
    
    conn.commit()
    conn.close()
    print("Database initialized with all tables")

# ============================================================================
# CORE FLASK AND DATABASE SETUP
# ============================================================================

app = Flask(__name__, template_folder='/home/team19/etps/fyp/ui/templates')
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfid_logs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80))

class EmergencyCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(80), nullable=False)
    hospital_name = db.Column(db.String(80), nullable=False)
    severity_level = db.Column(db.Integer, nullable=False)
    driver_id = db.Column(db.String(80), db.ForeignKey('driver.driver_id'))
    rfid1_number = db.Column(db.String(80), nullable=True)
    rfid2_number = db.Column(db.String(80), nullable=True)
    rfid_linked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class RFIDReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rfid_number = db.Column(db.String(80), nullable=False)
    reader_type = db.Column(db.String(10), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('emergency_case.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    processed = db.Column(db.Boolean, default=False)

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def save_scan_to_db(data, source, severity=None, patient_name=None):
    """Save to rfid_scans table (your existing table)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO rfid_scans (data, source, severity, patient_name) VALUES (?, ?, ?, ?)", 
                 (data, source, severity, patient_name))
        conn.commit()
        conn.close()
        print(f"[DB] Saved to rfid_scans: {data} from {source} with severity {severity}")
        return True
    except Exception as e:
        print(f"[DB ERROR] rfid_scans: {e}")
        return False

def save_emergency_case_direct(patient_name, hospital_name, severity_level, driver_id):
    """Save emergency case directly to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO emergency_case (patient_name, hospital_name, severity_level, driver_id, created_at) 
            VALUES (?, ?, ?, ?, ?)
        """, (patient_name, hospital_name, severity_level, driver_id, datetime.now()))
        
        case_id = c.lastrowid
        conn.commit()
        conn.close()
        
        print(f"[DB] Emergency case saved: ID={case_id}, Patient={patient_name}, Severity={severity_level}")
        return case_id
    except Exception as e:
        print(f"[DB ERROR] emergency_case: {e}")
        return None

def save_rfid_to_db(rfid_number, reader_type):
    """Save RFID reading to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Save to rfid_reading table
        c.execute("""
            INSERT INTO rfid_reading (rfid_number, reader_type, timestamp) 
            VALUES (?, ?, ?)
        """, (rfid_number, reader_type, datetime.now()))
        
        reading_id = c.lastrowid
        print(f"[{reader_type.upper()}] Saved RFID reading: {rfid_number} (ID: {reading_id})")
        
        # Also save to rfid_scans for compatibility
        c.execute("INSERT INTO rfid_scans (data, source) VALUES (?, ?)", 
                 (rfid_number, f"Signal {1 if reader_type == 'rfid1' else 2}"))
        
        # Try to link to most recent unlinked case
        c.execute("""
            SELECT id FROM emergency_case 
            WHERE (rfid1_number IS NULL OR rfid2_number IS NULL) 
            ORDER BY created_at DESC LIMIT 1
        """)
        
        recent_case = c.fetchone()
        if recent_case:
            case_id = recent_case[0]
            
            if reader_type == 'rfid1':
                c.execute("SELECT rfid1_number FROM emergency_case WHERE id = ?", (case_id,))
                if c.fetchone()[0] is None:  # rfid1_number is NULL
                    c.execute("UPDATE emergency_case SET rfid1_number = ? WHERE id = ?", (rfid_number, case_id))
                    c.execute("UPDATE rfid_reading SET case_id = ?, processed = 1 WHERE id = ?", (case_id, reading_id))
                    print(f"RFID1: Linked {rfid_number} to case {case_id}")
            
            elif reader_type == 'rfid2':
                c.execute("SELECT rfid2_number FROM emergency_case WHERE id = ?", (case_id,))
                if c.fetchone()[0] is None:  # rfid2_number is NULL
                    c.execute("UPDATE emergency_case SET rfid2_number = ? WHERE id = ?", (rfid_number, case_id))
                    c.execute("UPDATE rfid_reading SET case_id = ?, processed = 1 WHERE id = ?", (case_id, reading_id))
                    print(f"RFID2: Linked {rfid_number} to case {case_id}")
            
            # Check if both RFIDs are now linked
            c.execute("SELECT rfid1_number, rfid2_number FROM emergency_case WHERE id = ?", (case_id,))
            rfid1, rfid2 = c.fetchone()
            if rfid1 and rfid2:
                c.execute("UPDATE emergency_case SET rfid_linked = 1 WHERE id = ?", (case_id,))
                print(f"Case {case_id} fully linked!")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database error saving RFID ({reader_type}): {e}")
        return False

# ============================================================================
# RFID READING CLASSES
# ============================================================================

class RFID1Reader:
    """RFID Reader 1 - Serial/USB connection"""
    def __init__(self):
        self.running = False
        self.serial_connection = None

    def start_reading(self):
        if not RFID_AVAILABLE:
            print("RFID1: Running in simulation mode")
            return

        try:
            self.serial_connection = serial.Serial(
                port='/dev/ttyUSB0',
                baudrate=9600,
                timeout=1
            )
            time.sleep(2)
            self.running = True
            print("RFID1: Started reading from serial...")

            while self.running:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.readline().decode('utf-8').strip()
                    if data:
                        print(f"RFID1 Received: {data}")
                        save_rfid_to_db(data, 'rfid1')
                time.sleep(0.1)

        except Exception as e:
            print(f"RFID1 Error: {e}")
        finally:
            if self.serial_connection:
                self.serial_connection.close()

    def stop_reading(self):
        self.running = False

class RFID2Reader:
    """RFID Reader 2 - GPIO connection"""
    def __init__(self):
        self.running = False
        self.reader = None

    def start_reading(self):
        if not RFID_AVAILABLE:
            print("RFID2: Running in simulation mode")
            return

        try:
            self.reader = SimpleMFRC522()
            self.running = True
            print("RFID2: Started reading from GPIO...")

            while self.running:
                try:
                    print("RFID2: Place your RFID tag near the reader...")
                    id, text = self.reader.read()
                    if id:
                        print(f"RFID2 Received: {id}")
                        save_rfid_to_db(str(id), 'rfid2')
                except Exception as e:
                    print(f"RFID2 Read error: {e}")
                finally:
                    if RFID_AVAILABLE:
                        GPIO.cleanup()
                time.sleep(1)

        except Exception as e:
            print(f"RFID2 Error: {e}")

    def stop_reading(self):
        self.running = False

# Global RFID reader instances
rfid1_reader = RFID1Reader()
rfid2_reader = RFID2Reader()

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def home():
    if 'driver_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login functionality"""
    try:
        if request.method == 'POST':
            driver_id = request.form.get('driver_id')
            password = request.form.get('password')

            # Check credentials using direct database query
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT password_hash, name FROM driver WHERE driver_id = ?", (driver_id,))
            result = c.fetchone()
            conn.close()

            if result and pbkdf2_sha256.verify(password, result[0]):
                session['driver_id'] = driver_id
                session['driver_name'] = result[1]
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))

            flash('Invalid credentials!', 'error')
    except Exception as e:
        flash(f'Error during login: {str(e)}', 'error')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Main dashboard"""
    if 'driver_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            patient_name = request.form.get('patient_name')
            hospital_name = request.form.get('hospital_name')
            severity_level = request.form.get('severity_level')
            
            print(f"DEBUG: Form data - Patient: {patient_name}, Hospital: {hospital_name}, Severity: {severity_level}")
            
            # Validate inputs
            if not patient_name or not hospital_name or not severity_level:
                flash('All fields are required!', 'error')
                return redirect(url_for('dashboard'))
            
            try:
                severity_level = int(severity_level)
                if severity_level < 1 or severity_level > 5:
                    flash('Severity level must be between 1 and 5!', 'error')
                    return redirect(url_for('dashboard'))
            except (ValueError, TypeError):
                flash('Invalid severity level!', 'error')
                return redirect(url_for('dashboard'))

            # Save case using direct database function
            case_id = save_emergency_case_direct(patient_name, hospital_name, severity_level, session['driver_id'])
            
            if case_id:
                # Also save to rfid_scans for logging
                save_scan_to_db(f"Case-{case_id}", "Case Creation", severity_level, patient_name)
                
                flash(f'Emergency case for {patient_name} saved successfully! Case ID: {case_id} (Severity: {severity_level})', 'success')
                flash('Please scan RFID tags to link this case.', 'info')
            else:
                flash('Error saving emergency case!', 'error')

        except Exception as e:
            print(f"ERROR saving case: {str(e)}")
            flash(f"Error submitting case: {str(e)}", 'error')

        return redirect(url_for('dashboard'))

    # Get cases for current driver
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT id, patient_name, hospital_name, severity_level, rfid1_number, rfid2_number, 
                   rfid_linked, created_at 
            FROM emergency_case 
            WHERE driver_id = ? 
            ORDER BY created_at DESC
        """, (session['driver_id'],))
        
        cases_data = c.fetchall()
        conn.close()
        
        # Convert to dict format
        cases = []
        for case in cases_data:
            cases.append({
                'id': case[0],
                'patient_name': case[1],
                'hospital_name': case[2],
                'severity_level': case[3],
                'rfid1_number': case[4],
                'rfid2_number': case[5],
                'rfid_linked': case[6],
                'created_at': case[7]
            })
        
    except Exception as e:
        print(f"Error fetching cases: {e}")
        cases = []
        flash('Error loading cases', 'error')

    return render_template('dashboard.html', cases=cases)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/get_nearby_hospitals', methods=['POST'])
def get_nearby_hospitals():
    """Fixed hospital list"""
    hospitals = [
        "City General Hospital",
        "Metro Medical Center",
        "Emergency Care Hospital",
        "Central District Hospital",
        "Regional Medical Center",
        "St. Mary's Hospital",
        "General Hospital",
        "Community Health Center",
        "University Medical Center",
        "Sacred Heart Hospital",
        "Apollo Hospital",
        "Fortis Hospital",
        "Max Healthcare",
        "Manipal Hospital",
        "Columbia Asia Hospital"
    ]
    return jsonify({'hospitals': hospitals})

@app.route('/rfid_status')
def rfid_status():
    """Show RFID readings and case linking status"""
    if 'driver_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get recent RFID readings
        c.execute("""
            SELECT id, rfid_number, reader_type, case_id, processed, timestamp 
            FROM rfid_reading 
            ORDER BY timestamp DESC LIMIT 20
        """)
        readings_data = c.fetchall()
        
        # Get cases for current driver
        c.execute("""
            SELECT id, patient_name, hospital_name, severity_level, rfid1_number, rfid2_number, 
                   rfid_linked, created_at 
            FROM emergency_case 
            WHERE driver_id = ? 
            ORDER BY created_at DESC
        """, (session['driver_id'],))
        cases_data = c.fetchall()
        
        conn.close()
        
        # Convert to dict format
        readings = []
        for reading in readings_data:
            readings.append({
                'id': reading[0],
                'rfid_number': reading[1],
                'reader_type': reading[2],
                'case_id': reading[3],
                'processed': reading[4],
                'timestamp': reading[5]
            })
        
        cases = []
        for case in cases_data:
            cases.append({
                'id': case[0],
                'patient_name': case[1],
                'hospital_name': case[2],
                'severity_level': case[3],
                'rfid1_number': case[4],
                'rfid2_number': case[5],
                'rfid_linked': case[6],
                'created_at': case[7]
            })
        
    except Exception as e:
        print(f"Error in rfid_status: {e}")
        readings = []
        cases = []
        flash('Error loading RFID status', 'error')

    return render_template('rfid_status.html', readings=readings, cases=cases)

@app.route('/api/rfid_readings')
def api_rfid_readings():
    """API endpoint for RFID readings"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT id, rfid_number, reader_type, case_id, processed, timestamp 
            FROM rfid_reading 
            ORDER BY timestamp DESC LIMIT 10
        """)
        readings_data = c.fetchall()
        conn.close()
        
        readings = []
        for reading in readings_data:
            readings.append({
                'id': reading[0],
                'rfid_number': reading[1],
                'reader_type': reading[2],
                'case_id': reading[3],
                'processed': reading[4],
                'timestamp': reading[5]
            })
        
        return jsonify({'readings': readings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start_rfid_readers')
def start_rfid_readers():
    """Start RFID readers"""
    try:
        rfid1_thread = threading.Thread(target=rfid1_reader.start_reading, daemon=True)
        rfid1_thread.start()

        rfid2_thread = threading.Thread(target=rfid2_reader.start_reading, daemon=True)
        rfid2_thread.start()

        flash('RFID readers started successfully!', 'success')
    except Exception as e:
        flash(f'Error starting RFID readers: {e}', 'error')

    return redirect(url_for('dashboard'))

@app.route('/stop_rfid_readers')
def stop_rfid_readers():
    """Stop RFID readers"""
    try:
        rfid1_reader.stop_reading()
        rfid2_reader.stop_reading()
        flash('RFID readers stopped.', 'info')
    except Exception as e:
        flash(f'Error stopping RFID readers: {e}', 'error')

    return redirect(url_for('dashboard'))

# ============================================================================
# DEBUG AND TEST ROUTES
# ============================================================================

@app.route('/test_rfid2')
def test_rfid2():
    """Test RFID2 database functionality"""
    try:
        test_rfid = "123456789"
        result = save_rfid_to_db(test_rfid, 'rfid2')
        return f"Test RFID2 reading saved: {test_rfid} - Success: {result}"
    except Exception as e:
        return f"Error testing RFID2: {e}"

@app.route('/view_all_data')
def view_all_data():
    """View all data in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        result = "<h1>Database Contents</h1>"
        
        # Show rfid_scans
        c.execute("SELECT * FROM rfid_scans ORDER BY timestamp DESC LIMIT 10")
        scans = c.fetchall()
        result += "<h2>RFID Scans (Latest 10)</h2>"
        for scan in scans:
            result += f"<p>ID: {scan[0]}, Data: {scan[1]}, Source: {scan[2]}, Severity: {scan[3]}, Patient: {scan[4]}, Time: {scan[5]}</p>"
        
        # Show emergency cases
        c.execute("SELECT * FROM emergency_case ORDER BY created_at DESC")
        cases = c.fetchall()
        result += "<h2>Emergency Cases</h2>"
        for case in cases:
            result += f"<p>ID: {case[0]}, Patient: {case[1]}, Hospital: {case[2]}, Severity: {case[3]}, Driver: {case[4]}, RFID1: {case[5]}, RFID2: {case[6]}, Linked: {case[7]}, Time: {case[8]}</p>"
        
        # Show rfid readings
        c.execute("SELECT * FROM rfid_reading ORDER BY timestamp DESC LIMIT 10")
        readings = c.fetchall()
        result += "<h2>RFID Readings (Latest 10)</h2>"
        for reading in readings:
            result += f"<p>ID: {reading[0]}, RFID: {reading[1]}, Type: {reading[2]}, Case: {reading[3]}, Time: {reading[4]}, Processed: {reading[5]}</p>"
        
        conn.close()
        return result
        
    except Exception as e:
        return f"Error viewing data: {e}"

@app.route('/test')
def test_page():
    """Test page"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM emergency_case")
        case_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM rfid_reading")
        rfid_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM rfid_scans")
        scan_count = c.fetchone()[0]
        
        conn.close()
        
    except Exception as e:
        case_count = f"Error: {e}"
        rfid_count = "Error"
        scan_count = "Error"

    return f"""
    <h1>Emergency System - Fixed Database Version</h1>
    <p>System Status: Running</p>
    <p>Database: rfid_logs.db - Connected</p>
    <p>Total Cases: {case_count}</p>
    <p>Total RFID Readings: {rfid_count}</p>
    <p>Total RFID Scans: {scan_count}</p>
    <p>RFID Libraries Available: {RFID_AVAILABLE}</p>
    <hr>
    <h2>Test Login:</h2>
    <p>Driver ID: <code>driver123</code></p>
    <p>Password: <code>password123</code></p>
    <p><a href="/">Go to Login</a></p>
    <hr>
    <h2>RFID Control:</h2>
    <p><a href="/start_rfid_readers">Start RFID Readers</a></p>
    <p><a href="/stop_rfid_readers">Stop RFID Readers</a></p>
    <p><a href="/rfid_status">View RFID Status</a></p>
    <p><a href="/api/rfid_readings">API: Recent RFID Readings</a></p>
    <hr>
    <h2>Debug:</h2>
    <p><a href="/test_rfid2">Test RFID2 Save</a></p>
    <p><a href="/view_all_data">View All Database Data</a></p>
    """

# ============================================================================
# RUN THE APPLICATION
# ============================================================================

if __name__ == '__main__':
    # Initialize database first
    print("Initializing database...")
    init_db()
    
    # Start RFID readers automatically
    try:
        rfid1_thread = threading.Thread(target=rfid1_reader.start_reading, daemon=True)
        rfid1_thread.start()

        rfid2_thread = threading.Thread(target=rfid2_reader.start_reading, daemon=True)
        rfid2_thread.start()

        print("RFID readers started in background threads")
    except Exception as e:
        print(f"Could not start RFID readers: {e}")

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))
