from flask import Flask, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "facility_data.db"

def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, DB_NAME)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    return jsonify({"message": "SQLiteテーブル確認APIへようこそ。"})

@app.route("/tables")
def list_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row["name"] for row in cursor.fetchall()]
        return jsonify({"tables": tables})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()

@app.route("/table/users")
def show_table_users(users):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {users}")
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        return jsonify({"data": result})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()
        
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)