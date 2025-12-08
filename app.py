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
DIRECTORY_EXPIRATION = datetime(2024, 12, 15, 7, 59, 59, tzinfo=timezone.utc)  # Change this date!

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

# Define all available interests by category
INTEREST_CATEGORIES = {
    "Outdoors": [
        "Go on a neighborhood walk",
        "Walk to get boba or coffee",
        "Go on an easy hike"
    ],
    "Games": [
        "Play a board game",
        "Do a jigsaw puzzle",
        "Play trivia at a bar"
    ],
    "Everyday": [
        "Cook a simple dinner",
        "Do some gardening or plant potting",
        "Do a Costco run"
    ],
    "Explore": [
        "Visit a museum",
        "Explore a neighborhood in SF"
    ],
    "Creative": [
        "Do a craft",
        "Bake something"
    ]
}

# Get all interests as a flat list for the filter dropdown
ALL_INTERESTS = [interest for category_interests in INTEREST_CATEGORIES.values() for interest in category_interests]

# Hardcode your directory data here instead of using a database
# Each attendee can have an "interests" dict mapping interest names to True (interested) or False (not interested)
ATTENDEES = {
    "307-751-3953": {
        "name": "Zack Kawulok",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": False,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": False,
            "Do a Costco run": False,
            "Visit a museum": False,
            "Explore a neighborhood in SF": False,
            "Do a craft": False,
            "Bake something": False
        }
    },
    "727-422-0735": {
        "name": "Annie Ritch",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": True,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": False,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": False,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": True,
            "Bake something": True
        }
    },
    "858-922-2689": {
        "name": "Emily Petree",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": True,
            "Play a board game": False,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": True,
            "Cook a simple dinner": False,
            "Do some gardening or plant potting": False,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": False
        }
    },
    "424-237-6852": {
        "name": "Eve La Puma",
        "interests": {
            "Go on a neighborhood walk": False,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": False,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": False,
            "Visit a museum": False,
            "Explore a neighborhood in SF": False,
            "Do a craft": True,
            "Bake something": True
        }
    },
    "650-441-8589": {
        "name": "Gillian Hawes",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": False,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": True
        }
    },
    "650-441-7751": {
        "name": "Nick Cockton",
        "interests": {
            "Go on a neighborhood walk": False,
            "Walk to get boba or coffee": False,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": True,
            "Cook a simple dinner": False,
            "Do some gardening or plant potting": False,
            "Do a Costco run": False,
            "Visit a museum": False,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": False
        }
    },
    "617-792-6036": {
        "name": "Hilary Brumberg",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": False,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": False,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": False,
            "Do a craft": True,
            "Bake something": True
        }
    },
    "650-531-9217": {
        "name": "Joel Gibson",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": False,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": False,
            "Do a Costco run": True,
            "Visit a museum": False,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": False
        }
    },
    "303-917-4375": {
        "name": "Reid Miller",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": True,
            "Bake something": True
        }
    },
    "206-240-2363": {
        "name": "Helen",
        "interests": {
            "Go on a neighborhood walk": False,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": False,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": False,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": False,
            "Do a Costco run": False,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": True
        }
    },
    "919-946-6959": {
        "name": "Matt Zothner",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": False,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": True,
            "Cook a simple dinner": False,
            "Do some gardening or plant potting": False,
            "Do a Costco run": False,
            "Visit a museum": False,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": False
        }
    },
    "469-426-9925": {
        "name": "Krithika",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": False,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": False,
            "Do a craft": True,
            "Bake something": True
        }
    },
    "630-804-9289": {
        "name": "Sean van Dril",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": True,
            "Play a board game": True,
            "Do a jigsaw puzzle": True,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": False,
            "Do a Costco run": True,
            "Visit a museum": True,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": True
        }
    },
    "650-609-0610": {
        "name": "Neetu Saini",
        "interests": {
            "Go on a neighborhood walk": True,
            "Walk to get boba or coffee": True,
            "Go on an easy hike": False,
            "Play a board game": True,
            "Do a jigsaw puzzle": False,
            "Play trivia at a bar": True,
            "Cook a simple dinner": True,
            "Do some gardening or plant potting": True,
            "Do a Costco run": True,
            "Visit a museum": False,
            "Explore a neighborhood in SF": True,
            "Do a craft": False,
            "Bake something": True
        }
    }
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

@app.route("/")
def home():
    # Check if directory has expired
    if is_directory_expired():
        return render_template('expired.html')
    
    session_phone = session.get('phone')
    # Check if phone matches any attendee's normalized phone
    if not session_phone or not any(normalize_phone(attendee_phone) == session_phone for attendee_phone in ATTENDEES.keys()):
        return redirect(url_for('login'))
    
    # Convert attendees dict to list format for template, sorted alphabetically by name
    attendees_list = []
    for attendee_phone, attendee_data in ATTENDEES.items():
        if isinstance(attendee_data, dict):
            attendees_list.append({
                "phone": attendee_phone,
                "name": attendee_data["name"],
                "interests": attendee_data.get("interests", {})
            })
        else:
            # Backward compatibility: if it's just a string name
            attendees_list.append({
                "phone": attendee_phone,
                "name": attendee_data,
                "interests": {}
            })
    attendees_list.sort(key=lambda x: x["name"].lower())  # Sort alphabetically (case-insensitive)
    
    # Log page access
    log_event('directory_viewed', session_phone)
    
    return render_template('directory.html', 
                         attendees=attendees_list, 
                         interest_categories=INTEREST_CATEGORIES,
                         all_interests=ALL_INTERESTS)

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

@app.route("/log-filter", methods=["POST"])
def log_filter():
    phone = session.get('phone')
    if not phone or not any(normalize_phone(attendee_phone) == phone for attendee_phone in ATTENDEES.keys()):
        return jsonify({"error": "Not logged in"}), 401
    
    interest_name = request.form.get('interest', '')
    
    # Log filter event with interest name
    log_event('filter_applied', phone, {"interest": interest_name})
    
    return jsonify({"success": True})

@app.route("/health")
def health():
    """Healthcheck endpoint for Railway - must be fast and simple"""
    return jsonify({"status": "ok"}), 200

@app.route("/api/expiration")
def get_expiration_status():
    """API endpoint to get expiration status and countdown"""
    return jsonify({
        "expired": is_directory_expired(),
        "seconds_until_expiration": get_time_until_expiration(),
        "expiration_date": DIRECTORY_EXPIRATION.isoformat()
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Default to False for production safety, enable with FLASK_DEBUG=True for local dev
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
