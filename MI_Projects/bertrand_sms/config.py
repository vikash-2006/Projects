import os

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Database settings
    # Engine options: 'auto' (tries MySQL, falls back to SQLite), 'sqlite', 'mysql'
    DB_ENGINE = os.environ.get('DB_ENGINE', 'auto').lower()
    
    # SQLite configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH', os.path.join(BASE_DIR, 'bertrand.db'))

    # MySQL configuration
    DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'bertrand_seafood')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))

    # Twilio SMS configuration
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") 
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '000000000000')

    # Store branding & default info
    STORE_NAME = os.environ.get('STORE_NAME', "Bertrand's Crawfish & Seafood")
    STORE_PHONE = os.environ.get('STORE_PHONE', "(337) 555-0100")
    STORE_ADDRESS = os.environ.get('STORE_ADDRESS', "1024 Crawfish Row, Breaux Bridge, LA 70517")
    REVIEW_LINK = os.environ.get('REVIEW_LINK', "bit.ly/bertrand-review")

    # Admin default login credentials
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
