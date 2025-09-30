import sqlite3
import os
from datetime import datetime
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, g

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'your-secret-key-change-this'  # Change this!

# Database file path
DB_PATH = 'nau_logs.db'

def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_logging_db():
    """Initialize the logging database"""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            phone TEXT,
            user_agent TEXT,
            timestamp TEXT NOT NULL
        )
    ''')
    db.commit()

def log_event(event_type, phone=None):
    """Log an event to the database"""
    db = get_db()
    timestamp = db.now().isoformat() if hasattr(db, 'now') else datetime.now().isoformat()
    db.execute(
        'INSERT INTO logs (event_type, phone, user_agent, timestamp) VALUES (?, ?, ?, ?)',
        (event_type, phone, request.headers.get('User-Agent', ''), datetime.now().isoformat())
    )
    db.commit()

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Hardcode your directory data here instead of using a database
ATTENDEES = {
    "+1(555)123-4567": "John Smith",
    "+1(555)234-5678": "Jane Doe", 
    "+1(555)345-6789": "Bob Johnson",
    # Add more attendees here: "phone": "name"
}

def normalize_phone(phone_str):
    """Convert phone number to format like '+15551234567'"""
    if not phone_str:
        return None
    # Extract just the digits
    digits = ''.join(ch for ch in phone_str if ch.isdigit())
    # Handle US numbers
    if len(digits) == 10:
        return f"+1{digits}"  # Add country code
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    return None

# Initialize database on startup
@app.before_request
def before_request():
    init_logging_db()

@app.route("/")
def home():
    phone = session.get('phone')
    # Check if phone matches any attendee's normalized phone
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return redirect(url_for('login'))
    
    # Convert attendees dict to list format for template, sorted alphabetically by name
    attendees_list = [{"phone": phone, "name": name} for phone, name in ATTENDEES.items()]
    attendees_list.sort(key=lambda x: x["name"].lower())  # Sort alphabetically (case-insensitive)
    
    # Log page access
    log_event('directory_viewed', phone)
    
    return render_template('directory.html', attendees=attendees_list)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone_raw = request.form.get('phone', '')
        phone_normalized = normalize_phone(phone_raw)
        
        if phone_normalized and any(normalize_phone(attendee_phone) == phone_normalized for attendee_phone in ATTENDEES.keys()):
            session['phone'] = phone_normalized
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Phone number not found")
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.pop('phone', None)
    return redirect(url_for('login'))

@app.route("/copy", methods=["POST"])
def copy_contact():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401
    
    contact_info = request.form.get('contact', '')
    
    # Log copy event
    log_event('phone_copied', phone)
    
    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
