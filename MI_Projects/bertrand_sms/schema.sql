-- ============================================================
--  Bertrand's Crawfish & Seafood Distribution — DB Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS bertrand_seafood;
USE bertrand_seafood;

-- ── Customers ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(120)  NOT NULL,
    phone       VARCHAR(20)   NOT NULL UNIQUE,
    email       VARCHAR(120),
    address     TEXT,
    city        VARCHAR(80),
    state       VARCHAR(40),
    zip         VARCHAR(20),
    notes       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Drivers ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drivers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(120)  NOT NULL,
    phone       VARCHAR(20)   NOT NULL UNIQUE,
    email       VARCHAR(120),
    vehicle     VARCHAR(100),
    license     VARCHAR(60),
    status      ENUM('available','on_delivery','off_duty') DEFAULT 'available',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Products ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(120)  NOT NULL,
    description TEXT,
    price       DECIMAL(10,2) NOT NULL,
    unit        VARCHAR(30)   DEFAULT 'lb',
    stock_qty   DECIMAL(10,2) DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Orders ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_number    VARCHAR(30) NOT NULL UNIQUE,
    customer_id     INT NOT NULL,
    driver_id       INT,
    status          ENUM(
                        'pending',
                        'confirmed',
                        'preparing',
                        'out_for_delivery',
                        'delivered',
                        'cancelled'
                    ) DEFAULT 'pending',
    total_amount    DECIMAL(10,2) DEFAULT 0,
    delivery_address TEXT,
    delivery_date   DATE,
    delivery_time   VARCHAR(30),
    notes           TEXT,
    sms_sent        TINYINT(1) DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (driver_id)   REFERENCES drivers(id)   ON DELETE SET NULL
);

-- ── Order Items ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    DECIMAL(10,2) NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    subtotal    DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- ── SMS Logs ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sms_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT,
    recipient   VARCHAR(20)  NOT NULL,
    recipient_type ENUM('customer','driver') NOT NULL,
    message     TEXT         NOT NULL,
    status      VARCHAR(30)  DEFAULT 'sent',
    twilio_sid  VARCHAR(60),
    sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
);

-- ── Seed Products ────────────────────────────────────────────
INSERT IGNORE INTO products (name, description, price, unit, stock_qty) VALUES
('Live Crawfish',    'Fresh live crawfish, sold by the sack',         45.00, 'sack',  50),
('Boiled Crawfish',  'Ready-to-eat boiled crawfish with seasoning',   55.00, 'lb',    30),
('Gulf Shrimp',      'Fresh Gulf shrimp, head-on',                    12.00, 'lb',    80),
('Blue Crab',        'Live blue crabs, sold by the dozen',            18.00, 'dozen', 40),
('Catfish Fillet',   'Farm-raised catfish fillets',                    8.50, 'lb',    60),
('Alligator Meat',   'Farm-raised Louisiana alligator',               14.00, 'lb',    20),
('Oysters',          'Gulf oysters, fresh in shell',                  15.00, 'dozen', 35),
('Crawfish Tails',   'Peeled crawfish tail meat, frozen',             22.00, 'lb',    45);
