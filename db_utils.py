# db_utils.py

from datetime import datetime
import sqlite3
import os 
import logging

# logger 設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# main.pyが起動するたびfacilitiesにスクレイピングし更新
def save_facilities(facilities, db_name="facility_data.db"):
    logger.info(f'保存対象の施設数:{len(facilities)}')
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_name)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # テーブルが存在しない場合に作成
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facilities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
        ''')

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

# スクレイピング時に、希望者のいる施設のみ限定するためにuser_wishesを参照する
def fetch_wished_facilities(db_name="facility_data.db"):
    
    logger = logging.getLogger(__name__)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # user_wishes にある希望施設の facility_id と user_id を facilities に JOIN
        cursor.execute('''
            SELECT uw.user_id, uw.facility_id, f.name AS facility_name, uw.wish_date
            FROM user_wishes uw
            JOIN facilities f ON uw.facility_id = f.id
        ''')

        rows = cursor.fetchall()
        logger.info(f"JOIN結果: {len(rows)} 件取得")

        if not rows:
            logger.info("希望される施設がありません")
            return []

        return [
            {
                "user_id": row["user_id"],
                "facility_id": row["facility_id"],
                "facility_name": row["facility_name"],
                "wish_date": row["wish_date"]  
            }
            for row in rows
        ]

    except sqlite3.Error as e:
        logger.error(f"DBエラー: {e}")
        return []

    finally:
        conn.close()

# スクレイピングしたデータから施設の予約可否情報を抽出してfacility_availabilitiesテーブルに入れる
def parse_and_save_avl(soup, facility_id, db_name="facility_data.db"):
    from line_bot_server import notify_user # 循環Import対策
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

                # データ検知時、テーブルがなかったら作成する
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS facility_availabilities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        facility_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        status TEXT,
                        UNIQUE(facility_id, date)
                    )
                ''')
                
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

                    for user_id in get_wished_user(facility_id, join_date):
                        notify_user(user_id, f"あなたの希望している施設の予約に空きが出ました！")
                        logging.info(f"通知 → user={user_id}, facility={facility_id}, date={join_date}")

                else:
                    logging.info(f"既に登録済み: {facility_id} {join_date} ")

                # !!!!通知したfacility_availabilitiesデータは元テーブルから消すべき（？）!!!!!

    conn.commit()
    conn.close()
    logger.info(f"{facility_id} の空きデータ {count} 件を保存しました。")

# ユーザーがボットをフォローしたときそのIDをusersテーブルに保存
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

# ボットに希望とメッセージしたuserにfacilitiesテーブルの内容を渡す
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

# ユーザー希望する施設と日程を入力したときそれをuser_wishesにIDと紐づけて保存
def register_user_selection(user_id, facility_id, db_name="facility_data.db"):
    logger.info(f"[絶対パス確認] {os.path.abspath(db_name)}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    logger.info(f"[登録処理開始] user_id={user_id}, facility_id={facility_id}")
    logger.info(f"[DB接続確認] facility_data.db 実パス: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 外部キー制約を有効化（もし参照先がある場合）
        cursor.execute("PRAGMA foreign_keys = ON;")

        # テーブル作成を最初に明示しておく
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_wishes (
                user_id TEXT NOT NULL,
                facility_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, facility_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (facility_id) REFERENCES facilities(id)
            );
        """)
        conn.commit()  # ←テーブル作成を確実に反映

        # 登録処理
        cursor.execute("""
            INSERT INTO user_wishes (user_id, facility_id)
            VALUES (?, ?)
            ON CONFLICT(user_id, facility_id) DO UPDATE SET created_at = CURRENT_TIMESTAMP;
        """, (user_id, facility_id))
        conn.commit()

        logger.info(f"[登録成功] {user_id=} に {facility_id=} を登録")

    except sqlite3.Error as e:
        logger.error(f"[登録失敗] {user_id=}, {facility_id=} - エラー内容: {e}")

    finally:
        conn.close()
        logger.info("[DB接続終了]")

# 施設の空きが検知されたら対象の施設のIDを受け取って希望者のIDを返す
def get_wished_user(facility_id, join_date, db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM user_wishes WHERE facility_id = ? AND wish_date = ?",
        (facility_id, join_date)
    )
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results