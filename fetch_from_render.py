# fetch_from_render.py
import requests
import sqlite3
import time

def fetch_users_from_render():
    try:
        # RenderにAPI作成が必要
        url = "https://itsnotificationbot.onrender.com/api/users"
        response = requests.get(url)
        
        if response.status_code == 200:
            users = response.json()
            save_to_local_db(users)
        
    except Exception as e:
        print(f"取得エラー: {e}")

def save_to_local_db(users):
    db_path = r"C:\Users\line-messaging-bot\LineBot\facility_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for user in users:
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
        ''', (user['user_id'],))
    
    conn.commit()
    conn.close()

# 10秒ごとにチェック
while True:
    fetch_users_from_render()
    time.sleep(10)