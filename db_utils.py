# db_utils.py

from datetime import datetime
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

def save_facility_names_to_db(facility_names, db_name="facility_data.db"):
    """
    スクレイピングで取得した施設名をDBに保存
    """
    if not facility_names:
        logger.warning("保存する施設データがありません")
        return

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_name)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # テーブルが存在しない場合のみ作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facility_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_name TEXT NOT NULL,
                available_date TEXT,
                is_available INTEGER,
                last_checked_at TEXT,
                scraping_config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        saved_count = 0
        skipped_count = 0

        for facility in facility_names:
            name = facility.get("facility_name")
            
            if not name:
                logger.warning("施設名が空です。スキップします")
                continue

            # すでに存在している施設名か確認（available_date が NULL の新規データとみなす）
            cursor.execute("""
                SELECT COUNT(*) FROM facility_availability
                WHERE facility_name = ? AND available_date IS NULL
            """, (name,))
            exists = cursor.fetchone()[0]

            if exists == 0:
                cursor.execute("""
                    INSERT INTO facility_availability (
                        facility_name, available_date, is_available, last_checked_at, scraping_config
                    ) VALUES (?, NULL, NULL, ?, NULL)
                """, (name, datetime.now().isoformat()))
                saved_count += 1
                logger.info(f"登録済み: {name}")
            else:
                skipped_count += 1
                logger.info(f"スキップ（既存）: {name}")
            
        conn.commit()
        logger.info(f"施設名の保存が完了しました。登録: {saved_count}件, スキップ: {skipped_count}件")

    except sqlite3.Error as e:
        logger.error(f"SQLiteエラー: {e}")
        logger.error(f"エラーが発生したSQL操作の詳細を確認してください")
        if 'conn' in locals():
            conn.rollback()
    except Exception as e:
        logger.error(f"データベース保存エラー: {e}")
        logger.error(f"エラーの詳細: {type(e).__name__}: {str(e)}")
        
    finally:
        if 'conn' in locals():
            conn.close()

def save_availability_data(results, db_name="facility_data.db"):
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for item in results:
        cursor.execute("""
            INSERT INTO facility_availability (
                facility_name,
                available_date,
                is_available,
                last_checked_at,
                scraping_source
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            item['facility_name'],
            item['available_date'],
            int(item['is_available']),
            item['last_checked_at'],
            item['scraping_config'].get('source_url')
        ))

    conn.commit()
    conn.close()
    
def save_availabilities_to_db(availability_data, db_name="facility_data.db"):
    """
    予約可否データ（施設ごとの空き状況リスト）をSQLiteに保存
    """
    try:
        if availability_data:
            print("=== デバッグ情報 ===")
            print(f"availability_data の型: {type(availability_data)}")
            print(f"最初の要素: {availability_data[0]}")
            print(f"facility_name の型: {type(availability_data[0]['facility_name'])}")
            print(f"facility_name の値: {availability_data[0]['facility_name']}")
            print("==================")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_name)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for row in availability_data:
            cursor.execute("""
                INSERT INTO facility_availability (
                    facility_name,
                    available_date,
                    is_available,
                    last_checked_at,
                    scraping_config
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                row["facility_name"],
                row["available_date"],
                int(row["is_available"]),
                str(row["last_checked_at"]),
                json.dumps(row["scraping_config"])
            ))

        conn.commit()
        logger.info(f"{len(availability_data)} 件の予約データをDBに保存しました ")

    except Exception as e:
        logger.error(f"DB保存エラー: {e}")
        return[]

    finally:
        conn.close()