"""
SQL + LLM Connect
------------------
Flask backend that takes a plain-English condition from the user,
asks Gemini to turn it into a SQL query for the connected MySQL
database, runs that query, and returns the results.

Flow (matches the notebook sketch):
  app.py -> Gemini API key -> request -> response text + SQL prompt
"""

import os
import sys

# --- Auto-activate venv ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "bin", "python")  # Mac/Linux path

if sys.prefix == sys.base_prefix:  # matlab venv active nahi hai
    if not os.path.exists(VENV_PYTHON):
        print(f"venv nahi mila: {VENV_PYTHON}")
        sys.exit(1)
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)
# --- venv activated, ab normal imports chalenge ---

import re
import json
import traceback
from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import Error as MySQLError
import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

load_dotenv()  # reads .env -> GOOGLE_API_KEY, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

app = Flask(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY is missing. Create a .env file (see .env.example) "
        "and paste your Makersuite API key into it."
    )

genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "port": int(os.getenv("DB_PORT", 3306)),
}

# Only these statement types are allowed to run. Everything else (INSERT,
# UPDATE, DELETE, DROP, ALTER, etc.) is rejected before it ever touches MySQL.
ALLOWED_STATEMENT = re.compile(r"^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b", re.IGNORECASE)
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_schema_description(conn):
    """Builds a compact text description of every table + its columns so
    Gemini knows what it's allowed to query against."""
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    schema_lines = []
    for table in tables:
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        col_desc = ", ".join(f"{col[0]} ({col[1]})" for col in columns)
        schema_lines.append(f"- {table}: {col_desc}")
    cursor.close()
    return "\n".join(schema_lines) if schema_lines else "No tables found."

def get_schema_structured(conn):
    """Returns schema as a list of {table, columns} for frontend suggestions."""
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    structured = []
    for table in tables:
        cursor.execute(f"DESCRIBE `{table}`")
        columns = [col[0] for col in cursor.fetchall()]
        structured.append({"table": table, "columns": columns})
    cursor.close()
    return structured

def build_sql_prompt(condition, schema_text):
    return f"""You are a MySQL expert. Convert the user's plain-English condition
into a single, safe, read-only MySQL query.

Database schema:
{schema_text}

Rules:
- Only generate SELECT, SHOW, DESCRIBE, or EXPLAIN statements.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE statements.
- Use only the tables and columns listed in the schema above.
- Return ONLY the raw SQL query, no markdown formatting, no code fences, no explanation.

User condition: "{condition}"

SQL query:"""


def clean_sql(raw_text):
    """Strips markdown code fences / stray formatting Gemini sometimes adds."""
    text = raw_text.strip()
    text = re.sub(r"^```sql\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"```$", "", text.strip())
    return text.strip().rstrip(";").strip()


def is_query_safe(sql):
    if not ALLOWED_STATEMENT.match(sql):
        return False, "Only SELECT, SHOW, DESCRIBE, or EXPLAIN statements are allowed."
    if FORBIDDEN_KEYWORDS.search(sql):
        return False, "Query contains a disallowed keyword (write operations are blocked)."
    if ";" in sql:
        return False, "Multiple statements are not allowed."
    return True, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", model_name=MODEL_NAME)


@app.route("/api/schema", methods=["GET"])
def api_schema():
    try:
        conn = get_db_connection()
        schema_text = get_schema_description(conn)
        schema_structured = get_schema_structured(conn)
        conn.close()
        return jsonify({"ok": True, "schema": schema_text, "tables": schema_structured})
    except MySQLError as e:
        return jsonify({"ok": False, "error": f"Database connection failed: {str(e)}"}), 500


@app.route("/api/query", methods=["POST"])
def api_query():
    data = request.get_json(silent=True) or {}
    condition = (data.get("condition") or "").strip()
    sql_override = (data.get("sql") or "").strip()

    if not condition and not sql_override:
        return jsonify({"ok": False, "error": "Please enter a condition to search for."}), 400

    # 1. Connect to MySQL
    try:
        conn = get_db_connection()
    except MySQLError as e:
        return jsonify({"ok": False, "error": f"Could not connect to MySQL: {str(e)}"}), 500

    if sql_override:
        # The user edited a previously generated query and wants to re-run it
        # as-is. Skip Gemini entirely, but still enforce the same safety check
        # below — user-edited SQL needs the same read-only guard as generated SQL.
        generated_sql = clean_sql(sql_override)
    else:
        # 2. Read the schema, then ask Gemini to convert the condition into SQL
        try:
            schema_text = get_schema_description(conn)
        except MySQLError as e:
            conn.close()
            return jsonify({"ok": False, "error": f"Could not read database schema: {str(e)}"}), 500

        sql_prompt = build_sql_prompt(condition, schema_text)
        try:
            gemini_response = model.generate_content(sql_prompt)
            response_text = gemini_response.text
        except Exception as e:
            conn.close()
            return jsonify({"ok": False, "error": f"Gemini request failed: {str(e)}"}), 500

        generated_sql = clean_sql(response_text)

    # 3. Safety check before running anything
    safe, reason = is_query_safe(generated_sql)
    if not safe:
        conn.close()
        return jsonify({
            "ok": False,
            "error": f"Generated query was blocked: {reason}",
            "sql": generated_sql,
        }), 400

    # 4. Run the query
    try:
        cursor = conn.cursor()
        cursor.execute(generated_sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except MySQLError as e:
        conn.close()
        return jsonify({
            "ok": False,
            "error": f"MySQL error while running the generated query: {str(e)}",
            "sql": generated_sql,
        }), 400

    results = [dict(zip(columns, row)) for row in rows]

    return jsonify({
        "ok": True,
        "condition": condition,
        "sql": generated_sql,
        "columns": columns,
        "rows": results,
        "row_count": len(results),
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    traceback.print_exc()
    return jsonify({"ok": False, "error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)