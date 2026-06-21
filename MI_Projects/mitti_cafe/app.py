# ============================================================
#  MITTI Cafe — Integrated Flask Backend
#  Includes: ML Churn Prediction + MySQL Auth/Reservations/Cart
#
#  SETUP (run once):
#  pip3 install flask flask-cors scikit-learn pandas numpy joblib mysql-connector-python --break-system-packages
#
#  RUN:
#  python3 train_model.py    ← first time only (for ML model)
#  python3 app.py            ← start the server
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import pandas as pd
import numpy as np
import joblib
import json
import os
import uuid
import hashlib
import hmac
import re
from datetime import datetime, date, timedelta

app = Flask(__name__)
CORS(app)


# ════════════════════════════════════════════
#  DATABASE CONFIG
# ════════════════════════════════════════════
DB_HOST     = "127.0.0.1"
DB_USER     = "root"
DB_PASSWORD = "root123"
DB_NAME     = "mitti_cafe"

SECRET_KEY = os.environ.get("MITTI_SECRET", "mitti-soil-secret-2024")


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME
    )


# ════════════════════════════════════════════
#  ML MODEL CONFIG
# ════════════════════════════════════════════
MODEL_PATH  = "model/churn_model.pkl"
SCALER_PATH = "model/churn_scaler.pkl"
INFO_PATH   = "model/model_info.json"

ml_model  = None
ml_scaler = None
ml_info   = {}

FEATURES = [
    "cafe_visits_last_month",
    "whatsapp_opened",
    "box_accepted",
    "months_subscribed",
    "plan_type"
]


def load_ml_model():
    """Load saved ML model files into memory at startup"""
    global ml_model, ml_scaler, ml_info
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            ml_model  = joblib.load(MODEL_PATH)
            ml_scaler = joblib.load(SCALER_PATH)
            with open(INFO_PATH) as f:
                ml_info = json.load(f)
            print(f"[ML] ✅ Model loaded — Accuracy: {ml_info.get('accuracy')}%")
        else:
            print("[ML] ⚠️  Model not found. Run: python3 train_model.py first")
    except Exception as e:
        print(f"[ML] ❌ Error loading model: {e}")

load_ml_model()


# ════════════════════════════════════════════
#  AUTH HELPERS
# ════════════════════════════════════════════

def hash_password(password: str) -> str:
    return hmac.new(SECRET_KEY.encode(), password.encode(), hashlib.sha256).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)

def generate_session_token() -> str:
    return str(uuid.uuid4())

def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))

def get_user_from_token(token: str):
    """Returns user dict if token is valid and not expired, else None."""
    if not token:
        return None
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT u.id, u.first_name, u.last_name, u.email, u.phone,
                   u.role, u.created_at, u.last_login
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = %s AND s.expires_at > NOW()
        ''', (token,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user:
            if user.get('created_at'): user['created_at'] = str(user['created_at'])
            if user.get('last_login'): user['last_login']  = str(user['last_login'])
        return user
    except:
        return None

def require_auth():
    """Call at start of protected routes. Returns (user, error_response)."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user  = get_user_from_token(token)
    if not user:
        return None, (jsonify({"success": False, "error": "Unauthorized. Please sign in."}), 401)
    return user, None


# ════════════════════════════════════════════
#  DATABASE INITIALISATION
# ════════════════════════════════════════════

def init_db():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cur.close(); conn.close()

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            first_name    VARCHAR(100) NOT NULL,
            last_name     VARCHAR(100),
            email         VARCHAR(150) NOT NULL UNIQUE,
            phone         VARCHAR(20),
            password_hash VARCHAR(255) NOT NULL,
            role          ENUM('customer','staff','admin') DEFAULT 'customer',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login    TIMESTAMP NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            user_id      INT NOT NULL,
            token        VARCHAR(100) NOT NULL UNIQUE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at   TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL 30 DAY),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            user_id        INT,
            first_name     VARCHAR(100) NOT NULL,
            last_name      VARCHAR(100),
            email          VARCHAR(150) NOT NULL,
            phone          VARCHAR(20),
            enquiry_type   VARCHAR(100) NOT NULL,
            preferred_date DATE,
            num_guests     INT,
            message        TEXT,
            status         ENUM('pending','confirmed','cancelled') DEFAULT 'pending',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS cart_sessions (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            user_id        INT,
            reservation_id INT,
            session_token  VARCHAR(100) NOT NULL UNIQUE,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)        REFERENCES users(id)        ON DELETE SET NULL,
            FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            session_token  VARCHAR(100) NOT NULL,
            item_name      VARCHAR(200) NOT NULL,
            item_emoji     VARCHAR(10),
            item_price     DECIMAL(8,2) NOT NULL,
            item_category  VARCHAR(100),
            item_tags      VARCHAR(255),
            quantity       INT DEFAULT 1,
            added_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_token)
                REFERENCES cart_sessions(session_token) ON DELETE CASCADE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS harvest_bookings (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            user_id          INT,
            first_name       VARCHAR(100) NOT NULL,
            last_name        VARCHAR(100),
            email            VARCHAR(150) NOT NULL,
            phone            VARCHAR(20),
            experience_type  ENUM('individual','family','corporate','school') DEFAULT 'individual',
            visit_date       DATE NOT NULL,
            time_slot        VARCHAR(20) NOT NULL,
            num_guests       INT DEFAULT 1,
            special_requests TEXT,
            status           ENUM('pending','confirmed','cancelled') DEFAULT 'pending',
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS plant_adoptions (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            user_id          INT,
            first_name       VARCHAR(100) NOT NULL,
            last_name        VARCHAR(100),
            email            VARCHAR(150) NOT NULL,
            phone            VARCHAR(20),
            plan_name        ENUM('seedling','grower','farmer') DEFAULT 'seedling',
            plan_price       DECIMAL(8,2) NOT NULL,
            plant_name       VARCHAR(100),
            delivery_address TEXT,
            status           ENUM('active','paused','cancelled') DEFAULT 'active',
            start_date       DATE DEFAULT (CURRENT_DATE),
            next_delivery    DATE,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    cur.close(); conn.close()
    print("✅ MySQL Running!")
    print("✅ Connected!")
    print(f"✅ Database '{DB_NAME}' Ready!")
    print("✅ All Tables Ready (users, user_sessions, reservations, cart_sessions, cart_items, harvest_bookings, plant_adoptions)")


# ════════════════════════════════════════════
#  HOME / HEALTH CHECK
# ════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "app"     : "MITTI Cafe API",
        "version" : "3.0",
        "status"  : "running",
        "ml"      : "Logistic Regression Churn Predictor — " + ("✅ Loaded" if ml_model else "❌ Not loaded"),
        "endpoints": {
            # ML
            "predict_churn"      : "POST /api/predict/churn",
            "predict_batch"      : "POST /api/predict/churn/batch",
            "predict_conversion" : "POST /api/predict/conversion",
            "model_info"         : "GET  /api/model/info",
            # Auth
            "register"           : "POST /api/auth/register",
            "login"              : "POST /api/auth/login",
            "logout"             : "POST /api/auth/logout",
            "me"                 : "GET  /api/auth/me",
            "update_profile"     : "PATCH /api/auth/profile",
            "change_password"    : "POST /api/auth/change-password",
            # Admin
            "list_users"         : "GET  /api/admin/users",
            # Reservations
            "reservations"       : "POST/GET /api/reservations",
            # Harvest
            "harvest"            : "POST/GET /api/harvest",
            "harvest_status"     : "PATCH /api/harvest/<id>/status",
            # Adoptions
            "adoptions"          : "POST/GET /api/adoptions",
            "adoption_status"    : "PATCH /api/adoptions/<id>/status",
            # Cart
            "cart_session"       : "POST /api/cart/session",
            "cart_add"           : "POST /api/cart/add",
            "cart_get"           : "GET  /api/cart/<session_token>",
            "cart_update"        : "PATCH /api/cart/update",
            "cart_remove"        : "DELETE /api/cart/remove",
            "cart_clear"         : "DELETE /api/cart/clear/<session_token>",
        }
    })


# ════════════════════════════════════════════
#  ML ENDPOINTS
# ════════════════════════════════════════════

@app.route("/api/predict/churn", methods=["POST"])
def predict_churn():
    """
    Predict churn risk for a single customer.

    Request body (JSON):
    {
        "cafe_visits_last_month": 2,
        "whatsapp_opened": 1,
        "box_accepted": 0,
        "months_subscribed": 3,
        "plan_type": 1
    }
    """
    if ml_model is None:
        return jsonify({"error": "Model not loaded. Run: python3 train_model.py first"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    missing = [f for f in FEATURES if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}", "required": FEATURES}), 400

    try:
        input_df     = pd.DataFrame([{f: data[f] for f in FEATURES}])
        input_scaled = ml_scaler.transform(input_df)
        proba        = ml_model.predict_proba(input_scaled)[0]
        prediction   = ml_model.predict(input_scaled)[0]

        churn_prob    = float(proba[1])
        churn_percent = round(churn_prob * 100, 1)

        if churn_prob >= 0.70:
            risk_level = "HIGH";   risk_emoji = "🔴"
            action = "Send WhatsApp retention offer immediately. Consider a free cafe visit."
        elif churn_prob >= 0.40:
            risk_level = "MEDIUM"; risk_emoji = "🟡"
            action = "Send a personal check-in WhatsApp. Remind them of upcoming harvest."
        else:
            risk_level = "LOW";    risk_emoji = "🟢"
            action = "Customer is healthy. Continue regular engagement."

        confidence_score = abs(churn_prob - 0.5) * 2
        confidence = "HIGH"   if confidence_score > 0.6 else \
                     "MEDIUM" if confidence_score > 0.3 else "LOW"

        return jsonify({
            "churn_probability" : round(churn_prob, 4),
            "churn_percent"     : churn_percent,
            "prediction"        : int(prediction),
            "prediction_label"  : "CHURN" if prediction == 1 else "STAY",
            "risk_level"        : risk_level,
            "risk_emoji"        : risk_emoji,
            "action"            : action,
            "confidence"        : confidence,
            "timestamp"         : datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict/churn/batch", methods=["POST"])
def predict_churn_batch():
    """Predict churn risk for multiple customers at once."""
    if ml_model is None:
        return jsonify({"error": "Model not loaded"}), 503

    data      = request.get_json()
    customers = data.get("customers", [])
    if not customers:
        return jsonify({"error": "No customers provided"}), 400

    results       = []
    at_risk_count = 0

    for i, customer in enumerate(customers):
        try:
            input_df     = pd.DataFrame([{f: customer.get(f, 0) for f in FEATURES}])
            input_scaled = ml_scaler.transform(input_df)
            proba        = ml_model.predict_proba(input_scaled)[0]
            prediction   = ml_model.predict(input_scaled)[0]
            churn_prob   = float(proba[1])

            risk = "HIGH"   if churn_prob >= 0.70 else \
                   "MEDIUM" if churn_prob >= 0.40 else "LOW"

            if churn_prob >= 0.50:
                at_risk_count += 1

            results.append({
                "customer_id"   : customer.get("customer_id", f"C{i+1:03d}"),
                "name"          : customer.get("name", f"Customer {i+1}"),
                "churn_percent" : round(churn_prob * 100, 1),
                "prediction"    : int(prediction),
                "risk_level"    : risk,
            })
        except Exception as e:
            results.append({"customer_id": customer.get("customer_id", "?"), "error": str(e)})

    results.sort(key=lambda x: x.get("churn_percent", 0), reverse=True)

    return jsonify({
        "total_customers" : len(customers),
        "at_risk_count"   : at_risk_count,
        "at_risk_percent" : round((at_risk_count / len(customers)) * 100, 1),
        "results"         : results,
        "timestamp"       : datetime.now().isoformat()
    })


@app.route("/api/model/info", methods=["GET"])
def model_info():
    """Returns info about the currently loaded ML model."""
    if ml_model is None:
        return jsonify({"status": "not_loaded", "message": "Run train_model.py"}), 503
    return jsonify({
        "status"     : "loaded",
        "model_type" : ml_info.get("model_type"),
        "accuracy"   : ml_info.get("accuracy"),
        "features"   : ml_info.get("features"),
        "trained_on" : ml_info.get("trained_on"),
        "version"    : ml_info.get("version"),
    })


@app.route("/api/predict/conversion", methods=["POST"])
def predict_conversion():
    """
    Predict if a Harvest Experience visitor will adopt a Plant subscription.
    Rule-based scoring (upgrade to ML model once data is collected).
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    score            = 0.0
    feedback_rating  = data.get("feedback_rating",  3)
    asked_about_plan = data.get("asked_about_plan",  False)
    visited_before   = data.get("visited_before",    False)
    items_ordered    = data.get("items_ordered",     1)
    group_size       = data.get("group_size",        1)
    experience_type  = data.get("experience_type",   "individual")

    if feedback_rating >= 4:             score += 0.30
    if feedback_rating == 5:             score += 0.15
    if asked_about_plan:                 score += 0.25
    if visited_before:                   score += 0.15
    if items_ordered >= 2:               score += 0.10
    if group_size >= 3:                  score += 0.05
    if experience_type == "family":      score += 0.10
    if experience_type == "corporate":   score -= 0.10

    score = max(0.0, min(1.0, score))

    if score >= 0.65:
        message = "Very likely to subscribe. Share the Grower plan brochure before they leave."
    elif score >= 0.40:
        message = "Good potential. Offer a 1-month free trial of the Seedling plan."
    else:
        message = "Low conversion chance now. Add to nurture WhatsApp list."

    return jsonify({
        "conversion_probability" : round(score, 4),
        "conversion_percent"     : round(score * 100, 1),
        "likelihood"             : "HIGH" if score >= 0.65 else "MEDIUM" if score >= 0.40 else "LOW",
        "recommended_plan"       : "Grower" if score >= 0.65 else "Seedling",
        "action"                 : message
    })


# ════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════

@app.route('/api/auth/register', methods=['POST'])
def register():
    data       = request.get_json()
    first_name = data.get('firstName', '').strip()
    last_name  = data.get('lastName',  '').strip()
    email      = data.get('email',     '').strip().lower()
    phone      = data.get('phone',     '').strip()
    password   = data.get('password',  '')

    if not first_name or not email or not password:
        return jsonify({"success": False, "error": "First name, email, and password are required."}), 400
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Invalid email address."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "An account with this email already exists."}), 409

        pw_hash = hash_password(password)
        cur.execute('''
            INSERT INTO users (first_name, last_name, email, phone, password_hash)
            VALUES (%s, %s, %s, %s, %s)
        ''', (first_name, last_name or None, email, phone or None, pw_hash))
        conn.commit()
        user_id = cur.lastrowid

        token = generate_session_token()
        cur.execute("INSERT INTO user_sessions (user_id, token) VALUES (%s, %s)", (user_id, token))

        cart_token = generate_session_token()
        cur.execute("INSERT INTO cart_sessions (user_id, session_token) VALUES (%s, %s)", (user_id, cart_token))

        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_id,))
        conn.commit()

        cur.execute("SELECT id, first_name, last_name, email, phone, role, created_at FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        user['created_at'] = str(user['created_at'])

        cur.close(); conn.close()
        print(f"✅ New user registered: #{user_id} | {email}")

        return jsonify({
            "success":      True,
            "user":         user,
            "sessionToken": token,
            "cartToken":    cart_token,
            "message":      f"Welcome to MITTI, {first_name}! 🌱"
        })

    except Exception as e:
        print(f"❌ Register error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = data.get('email',    '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user or not verify_password(password, user['password_hash']):
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Invalid email or password."}), 401

        token = generate_session_token()
        cur.execute("INSERT INTO user_sessions (user_id, token) VALUES (%s, %s)", (user['id'], token))

        cur.execute("SELECT session_token FROM cart_sessions WHERE user_id = %s LIMIT 1", (user['id'],))
        existing_cart = cur.fetchone()
        if not existing_cart:
            cart_token = generate_session_token()
            cur.execute("INSERT INTO cart_sessions (user_id, session_token) VALUES (%s, %s)", (user['id'], cart_token))
        else:
            cart_token = existing_cart['session_token']

        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
        conn.commit()

        safe_user = {
            "id":        user['id'],
            "firstName": user['first_name'],
            "lastName":  user['last_name'],
            "email":     user['email'],
            "phone":     user['phone'],
            "role":      user['role'],
            "createdAt": str(user['created_at'])
        }

        cur.close(); conn.close()
        print(f"✅ Login: #{user['id']} | {email}")

        return jsonify({
            "success":      True,
            "user":         safe_user,
            "sessionToken": token,
            "cartToken":    cart_token
        })

    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if not token:
        return jsonify({"success": False, "error": "No token provided."}), 400
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE token = %s", (token,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Logged out successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/me', methods=['GET'])
def get_me():
    user, err = require_auth()
    if err: return err
    return jsonify({"success": True, "user": user})


@app.route('/api/auth/profile', methods=['PATCH'])
def update_profile():
    user, err = require_auth()
    if err: return err

    data       = request.get_json()
    first_name = data.get('firstName', '').strip()
    last_name  = data.get('lastName',  '').strip()
    phone      = data.get('phone',     '').strip()

    if not first_name:
        return jsonify({"success": False, "error": "First name is required."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE users SET first_name=%s, last_name=%s, phone=%s WHERE id=%s",
            (first_name, last_name or None, phone or None, user['id'])
        )
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Profile updated!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/change-password', methods=['POST'])
def change_password():
    user, err = require_auth()
    if err: return err

    data         = request.get_json()
    old_password = data.get('oldPassword', '')
    new_password = data.get('newPassword', '')

    if len(new_password) < 8:
        return jsonify({"success": False, "error": "New password must be at least 8 characters."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user['id'],))
        row = cur.fetchone()
        if not verify_password(old_password, row['password_hash']):
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Current password is incorrect."}), 401

        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_password), user['id']))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Password changed successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════════
#  ADMIN — USER MANAGEMENT
# ════════════════════════════════════════════

@app.route('/api/admin/users', methods=['GET'])
def list_users():
    user, err = require_auth()
    if err: return err
    if user['role'] not in ('admin', 'staff'):
        return jsonify({"success": False, "error": "Access denied."}), 403

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT u.id, u.first_name, u.last_name, u.email, u.phone,
                   u.role, u.created_at, u.last_login,
                   COUNT(DISTINCT r.id)  AS reservation_count,
                   COUNT(DISTINCT cs.id) AS cart_session_count,
                   COUNT(DISTINCT hb.id) AS harvest_booking_count,
                   COUNT(DISTINCT pa.id) AS plant_adoption_count
            FROM users u
            LEFT JOIN reservations     r  ON r.user_id  = u.id
            LEFT JOIN cart_sessions    cs ON cs.user_id = u.id
            LEFT JOIN harvest_bookings hb ON hb.user_id = u.id
            LEFT JOIN plant_adoptions  pa ON pa.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        ''')
        users = cur.fetchall()
        for u in users:
            if u.get('created_at'): u['created_at'] = str(u['created_at'])
            if u.get('last_login'): u['last_login']  = str(u['last_login'])
        cur.close(); conn.close()
        return jsonify({"success": True, "users": users, "total": len(users)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════════
#  RESERVATION ROUTES
# ════════════════════════════════════════════

@app.route('/api/reservations', methods=['POST'])
def save_reservation():
    data = request.get_json()

    first_name     = data.get('firstName',     '').strip()
    last_name      = data.get('lastName',      '').strip()
    email          = data.get('email',         '').strip()
    phone          = data.get('phone',         '').strip()
    enquiry_type   = data.get('enquiryType',   '').strip()
    preferred_date = data.get('preferredDate') or None
    num_guests     = data.get('numGuests')     or None
    message        = data.get('message',       '').strip()
    session_token  = data.get('sessionToken')  or None

    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)
    user_id   = auth_user['id'] if auth_user else None

    if not first_name or not email or not enquiry_type:
        return jsonify({"success": False, "error": "First name, email, and enquiry type are required."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO reservations
                (user_id, first_name, last_name, email, phone,
                 enquiry_type, preferred_date, num_guests, message)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_id,
            first_name, last_name or None, email, phone or None,
            enquiry_type, preferred_date,
            int(num_guests) if num_guests else None,
            message or None
        ))
        conn.commit()
        reservation_id = cur.lastrowid

        if session_token:
            cur.execute(
                "UPDATE cart_sessions SET reservation_id = %s WHERE session_token = %s",
                (reservation_id, session_token)
            )
            conn.commit()

        cur.close(); conn.close()
        print(f"✅ Reservation saved! ID: {reservation_id} | {first_name} | {enquiry_type}")

        return jsonify({
            "success": True,
            "id":      reservation_id,
            "message": "Reservation saved! We'll confirm within 2 hours."
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)

    if not auth_user:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        if auth_user['role'] in ('admin', 'staff'):
            cur.execute('''
                SELECT r.*, u.email AS user_email FROM reservations r
                LEFT JOIN users u ON r.user_id = u.id
                ORDER BY r.created_at DESC
            ''')
        else:
            cur.execute(
                "SELECT * FROM reservations WHERE user_id = %s ORDER BY created_at DESC",
                (auth_user['id'],)
            )

        rows = cur.fetchall()
        for row in rows:
            if row.get('preferred_date'): row['preferred_date'] = str(row['preferred_date'])
            if row.get('created_at'):     row['created_at']     = str(row['created_at'])
        cur.close(); conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════
#  HARVEST BOOKING ROUTES
# ════════════════════════════════════════════

@app.route('/api/harvest', methods=['POST'])
def create_harvest_booking():
    data = request.get_json()

    first_name       = data.get('firstName',      '').strip()
    last_name        = data.get('lastName',       '').strip()
    email            = data.get('email',          '').strip()
    phone            = data.get('phone',          '').strip()
    experience_type  = data.get('experienceType', 'individual').strip()
    visit_date       = data.get('visitDate')      or None
    time_slot        = data.get('timeSlot',       '').strip()
    num_guests       = data.get('numGuests',      1)
    special_requests = data.get('specialRequests','').strip()

    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)
    user_id   = auth_user['id'] if auth_user else None

    if not first_name or not email or not visit_date or not time_slot:
        return jsonify({"success": False,
                        "error": "First name, email, visit date, and time slot are required."}), 400

    if experience_type not in ('individual', 'family', 'corporate', 'school'):
        experience_type = 'individual'

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO harvest_bookings
                (user_id, first_name, last_name, email, phone,
                 experience_type, visit_date, time_slot, num_guests, special_requests)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_id,
            first_name, last_name or None, email, phone or None,
            experience_type, visit_date, time_slot,
            int(num_guests) if num_guests else 1,
            special_requests or None
        ))
        conn.commit()
        booking_id = cur.lastrowid
        cur.close(); conn.close()

        print(f"✅ Harvest booking! ID: {booking_id} | {first_name} | {experience_type} | {visit_date} {time_slot}")

        return jsonify({
            "success": True,
            "id":      booking_id,
            "message": f"Harvest slot booked! See you on {visit_date} at {time_slot}. 🌿"
        })

    except Exception as e:
        print(f"❌ Harvest booking error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/harvest', methods=['GET'])
def get_harvest_bookings():
    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)

    if not auth_user:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        if auth_user['role'] in ('admin', 'staff'):
            cur.execute('''
                SELECT hb.*, u.email AS user_email FROM harvest_bookings hb
                LEFT JOIN users u ON hb.user_id = u.id
                ORDER BY hb.visit_date ASC, hb.time_slot ASC
            ''')
        else:
            cur.execute(
                "SELECT * FROM harvest_bookings WHERE user_id = %s ORDER BY visit_date DESC",
                (auth_user['id'],)
            )

        rows = cur.fetchall()
        for row in rows:
            if row.get('visit_date'): row['visit_date'] = str(row['visit_date'])
            if row.get('created_at'): row['created_at'] = str(row['created_at'])
        cur.close(); conn.close()
        return jsonify({"success": True, "bookings": rows, "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/harvest/<int:booking_id>/status', methods=['PATCH'])
def update_harvest_status(booking_id):
    user, err = require_auth()
    if err: return err
    if user['role'] not in ('admin', 'staff'):
        return jsonify({"success": False, "error": "Access denied."}), 403

    data   = request.get_json()
    status = data.get('status', '').strip()
    if status not in ('pending', 'confirmed', 'cancelled'):
        return jsonify({"success": False, "error": "Invalid status."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("UPDATE harvest_bookings SET status = %s WHERE id = %s", (status, booking_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": f"Booking #{booking_id} marked as {status}."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════════
#  PLANT ADOPTION ROUTES
# ════════════════════════════════════════════

PLAN_PRICES = {
    'seedling':  499.00,
    'grower':    899.00,
    'farmer':   1499.00,
}

@app.route('/api/adoptions', methods=['POST'])
def create_adoption():
    data = request.get_json()

    first_name       = data.get('firstName',       '').strip()
    last_name        = data.get('lastName',        '').strip()
    email            = data.get('email',           '').strip()
    phone            = data.get('phone',           '').strip()
    plan_name        = data.get('planName',        'seedling').strip().lower()
    plant_name       = data.get('plantName',       '').strip()
    delivery_address = data.get('deliveryAddress', '').strip()

    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)
    user_id   = auth_user['id'] if auth_user else None

    if not first_name or not email:
        return jsonify({"success": False, "error": "First name and email are required."}), 400
    if plan_name not in PLAN_PRICES:
        return jsonify({"success": False, "error": "Invalid plan. Choose seedling, grower, or farmer."}), 400

    plan_price    = PLAN_PRICES[plan_name]
    today         = date.today()
    next_delivery = today + timedelta(days=30)

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO plant_adoptions
                (user_id, first_name, last_name, email, phone,
                 plan_name, plan_price, plant_name, delivery_address,
                 start_date, next_delivery)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_id,
            first_name, last_name or None, email, phone or None,
            plan_name, plan_price,
            plant_name or None,
            delivery_address or None,
            today, next_delivery
        ))
        conn.commit()
        adoption_id = cur.lastrowid
        cur.close(); conn.close()

        print(f"✅ Plant adoption! ID: {adoption_id} | {first_name} | {plan_name} | ₹{plan_price}/month")

        return jsonify({
            "success":      True,
            "id":           adoption_id,
            "plan":         plan_name,
            "price":        plan_price,
            "nextDelivery": str(next_delivery),
            "message":      f"Welcome to the MITTI family, {first_name}! Your {plan_name.capitalize()} plan starts today. 🌱"
        })

    except Exception as e:
        print(f"❌ Adoption error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/adoptions', methods=['GET'])
def get_adoptions():
    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)

    if not auth_user:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        if auth_user['role'] in ('admin', 'staff'):
            cur.execute('''
                SELECT pa.*, u.email AS user_email FROM plant_adoptions pa
                LEFT JOIN users u ON pa.user_id = u.id
                ORDER BY pa.created_at DESC
            ''')
        else:
            cur.execute(
                "SELECT * FROM plant_adoptions WHERE user_id = %s ORDER BY created_at DESC",
                (auth_user['id'],)
            )

        rows = cur.fetchall()
        for row in rows:
            if row.get('start_date'):    row['start_date']    = str(row['start_date'])
            if row.get('next_delivery'): row['next_delivery'] = str(row['next_delivery'])
            if row.get('created_at'):    row['created_at']    = str(row['created_at'])
        cur.close(); conn.close()
        return jsonify({"success": True, "adoptions": rows, "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/adoptions/<int:adoption_id>/status', methods=['PATCH'])
def update_adoption_status(adoption_id):
    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)
    if not auth_user:
        return jsonify({"success": False, "error": "Unauthorized."}), 401

    data   = request.get_json()
    status = data.get('status', '').strip()
    if status not in ('active', 'paused', 'cancelled'):
        return jsonify({"success": False, "error": "Invalid status."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT user_id FROM plant_adoptions WHERE id = %s", (adoption_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Adoption not found."}), 404

        if auth_user['role'] not in ('admin', 'staff') and row['user_id'] != auth_user['id']:
            cur.close(); conn.close()
            return jsonify({"success": False, "error": "Access denied."}), 403

        cur.execute("UPDATE plant_adoptions SET status = %s WHERE id = %s", (status, adoption_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": f"Adoption #{adoption_id} is now {status}."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════════
#  CART ROUTES
# ════════════════════════════════════════════

@app.route('/api/cart/session', methods=['POST'])
def create_cart_session():
    token     = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    auth_user = get_user_from_token(token)
    user_id   = auth_user['id'] if auth_user else None

    if user_id:
        try:
            conn = get_connection()
            cur  = conn.cursor(dictionary=True)
            cur.execute("SELECT session_token FROM cart_sessions WHERE user_id = %s LIMIT 1", (user_id,))
            existing = cur.fetchone()
            cur.close(); conn.close()
            if existing:
                return jsonify({"success": True, "sessionToken": existing['session_token']})
        except:
            pass

    cart_token = generate_session_token()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("INSERT INTO cart_sessions (user_id, session_token) VALUES (%s, %s)", (user_id, cart_token))
        conn.commit()
        cur.close(); conn.close()
        print(f"✅ Cart session created: {cart_token} | user: {user_id}")
        return jsonify({"success": True, "sessionToken": cart_token})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    data          = request.get_json()
    session_token = data.get('sessionToken')
    item_name     = data.get('itemName',    '').strip()
    item_emoji    = data.get('itemEmoji',   '')
    item_price    = data.get('itemPrice',   0)
    item_category = data.get('itemCategory','')
    item_tags     = data.get('itemTags',    '')

    if not session_token or not item_name:
        return jsonify({"success": False, "error": "sessionToken and itemName required."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor()

        cur.execute(
            "SELECT id, quantity FROM cart_items WHERE session_token = %s AND item_name = %s",
            (session_token, item_name)
        )
        existing = cur.fetchone()

        if existing:
            cur.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE id = %s", (existing[0],))
            msg = "Quantity updated!"
        else:
            cur.execute('''
                INSERT INTO cart_items
                    (session_token, item_name, item_emoji, item_price, item_category, item_tags)
                VALUES (%s,%s,%s,%s,%s,%s)
            ''', (session_token, item_name, item_emoji, item_price, item_category, item_tags))
            msg = "Item added to cart!"

        conn.commit()
        cur.close(); conn.close()
        print(f"✅ Cart updated: {item_name} | session: {session_token[:8]}...")
        return jsonify({"success": True, "message": msg})

    except Exception as e:
        print(f"❌ Cart error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cart/<session_token>', methods=['GET'])
def get_cart(session_token):
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT ci.*, cs.reservation_id, cs.user_id
            FROM cart_items ci
            JOIN cart_sessions cs ON ci.session_token = cs.session_token
            WHERE ci.session_token = %s
            ORDER BY ci.added_at ASC
        ''', (session_token,))
        items = cur.fetchall()
        for item in items:
            if item.get('added_at'): item['added_at'] = str(item['added_at'])

        total = sum(float(i['item_price']) * i['quantity'] for i in items)
        cur.close(); conn.close()
        return jsonify({"success": True, "items": items, "total": round(total, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cart/update', methods=['PATCH'])
def update_cart_item():
    data          = request.get_json()
    session_token = data.get('sessionToken')
    item_id       = data.get('itemId')
    quantity      = data.get('quantity', 1)

    if quantity < 1:
        return jsonify({"success": False, "error": "Quantity must be at least 1."}), 400

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE cart_items SET quantity = %s WHERE id = %s AND session_token = %s",
            (quantity, item_id, session_token)
        )
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Quantity updated!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cart/remove', methods=['DELETE'])
def remove_cart_item():
    data          = request.get_json()
    session_token = data.get('sessionToken')
    item_id       = data.get('itemId')

    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "DELETE FROM cart_items WHERE id = %s AND session_token = %s",
            (item_id, session_token)
        )
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Item removed!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cart/clear/<session_token>', methods=['DELETE'])
def clear_cart(session_token):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE session_token = %s", (session_token,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"success": True, "message": "Cart cleared!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    print("\n🌱 MITTI Cafe Server starting...")
    print("   API running at: http://127.0.0.1:5000")
    print("   ML model status:", "✅ Loaded" if ml_model else "❌ Not found — run train_model.py")
    app.run(debug=True, port=5000)