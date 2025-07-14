# db_utils.py

from datetime import datetime
from psycopg2.extras import RealDictCursor
import psycopg2
import os 
import logging

# .envから環境変数を通す
database_url = os.getenv('DATABASE_URL')

# logger 設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 初回起動時にfacilities,users,user_wishesテーブルを作成する
def create_tables():
    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return
    
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # facilitiesテーブルを作成
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS facilities (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL
                    );
                ''')
                # usersテーブルを作成
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY
                    );
                ''')
                # user_wishesテーブルを作成
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
                
    except psycopg2.Error as e:
        logger.error(f"データベースエラー: {e}")
        
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")

# main.pyが起動するたびfacilitiesにスクレイピングし更新
def save_facilities(facilities):
    logger.info(f'保存対象の施設数:{len(facilities)}')

    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return
    
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                new_count = 0
                skip_count = 0
                
                for facility in facilities:
                    try:
                        cursor.execute('''
                            INSERT INTO facilities (id, name)
                            VALUES (%s, %s)
                            ON CONFLICT(id) DO NOTHING
                        ''', (facility['id'], facility['name']))
                        
                        # 実際に挿入された行数を確認
                        if cursor.rowcount > 0:
                            new_count += 1
                            logger.info(f"新規保存: {facility['name']} (ID={facility['id']})")
                        else:
                            skip_count += 1
                            logger.info(f"既存のためスキップ: {facility['name']} (ID={facility['id']})")
                            
                    except psycopg2.Error as e:
                        logger.error(f"保存失敗: {facility['id']} - {e}")
                        continue

                logger.info(f'施設情報保存完了 - 新規: {new_count}件, スキップ: {skip_count}件')
    
    except psycopg2.Error as e:
        logger.error(f'DB接続エラー: {e}')
    except Exception as e:
        logger.error(f'予期しないエラー: {e}')

# スクレイピング時に、希望者のいる施設のみ限定するためにuser_wishesを参照する
def fetch_wished_facilities():
    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return []
    
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # user_wishesにある希望施設情報をfacilitiesと結合
                cursor.execute('''
                    SELECT uw.user_id, uw.facility_id, f.name As facility_name
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
    
    except psycopg2.Error as e:
        logger.error(f"DBエラー: {e}")
        return []
    
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        return []

# ユーザーがボットをフォローしたときそのIDをusersテーブルに保存
def save_followed_userid(userid):
    logger.info(f"保存対象のユーザID:{userid}")
    
    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return
    
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    INSERT INTO users (user_id)
                    VALUES (%s)
                    ON CONFLICT(user_id) DO NOTHING
                ''', (userid,))
                
                affected_rows = cursor.rowcount
                logger.info(f"挿入された行数: {affected_rows}")
                
        logger.info(f"ユーザーID:{userid} を保存しました")

    except psycopg2.Error as e:
        logger.error(f"DBエラー: {e}")
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")

# DBから施設データを取得
def get_items_from_db():
    
    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return []

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT id, name
                    FROM facilities
                    ORDER BY name
                ''')
                items = cursor.fetchall()
                logger.info(f"{len(items)} 件の施設データを取得しました")
                return items

    except psycopg2.Error as e:
        logger.error(f"DBエラー: {e}")
        return []
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        return []

# ユーザー希望する施設と日程を入力したときそれをuser_wishesにIDと紐づけて保存
def register_user_selection(user_id, facility_id):

    logger.info(f"[登録処理開始] user_id={user_id}, facility_id={facility_id}")

    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO user_wishes (user_id, facility_id)
                    VALUES (%s, %s)
                    ON CONFLICT(user_id, facility_id)
                    DO UPDATE SET created_at = CURRENT_TIMESTAMP
                """, (user_id, facility_id))

                conn.commit()
                logger.info(f"[登録成功] user_id={user_id} に facility_id={facility_id} を登録")

    except psycopg2.Error as e:
        logger.error(f"[登録失敗] user_id={user_id}, facility_id={facility_id} - DBエラー: {e}")
    except Exception as e:
        logger.error(f"[予期しないエラー] user_id={user_id}, facility_id={facility_id} - 内容: {e}")

# 施設の空きが検知されたら対象の施設のIDを受け取って希望者のIDを返す
def get_wished_user(facility_id):

    logger.info(f"[希望者検索開始] facility_id={facility_id}")

    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return []

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT user_id
                    FROM user_wishes
                    WHERE facility_id = %s
                """, (facility_id,))
                
                results = [row['user_id'] for row in cursor.fetchall()]
                logger.info(f"[希望者取得] 対象ユーザー数: {len(results)} 件")
                return results

    except psycopg2.Error as e:
        logger.error(f"[DBエラー] get_wished_user: {e}")
        return []
    except Exception as e:
        logger.error(f"[予期しないエラー] get_wished_user: {e}")
        return []

# userのデータをusers、user_wishesから消す
def remove_user_from_db(user_id):

    logger.info(f"[削除開始] 対象ユーザーID: {user_id}")

    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # user_wishes から先に削除（外部キー制約がある場合を考慮）
                cursor.execute("DELETE FROM user_wishes WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                conn.commit()
                
                logger.info(f"[削除成功] user_id={user_id} の関連データを削除しました")

    except psycopg2.Error as e:
        logger.error(f"[DBエラー] 削除処理失敗: user_id={user_id} - 内容: {e}")
    except Exception as e:
        logger.error(f"[予期しないエラー] 削除処理失敗: user_id={user_id} - 内容: {e}")

