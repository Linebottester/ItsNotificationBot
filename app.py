from flask import Flask, jsonify
import logging
import sqlite3
import os

# logger 設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_db_connection(db_name="facility_data.db"):

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)
    logger.info(f"[DB接続処理] 接続先パス: {db_path}")

    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    return jsonify({"message": "SQLiteテーブル確認APIへようこそ。"})

@app.route("/tables")
def list_tables(db_name="facility_data.db"):

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

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

@app.route("/table/<table_name>")
def show_table_contents(table_name, db_name="facility_data.db"):

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
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