# local_server.py Render→ローカルのデータ受信を行う

from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/api/save-user', methods=['POST'])
def save_user():
    """RenderからユーザーIDを受信してローカルDBに保存"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        # ローカルDBに保存
        db_path = r"C:\Users\line-messaging-bot\LineBot\facility_data.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
        ''', (user_id,))
        conn.commit()
        conn.close()
        
        print(f"ローカルDBに保存: {user_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"エラー: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)