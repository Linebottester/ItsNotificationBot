from flask import Flask, jsonify
import sqlite3
import os
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    """ホームページ"""
    return jsonify({
        'message': 'DB検査用API',
        'endpoints': [
            '/api/db_info - DBの全テーブル情報',
            '/api/facilities - 施設一覧',
            '/api/users - ユーザー一覧'
        ]
    })

@app.route('/api/db_info')
def get_db_info():
    """DB情報を返すAPI"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "facility_data.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        tables_info = []
        for table in tables:
            table_name = table[0]
            
            # レコード数を取得
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            
            # サンプルデータを取得（最初の3件）
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_data = cursor.fetchall()
            
            tables_info.append({
                'table_name': table_name,
                'record_count': count,
                'sample_data': sample_data
            })
        
        conn.close()
        return jsonify(tables_info)
        
    except Exception as e:
        logger.error(f"DB情報取得エラー: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/facilities')
def get_facilities():
    """施設一覧を返すAPI"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "facility_data.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM facilities")
        facilities = cursor.fetchall()
        
        conn.close()
        return jsonify(facilities)
        
    except Exception as e:
        logger.error(f"施設データ取得エラー: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/users')
def get_users():
    """ユーザー一覧を返すAPI"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "facility_data.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        conn.close()
        return jsonify(users)
        
    except Exception as e:
        logger.error(f"ユーザーデータ取得エラー: {e}")
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)