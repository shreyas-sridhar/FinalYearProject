# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import io
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ambulance.db'
db = SQLAlchemy(app)

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

# Create tables
with app.app_context():
    db.create_all()
    # Create a test driver if none exists
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

@app.route('/logout')
def logout():
    session.pop('driver_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)