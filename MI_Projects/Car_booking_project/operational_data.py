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
    query = "SELECT * FROM bookings"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

df = load_data()
print(df.head())

print("✅ Data Loaded Successfully!")

print(df.isnull().sum())

print("✅ Missing Values Checked!")

print(df.describe())

print("✅ Data Described!")

print("Encoding Categorical Columns into numerical values...")

df1 = df.copy()
print(df1.head(1))

print(df1.columns)
df1.drop(columns=[
    'booking_ref',
    'first_name',
    'last_name',
    'email',
    'pickup_time',  
    'created_at'
], inplace=True)

print(df1.columns)


from sklearn.preprocessing import LabelEncoder

from sklearn.preprocessing import LabelEncoder

label_encoders = {}

for col in df1.select_dtypes(include=['object']).columns:
    le = LabelEncoder()
    df1[col] = le.fit_transform(df1[col])
    label_encoders[col] = le   # store encoder


print("✅ Categorical Columns Encoded!")
# print(df1.head(5))

x = df1.drop(columns=['car_type'])
y = df1['car_type']

from sklearn.model_selection import train_test_split

x_train, x_test, y_train, y_test = train_test_split(x,y,test_size=0.2, random_state=42)

print(np.round(x_train.describe()))

from sklearn.preprocessing import StandardScaler

sc = StandardScaler()

x_train_sc = sc.fit_transform(x_train)

x_train_new = pd.DataFrame(x_train_sc, columns=x_train.columns)

print(np.round(x_train_new.describe()))