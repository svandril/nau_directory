import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timezone
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, g

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'your-secret-key-change-this'  # Change this!

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("Warning: DATABASE_URL not set. Logging will be disabled.")
    DATABASE_URL = None

# Directory expiration configuration
# Set this to your desired expiration date/time (UTC)
DIRECTORY_EXPIRATION = datetime(2025, 11, 11, 6, 59, 59, tzinfo=timezone.utc)  # Change this date!

def get_db():
    """Get database connection"""
    if DATABASE_URL is None:
        return None
        
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(DATABASE_URL)
            g.db.autocommit = True
        except psycopg2.Error as e:
            print(f"Database connection error: {e}")
            # Return None to handle gracefully
            return None
    return g.db

def init_logging_db():
    """Initialize the logging database"""
    db = get_db()
    if db is None:
        print("Skipping database initialization - no connection")
        return
    
    try:
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                user_agent TEXT,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        ''')
        cursor.close()
    except psycopg2.Error as e:
        print(f"Database initialization error: {e}")

def log_event(event_type, phone=None):
    """Log an event to the database"""
    db = get_db()
    if db is None:
        print(f"Logging skipped - no database connection: {event_type}")
        return
    
    try:
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO logs (event_type, phone, user_agent, timestamp) VALUES (%s, %s, %s, %s)',
            (event_type, phone, request.headers.get('User-Agent', ''), datetime.now(timezone.utc))
        )
        cursor.close()
    except psycopg2.Error as e:
        print(f"Logging error: {e}")

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Hardcode your directory data here instead of using a database
ATTENDEES = {
    "307-751-3953": "Zack Kawulok",
    "408-332-2494": "Lina Saleh",
    "347-258-0261": "Rucy Cui",
    "727-422-0735": "Annie Ritch",
    "858-922-2689": "Emily Petree",
    "628-260-2470": "Manuel Meyer",
    "408-833-8472": "Esha Dholia",
    "424-237-6852": "Eve La Puma",
    "650-441-8589": "Gillian Hawes",
    "650-441-7751": "Nick Cockton",
    "617-792-6036": "Hilary Brumberg",
    "650-531-9217": "Joel Gibson",
    "303-917-4375": "Reid Miller",
    "816-824-6601": "Vivek Ramalingum",
    "607-271-1316": "Katie Collins",
    "847-877-3450": "Lindsay Mehl",
    "630-804-9289": "Sean van Dril",
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

def is_directory_expired():
    """Check if the directory has expired"""
    return datetime.now(timezone.utc) > DIRECTORY_EXPIRATION

def get_time_until_expiration():
    """Get seconds until expiration (negative if expired)"""
    now = datetime.now(timezone.utc)
    delta = DIRECTORY_EXPIRATION - now
    return int(delta.total_seconds())

# Initialize database once at startup (not on every request)
# This runs when the app module is imported, before any requests
init_logging_db()

@app.route("/")
def home():
    # Check if directory has expired
    if is_directory_expired():
        return render_template('expired.html')
    
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
    # Check if directory has expired
    if is_directory_expired():
        return render_template('expired.html')
    
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

@app.route("/log-phone-click", methods=["POST"])
def log_phone_click():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401
    
    clicked_phone = request.form.get('phone', '')
    clicked_name = request.form.get('name', '')
    
    # Log phone click event
    log_event('phone_clicked', phone)
    
    return jsonify({"success": True})

@app.route("/api/expiration")
def get_expiration_status():
    """API endpoint to get expiration status and countdown"""
    return jsonify({
        "expired": is_directory_expired(),
        "seconds_until_expiration": get_time_until_expiration(),
        "expiration_date": DIRECTORY_EXPIRATION.isoformat()
    })

@app.route("/health")
def health():
    """Healthcheck endpoint for Railway"""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Default to False for production safety, enable with FLASK_DEBUG=True for local dev
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
