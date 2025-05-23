from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
import requests
import time

# Mock GPIO for testing without Raspberry Pi
class MockGPIO:
    BCM = "BCM"
    OUT = "OUT"
    HIGH = True
    LOW = False
    
    @staticmethod
    def setmode(mode):
        print(f"[MOCK GPIO] Set mode: {mode}")
    
    @staticmethod
    def setwarnings(state):
        print(f"[MOCK GPIO] Set warnings: {state}")
    
    @staticmethod
    def setup(pin, mode):
        print(f"[MOCK GPIO] Setup pin {pin} as {mode}")
    
    @staticmethod
    def output(pin, state):
        state_str = "HIGH" if state else "LOW"
        print(f"[MOCK GPIO] Set pin {pin} to {state_str}")
    
    @staticmethod
    def cleanup():
        print("[MOCK GPIO] Cleanup called")

# Use mock GPIO instead of real RPi.GPIO
GPIO = MockGPIO()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team.db'
db = SQLAlchemy(app)

# Mappls API credentials
MAPPLS_CLIENT_ID = "96dHZVzsAus4KWbL-LEHP6EZXgGmw1BnAhVgiPaH2clb-UM7cNc13PnwC8ihPlM8I3e1xZY8eIYc7FmgTcGsfoIv2T9xV0jV"
MAPPLS_CLIENT_SECRET = "lrFxI-iSEg93wYXBhCN1LDXh9pkvzTG8kPcdhkUwXIvC_wWkPT83qDpR3cTXkG68N4es96l_k9qLVKVjgVTUZgf6IWP_tjiIGTFw1GaDHh8="
MAPPLS_TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"
# Token cache
mappls_token = None
mappls_token_expiry = 0

# GPIO Setup (now using mock)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
ALERT_PIN = 18  # Change this to your connected pin
GPIO.setup(ALERT_PIN, GPIO.OUT)

# Priority system API URL
PRIORITY_API_URL = "http://127.0.0.1:5001"

def get_mappls_token():
    global mappls_token, mappls_token_expiry

    if mappls_token and time.time() < mappls_token_expiry:
        return mappls_token

    data = {
        'grant_type': 'client_credentials',
        'client_id': MAPPLS_CLIENT_ID,
        'client_secret': MAPPLS_CLIENT_SECRET
    }

    try:
        response = requests.post(MAPPLS_TOKEN_URL, data=data, timeout=10)
        if response.status_code == 200:
            token_info = response.json()
            mappls_token = token_info['access_token']
            mappls_token_expiry = time.time() + token_info['expires_in'] - 60
            return mappls_token
        else:
            raise Exception("Failed to fetch Mappls token: " + response.text)
    except requests.exceptions.RequestException as e:
        print(f"Mappls API error: {e}")
        raise Exception("Failed to connect to Mappls API")

# Database Models
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
    rfid_number = db.Column(db.String(80), nullable=True)  # Store linked RFID
    rfid_linked = db.Column(db.Boolean, default=False)  # Track if RFID is linked
    submitted_to_priority = db.Column(db.Boolean, default=False)  # Track if sent to priority system

# Create tables and add test driver
with app.app_context():
    db.create_all()
    if not Driver.query.filter_by(driver_id='driver123').first():
        test_driver = Driver(
            driver_id='driver123',
            password_hash=pbkdf2_sha256.hash('password123'),
            name='Test Driver'
        )
        db.session.add(test_driver)
        db.session.commit()
        print("Test driver created: driver123 / password123")

# Mock Priority System API calls for testing
def mock_priority_api_call(endpoint, data=None, method='POST'):
    """Mock function to simulate priority system API calls"""
    print(f"[MOCK API] {method} {PRIORITY_API_URL}{endpoint}")
    if data:
        print(f"[MOCK API] Data: {data}")
    
    if endpoint == '/pending_case':
        # Simulate successful case submission
        return {'status': 'success', 'message': 'Case submitted to priority system'}
    elif endpoint == '/pending_cases':
        # Simulate pending cases response (empty for testing)
        return {'pending_cases': []}
    
    return {'status': 'success'}

# Routes
@app.route('/')
def home():
    if 'driver_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            driver_id = request.form.get('driver_id')
            password = request.form.get('password')

            driver = Driver.query.filter_by(driver_id=driver_id).first()

            if driver and pbkdf2_sha256.verify(password, driver.password_hash):
                session['driver_id'] = driver_id
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))

            flash('Invalid credentials!', 'error')
    except Exception as e:
        flash(f'Error during login: {str(e)}', 'error')
        print(f"Error during login: {str(e)}")
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'driver_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            severity = int(request.form.get('severity_level'))
            new_case = EmergencyCase(
                patient_name=request.form.get('patient_name'),
                hospital_name=request.form.get('hospital_name'),
                severity_level=severity,
                driver_id=session['driver_id']
            )
            db.session.add(new_case)
            db.session.commit()

            # Send to priority system (mocked for testing)
            try:
                print(f"[TESTING] Submitting case {new_case.id} to priority system...")
                mock_response = mock_priority_api_call('/pending_case', {
                    "case_id": new_case.id,
                    "patient_name": new_case.patient_name,
                    "hospital_name": new_case.hospital_name,
                    "trauma_level": severity
                })
                
                new_case.submitted_to_priority = True
                db.session.commit()
                flash('Emergency case submitted! Please scan RFID tag to activate priority.', 'info')
                print(f"[TESTING] Case {new_case.id} successfully submitted to priority system")
                    
            except Exception as e:
                flash('Case saved but priority system is offline.', 'warning')
                print(f"Priority system error: {e}")

            # GPIO Trigger: alert on high severity (mocked)
            if severity >= 3:
                print(f"[TESTING] HIGH SEVERITY ALERT! Level {severity} case detected")
                GPIO.output(ALERT_PIN, GPIO.HIGH)
                time.sleep(2)
                GPIO.output(ALERT_PIN, GPIO.LOW)
                print("[TESTING] Alert signal completed")

        except Exception as e:
            flash(f"Error submitting case: {str(e)}", 'error')
            print(f"Error submitting case: {str(e)}")

        return redirect(url_for('dashboard'))

    # Get cases and their RFID link status
    cases = EmergencyCase.query.filter_by(driver_id=session['driver_id']).all()
    
    # Check RFID link status for each case (mocked)
    for case in cases:
        if case.submitted_to_priority and not case.rfid_linked:
            try:
                # Mock check if case is still pending RFID scan
                mock_response = mock_priority_api_call('/pending_cases', method='GET')
                pending_cases = mock_response.get('pending_cases', [])
                case_still_pending = any(p.get('case_id') == case.id for p in pending_cases)
                
                # For testing, simulate RFID linking after 2 minutes
                if not case_still_pending:
                    case.rfid_linked = True
                    db.session.commit()
                    print(f"[TESTING] Case {case.id} RFID status updated to linked")
            except Exception as e:
                print(f"Error checking RFID status for case {case.id}: {e}")
    
    return render_template('dashboard.html', cases=cases)

@app.route('/check_rfid_status/<int:case_id>')
def check_rfid_status(case_id):
    """API endpoint to check if RFID has been linked to a case"""
    case = EmergencyCase.query.get_or_404(case_id)
    
    try:
        # Mock the priority system check
        mock_response = mock_priority_api_call('/pending_cases', method='GET')
        pending_cases = mock_response.get('pending_cases', [])
        is_pending = any(p.get('case_id') == case_id for p in pending_cases)
        
        # For testing purposes, simulate RFID linking randomly or after some time
        import random
        if not is_pending and case.submitted_to_priority and not case.rfid_linked:
            # Simulate 50% chance of RFID being linked for testing
            if random.choice([True, False]):
                case.rfid_linked = True
                db.session.commit()
                print(f"[TESTING] Case {case_id} RFID randomly linked for testing")
                return jsonify({"status": "linked", "rfid_linked": True})
        
        return jsonify({"status": "pending" if not case.rfid_linked else "linked", "rfid_linked": case.rfid_linked})
        
    except Exception as e:
        print(f"Error checking RFID status: {e}")
        return jsonify({"status": "unknown", "rfid_linked": case.rfid_linked})

@app.route('/get_nearby_hospitals', methods=['POST'])
def get_nearby_hospitals():
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not latitude or not longitude:
        return jsonify({'error': 'Location not provided'}), 400

    try:
        token = get_mappls_token()
    except Exception as e:
        print("Token fetch error:", e)
        # Return mock hospitals for testing when API fails
        mock_hospitals = [
            "City General Hospital",
            "Metro Medical Center", 
            "Emergency Care Hospital",
            "Central District Hospital",
            "Regional Medical Center"
        ]
        print("[TESTING] Using mock hospitals due to API error")
        return jsonify({'hospitals': mock_hospitals})

    headers = {
        "Authorization": f"bearer {token}"
    }

    url = f"https://atlas.mappls.com/api/places/nearby/json?keywords=hospital&refLocation={latitude},{longitude}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        results = response.json()
    except Exception as e:
        print("Mappls API error:", e)
        # Return mock hospitals for testing
        mock_hospitals = [
            "City General Hospital",
            "Metro Medical Center", 
            "Emergency Care Hospital",
            "Central District Hospital",
            "Regional Medical Center"
        ]
        print("[TESTING] Using mock hospitals due to API error")
        return jsonify({'hospitals': mock_hospitals})

    if 'suggestedLocations' in results:
        hospital_names = [place['placeName'] for place in results['suggestedLocations']]
        return jsonify({'hospitals': hospital_names})

    # Fallback to mock hospitals
    mock_hospitals = [
        "City General Hospital",
        "Metro Medical Center", 
        "Emergency Care Hospital", 
        "Central District Hospital",
        "Regional Medical Center"
    ]
    print("[TESTING] Using mock hospitals as fallback")
    return jsonify({'hospitals': mock_hospitals})

@app.route('/logout')
def logout():
    session.pop('driver_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# FIXED RFID API Routes for Postman Testing
@app.route('/api/rfid/scan', methods=['POST'])
def rfid_scan():
    """API endpoint to simulate RFID scanning via Postman - FIXED VERSION"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        rfid_number = data.get('rfid_number')
        case_id = data.get('case_id')
        
        if not rfid_number:
            return jsonify({'error': 'rfid_number is required'}), 400
            
        if not case_id:
            return jsonify({'error': 'case_id is required'}), 400
            
        # Find the case
        case = EmergencyCase.query.get(case_id)
        if not case:
            return jsonify({'error': f'Case {case_id} not found'}), 404
            
        # FIXED: Check if case already has a valid RFID linked (both conditions must be true)
        if case.rfid_linked and case.rfid_number:
            return jsonify({
                'message': f'Case {case_id} already has RFID {case.rfid_number} linked',
                'rfid_number': case.rfid_number,
                'case_id': case_id,
                'status': 'already_linked'
            }), 200
            
        # FIXED: Handle inconsistent state where rfid_linked is True but rfid_number is None
        if case.rfid_linked and not case.rfid_number:
            print(f"[RFID API] Warning: Case {case_id} had rfid_linked=True but rfid_number=None. Fixing inconsistent state...")
            case.rfid_linked = False
            
        # Link RFID to case
        case.rfid_number = rfid_number
        case.rfid_linked = True
        db.session.commit()
        
        print(f"[RFID API] RFID {rfid_number} successfully linked to case {case_id}")
        
        return jsonify({
            'message': f'RFID {rfid_number} successfully linked to case {case_id}',
            'rfid_number': rfid_number,
            'case_id': case_id,
            'patient_name': case.patient_name,
            'hospital_name': case.hospital_name,
            'severity_level': case.severity_level,
            'status': 'linked'
        }), 200
        
    except Exception as e:
        print(f"RFID scan error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/rfid/unlink', methods=['POST'])
def rfid_unlink():
    """API endpoint to unlink RFID from a case (for testing)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        case_id = data.get('case_id')
        
        if not case_id:
            return jsonify({'error': 'case_id is required'}), 400
            
        # Find the case
        case = EmergencyCase.query.get(case_id)
        if not case:
            return jsonify({'error': f'Case {case_id} not found'}), 404
            
        if not case.rfid_linked and not case.rfid_number:
            return jsonify({
                'message': f'Case {case_id} has no RFID linked',
                'case_id': case_id,
                'status': 'not_linked'
            }), 200
            
        # Unlink RFID from case
        old_rfid = case.rfid_number
        case.rfid_number = None
        case.rfid_linked = False
        db.session.commit()
        
        print(f"[RFID API] RFID {old_rfid} unlinked from case {case_id}")
        
        return jsonify({
            'message': f'RFID {old_rfid} unlinked from case {case_id}',
            'old_rfid_number': old_rfid,
            'case_id': case_id,
            'status': 'unlinked'
        }), 200
        
    except Exception as e:
        print(f"RFID unlink error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# NEW: Admin route to fix inconsistent RFID states
@app.route('/api/admin/fix_rfid_states', methods=['POST'])
def fix_rfid_states():
    """Admin endpoint to fix inconsistent RFID states in database"""
    try:
        # Find cases where rfid_linked is True but rfid_number is None
        inconsistent_cases = EmergencyCase.query.filter(
            EmergencyCase.rfid_linked == True,
            EmergencyCase.rfid_number.is_(None)
        ).all()
        
        fixed_count = 0
        fixed_case_ids = []
        for case in inconsistent_cases:
            case.rfid_linked = False
            fixed_count += 1
            fixed_case_ids.append(case.id)
            print(f"[ADMIN] Fixed inconsistent state for case {case.id}")
            
        db.session.commit()
        
        return jsonify({
            'message': f'Fixed {fixed_count} inconsistent RFID states',
            'fixed_cases': fixed_count,
            'fixed_case_ids': fixed_case_ids,
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"Fix RFID states error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/cases/<int:case_id>', methods=['GET'])
def get_case_details(case_id):
    """API endpoint to get case details"""
    try:
        case = EmergencyCase.query.get(case_id)
        if not case:
            return jsonify({'error': f'Case {case_id} not found'}), 404
            
        return jsonify({
            'case_id': case.id,
            'patient_name': case.patient_name,
            'hospital_name': case.hospital_name,
            'severity_level': case.severity_level,
            'driver_id': case.driver_id,
            'rfid_number': case.rfid_number,
            'rfid_linked': case.rfid_linked,
            'submitted_to_priority': case.submitted_to_priority
        }), 200
        
    except Exception as e:
        print(f"Get case error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/cases', methods=['GET'])
def get_all_cases():
    """API endpoint to get all cases"""
    try:
        cases = EmergencyCase.query.all()
        cases_list = []
        
        for case in cases:
            cases_list.append({
                'case_id': case.id,
                'patient_name': case.patient_name,
                'hospital_name': case.hospital_name,
                'severity_level': case.severity_level,
                'driver_id': case.driver_id,
                'rfid_number': case.rfid_number,
                'rfid_linked': case.rfid_linked,
                'submitted_to_priority': case.submitted_to_priority
            })
            
        return jsonify({
            'cases': cases_list,
            'total_cases': len(cases_list)
        }), 200
        
    except Exception as e:
        print(f"Get all cases error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# Test routes for development
@app.route('/test')
def test_page():
    """Test page to verify everything is working"""
    return f"""
    <h1>Emergency System Test Page</h1>
    <p>System Status: ✅ Running</p>
    <p>Database: ✅ Connected</p>
    <p>GPIO: ✅ Mock Mode (No Raspberry Pi)</p>
    <p>Priority API: ✅ Mock Mode</p>
    <hr>
    <h2>Test Login:</h2>
    <p>Driver ID: <code>driver123</code></p>
    <p>Password: <code>password123</code></p>
    <p><a href="/">Go to Login</a></p>
    <hr>
    <h2>🔧 FIXED RFID API Testing with Postman:</h2>
    
    <h3>1. Fix Database Inconsistencies (Run First):</h3>
    <p><strong>POST</strong> <code>http://127.0.0.1:5000/api/admin/fix_rfid_states</code></p>
    <p><em>No body required - this will fix any cases with rfid_linked=True but rfid_number=None</em></p>
    
    <h3>2. Link RFID to Case:</h3>
    <p><strong>POST</strong> <code>http://127.0.0.1:5000/api/rfid/scan</code></p>
    <pre>{{
  "rfid_number": "RFID123456",
  "case_id": 1
}}</pre>
    
    <h3>3. Unlink RFID from Case:</h3>
    <p><strong>POST</strong> <code>http://127.0.0.1:5000/api/rfid/unlink</code></p>
    <pre>{{
  "case_id": 1
}}</pre>
    
    <h3>4. Get Case Details:</h3>
    <p><strong>GET</strong> <code>http://127.0.0.1:5000/api/cases/1</code></p>
    
    <h3>5. Get All Cases:</h3>
    <p><strong>GET</strong> <code>http://127.0.0.1:5000/api/cases</code></p>
    
    <hr>
    <h2>🚨 Troubleshooting Steps for Null RFID Issue:</h2>
    <ol>
        <li>First, run the fix admin endpoint to clean up inconsistent states</li>
        <li>Then try linking RFID again</li>
        <li>If still having issues, check the case details endpoint to see current state</li>
    </ol>
    """

import atexit

@atexit.register
def cleanup_gpio():
    GPIO.cleanup()

if __name__ == '__main__':
    print("="*50)
    print("🚨 EMERGENCY SYSTEM - TESTING MODE (FIXED VERSION)")
    print("="*50)
    print("✅ Running without Raspberry Pi (GPIO mocked)")
    print("✅ Priority system API calls mocked")
    print("✅ Mappls API with fallback to mock data")
    print("🔧 FIXED: RFID null value issue resolved")
    print("📝 Test credentials: driver123 / password123")
    print("🌐 Test page available at: http://127.0.0.1:5000/test")
    print("="*50)
    print("🔧 FIXES APPLIED:")
    print("  - RFID scan now checks both rfid_linked AND rfid_number")
    print("  - Added admin route to fix inconsistent database states")
    print("  - Better error handling and logging for RFID operations")
    print("="*50)
    
    app.run(host='127.0.0.1', port=5000, debug=True)
