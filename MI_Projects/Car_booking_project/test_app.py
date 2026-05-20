import pandas as pd
from app import get_db_connection
from operational_data import load_data
from sklearn.preprocessing import StandardScaler


# ─────────────────────────────────────────────
# 1. Test Database Connection
# ─────────────────────────────────────────────
def test_db_connetion():
    conn = get_db_connection()
    assert conn.is_connected()
    conn.close()


# ─────────────────────────────────────────────
# 2. Test Data Loading
# ─────────────────────────────────────────────
def test_load_data():
    df = load_data()
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


# ─────────────────────────────────────────────
# 3. Test Columns Exist
# ─────────────────────────────────────────────
def test_columns_exist():
    df = load_data()
    
    # change column names based on your table
    expected_columns = ['id']  
    
    for col in expected_columns:
        assert col in df.columns


# ─────────────────────────────────────────────
# 4. Test Standardization
# ─────────────────────────────────────────────
def test_standardization():
    df = load_data()
    
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
    
    scaler = StandardScaler()
    scaled = scaler.fit_transform(df[numeric_cols])
    
    # Mean should be close to 0
    assert abs(scaled.mean()) < 1e-6


# ─────────────────────────────────────────────
# 5. Test for Missing Values
# ─────────────────────────────────────────────
def test_no_missing_values():
    df = load_data()
    
    # Check if any null values exist
    assert df.isnull().sum().sum() == 0