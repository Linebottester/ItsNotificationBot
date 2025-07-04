# main.py

from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
from line_bot_utils import app, line_bot_api, handler
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from flask import Flask, request, abort, jsonify
import sqlite3
import os
import logging





# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    logging.basicConfig(level=logging.INFO)

    
    # 施設の名前とURL一覧を取得 
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13TjJjVFBrbG1KbFZuYzAxVFp5Vkhkd0YyWWZWR2JuOTJiblpTWjFKSGQ5a0hkdzFXWg%3D%3D&join_date=&night_count=1"
    
    # 施設名と施設IDを取得する　毎回見に行くのはナンセンスな気がする　月初めのみに限定すべきか
    facilities = scrape_facility_names_ids(facility_url)

    save_facilities(facilities) #取得してきた施設と施設IDをDBへ保存

    # 希望されている施設IDと名前をDBから取得
    wished_facilities = fetch_wished_facilities()

    for wished_facility in wished_facilities:
        #　施設を限定してスクレイピングをおこなう
        scrape_avl_from_calender(facility_id=wished_facility["id"], facility_name=wished_facility["facility_name"])

@app.route('/api/users', methods=['GET'])
def get_users():
    """ユーザー一覧をJSON形式で返す"""
    import sqlite3
    import os
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "facility_data.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT user_id, registered_at FROM users")
        users = cursor.fetchall()
        
        users_list = []
        for user in users:
            users_list.append({
                'user_id': user[0],
                'registered_at': user[1]
            })
        
        return jsonify(users_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == "__main__":
    main()
