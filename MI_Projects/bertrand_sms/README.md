# 🦞 Bertrand's Crawfish & Seafood — SMS Order Management System

## Tech Stack
| Layer     | Technology               |
|-----------|--------------------------|
| Frontend  | HTML5 + CSS3 + Vanilla JS|
| Backend   | Python Flask             |
| Database  | MySQL                    |
| SMS       | Twilio                   |

---

## Project Structure
```
bertrand_sms/
├── app.py              # Flask entry point & blueprint registration
├── config.py           # MySQL, Twilio, Flask settings
├── sms_helper.py       # Twilio send + message templates
├── schema.sql          # MySQL schema + seed data
├── requirements.txt
├── routes/
│   ├── orders.py       # CRUD + status change triggers SMS
│   ├── drivers.py      # Driver CRUD
│   ├── customers.py    # Customer CRUD
│   ├── sms.py          # Twilio webhook + manual SMS + logs
│   └── dashboard.py    # Stats API
├── templates/
│   ├── index.html      # Dashboard
│   ├── orders.html     # Order management
│   ├── customers.html  # Customer management
│   └── drivers.html    # Driver management
└── static/
    ├── css/main.css
    └── js/main.js
```

---

## Setup Steps

### 1. Clone / Copy project
```bash
cd /your/projects
# Place the bertrand_sms folder here
cd bertrand_sms
```

### 2. Create Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip3 install -r requirements.txt
```

### 3. Set up MySQL
```bash
mysql -u root -p
```
```sql
SOURCE schema.sql;
```

### 4. Configure credentials
Edit `config.py` or set environment variables:

```bash
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=bertrand_seafood
export TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export TWILIO_AUTH_TOKEN=your_auth_token
export TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
```

> 💡 Get your Twilio credentials at https://console.twilio.com

### 5. Run the Flask server
```bash
python app.py
```
Open browser: **http://localhost:5000**

---

## Twilio Webhook Setup

To receive incoming SMS replies from customers/drivers:

1. In Twilio Console → Phone Numbers → your number
2. Set **"A MESSAGE COMES IN"** webhook to:
   ```
   https://yourdomain.com/api/sms/webhook
   ```
   (Use [ngrok](https://ngrok.com) for local development: `ngrok http 5000`)

### Inbound SMS Commands
| Customer texts | Response |
|---------------|----------|
| STATUS or ORDER | Latest order status |
| REVIEW | Google review link |

| Driver texts | Response |
|-------------|----------|
| ACCEPT | Confirms pickup of assigned order |

---

## API Endpoints

### Orders
| Method | URL | Description |
|--------|-----|-------------|
| GET  | /api/orders/ | List all orders |
| POST | /api/orders/ | Create new order |
| GET  | /api/orders/products_list | List products |
| PATCH| /api/orders/:id/status | Update status + auto-SMS |
| PATCH| /api/orders/:id/assign-driver | Assign driver |
| DELETE| /api/orders/:id | Delete order |

### Customers
| Method | URL | Description |
|--------|-----|-------------|
| GET  | /api/customers/ | List all |
| POST | /api/customers/ | Create |
| PUT  | /api/customers/:id | Update |
| DELETE| /api/customers/:id | Delete |

### Drivers
| Method | URL | Description |
|--------|-----|-------------|
| GET  | /api/drivers/ | List all |
| POST | /api/drivers/ | Create |
| PUT  | /api/drivers/:id | Update |
| DELETE| /api/drivers/:id | Delete |

### SMS
| Method | URL | Description |
|--------|-----|-------------|
| POST | /api/sms/send | Manual SMS send |
| GET  | /api/sms/logs | SMS history |
| POST | /api/sms/webhook | Twilio inbound webhook |

---

## Automatic SMS Triggers

| Status Change | Who Gets SMS |
|--------------|-------------|
| → confirmed | Customer (confirmation) + Driver (new delivery) |
| → out_for_delivery | Customer (driver info) |
| → delivered | Customer (delivery confirmation) |
| → cancelled | Customer (cancellation notice) |

---

## Production Deployment (Ubuntu + Gunicorn + Nginx)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Nginx config:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
