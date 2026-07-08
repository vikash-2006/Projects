-- ===========================================================
-- SQL + LLM Connect — sample database
-- Run this once in MySQL to create and seed a test database.
--
--   mysql -u root -p < sample_database.sql
--
-- Then set DB_NAME=sql_llm_demo in your .env
-- ===========================================================

DROP DATABASE IF EXISTS sql_llm_demo;
CREATE DATABASE sql_llm_demo;
USE sql_llm_demo;

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    city VARCHAR(50),
    signup_date DATE
);

INSERT INTO customers (name, email, city, signup_date) VALUES
('Aarav Sharma',   'aarav.sharma@example.com',   'Jaipur',    '2024-01-15'),
('Priya Singh',    'priya.singh@example.com',    'Jaipur',    '2024-02-10'),
('Rohan Mehta',    'rohan.mehta@example.com',    'Mumbai',    '2024-01-22'),
('Sneha Gupta',    'sneha.gupta@example.com',    'Delhi',     '2024-03-05'),
('Vikram Rathore', 'vikram.rathore@example.com', 'Jaipur',    '2023-11-30'),
('Ananya Joshi',   'ananya.joshi@example.com',   'Bengaluru', '2024-02-18'),
('Karan Verma',    'karan.verma@example.com',    'Mumbai',    '2023-12-09'),
('Ishita Kapoor',  'ishita.kapoor@example.com',  'Delhi',     '2024-04-01'),
('Aditya Nair',    'aditya.nair@example.com',    'Bengaluru', '2024-01-29'),
('Meera Pillai',   'meera.pillai@example.com',   'Chennai',   '2024-03-14'),
('Sanjay Kumar',   'sanjay.kumar@example.com',   'Jaipur',    '2023-10-05'),
('Divya Reddy',    'divya.reddy@example.com',    'Hyderabad', '2024-02-27');

CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 0
);

INSERT INTO products (name, category, price, stock) VALUES
('Wireless Mouse',          'Electronics', 799.00,  150),
('Mechanical Keyboard',     'Electronics', 3499.00,  80),
('USB-C Hub',               'Electronics', 1299.00, 120),
('Noise Cancelling Headphones', 'Electronics', 6999.00, 45),
('Office Chair',            'Furniture',   8999.00,  30),
('Standing Desk',           'Furniture',  14999.00,  18),
('Desk Lamp',                'Furniture',   1499.00,  60),
('Notebook Set',             'Stationery',   299.00, 300),
('Fountain Pen',              'Stationery',   899.00, 100),
('Backpack',                 'Accessories', 2199.00,  75),
('Water Bottle',              'Accessories',  499.00, 200),
('Yoga Mat',                  'Fitness',     999.00, 110);

CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    total_amount DECIMAL(10, 2) NOT NULL,
    order_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

INSERT INTO orders (customer_id, product_id, quantity, total_amount, order_date, status) VALUES
(1, 4, 1, 6999.00, '2026-05-12', 'completed'),
(1, 11, 2, 998.00, '2026-06-01', 'completed'),
(2, 5, 1, 8999.00, '2026-04-20', 'completed'),
(2, 9, 3, 2697.00, '2026-06-10', 'completed'),
(3, 6, 1, 14999.00, '2026-03-15', 'completed'),
(3, 2, 1, 3499.00, '2026-06-15', 'pending'),
(4, 8, 5, 1495.00, '2026-05-29', 'completed'),
(4, 10, 1, 2199.00, '2026-06-05', 'completed'),
(5, 4, 1, 6999.00, '2026-02-18', 'completed'),
(5, 5, 1, 8999.00, '2026-06-12', 'completed'),
(6, 12, 2, 1998.00, '2026-05-03', 'completed'),
(6, 3, 1, 1299.00, '2026-06-16', 'completed'),
(7, 6, 1, 14999.00, '2026-01-25', 'completed'),
(7, 7, 2, 2998.00, '2026-06-08', 'cancelled'),
(8, 1, 3, 2397.00, '2026-04-11', 'completed'),
(8, 9, 1, 899.00, '2026-06-14', 'completed'),
(9, 4, 1, 6999.00, '2026-03-22', 'completed'),
(9, 11, 1, 499.00, '2026-06-02', 'completed'),
(10, 2, 1, 3499.00, '2026-05-19', 'completed'),
(10, 8, 10, 2990.00, '2026-06-09', 'completed'),
(11, 5, 1, 8999.00, '2026-02-02', 'completed'),
(11, 6, 1, 14999.00, '2026-06-13', 'completed'),
(12, 10, 2, 4398.00, '2026-04-28', 'completed'),
(12, 3, 1, 1299.00, '2026-06-17', 'completed');
