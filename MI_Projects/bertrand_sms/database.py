import os
import sqlite3
import datetime
from werkzeug.security import generate_password_hash
from config import Config

_ACTIVE_ENGINE = None

def determine_active_engine():
    global _ACTIVE_ENGINE
    if _ACTIVE_ENGINE is not None:
        return _ACTIVE_ENGINE

    if Config.DB_ENGINE == 'sqlite':
        _ACTIVE_ENGINE = 'sqlite'
        return _ACTIVE_ENGINE

    if Config.DB_ENGINE == 'mysql':
        _ACTIVE_ENGINE = 'mysql'
        return _ACTIVE_ENGINE

    # Default 'auto': try MySQL first, fallback to SQLite
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT,
            connection_timeout=2
        )
        conn.close()
        _ACTIVE_ENGINE = 'mysql'
        print("🟢 Database Engine: MySQL (connected successfully)")
    except Exception as e:
        _ACTIVE_ENGINE = 'sqlite'
        print(f"🟡 Database Engine: SQLite fallback (MySQL unavailable: {e})")

    return _ACTIVE_ENGINE

class DictRow(dict):
    """Allows accessing dict items as attributes if needed."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_connection():
    engine = determine_active_engine()
    if engine == 'mysql':
        import mysql.connector
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            port=Config.DB_PORT
        )
        return conn, 'mysql'
    else:
        conn = sqlite3.connect(Config.SQLITE_DB_PATH)
        conn.row_factory = dict_factory
        # Enable foreign key constraints in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn, 'sqlite'

def prepare_sql(sql, engine):
    """
    Adjusts query syntax for SQLite vs MySQL.
    In MySQL placeholders are '%s'. In SQLite placeholders are '?'.
    """
    if engine == 'sqlite':
        # Replace MySQL placeholders %s with SQLite ?
        sql = sql.replace('%s', '?')
        # Replace MySQL specific date functions if present
        sql = sql.replace('NOW()', "datetime('now', 'localtime')")
        sql = sql.replace('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP', "CURRENT_TIMESTAMP")
    return sql

def execute_query(sql, params=(), fetch_all=False, fetch_one=False, commit=False):
    conn, engine = get_connection()
    sql_prepared = prepare_sql(sql, engine)
    
    try:
        if engine == 'mysql':
            cur = conn.cursor(dictionary=True)
            cur.execute(sql_prepared, params)
            
            result = None
            if fetch_all:
                result = cur.fetchall()
            elif fetch_one:
                result = cur.fetchone()
                
            last_id = cur.lastrowid
            if commit:
                conn.commit()
            cur.close()
            conn.close()
            
            if fetch_all or fetch_one:
                return serialize_results(result)
            return last_id
        else:
            cur = conn.cursor()
            cur.execute(sql_prepared, params)
            
            result = None
            if fetch_all:
                result = cur.fetchall()
            elif fetch_one:
                result = cur.fetchone()
                
            last_id = cur.lastrowid
            if commit:
                conn.commit()
            cur.close()
            conn.close()
            
            if fetch_all or fetch_one:
                return serialize_results(result)
            return last_id

    except Exception as e:
        conn.close()
        print(f"❌ Database Query Error ({engine}): {e}\nSQL: {sql_prepared}\nParams: {params}")
        raise e

def serialize_results(data):
    """Ensures datetimes and decimals are JSON-serializable."""
    if data is None:
        return None
    if isinstance(data, list):
        return [serialize_dict(row) for row in data]
    if isinstance(data, dict):
        return serialize_dict(data)
    return data

def serialize_dict(row):
    if not isinstance(row, dict):
        return row
    new_row = {}
    for k, v in row.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            new_row[k] = str(v)
        elif isinstance(v, (int, float, str, bool)) or v is None:
            new_row[k] = v
        else:
            new_row[k] = str(v)
    return new_row

def init_db():
    engine = determine_active_engine()
    
    if engine == 'mysql':
        # Ensure Database exists
        import mysql.connector
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.close()
        conn.close()

    conn, engine = get_connection()
    
    if engine == 'mysql':
        queries = [
            '''CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) NOT NULL UNIQUE,
                password VARCHAR(250) NOT NULL,
                role ENUM("admin","staff") DEFAULT "admin",
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                phone VARCHAR(20) NOT NULL UNIQUE,
                email VARCHAR(120),
                address TEXT,
                city VARCHAR(80),
                state VARCHAR(40),
                zip VARCHAR(20),
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS drivers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                phone VARCHAR(20) NOT NULL UNIQUE,
                email VARCHAR(120),
                vehicle VARCHAR(100),
                license VARCHAR(60),
                status ENUM("available","on_delivery","off_duty") DEFAULT "available",
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                unit VARCHAR(30) DEFAULT "lb",
                stock_qty DECIMAL(10,2) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(30) NOT NULL UNIQUE,
                customer_id INT NOT NULL,
                driver_id INT,
                status ENUM("pending","confirmed","preparing","out_for_delivery","delivered","cancelled") DEFAULT "pending",
                total_amount DECIMAL(10,2) DEFAULT 0,
                delivery_address TEXT,
                delivery_date DATE,
                delivery_time VARCHAR(30),
                notes TEXT,
                sms_sent TINYINT(1) DEFAULT 0,
                reminder_sent TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )''',
            '''CREATE TABLE IF NOT EXISTS sms_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT,
                recipient VARCHAR(20) NOT NULL,
                recipient_type VARCHAR(20) DEFAULT "customer",
                message TEXT NOT NULL,
                status VARCHAR(30) DEFAULT "sent",
                twilio_sid VARCHAR(60),
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS sms_templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS settings (
                key_name VARCHAR(100) PRIMARY KEY,
                val_value TEXT NOT NULL
            )'''
        ]
    else:
        # SQLite schema
        queries = [
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT "admin",
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                email TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                email TEXT,
                vehicle TEXT,
                license TEXT,
                status TEXT DEFAULT "available",
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                unit TEXT DEFAULT "lb",
                stock_qty REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                customer_id INTEGER NOT NULL,
                driver_id INTEGER,
                status TEXT DEFAULT "pending",
                total_amount REAL DEFAULT 0,
                delivery_address TEXT,
                delivery_date TEXT,
                delivery_time TEXT,
                notes TEXT,
                sms_sent INTEGER DEFAULT 0,
                reminder_sent INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )''',
            '''CREATE TABLE IF NOT EXISTS sms_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                recipient TEXT NOT NULL,
                recipient_type TEXT DEFAULT "customer",
                message TEXT NOT NULL,
                status TEXT DEFAULT "sent",
                twilio_sid TEXT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS sms_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS settings (
                key_name TEXT PRIMARY KEY,
                val_value TEXT NOT NULL
            )'''
        ]

    for q in queries:
        execute_query(q, commit=True)

    # Seed Default User
    user = execute_query("SELECT * FROM users WHERE username=%s", (Config.ADMIN_USERNAME,), fetch_one=True)
    if not user:
        pwd_hash = generate_password_hash(Config.ADMIN_PASSWORD)
        execute_query(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (Config.ADMIN_USERNAME, pwd_hash, "admin"),
            commit=True
        )
        print(f"✅ Default User Created: {Config.ADMIN_USERNAME} / {Config.ADMIN_PASSWORD}")

    # Seed Default Products if empty
    prods = execute_query("SELECT COUNT(*) as cnt FROM products", fetch_one=True)
    cnt = prods.get('cnt', 0) if prods else 0
    if cnt == 0:
        seed_products = [
            ('Live Crawfish',    'Fresh live Louisiana crawfish (by the sack)', 45.00, 'sack',  50),
            ('Boiled Crawfish',  'Hot & spicy boiled crawfish with corn & potatoes', 55.00, 'lb', 35),
            ('Gulf Shrimp',      'Fresh wild-caught Gulf shrimp, head-on', 12.00, 'lb', 80),
            ('Blue Crab',        'Live jumbo Louisiana blue crabs', 18.00, 'dozen', 40),
            ('Catfish Fillet',   'Fresh farm-raised catfish fillets', 8.50, 'lb', 60),
            ('Alligator Meat',   'Premium tender alligator tail meat', 14.00, 'lb', 25),
            ('Louisiana Oysters','Fresh Gulf oysters in shell', 15.00, 'dozen', 30),
            ('Crawfish Tails',   'Peeled crawfish tail meat, frozen', 22.00, 'lb', 45)
        ]
        for p in seed_products:
            execute_query(
                "INSERT INTO products (name, description, price, unit, stock_qty) VALUES (%s, %s, %s, %s, %s)",
                p, commit=True
            )
        print("✅ Default Products Seeded")

    # Seed Sample Customers if empty
    custs = execute_query("SELECT COUNT(*) as cnt FROM customers", fetch_one=True)
    if custs and custs.get('cnt', 0) == 0:
        seed_customers = [
            ('Jean LeBlanc', '+13375550192', 'jean@cajunboil.com', '402 Bayou Rd', 'Breaux Bridge', 'LA', '70517', 'VIP Customer'),
            ('Marie Thibodeaux', '+13375550811', 'marie@gulfseafood.com', '120 Main St', 'Lafayette', 'LA', '70501', 'Prefers extra spicy seasoning'),
            ('Boudreaux Seafood Shack', '+13375550944', 'orders@boudreaux.com', '88 River Rd', 'New Iberia', 'LA', '70560', 'Commercial wholesale buyer')
        ]
        for c in seed_customers:
            execute_query(
                "INSERT INTO customers (name, phone, email, address, city, state, zip, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                c, commit=True
            )
        print("✅ Default Customers Seeded")

    # Seed Sample Drivers if empty
    drivs = execute_query("SELECT COUNT(*) as cnt FROM drivers", fetch_one=True)
    if drivs and drivs.get('cnt', 0) == 0:
        seed_drivers = [
            ('Travis Landry', '+13375550341', 'travis@bertrands.com', 'Refrigerated Truck #1', 'LA-DL-98421', 'available'),
            ('Beau Fontenot', '+13375550732', 'beau@bertrands.com', 'Express Van #2', 'LA-DL-11049', 'available')
        ]
        for d in seed_drivers:
            execute_query(
                "INSERT INTO drivers (name, phone, email, vehicle, license, status) VALUES (%s,%s,%s,%s,%s,%s)",
                d, commit=True
            )
        print("✅ Default Drivers Seeded")

    # Seed Sample SMS Templates if empty
    tmpl = execute_query("SELECT COUNT(*) as cnt FROM sms_templates", fetch_one=True)
    if tmpl and tmpl.get('cnt', 0) == 0:
        seed_templates = [
            ('Weekend Crawfish Special', "🦞 Bertrand's Crawfish Special! Live crawfish sacks only $40 this weekend. Text ORDER to reserve yours!"),
            ('Delivery Reminder', "🚚 Hi {customer_name}, your Bertrand's seafood order #{order_number} will be delivered today between {delivery_time}."),
            ('Google Review Request', "⭐ Thank you for ordering from Bertrand's Crawfish! Please leave us a review: bit.ly/bertrand-review")
        ]
        for t in seed_templates:
            execute_query("INSERT INTO sms_templates (name, message) VALUES (%s, %s)", t, commit=True)
        print("✅ Default SMS Templates Seeded")
