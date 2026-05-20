import pandas as pd
import numpy as np
from pathlib import Path

import mysql.connector
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE CONFIG  ← change password if different
# ─────────────────────────────────────────────────────────────────────────────

DB_HOST     = "127.0.0.1"
DB_USER     = "root"
DB_PASSWORD = "root123"
DB_NAME     = "drivex_db"

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Reusable MySQL Connection
# ─────────────────────────────────────────────────────────────────────────────

def get_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn

def get_engine():
    url = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    return create_engine(url)

def setup_database():
    """Create database if it doesn't exist."""
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME};")
    conn.close()
    print("✅ MySQL Running!")
    print("✅ Connected!")
    print(f"✅ Database '{DB_NAME}' Ready!")

# Setup DB once
setup_database()

def load_data():
    conn = get_connection()
    query = "SELECT * FROM combined_booking_feedback"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

df = load_data()
print(df.head())

print("Data Loaded Successfully!")

print(df.isnull().sum())