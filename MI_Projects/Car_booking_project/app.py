from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ── MySQL Connection Settings ──
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "root123"
MYSQL_DB = "drivex_db"

def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )

# ── Create Database and Tables if not exists
def init_db():
    # 1. Connect without database to create the database itself
    temp_conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD
    )
    temp_cur = temp_conn.cursor()
    temp_cur.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
    temp_cur.close()
    temp_conn.close()

    # 2. Connect to the newly created database to create the tables
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create Bookings Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            booking_ref VARCHAR(50),
            car_type VARCHAR(50),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(100),
            phone VARCHAR(50),
            pickup_date VARCHAR(50),
            return_date VARCHAR(50),
            pickup_time VARCHAR(50),
            location VARCHAR(200),
            license VARCHAR(100),
            extra_driver VARCHAR(50),
            insurance VARCHAR(50),
            notes TEXT,
            created_at VARCHAR(50)
        )
    ''')

    # Create Feedback Table (Linked to Bookings using 'id')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INT AUTO_INCREMENT PRIMARY KEY,
            booking_id INT NOT NULL,
            rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()

# ── Serve HTML
@app.route('/')
def index():
    return render_template('index.html')

# ── Save booking
@app.route('/book', methods=['POST'])
def book():
    data = request.get_json()

    ref = "BKG-" + datetime.now().strftime("%f")[:6].upper()
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO bookings (
            booking_ref, car_type, first_name, last_name,
            email, phone, pickup_date, return_date,
            pickup_time, location, license,
            extra_driver, insurance, notes, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (
        ref,
        data.get('car_type'),
        data.get('first_name'),
        data.get('last_name'),
        data.get('email'),
        data.get('phone'),
        data.get('pickup_date'),
        data.get('return_date'),
        data.get('pickup_time'),
        data.get('location'),
        data.get('license'),
        data.get('extra_driver'),
        data.get('insurance'),
        data.get('notes'),
        created
    ))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "booking_ref": ref})

# ── Save Feedback
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    booking_ref = data.get('booking_ref')
    rating = data.get('rating')
    comments = data.get('comments')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # 1. Look up the booking using the booking_ref
        cur.execute("SELECT id FROM bookings WHERE booking_ref = %s", (booking_ref,))
        booking = cur.fetchone()

        # If booking doesn't exist, return an error
        if not booking:
            return jsonify({"success": False, "error": "Invalid Booking Reference. Please check your ID."}), 404

        # 2. Get the unique 'id' from the bookings table
        booking_id = booking['id']

        # 3. Insert the feedback using the 'booking_id'
        cur.execute('''
            INSERT INTO feedback (booking_id, rating, comments) 
            VALUES (%s, %s, %s)
        ''', (booking_id, rating, comments))
        
        conn.commit()
        return jsonify({"success": True, "message": "Feedback submitted successfully!"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    init_db()
    app.run(debug=True)