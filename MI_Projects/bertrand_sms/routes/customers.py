from flask import Blueprint, request, jsonify
from flask_login import login_required
from database import execute_query

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/api/customers/', methods=['GET'])
@login_required
def get_customers():
    search = request.args.get('search', '').strip()
    sql = '''
        SELECT c.*, 
               COUNT(o.id) as total_orders, 
               COALESCE(SUM(o.total_amount), 0) as total_spent
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        WHERE 1=1
    '''
    params = []
    if search:
        sql += ' AND (c.name LIKE %s OR c.phone LIKE %s OR c.city LIKE %s)'
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param])

    sql += ' GROUP BY c.id ORDER BY c.created_at DESC'
    customers = execute_query(sql, tuple(params), fetch_all=True) or []
    return jsonify(customers)

@customers_bp.route('/api/customers/<int:cust_id>', methods=['GET'])
@login_required
def get_customer(cust_id):
    customer = execute_query("SELECT * FROM customers WHERE id = %s", (cust_id,), fetch_one=True)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    orders = execute_query('''
        SELECT id, order_number, status, total_amount, delivery_date, created_at
        FROM orders WHERE customer_id = %s ORDER BY created_at DESC
    ''', (cust_id,), fetch_all=True) or []

    customer['orders'] = orders
    return jsonify(customer)

@customers_bp.route('/api/customers/', methods=['POST'])
@login_required
def create_customer():
    data = request.get_json() or {}
    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    address = data.get('address', '').strip()
    city = data.get('city', 'Breaux Bridge').strip()
    state = data.get('state', 'LA').strip()
    zip_code = data.get('zip', '').strip()
    notes = data.get('notes', '').strip()

    if not name or not phone:
        return jsonify({'error': 'Name and phone number are required'}), 400

    # Format phone number simple check
    existing = execute_query("SELECT id FROM customers WHERE phone = %s", (phone,), fetch_one=True)
    if existing:
        return jsonify({'error': 'A customer with this phone number already exists'}), 400

    cust_id = execute_query('''
        INSERT INTO customers (name, phone, email, address, city, state, zip, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (name, phone, email, address, city, state, zip_code, notes), commit=True)

    return jsonify({
        'success': True,
        'customer_id': cust_id,
        'message': f"Customer '{name}' added successfully!"
    }), 201

@customers_bp.route('/api/customers/<int:cust_id>', methods=['PUT'])
@login_required
def update_customer(cust_id):
    customer = execute_query("SELECT * FROM customers WHERE id = %s", (cust_id,), fetch_one=True)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    data = request.get_json() or {}
    name  = data.get('name', customer['name']).strip()
    phone = data.get('phone', customer['phone']).strip()
    email = data.get('email', customer['email']).strip()
    address = data.get('address', customer['address']).strip()
    city = data.get('city', customer['city']).strip()
    state = data.get('state', customer['state']).strip()
    zip_code = data.get('zip', customer['zip']).strip()
    notes = data.get('notes', customer['notes']).strip()

    if not name or not phone:
        return jsonify({'error': 'Name and phone are required'}), 400

    # Check phone uniqueness if changed
    if phone != customer['phone']:
        dup = execute_query("SELECT id FROM customers WHERE phone = %s AND id != %s", (phone, cust_id), fetch_one=True)
        if dup:
            return jsonify({'error': 'Another customer already uses this phone number'}), 400

    execute_query('''
        UPDATE customers SET name=%s, phone=%s, email=%s, address=%s, city=%s, state=%s, zip=%s, notes=%s
        WHERE id=%s
    ''', (name, phone, email, address, city, state, zip_code, notes, cust_id), commit=True)

    return jsonify({'success': True, 'message': 'Customer updated successfully'})

@customers_bp.route('/api/customers/<int:cust_id>', methods=['DELETE'])
@login_required
def delete_customer(cust_id):
    customer = execute_query("SELECT * FROM customers WHERE id = %s", (cust_id,), fetch_one=True)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    execute_query("DELETE FROM customers WHERE id = %s", (cust_id,), commit=True)
    return jsonify({'success': True, 'message': f"Customer '{customer['name']}' deleted"})
