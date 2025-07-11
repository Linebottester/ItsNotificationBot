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
        # user_wishes にある希望施設情報を facilities に JOIN
        cursor.execute('''
            SELECT uw.user_id, uw.facility_id, f.name AS facility_name
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
                "facility_name": row["facility_name"]
            }
            for row in rows
        ]

    except sqlite3.Error as e:
        logger.error(f"DBエラー: {e}")
        return []

    finally:
        conn.close()

# スクレイピングしたデータから施設の予約可否情報を抽出して通知する
def parse_and_notify_available_dates(soup, facility_id, facility_name, user_id):
    from line_bot_server import notify_user
    logger = logging.getLogger(__name__)
    available_dates = []

    for td in soup.find_all("td", attrs={"data-join-time": True, "data-night-count": "1"}):
        status_icon = td.find("span", class_="icon")
        if status_icon:
            status_text = status_icon.get_text(strip=True)
            join_date = td["data-join-time"]
            if status_text != "☓":
                logger.info(f"空きあり: {facility_id} {join_date} 状態: {status_text}")
                available_dates.append(join_date)
            else:
                logger.debug(f"満室: {facility_id} {join_date} 状態: {status_text}")

    if not available_dates:
        logger.info(f"{facility_id} に空き日程はありません")
        return

    # 空き日を整形してまとめて通知
    formatted_dates = []
    for date_str in available_dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = "月火水木金土日"[dt.weekday()]
        formatted_dates.append(f"{dt.month}月{dt.day}日（{weekday}）")

    notify_text = f"{facility_name}の次の日程に空きがあります。\n" + "、".join(formatted_dates)
    notify_user(user_id, notify_text)
    logger.info(f"{facility_id} に空き通知を送信 → {notify_text}")

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
def get_wished_user(facility_id, db_name="facility_data.db"):
    logger = logging.getLogger(__name__)
    logger.info(f"get_wished_user() 呼び出し: facility_id={facility_id}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM user_wishes WHERE facility_id = ?",
            (facility_id,)  # ,をつける書き方をタプルといい、これがないとstr扱いになるらしい
        )
        results = [row[0] for row in cursor.fetchall()]
        logger.info(f"対象ユーザー数: {len(results)} 件")
        return results

    except sqlite3.Error as e:
        logger.error(f"get_wished_user() DBエラー: {e}")
        return []

    finally:
        conn.close()