# ============================================================
#  Bertrand's Crawfish & Seafood Distribution
#  Automated SMS Order & Delivery Management System
# ============================================================

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import mysql.connector
import os
import uuid
import datetime

load_dotenv()  # loads variables from a local .env file, if present

app = Flask(__name__)
CORS(app)

app.secret_key = os.environ.get('SECRET_KEY', 'bertrand-secret-2024')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id       = id
        self.username = username
        self.role     = role

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        u = cur.fetchone()
        cur.close(); conn.close()
        if u:
            return User(u['id'], u['username'], u['role'])
    except:
        pass
    return None

# ════════════════════════════════════════════
#  DATABASE CONFIG
# ════════════════════════════════════════════
DB_HOST     = os.environ.get("DB_HOST",     "127.0.0.1")
DB_USER     = os.environ.get("DB_USER",     "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME     = os.environ.get("DB_NAME",     "bertrand_seafood")

# ════════════════════════════════════════════
#  TWILIO CONFIG
# ════════════════════════════════════════════
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID",  "")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN",   "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

# ════════════════════════════════════════════
#  DATABASE CONNECTION
# ════════════════════════════════════════════
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# ════════════════════════════════════════════
#  SMS HELPER
# ════════════════════════════════════════════
def send_sms(to, message):
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to
        )
        return {'success': True, 'sid': msg.sid, 'error': None}
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return {'success': False, 'sid': None, 'error': str(e)}

def log_sms(cur, order_id, recipient, rtype, message, result):
    cur.execute('''
        INSERT INTO sms_logs (order_id, recipient, recipient_type, message, status, twilio_sid)
        VALUES (%s,%s,%s,%s,%s,%s)
    ''', (order_id, recipient, rtype, message,
          'sent' if result['success'] else 'failed', result.get('sid')))

def gen_order_number():
    return 'BC-' + str(uuid.uuid4())[:8].upper()

def serialize(row):
    if not row:
        return row
    for k, v in row.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            row[k] = str(v)
        elif isinstance(v, float):
            row[k] = float(v)
    return row

# ════════════════════════════════════════════
#  DATABASE INITIALISATION
# ════════════════════════════════════════════
def init_db():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.close(); conn.close()

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            username   VARCHAR(80)  NOT NULL UNIQUE,
            password   VARCHAR(200) NOT NULL,
            role       ENUM("admin","staff") DEFAULT "admin",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute('''
            INSERT INTO users (username, password, role)
            VALUES (%s, %s, %s)
        ''', (os.environ.get('ADMIN_USERNAME','admin'),
              generate_password_hash(os.environ.get('ADMIN_PASSWORD','admin123')),
              'admin'))
        conn.commit()
        print("✅ Default user created: admin / admin123")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(120) NOT NULL,
            phone      VARCHAR(20)  NOT NULL UNIQUE,
            email      VARCHAR(120),
            address    TEXT,
            city       VARCHAR(80),
            state      VARCHAR(40),
            zip        VARCHAR(20),
            notes      TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(120) NOT NULL,
            phone      VARCHAR(20)  NOT NULL UNIQUE,
            email      VARCHAR(120),
            vehicle    VARCHAR(100),
            license    VARCHAR(60),
            status     ENUM("available","on_delivery","off_duty") DEFAULT "available",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(120)  NOT NULL,
            description TEXT,
            price       DECIMAL(10,2) NOT NULL,
            unit        VARCHAR(30)   DEFAULT "lb",
            stock_qty   DECIMAL(10,2) DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            order_number     VARCHAR(30)   NOT NULL UNIQUE,
            customer_id      INT           NOT NULL,
            driver_id        INT,
            status           ENUM("pending","confirmed","preparing","out_for_delivery","delivered","cancelled") DEFAULT "pending",
            total_amount     DECIMAL(10,2) DEFAULT 0,
            delivery_address TEXT,
            delivery_date    DATE,
            delivery_time    VARCHAR(30),
            notes            TEXT,
            sms_sent         TINYINT(1)    DEFAULT 0,
            reminder_sent    TINYINT(1)    DEFAULT 0,
            created_at       DATETIME      DEFAULT CURRENT_TIMESTAMP,
            updated_at       DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (driver_id)   REFERENCES drivers(id)   ON DELETE SET NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            order_id   INT           NOT NULL,
            product_id INT           NOT NULL,
            quantity   DECIMAL(10,2) NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            subtotal   DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS sms_logs (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            order_id       INT,
            recipient      VARCHAR(20) NOT NULL,
            recipient_type ENUM("customer","driver") NOT NULL,
            message        TEXT        NOT NULL,
            status         VARCHAR(30) DEFAULT "sent",
            twilio_sid     VARCHAR(60),
            sent_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
        )
    ''')

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.executemany('''
            INSERT INTO products (name, description, price, unit, stock_qty)
            VALUES (%s,%s,%s,%s,%s)
        ''', [
            ('Live Crawfish',   'Fresh live crawfish, sold by the sack',       45.00, 'sack',  50),
            ('Boiled Crawfish', 'Ready-to-eat boiled crawfish with seasoning', 55.00, 'lb',    30),
            ('Gulf Shrimp',     'Fresh Gulf shrimp, head-on',                  12.00, 'lb',    80),
            ('Blue Crab',       'Live blue crabs, sold by the dozen',          18.00, 'dozen', 40),
            ('Catfish Fillet',  'Farm-raised catfish fillets',                  8.50, 'lb',    60),
            ('Alligator Meat',  'Farm-raised Louisiana alligator',             14.00, 'lb',    20),
            ('Oysters',         'Gulf oysters, fresh in shell',                15.00, 'dozen', 35),
            ('Crawfish Tails',  'Peeled crawfish tail meat, frozen',           22.00, 'lb',    45),
        ])
        conn.commit()
        print("✅ Seed products inserted!")

    cur.execute("SELECT COUNT(*) FROM drivers")
    if cur.fetchone()[0] == 0:
        cur.executemany('''
            INSERT INTO drivers (name, phone, vehicle, status)
            VALUES (%s,%s,%s,%s)
        ''', [
            ('Marcus Broussard', '+15551110001', 'White Ford F-150',     'available'),
            ('Sandra LeBlanc',   '+15551110002', 'Blue Chevy Silverado', 'available'),
        ])
        conn.commit()
        print("✅ Seed drivers inserted!")

    cur.close(); conn.close()
    print("✅ MySQL Running!")
    print("✅ Connected!")
    print(f"✅ Database '{DB_NAME}' Ready!")
    print("✅ All Tables Ready (customers, drivers, products, orders, order_items, sms_logs)")


# ════════════════════════════════════════════
#  LOGIN / LOGOUT
# ════════════════════════════════════════════
@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        u = cur.fetchone()
        cur.close(); conn.close()
        if u and check_password_hash(u['password'], password):
            user = User(u['id'], u['username'], u['role'])
            login_user(user)
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password')
    except Exception as e:
        return render_template('login.html', error=str(e))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))


# ════════════════════════════════════════════
#  FRONTEND PAGES
# ════════════════════════════════════════════
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/orders')
@login_required
def orders_page():
    return render_template('orders.html')

@app.route('/drivers')
@login_required
def drivers_page():
    return render_template('drivers.html')

@app.route('/customers')
@login_required
def customers_page():
    return render_template('customers.html')

@app.route('/products')
@login_required
def products_page():
    return render_template('products.html')

@app.route('/reports')
@login_required
def reports_page():
    return render_template('reports.html')

@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')


# ════════════════════════════════════════════
#  HEALTH CHECK
# ════════════════════════════════════════════
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "app":     "Bertrand's Crawfish SMS Management",
        "version": "1.0",
        "status":  "running",
        "time":    datetime.datetime.now().isoformat()
    })


# ════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════
@app.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT COUNT(*) AS total FROM orders")
        total_orders = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='pending'")
        pending = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='out_for_delivery'")
        in_transit = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='delivered'")
        delivered = cur.fetchone()['cnt']

        cur.execute("SELECT COALESCE(SUM(total_amount),0) AS rev FROM orders WHERE status='delivered'")
        revenue = float(cur.fetchone()['rev'])

        cur.execute("SELECT COUNT(*) AS cnt FROM customers")
        customers = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) AS cnt FROM drivers WHERE status='available'")
        available_drivers = cur.fetchone()['cnt']

        cur.execute('''
            SELECT o.order_number, o.status, o.total_amount, o.created_at,
                   c.name AS customer_name
            FROM orders o JOIN customers c ON o.customer_id = c.id
            ORDER BY o.created_at DESC LIMIT 5
        ''')
        recent = cur.fetchall()
        for r in recent:
            for k, v in r.items():
                if isinstance(v, (datetime.datetime, datetime.date)): r[k] = str(v)
            r['total_amount'] = float(r['total_amount'])

        cur.execute("SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status")
        by_status = cur.fetchall()

        cur.close(); conn.close()
        return jsonify({
            'total_orders':      total_orders,
            'pending':           pending,
            'in_transit':        in_transit,
            'delivered':         delivered,
            'revenue':           revenue,
            'customers':         customers,
            'available_drivers': available_drivers,
            'recent_orders':     recent,
            'by_status':         by_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  REPORTS API
# ════════════════════════════════════════════
@app.route('/api/reports/summary', methods=['GET'])
@login_required
def reports_summary():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        # Monthly revenue (last 6 months)
        cur.execute('''
            SELECT DATE_FORMAT(created_at, '%Y-%m') AS month,
                   COUNT(*) AS total_orders,
                   COALESCE(SUM(total_amount), 0) AS revenue
            FROM orders
            WHERE status = 'delivered'
            AND created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month ASC
        ''')
        monthly = cur.fetchall()
        for r in monthly: r['revenue'] = float(r['revenue'])

        # Best selling products
        cur.execute('''
            SELECT p.name, SUM(oi.quantity) AS total_qty,
                   SUM(oi.subtotal) AS total_revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'delivered'
            GROUP BY p.id, p.name
            ORDER BY total_revenue DESC
            LIMIT 5
        ''')
        top_products = cur.fetchall()
        for r in top_products:
            r['total_qty']     = float(r['total_qty'])
            r['total_revenue'] = float(r['total_revenue'])

        # Driver delivery count
        cur.execute('''
            SELECT d.name, COUNT(o.id) AS deliveries,
                   COALESCE(SUM(o.total_amount), 0) AS total_value
            FROM drivers d
            LEFT JOIN orders o ON o.driver_id = d.id AND o.status = 'delivered'
            GROUP BY d.id, d.name
            ORDER BY deliveries DESC
        ''')
        driver_stats = cur.fetchall()
        for r in driver_stats: r['total_value'] = float(r['total_value'])

        # Overall stats
        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='delivered'")
        total_delivered = cur.fetchone()['cnt']

        cur.execute("SELECT COALESCE(SUM(total_amount),0) AS rev FROM orders WHERE status='delivered'")
        total_revenue = float(cur.fetchone()['rev'])

        cur.execute("SELECT COUNT(*) AS cnt FROM customers")
        total_customers = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='cancelled'")
        total_cancelled = cur.fetchone()['cnt']

        cur.close(); conn.close()
        return jsonify({
            'monthly':          monthly,
            'top_products':     top_products,
            'driver_stats':     driver_stats,
            'total_delivered':  total_delivered,
            'total_revenue':    total_revenue,
            'total_customers':  total_customers,
            'total_cancelled':  total_cancelled,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  SEARCH API
# ════════════════════════════════════════════
@app.route('/api/search', methods=['GET'])
@login_required
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'orders': [], 'customers': []})
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        like = f'%{q}%'

        cur.execute('''
            SELECT o.id, o.order_number, o.status, o.total_amount, o.delivery_date,
                   c.name AS customer_name
            FROM orders o JOIN customers c ON o.customer_id = c.id
            WHERE o.order_number LIKE %s OR c.name LIKE %s OR o.delivery_address LIKE %s
            ORDER BY o.created_at DESC LIMIT 10
        ''', (like, like, like))
        orders = cur.fetchall()
        for r in orders:
            r['total_amount'] = float(r['total_amount'])
            if isinstance(r.get('delivery_date'), datetime.date):
                r['delivery_date'] = str(r['delivery_date'])

        cur.execute('''
            SELECT id, name, phone, email, city
            FROM customers
            WHERE name LIKE %s OR phone LIKE %s OR email LIKE %s
            ORDER BY name LIMIT 10
        ''', (like, like, like))
        customers = cur.fetchall()

        cur.close(); conn.close()
        return jsonify({'orders': orders, 'customers': customers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  CUSTOMER ORDER HISTORY
# ════════════════════════════════════════════
@app.route('/api/customers/<int:cid>/history', methods=['GET'])
@login_required
def customer_history(cid):
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM customers WHERE id=%s", (cid,))
        customer = cur.fetchone()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        for k, v in customer.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                customer[k] = str(v)

        cur.execute('''
            SELECT o.*, d.name AS driver_name
            FROM orders o
            LEFT JOIN drivers d ON o.driver_id = d.id
            WHERE o.customer_id = %s
            ORDER BY o.created_at DESC
        ''', (cid,))
        orders = cur.fetchall()
        for r in orders:
            r['total_amount'] = float(r['total_amount'])
            for k, v in r.items():
                if isinstance(v, (datetime.datetime, datetime.date)):
                    r[k] = str(v)

        cur.execute('''
            SELECT COUNT(*) AS total_orders,
                   COALESCE(SUM(total_amount), 0) AS total_spent,
                   COUNT(CASE WHEN status='delivered' THEN 1 END) AS delivered,
                   COUNT(CASE WHEN status='cancelled' THEN 1 END) AS cancelled
            FROM orders WHERE customer_id = %s
        ''', (cid,))
        stats = cur.fetchone()
        stats['total_spent'] = float(stats['total_spent'])

        cur.close(); conn.close()
        return jsonify({'customer': customer, 'orders': orders, 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  CUSTOMERS
# ════════════════════════════════════════════
@app.route('/api/customers/', methods=['GET'])
def get_customers():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM customers ORDER BY name")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([serialize(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/customers/', methods=['POST'])
def create_customer():
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO customers (name, phone, email, address, city, state, zip, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (d['name'], d['phone'], d.get('email',''), d.get('address',''),
              d.get('city',''), d.get('state',''), d.get('zip',''), d.get('notes','')))
        conn.commit()
        new_id = cur.lastrowid
        cur.close(); conn.close()
        print(f"✅ Customer created: {d['name']}")
        return jsonify({'success': True, 'id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/customers/<int:cid>', methods=['PUT'])
def update_customer(cid):
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            UPDATE customers SET name=%s, phone=%s, email=%s, address=%s,
                   city=%s, state=%s, zip=%s, notes=%s WHERE id=%s
        ''', (d['name'], d['phone'], d.get('email',''), d.get('address',''),
              d.get('city',''), d.get('state',''), d.get('zip',''), d.get('notes',''), cid))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/customers/<int:cid>', methods=['DELETE'])
def delete_customer(cid):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id=%s", (cid,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  PRODUCTS
# ════════════════════════════════════════════
@app.route('/api/products/', methods=['GET'])
def get_products():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM products ORDER BY name")
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows: r['price'] = float(r['price']); r['stock_qty'] = float(r['stock_qty'])
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/', methods=['POST'])
def create_product():
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO products (name, description, price, unit, stock_qty)
            VALUES (%s,%s,%s,%s,%s)
        ''', (d['name'], d.get('description',''), d['price'], d.get('unit','lb'), d.get('stock_qty', 0)))
        conn.commit()
        new_id = cur.lastrowid
        cur.close(); conn.close()
        print(f"✅ Product created: {d['name']}")
        return jsonify({'success': True, 'id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:pid>', methods=['PUT'])
def update_product(pid):
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            UPDATE products SET name=%s, description=%s, price=%s, unit=%s, stock_qty=%s
            WHERE id=%s
        ''', (d['name'], d.get('description',''), d['price'], d.get('unit','lb'), d.get('stock_qty', 0), pid))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:pid>', methods=['DELETE'])
def delete_product(pid):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=%s", (pid,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  DRIVERS
# ════════════════════════════════════════════
@app.route('/api/drivers/', methods=['GET'])
def get_drivers():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM drivers ORDER BY name")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([serialize(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/drivers/', methods=['POST'])
def create_driver():
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO drivers (name, phone, email, vehicle, license, status)
            VALUES (%s,%s,%s,%s,%s,%s)
        ''', (d['name'], d['phone'], d.get('email',''), d.get('vehicle',''),
              d.get('license',''), d.get('status','available')))
        conn.commit()
        new_id = cur.lastrowid
        cur.close(); conn.close()
        print(f"✅ Driver created: {d['name']}")
        return jsonify({'success': True, 'id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/drivers/<int:did>', methods=['PUT'])
def update_driver(did):
    d = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            UPDATE drivers SET name=%s, phone=%s, email=%s, vehicle=%s, license=%s, status=%s
            WHERE id=%s
        ''', (d['name'], d['phone'], d.get('email',''), d.get('vehicle',''),
              d.get('license',''), d.get('status','available'), did))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/drivers/<int:did>', methods=['DELETE'])
def delete_driver(did):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM drivers WHERE id=%s", (did,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  ORDERS
# ════════════════════════════════════════════
@app.route('/api/orders/', methods=['GET'])
def get_orders():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone,
                   d.name AS driver_name, d.phone AS driver_phone
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN drivers d ON o.driver_id = d.id
            ORDER BY o.created_at DESC
        ''')
        orders = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([serialize(r) for r in orders])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/products_list', methods=['GET'])
def products_list():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, price, unit FROM products ORDER BY name")
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows: r['price'] = float(r['price'])
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):


    
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone,
                   d.name AS driver_name, d.phone AS driver_phone
            FROM orders o JOIN customers c ON o.customer_id = c.id
            LEFT JOIN drivers d ON o.driver_id = d.id
            WHERE o.id = %s
        ''', (order_id,))
        order = cur.fetchone()
        if not order:
            cur.close(); conn.close()
            return jsonify({'error': 'Order not found'}), 404
        cur.execute('''
            SELECT oi.*, p.name AS product_name FROM order_items oi
            JOIN products p ON oi.product_id = p.id WHERE oi.order_id = %s
        ''', (order_id,))
        order['items'] = cur.fetchall()
        cur.close(); conn.close()
        return jsonify(serialize(order))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/orders/', methods=['POST'])
def create_order():
    data = request.get_json()
    for f in ['customer_id', 'items', 'delivery_address', 'delivery_date']:
        if f not in data:
            return jsonify({'error': f'Missing field: {f}'}), 400
    try:
        order_number = gen_order_number()
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        # 1) Validate items + check stock
        total = 0
        stock_ok = True
        for item in data['items']:
            cur.execute("SELECT price, stock_qty FROM products WHERE id = %s", (item['product_id'],))
            p = cur.fetchone()
            if not p:
                cur.close(); conn.close()
                return jsonify({'error': f"Product {item['product_id']} not found"}), 400
            if float(p['stock_qty']) < float(item['quantity']):
                stock_ok = False
            total += float(p['price']) * float(item['quantity'])

        # 2) Auto-assign an available driver if none was chosen
        driver_id = data.get('driver_id') or None
        if not driver_id:
            cur.execute("SELECT id FROM drivers WHERE status='available' ORDER BY id LIMIT 1")
            d = cur.fetchone()
            if d:
                driver_id = d['id']

        # 3) Decide status based on stock
        status = 'confirmed' if stock_ok else 'pending'

        cur.execute('''
            INSERT INTO orders (order_number, customer_id, driver_id, delivery_address,
                                delivery_date, delivery_time, notes, total_amount, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (order_number, data['customer_id'], driver_id,
              data['delivery_address'], data['delivery_date'],
              data.get('delivery_time', 'TBD'), data.get('notes', ''), total, status))
        order_id = cur.lastrowid

        for item in data['items']:
            cur.execute("SELECT price FROM products WHERE id = %s", (item['product_id'],))
            p   = cur.fetchone()
            up  = float(p['price'])
            sub = up * float(item['quantity'])
            cur.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
                VALUES (%s,%s,%s,%s,%s)
            ''', (order_id, item['product_id'], item['quantity'], up, sub))

        # 4) Deduct stock + mark driver busy only if confirmed
        if stock_ok:
            for item in data['items']:
                cur.execute('''
                    UPDATE products SET stock_qty = stock_qty - %s
                    WHERE id = %s AND stock_qty >= %s
                ''', (item['quantity'], item['product_id'], item['quantity']))

            if driver_id:
                cur.execute("UPDATE drivers SET status='on_delivery' WHERE id=%s", (driver_id,))

        conn.commit()

        # 5) Fetch customer + driver contact info for SMS
        cur.execute("SELECT name, phone FROM customers WHERE id=%s", (data['customer_id'],))
        cust = cur.fetchone()

        driver = None
        if driver_id:
            cur.execute("SELECT name, phone FROM drivers WHERE id=%s", (driver_id,))
            driver = cur.fetchone()

        sms_results = []

        if stock_ok:
            msg = (f"Hi {cust['name']}! ✅ Your Bertrand's order #{order_number} is CONFIRMED. "
                   f"Total: ${total:.2f}. Delivery: {data['delivery_date']}. We'll text when on the way! 🦞")
            result = send_sms(cust['phone'], msg)
            log_sms(cur, order_id, cust['phone'], 'customer', msg, result)
            sms_results.append({'to': 'customer', **result})

            if driver:
                dmsg = (f"🚚 NEW DELIVERY — Bertrand's\nOrder #{order_number}\n"
                        f"Customer: {cust['name']}\nAddress: {data['delivery_address']}\n"
                        f"Time: {data.get('delivery_time','TBD')}\nReply ACCEPT to confirm.")
                dresult = send_sms(driver['phone'], dmsg)
                log_sms(cur, order_id, driver['phone'], 'driver', dmsg, dresult)
                sms_results.append({'to': 'driver', **dresult})
        else:
            msg = (f"Hi {cust['name']}, we received your Bertrand's order #{order_number}, "
                   f"but some items are currently OUT OF STOCK. We'll contact you shortly. 🦞")
            result = send_sms(cust['phone'], msg)
            log_sms(cur, order_id, cust['phone'], 'customer', msg, result)
            sms_results.append({'to': 'customer', **result})

        conn.commit()
        cur.close(); conn.close()
        print(f"✅ Order created: {order_number} | Total: ${total:.2f} | Status: {status} | Driver: {driver_id}")
        return jsonify({
            'success': True, 'order_id': order_id, 'order_number': order_number,
            'total': total, 'status': status, 'driver_id': driver_id,
            'sms_results': sms_results
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    data   = request.get_json()
    status = data.get('status')
    valid  = ['pending','confirmed','preparing','out_for_delivery','delivered','cancelled']
    if status not in valid:
        return jsonify({'error': 'Invalid status'}), 400
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))

        cur.execute('''
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone,
                   d.name AS driver_name, d.phone AS driver_phone
            FROM orders o JOIN customers c ON o.customer_id = c.id
            LEFT JOIN drivers d ON o.driver_id = d.id WHERE o.id = %s
        ''', (order_id,))
        order = cur.fetchone()

        sms_results = []

        def notify(phone, rtype, msg):
            result = send_sms(phone, msg)
            log_sms(cur, order_id, phone, rtype, msg, result)
            sms_results.append({'to': rtype, **result})

        num   = order['order_number']
        cust  = order['customer_name']
        amt   = float(order['total_amount'])
        ddate = str(order['delivery_date'])

        if status == 'confirmed':
            notify(order['customer_phone'], 'customer',
                   f"Hi {cust}! ✅ Your Bertrand's order #{num} is CONFIRMED. "
                   f"Total: ${amt:.2f}. Delivery: {ddate}. We'll text when on the way! 🦞")
            if order.get('driver_id') and order.get('driver_phone'):
                notify(order['driver_phone'], 'driver',
                       f"🚚 NEW DELIVERY — Bertrand's\nOrder #{num}\n"
                       f"Customer: {cust}\nAddress: {order['delivery_address']}\n"
                       f"Time: {order.get('delivery_time','TBD')}\nReply ACCEPT to confirm.")

        elif status == 'out_for_delivery':
            notify(order['customer_phone'], 'customer',
                   f"Hi {cust}! 🚚 Your Bertrand's order #{num} is OUT FOR DELIVERY! "
                   f"Driver: {order.get('driver_name','')} ({order.get('driver_phone','')}). 🦞")

        elif status == 'delivered':
            notify(order['customer_phone'], 'customer',
                   f"Hi {cust}! 📦 Your Bertrand's order #{num} has been DELIVERED. "
                   f"Enjoy your seafood! Reply REVIEW for feedback. Thank you! 🦞❤️")

            if order.get('driver_id'):
                cur.execute("UPDATE drivers SET status='available' WHERE id=%s", (order['driver_id'],))

        elif status == 'cancelled':
            notify(order['customer_phone'], 'customer',
                   f"Hi {cust}, your Bertrand's order #{num} has been CANCELLED. "
                   f"Questions? Call (337) 555-0100. We hope to serve you again! 🦞")

        conn.commit()
        cur.close(); conn.close()
        print(f"✅ Order #{num} → {status} | SMS: {len(sms_results)}")
        return jsonify({'success': True, 'sms_results': sms_results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:order_id>/assign-driver', methods=['PATCH'])
def assign_driver(order_id):
    data = request.get_json()
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("UPDATE orders SET driver_id=%s WHERE id=%s",
                    (data.get('driver_id'), order_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  INVOICE
# ════════════════════════════════════════════
@app.route('/api/orders/<int:order_id>/invoice', methods=['GET'])
def generate_invoice(order_id):
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone,
                   c.email AS customer_email, c.address AS customer_address,
                   c.city AS customer_city, c.state AS customer_state,
                   d.name AS driver_name, d.phone AS driver_phone
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN drivers d ON o.driver_id = d.id
            WHERE o.id = %s
        ''', (order_id,))
        order = cur.fetchone()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        cur.execute('''
            SELECT oi.quantity, oi.unit_price, oi.subtotal, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        ''', (order_id,))
        items = cur.fetchall()
        cur.close(); conn.close()

        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from flask import send_file
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=40, leftMargin=40,
                                topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        story  = []

        story.append(Paragraph("BERTRAND'S CRAWFISH & SEAFOOD",
            ParagraphStyle('h', fontSize=26, textColor=colors.HexColor('#E85D26'),
                           fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)))
        story.append(Paragraph("Fresh Gulf Seafood Distribution",
            ParagraphStyle('s', fontSize=11, textColor=colors.HexColor('#888888'),
                           fontName='Helvetica', alignment=TA_CENTER, spaceAfter=2)))
        story.append(Paragraph("(337) 555-0100",
            ParagraphStyle('s2', fontSize=10, textColor=colors.HexColor('#888888'),
                           fontName='Helvetica', alignment=TA_CENTER, spaceAfter=2)))
        story.append(Spacer(1, 16))
        story.append(Paragraph(f"INVOICE — {order['order_number']}",
            ParagraphStyle('inv', fontSize=18, textColor=colors.HexColor('#222222'),
                           fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)))
        story.append(Spacer(1, 14))

        info_data = [
            ['Customer:',  order['customer_name'],         'Invoice Date:', str(datetime.date.today())],
            ['Phone:',     order['customer_phone'],        'Delivery Date:', str(order['delivery_date'] or '-')],
            ['Email:',     order['customer_email'] or '-', 'Status:', order['status'].replace('_',' ').title()],
            ['Address:',   f"{order['customer_address'] or ''}, {order['customer_city'] or ''}",
             'Driver:', order['driver_name'] or '-'],
        ]
        info_table = Table(info_data, colWidths=[90, 180, 90, 150])
        info_table.setStyle(TableStyle([
            ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME',      (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME',      (2,0), (2,-1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('TEXTCOLOR',     (0,0), (0,-1), colors.HexColor('#E85D26')),
            ('TEXTCOLOR',     (2,0), (2,-1), colors.HexColor('#E85D26')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))

        item_data = [['#', 'Product', 'Qty', 'Unit', 'Unit Price', 'Subtotal']]
        for i, item in enumerate(items, 1):
            item_data.append([
                str(i), item['product_name'],
                f"{float(item['quantity']):.2f}", item['unit'],
                f"${float(item['unit_price']):.2f}", f"${float(item['subtotal']):.2f}",
            ])
        item_table = Table(item_data, colWidths=[30, 200, 60, 60, 80, 80])
        item_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#E85D26')),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('ALIGN',         (2,0), (-1,-1), 'CENTER'),
            ('ALIGN',         (4,0), (-1,-1), 'RIGHT'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.HexColor('#FFF8F5'), colors.white]),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
        ]))
        story.append(item_table)
        story.append(Spacer(1, 10))

        total_table = Table(
            [['', '', '', '', 'TOTAL:', f"${float(order['total_amount']):.2f}"]],
            colWidths=[30, 200, 60, 60, 80, 80])
        total_table.setStyle(TableStyle([
            ('FONTNAME',   (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 13),
            ('TEXTCOLOR',  (4,0), (-1,-1), colors.HexColor('#E85D26')),
            ('ALIGN',      (4,0), (-1,-1), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(total_table)
        story.append(Spacer(1, 30))
        story.append(Paragraph("Thank you for your business!",
            ParagraphStyle('f', fontSize=9, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)))
        story.append(Paragraph("Bertrand's Crawfish & Seafood — Fresh Gulf Seafood Since 1985",
            ParagraphStyle('f2', fontSize=9, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)))

        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, mimetype='application/pdf',
                         download_name=f"invoice_{order['order_number']}.pdf",
                         as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  LOW STOCK ALERT
# ════════════════════════════════════════════
@app.route('/api/products/low-stock', methods=['GET'])
@login_required
def low_stock():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT id, name, stock_qty, unit
            FROM products
            WHERE stock_qty < 10
            ORDER BY stock_qty ASC
        ''')
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows: r['stock_qty'] = float(r['stock_qty'])
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
#  USER SETTINGS
# ════════════════════════════════════════════
@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    d = request.get_json()
    current = d.get('current_password')
    new     = d.get('new_password')
    confirm = d.get('confirm_password')
    if new != confirm:
        return jsonify({'error': 'New passwords do not match'}), 400
    if len(new) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE id=%s", (current_user.id,))
        u = cur.fetchone()
        if not check_password_hash(u['password'], current):
            cur.close(); conn.close()
            return jsonify({'error': 'Current password is incorrect'}), 400
        cur.execute("UPDATE users SET password=%s WHERE id=%s",
                    (generate_password_hash(new), current_user.id))
        conn.commit()
        cur.close(); conn.close()
        print(f"✅ Password changed for user: {current_user.username}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_me():
    return jsonify({'username': current_user.username, 'role': current_user.role})


# ════════════════════════════════════════════
#  SMS
# ════════════════════════════════════════════
@app.route('/api/sms/send', methods=['POST'])
def send_manual_sms():
    d      = request.get_json()
    result = send_sms(d['to'], d['message'])
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO sms_logs (order_id, recipient, recipient_type, message, status, twilio_sid)
            VALUES (%s,%s,%s,%s,%s,%s)
        ''', (d.get('order_id'), d['to'], d.get('type','customer'), d['message'],
              'sent' if result['success'] else 'failed', result.get('sid')))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ SMS log error: {e}")
    return jsonify(result)

@app.route('/api/sms/logs', methods=['GET'])
def sms_logs():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM sms_logs ORDER BY sent_at DESC LIMIT 100")
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows:
            for k, v in r.items():
                if isinstance(v, (datetime.datetime, datetime.date)): r[k] = str(v)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sms/webhook', methods=['POST'])
def sms_webhook():
    from_number  = request.form.get('From', '')
    body         = request.form.get('Body', '').strip().upper()
    response_msg = "Thanks for contacting Bertrand's Crawfish!"
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        if 'STATUS' in body or 'ORDER' in body:
            cur.execute('''
                SELECT o.order_number, o.status, o.delivery_date
                FROM orders o JOIN customers c ON o.customer_id = c.id
                WHERE c.phone = %s ORDER BY o.created_at DESC LIMIT 1
            ''', (from_number,))
            order = cur.fetchone()
            if order:
                response_msg = (f"Bertrand's Order #{order['order_number']}\n"
                                f"Status: {order['status'].replace('_',' ').title()}\n"
                                f"Delivery: {order['delivery_date']}")
            else:
                response_msg = "No recent orders found. Call (337) 555-0100!"
        elif 'ACCEPT' in body:
            cur.execute('''
                SELECT o.id, o.order_number FROM orders o
                JOIN drivers d ON o.driver_id = d.id
                WHERE d.phone = %s AND o.status = "confirmed"
                ORDER BY o.created_at DESC LIMIT 1
            ''', (from_number,))
            order = cur.fetchone()
            if order:
                cur.execute("UPDATE orders SET status='preparing' WHERE id=%s", (order['id'],))
                conn.commit()
                response_msg = f"Order #{order['order_number']} accepted!"
        elif 'REVIEW' in body:
            response_msg = "Thank you! Leave a review: bit.ly/bertrand-review"
        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ Webhook error: {e}")
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Message>{response_msg}</Message></Response>'), 200, {'Content-Type': 'text/xml'}


# ════════════════════════════════════════════
#  AUTOMATIC REMINDER SCHEDULER
# ════════════════════════════════════════════
def send_delivery_reminders():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        cur.execute("""
            SELECT o.id, o.order_number, o.total_amount, o.delivery_date,
                   c.name as customer_name, c.phone as customer_phone
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE o.delivery_date = %s
            AND o.status IN ('confirmed','preparing')
            AND o.reminder_sent = 0
        """, (tomorrow,))
        orders = cur.fetchall()
        for order in orders:
            msg = (f"Hi {order['customer_name']}! Reminder: Your Bertrand's order "
                   f"#{order['order_number']} is scheduled for delivery TOMORROW "
                   f"({order['delivery_date']}). Total: ${float(order['total_amount']):.2f}. "
                   f"Questions? Call (337) 555-0100")
            result = send_sms(order['customer_phone'], msg)
            if result['success']:
                cur.execute("UPDATE orders SET reminder_sent=1 WHERE id=%s", (order['id'],))
                print(f"✅ Reminder sent for order #{order['order_number']}")
            else:
                print(f"❌ Reminder failed for #{order['order_number']}: {result['error']}")
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ Scheduler error: {e}")


def check_low_stock():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT name, stock_qty, unit FROM products WHERE stock_qty < 10")
        rows = cur.fetchall()
        cur.close(); conn.close()
        if rows:
            print("\n⚠️  LOW STOCK ALERT:")
            for r in rows:
                print(f"   ❌ {r['name']}: {float(r['stock_qty'])} {r['unit']} remaining")
        else:
            print("✅ All products have sufficient stock")
    except Exception as e:
        print(f"❌ Low stock check error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_low_stock, 'cron', hour=9, minute=0)
scheduler.start()
print("⏰ Reminder scheduler started — runs daily at 10:00 AM")


# ════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    print("\n🦞 Bertrand's Crawfish SMS Server starting...")
    print("   API running at: http://127.0.0.1:5000")
    print("   Open browser:   http://localhost:5000")
    app.run(debug=True, port=5000)