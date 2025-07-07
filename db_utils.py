# db_utils.py

from datetime import datetime
import requests
import sqlite3
import os 
import logging
import json

# logger 設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def save_facilities(facilities, db_name="facility_data.db"):
    logger.info(f'保存対象の施設数:{len(facilities)}')
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_name)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for facility in facilities:
            try:
                cursor.execute('''
                    INSERT INTO facilities (id, name)
                    VALUES (?, ?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name
                ''', (facility['id'], facility['name']))
                logger.info(f"保存完了: {facility['name']} (ID={facility['id']})")
            except sqlite3.Error as e:
                    logger.error(f"保存失敗: {facility['id']} - {e}")

        conn.commit()
        logger.info('すべての施設情報を保存しました')
    
    except sqlite3.Error as e:
        logger.error(f'DB接続エラー: {e}')
    finally:
        conn.close()

def fetch_wished_facilities(db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        #希望のある施設名user_wishesから取得する
        cursor.execute("SELECT DISTINCT facility_name FROM user_wishes;")
        wished_names = [row[0] for row in cursor.fetchall()]

        if not wished_names:
            logger.info("希望される施設がありません")
            return []

        # SQL の IN 句を動的に生成
        placeholders = ",".join("?" for _ in wished_names)
        query = f'''
            SELECT id, name FROM facilities
            WHERE name IN ({placeholders})
        '''

        cursor.execute(query, wished_names)
        matched_facilities = cursor.fetchall()
        
        return [{"id": row["id"], "facility_name": row["name"]} for row in matched_facilities]

    except sqlite3.Error as e:
        logger.error(f"DBエラー:{e}")
        return []
    
    finally:
        conn.close()

    return [row[0] for row in rows]

def parse_and_save_avl(soup, facility_id, db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    count = 0
    # 一泊分かつ予約可能状況がXでないもののみに絞る　
    for td in soup.find_all("td", attrs={"data-join-time": True, "data-night-count": "1"}):
        status_icon = td.find("span", class_="icon")
        if status_icon:
            status_text = status_icon.get_text(strip=True)
            if status_text != "☓":  # ☓は除外する（満室）
                join_date = td["data-join-time"]
                
                # 挿入前にレコード数を確認（重複チェック用）
                cursor.execute('''
                    SELECT COUNT(*) FROM facility_availabilities WHERE facility_id = ? AND date = ?
                ''', (facility_id, join_date))
                before_count = cursor.fetchone()[0]

                # INSERT OR IGNORE による挿入
                cursor.execute('''
                    INSERT OR IGNORE INTO facility_availabilities (facility_id, date, status)
                    VALUES (?, ?, ?)
                ''', (facility_id, join_date, status_text))

                # 挿入後にレコード数を再確認
                cursor.execute('''
                    SELECT COUNT(*) FROM facility_availabilities WHERE facility_id = ? AND date = ?
                ''', (facility_id, join_date))
                after_count = cursor.fetchone()[0]

                # 新規データが挿入された=空き状況が発生したものとする
                if after_count > before_count:
                    logging.info(f"空きあり: {facility_id} {join_date} 状態: {status_text}")
                    count += 1
                    
                    # line_utils.py（仮）に関数を配置して通知を送るようにする

                else:
                    logging.info(f"既に登録済み: {facility_id} {join_date} ")

                # 通知したfacility_availabilitiesデータはnotice_logテーブルへ移行させて元テーブルから消す（？）

    conn.commit()
    conn.close()
    logger.info(f"{facility_id} の空きデータ {count} 件を保存しました。")

def save_followed_userid(userid, db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)
    
    # デバッグ用ログ追加
    logger.info(f"DBパス: {db_path}")
    logger.info(f"DBファイル存在確認: {os.path.exists(db_path)}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # usersテーブルがなければ作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY
            )
        ''')

        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
        ''', (userid,))
        
        # 実際に挿入されたかを確認
        affected_rows = cursor.rowcount
        logger.info(f"挿入された行数: {affected_rows}")
        
        conn.commit()
        logger.info(f"フォローしてくれたユーザのID:{userid} を保存しました。")
        
        # 確認用クエリ
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (userid,))
        count = cursor.fetchone()[0]
        logger.info(f"DBに保存されているか確認: {count}件")

    except sqlite3.Error as e:
        logger.error(f"DBエラー:{e}")
    
    finally:
        conn.close()
        
def save_userid_to_localdb(db_name="facility_data.db"):

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    response = requests.get('https://itsnotificationbot.onrender.com/api/latest_data')

    logger.info(f"API ステータス: {response.status_code}")
    logger.debug(f"レスポンス本文: {response.text}")

    if response.status_code == 200:
        data = response.json()

        conn = sqlite3.connect(db_path) 
        cursor = conn.cursor()

        for row in data:
            cursor.execute(
                "INSERT OR REPLACE INTO users (id, user_id, joined_at) VALUES (?, ?, ?)",
                (row[0], row[1], row[2])
            )

        conn.commit()
        conn.close()
        logger.info(f"ローカルDB '{db_name}' に {len(data)} 件の user_id を保存しました")

    else:
        logger.error("APIリクエストに失敗しました")

def get_items_from_db():
    """SQLiteからデータを取得"""
    conn = sqlite3.connect('facility_data.db')
    cursor = conn.cursor()
    
    # テーブルからデータを取得（例：商品テーブル）
    cursor.execute("SELECT id , name FROM facilities ORDER BY name")
    items = cursor.fetchall()
    
    conn.close()
    
    # 辞書形式に変換
    return [{'id': item[0], 'name': item[1]} for item in items]

def register_user_selection(user_id, item_id):
    conn = sqlite3.connect('facility_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_wishes (user_id, facility_id)
            VALUES (?, ?)
            ON CONFLICT(user_id, facility_id) DO NOTHING
        """, (user_id, item_id))

        temporary_selection[user_id] = facility_id  #　一度保持する
        

        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"登録失敗: {user_id}, {item_id} - {e}")
    finally:
        conn.close()




