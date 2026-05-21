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

def get_db():
    """Get database connection"""
    if DATABASE_URL is None:
        return None
        
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(DATABASE_URL)
            g.db.autocommit = True
            # Initialize schema lazily on first connection per request context
            if 'schema_initialized' not in g:
                try:
                    cursor = g.db.cursor()
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
                    g.schema_initialized = True
                except psycopg2.Error as e:
                    print(f"Schema initialization error: {e}")
        except psycopg2.Error as e:
            print(f"Database connection error: {e}")
            # Return None to handle gracefully
            return None
    return g.db

def log_event(event_type, phone=None, metadata=None):
    """Log an event to the database"""
    db = get_db()
    if db is None:
        print(f"Logging skipped - no database connection: {event_type}")
        return
    
    try:
        cursor = db.cursor()
        # Store metadata as JSON string in user_agent field for now (or we could add a metadata column)
        user_agent = request.headers.get('User-Agent', '')
        if metadata:
            import json
            user_agent = json.dumps({"user_agent": user_agent, "metadata": metadata})
        cursor.execute(
            'INSERT INTO logs (event_type, phone, user_agent, timestamp) VALUES (%s, %s, %s, %s)',
            (event_type, phone, user_agent, datetime.now(timezone.utc))
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
# Each attendee can have an "interests" dict mapping interest names to True (interested) or False (not interested)
ATTENDEES = {
    "303-917-4375": {
        "name": "Reid Miller",
    },
    "617-792-6036": {
        "name": "Hilary Brumberg",
        "bio": "Anything outside (hike, bike, neighborhood walk, park picnic, etc) and eat yummy food (gluten free)!",
    },
    "607-271-1316": {
        "name": "Katey Collins",
    },
    "727-422-0735": {
        "name": "Annie Ritch",
        "bio": "Moderately experimental baking, carrying textbooks up hills (hiking weight training), drinking tea, walking to boba shops/bakeries/tasty treats",
    },
    "628-260-2470": {
        "name": "Manuel Meyer",
        "bio": "Running, swimming, hiking, hanging at a cafe, board games.",
    },
    "858-922-2689": {
        "name": "Emily Petree",
        "bio": "Playing board games, knitting/crafts, walking",
    },
    "408-332-2494": {
        "name": "Lina Saleh",
        "bio": "Hanging out with friends, going on walks, hiking (light to moderate), Barry's, yoga, watching tv shows/documentaries, having thought provoking conversations, learning from different cultures and experiences.",
    },
    "919-946-6959": {
        "name": "Matt Zothner",
    },
    "650-441-7751": {
        "name": "Nick Cockton",
        "bio": "Running, hiking, grabbing dinner, seeing a movie.",
    },
    "650-441-8589": {
        "name": "Gillian Hawes",
        "bio": "Taking spin (cycling) classes, playing board games, pub trivia nights, hiking",
    },
    "424-237-6852": {
        "name": "Eve La Puma",
        "bio": "I love seeing plays, jamming out making music, playing board games",
    },
    "215-910-7554": {
        "name": "Cezar Gherghel",
    },
    "630-804-9289": {
        "name": "Sean van Dril",
    },
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

@app.route("/")
def home():
    session_phone = session.get('phone')
    # Check if phone matches any attendee's normalized phone
    if not session_phone or not any(normalize_phone(attendee_phone) == session_phone for attendee_phone in ATTENDEES.keys()):
        return redirect(url_for('login'))
    
    # Convert attendees dict to list format for template, sorted alphabetically by name
    attendees_list = []
    for attendee_phone, attendee_data in ATTENDEES.items():
        digits = ''.join(ch for ch in attendee_phone if ch.isdigit())
        photo_url = None
        for ext in ('jpg', 'jpeg', 'png', 'webp'):
            if os.path.exists(os.path.join('static', 'photos', f'{digits}.{ext}')):
                photo_url = f'/static/photos/{digits}.{ext}'
                break
        attendees_list.append({
            "phone": attendee_phone,
            "name": attendee_data["name"],
            "bio": attendee_data.get("bio", ""),
            "photo_url": photo_url,
        })
    attendees_list.sort(key=lambda x: x["name"].lower())  # Sort alphabetically (case-insensitive)
    
    # Log page access
    log_event('directory_viewed', session_phone)
    
    return render_template('directory.html', attendees=attendees_list)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone_raw = request.form.get('phone', '')
        phone_normalized = normalize_phone(phone_raw)
        
        if phone_normalized and any(normalize_phone(attendee_phone) == phone_normalized for attendee_phone in ATTENDEES.keys()):
            session['phone'] = phone_normalized
            log_event('login', phone_normalized)
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

    copied_name = request.form.get('name', '')
    copied_phone = request.form.get('phone', '')
    log_event('phone_copied', phone, {"copied_name": copied_name, "copied_phone": copied_phone})
    return jsonify({"success": True})

@app.route("/log-phone-click", methods=["POST"])
def log_phone_click():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401

    clicked_name = request.form.get('name', '')
    clicked_phone = request.form.get('phone', '')
    log_event('phone_clicked', phone, {"clicked_name": clicked_name, "clicked_phone": clicked_phone})
    return jsonify({"success": True})

@app.route("/log-bio-expand", methods=["POST"])
def log_bio_expand():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401

    expanded_name = request.form.get('name', '')
    log_event('bio_expanded', phone, {"expanded_name": expanded_name})
    return jsonify({"success": True})

@app.route("/log-photo-open", methods=["POST"])
def log_photo_open():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401

    viewed_name = request.form.get('name', '')
    log_event('photo_opened', phone, {"viewed_name": viewed_name})
    return jsonify({"success": True})

@app.route("/health")
def health():
    """Healthcheck endpoint for Railway - must be fast and simple"""
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Default to False for production safety, enable with FLASK_DEBUG=True for local dev
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
