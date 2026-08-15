import uuid
from config import Config
from database import execute_query

def send_sms(to_phone, message, order_id=None, recipient_type='customer'):
    """
    Sends an SMS via Twilio or logs it in simulated mode if Twilio credentials are invalid/mock.
    """
    if not to_phone or not message:
        return {'success': False, 'sid': None, 'error': 'Missing phone number or message'}

    # Attempt real Twilio send
    try:
        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_ACCOUNT_SID.startswith('AC') and len(Config.TWILIO_ACCOUNT_SID) == 34:
            from twilio.rest import Client
            client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(
                body=message,
                from_=Config.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            sid = msg.sid
            log_sms(to_phone, message, recipient_type, order_id, status='sent', twilio_sid=sid)
            print(f"📱 Twilio SMS Sent to {to_phone} (SID: {sid})")
            return {'success': True, 'sid': sid, 'simulated': False, 'error': None}
    except Exception as e:
        print(f"⚠️ Twilio API call failed: {e}. Falling back to simulation mode.")

    # Simulation / Mock SMS mode
    mock_sid = "SIM_" + str(uuid.uuid4())[:12].upper()
    log_sms(to_phone, message, recipient_type, order_id, status='simulated', twilio_sid=mock_sid)
    print(f"📱 [Simulated SMS] To: {to_phone} | Msg: {message[:60]}... (SID: {mock_sid})")
    return {'success': True, 'sid': mock_sid, 'simulated': True, 'error': None}


def log_sms(recipient, message, recipient_type='customer', order_id=None, status='sent', twilio_sid=None):
    try:
        execute_query('''
            INSERT INTO sms_logs (order_id, recipient, recipient_type, message, status, twilio_sid)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (order_id, recipient, recipient_type, message, status, twilio_sid), commit=True)
    except Exception as e:
        print(f"❌ Failed to log SMS: {e}")


def trigger_order_status_sms(order_id, new_status):
    """
    Triggers automated SMS messages based on order status change.
    """
    try:
        sql = '''
            SELECT o.*, c.name as customer_name, c.phone as customer_phone,
                   d.name as driver_name, d.phone as driver_phone
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN drivers d ON o.driver_id = d.id
            WHERE o.id = %s
        '''
        order = execute_query(sql, (order_id,), fetch_one=True)
        if not order:
            return

        cust_phone = order['customer_phone']
        cust_name  = order['customer_name']
        ord_num    = order['order_number']
        tot_amt    = float(order.get('total_amount', 0))

        if new_status == 'confirmed':
            msg = (f"Hi {cust_name}! Your Bertrand's Crawfish order #{ord_num} "
                   f"has been CONFIRMED. Total: ${tot_amt:.2f}. We will notify you when it is out for delivery!")
            send_sms(cust_phone, msg, order_id=order_id, recipient_type='customer')

            # Driver notification if driver is assigned
            if order.get('driver_phone'):
                drv_msg = (f"🚚 New Delivery Assigned! Order #{ord_num} for {cust_name}. "
                           f"Address: {order.get('delivery_address', 'N/A')}. Reply ACCEPT to confirm pickup.")
                send_sms(order['driver_phone'], drv_msg, order_id=order_id, recipient_type='driver')

        elif new_status == 'out_for_delivery':
            drv_info = f" with driver {order['driver_name']}" if order.get('driver_name') else ""
            msg = (f"🚚 Great news {cust_name}! Your order #{ord_num} is OUT FOR DELIVERY{drv_info}. "
                   f"Estimated delivery time: {order.get('delivery_time', 'Today')}.")
            send_sms(cust_phone, msg, order_id=order_id, recipient_type='customer')

        elif new_status == 'delivered':
            msg = (f"✅ Order #{ord_num} DELIVERED! Thank you for ordering from Bertrand's Crawfish & Seafood. "
                   f"Enjoy your feast! Leave us a review: {Config.REVIEW_LINK}")
            send_sms(cust_phone, msg, order_id=order_id, recipient_type='customer')

        elif new_status == 'cancelled':
            msg = (f"❌ Notice: Your Bertrand's Crawfish order #{ord_num} has been CANCELLED. "
                   f"If you have questions, please call us at {Config.STORE_PHONE}.")
            send_sms(cust_phone, msg, order_id=order_id, recipient_type='customer')

        # Update order sms_sent flag
        execute_query("UPDATE orders SET sms_sent=1 WHERE id=%s", (order_id,), commit=True)

    except Exception as e:
        print(f"❌ Error triggering status SMS for order #{order_id}: {e}")
