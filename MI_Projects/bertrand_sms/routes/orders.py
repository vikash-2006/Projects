import uuid
import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required
from database import execute_query
from sms_helper import trigger_order_status_sms, send_sms

orders_bp = Blueprint('orders', __name__)

def gen_order_number():
    return 'BC-' + str(uuid.uuid4())[:8].upper()

@orders_bp.route('/api/orders/', methods=['GET'])
@login_required
def get_orders():
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    sql = '''
        SELECT o.*, 
               c.name as customer_name, c.phone as customer_phone, c.address as customer_address,
               d.name as driver_name, d.phone as driver_phone
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN drivers d ON o.driver_id = d.id
        WHERE 1=1
    '''
    params = []

    if status and status != 'all':
        sql += ' AND o.status = %s'
        params.append(status)

    if search:
        sql += ' AND (o.order_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)'
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param])

    sql += ' ORDER BY o.created_at DESC'

    orders = execute_query(sql, tuple(params), fetch_all=True) or []
    
    # Attach item details for each order
    for o in orders:
        items = execute_query('''
            SELECT oi.*, p.name as product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        ''', (o['id'],), fetch_all=True) or []
        o['items'] = items

    return jsonify(orders)


@orders_bp.route('/api/orders/<int:order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    sql = '''
        SELECT o.*, 
               c.name as customer_name, c.phone as customer_phone, c.email as customer_email,
               c.address as customer_address, c.city as customer_city,
               d.name as driver_name, d.phone as driver_phone
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN drivers d ON o.driver_id = d.id
        WHERE o.id = %s
    '''
    order = execute_query(sql, (order_id,), fetch_one=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    items = execute_query('''
        SELECT oi.*, p.name as product_name, p.unit
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = %s
    ''', (order_id,), fetch_all=True) or []

    order['items'] = items
    return jsonify(order)


@orders_bp.route('/api/orders/', methods=['POST'])
@login_required
def create_order():
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    items = data.get('items', [])
    delivery_address = data.get('delivery_address', '')
    delivery_date = data.get('delivery_date') or str(datetime.date.today())
    delivery_time = data.get('delivery_time', 'Morning (8AM-12PM)')
    notes = data.get('notes', '')
    driver_id = data.get('driver_id') or None
    send_confirmation_sms = data.get('send_sms', True)

    if not customer_id:
        return jsonify({'error': 'Customer is required'}), 400
    if not items or not isinstance(items, list):
        return jsonify({'error': 'Order must include at least one product item'}), 400

    customer = execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        return jsonify({'error': 'Selected customer does not exist'}), 404

    if not delivery_address:
        delivery_address = f"{customer.get('address', '')}, {customer.get('city', '')}".strip(', ')

    order_num = gen_order_number()

    # Calculate total and validate products
    total_amount = 0.0
    processed_items = []

    for item in items:
        prod_id = item.get('product_id')
        qty = float(item.get('quantity', 0))
        if not prod_id or qty <= 0:
            continue

        prod = execute_query("SELECT * FROM products WHERE id = %s", (prod_id,), fetch_one=True)
        if not prod:
            return jsonify({'error': f"Product ID {prod_id} not found"}), 404

        price = float(prod['price'])
        subtotal = round(price * qty, 2)
        total_amount += subtotal

        processed_items.append({
            'product_id': prod_id,
            'quantity': qty,
            'unit_price': price,
            'subtotal': subtotal
        })

    if not processed_items:
        return jsonify({'error': 'No valid order items provided'}), 400

    total_amount = round(total_amount, 2)

    # Insert Order
    order_sql = '''
        INSERT INTO orders (order_number, customer_id, driver_id, status, total_amount, 
                            delivery_address, delivery_date, delivery_time, notes)
        VALUES (%s, %s, %s, 'confirmed', %s, %s, %s, %s, %s)
    '''
    order_id = execute_query(order_sql, (
        order_num, customer_id, driver_id, total_amount,
        delivery_address, delivery_date, delivery_time, notes
    ), commit=True)

    # Insert Order Items & Deduct Stock
    for item in processed_items:
        execute_query('''
            INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        ''', (order_id, item['product_id'], item['quantity'], item['unit_price'], item['subtotal']), commit=True)

        execute_query('''
            UPDATE products SET stock_qty = stock_qty - %s WHERE id = %s
        ''', (item['quantity'], item['product_id']), commit=True)

    # Trigger Automated Confirmation SMS
    if send_confirmation_sms:
        trigger_order_status_sms(order_id, 'confirmed')

    return jsonify({
        'success': True,
        'order_id': order_id,
        'order_number': order_num,
        'total_amount': total_amount,
        'message': f"Order #{order_num} created successfully!"
    }), 201


@orders_bp.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
@login_required
def update_order_status(order_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    valid_statuses = ['pending', 'confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled']

    if not new_status or new_status not in valid_statuses:
        return jsonify({'error': f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    order = execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch_one=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    old_status = order['status']
    execute_query("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id), commit=True)

    # If status changed to out_for_delivery and driver is assigned, set driver status to on_delivery
    if new_status == 'out_for_delivery' and order.get('driver_id'):
        execute_query("UPDATE drivers SET status = 'on_delivery' WHERE id = %s", (order['driver_id'],), commit=True)

    # Trigger auto SMS if status changed
    if old_status != new_status:
        trigger_order_status_sms(order_id, new_status)

    return jsonify({
        'success': True,
        'order_id': order_id,
        'old_status': old_status,
        'new_status': new_status,
        'message': f"Order #{order['order_number']} status updated to {new_status}"
    })


@orders_bp.route('/api/orders/<int:order_id>/assign-driver', methods=['PATCH'])
@login_required
def assign_driver(order_id):
    data = request.get_json() or {}
    driver_id = data.get('driver_id')

    order = execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch_one=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    if driver_id:
        driver = execute_query("SELECT * FROM drivers WHERE id = %s", (driver_id,), fetch_one=True)
        if not driver:
            return jsonify({'error': 'Driver not found'}), 404
        
        execute_query("UPDATE orders SET driver_id = %s WHERE id = %s", (driver_id, order_id), commit=True)
        
        # Send SMS to driver
        drv_msg = (f"🚚 Delivery Assignment: Order #{order['order_number']} assigned to you. "
                   f"Delivery address: {order.get('delivery_address')}. Time: {order.get('delivery_time')}")
        send_sms(driver['phone'], drv_msg, order_id=order_id, recipient_type='driver')
    else:
        execute_query("UPDATE orders SET driver_id = NULL WHERE id = %s", (order_id,), commit=True)

    return jsonify({'success': True, 'message': 'Driver assignment updated successfully'})


@orders_bp.route('/api/orders/<int:order_id>', methods=['DELETE'])
@login_required
def delete_order(order_id):
    order = execute_query("SELECT * FROM orders WHERE id = %s", (order_id,), fetch_one=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    # Restore product quantities if deleting non-cancelled order
    if order['status'] != 'cancelled':
        items = execute_query("SELECT * FROM order_items WHERE order_id = %s", (order_id,), fetch_all=True) or []
        for item in items:
            execute_query("UPDATE products SET stock_qty = stock_qty + %s WHERE id = %s",
                          (item['quantity'], item['product_id']), commit=True)

    execute_query("DELETE FROM orders WHERE id = %s", (order_id,), commit=True)
    return jsonify({'success': True, 'message': f"Order #{order['order_number']} deleted successfully"})
