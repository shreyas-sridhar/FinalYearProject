from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ambulance.db'
db = SQLAlchemy(app)

# Mappls API credentials
MAPPLS_CLIENT_ID = "96dHZVzsAut3ZnWxGN7Lm3B6i8IRC2Np5LbON8tlXDldDFKctykbSWqRno-N_HXyHU1mUZ-MUVLaUp-5nc5aEg=="
MAPPLS_CLIENT_SECRET = "lrFxI-iSEg_4M2nq1EpF0nl7fogCpyWBcz2YurJXC_WtcurKE4kW7p47lgkVPKQ9HlMd1KYuqO6Y8D9xoI9VvKn-iJj255K1"
MAPPLS_TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"

# Token cache
mappls_token = None
mappls_token_expiry = 0

def get_mappls_token():
    global mappls_token, mappls_token_expiry

    if mappls_token and time.time() < mappls_token_expiry:
        return mappls_token 

    data = {
        'grant_type': 'client_credentials',
        'client_id': MAPPLS_CLIENT_ID,
        'client_secret': MAPPLS_CLIENT_SECRET
    }

    response = requests.post(MAPPLS_TOKEN_URL, data=data)
    if response.status_code == 200:
        token_info = response.json()
        mappls_token = token_info['access_token']
        mappls_token_expiry = time.time() + token_info['expires_in'] - 60
        return mappls_token
    else:
        raise Exception("Failed to fetch Mappls token: " + response.text)

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

# Create tables and add test driver
with app.app_context():
    db.create_all()
    if not Driver.query.filter_by(driver_id='driver123').first():
        test_driver = Driver(
            driver_id='driver123',
            password_hash=generate_password_hash('password123'),
            name='Test Driver'
        )
        db.session.add(test_driver)
        db.session.commit()

# Routes
@app.route('/')
def home():
    if 'driver_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        driver_id = request.form.get('driver_id')
        password = request.form.get('password')
        
        driver = Driver.query.filter_by(driver_id=driver_id).first()
        
        if driver and check_password_hash(driver.password_hash, password):
            session['driver_id'] = driver_id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials!', 'error')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'driver_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_case = EmergencyCase(
            patient_name=request.form.get('patient_name'),
            hospital_name=request.form.get('hospital_name'),
            severity_level=int(request.form.get('severity_level')),
            driver_id=session['driver_id']
        )
        db.session.add(new_case)
        db.session.commit()
        flash('Emergency case submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    cases = EmergencyCase.query.filter_by(driver_id=session['driver_id']).all()
    return render_template('dashboard.html', cases=cases)

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
        return jsonify({'error': str(e)}), 500

    headers = {
        "Authorization": f"bearer {token}"
    }

    url = f"https://atlas.mappls.com/api/places/nearby/json?keywords=hospital&refLocation={latitude},{longitude}"
    try:
        response = requests.get(url, headers=headers)
        results = response.json()
    except Exception as e:
        print("Mappls API error:", e)
        return jsonify({'error': str(e)}), 500

    if 'suggestedLocations' in results:
        hospital_names = [place['placeName'] for place in results['suggestedLocations']]
        return jsonify({'hospitals': hospital_names})

    return jsonify({'hospitals': []})


@app.route('/logout')
def logout():
    session.pop('driver_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
