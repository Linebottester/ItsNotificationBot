# main.py

from db_utils import create_tables
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender

import logging

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# サービス起動時に1回だけ実行　各テーブルを作成
create_tables()

def main():
    from line_bot_server import notify_user 
    # 施設の名前とURL一覧を取得
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13TjJjVFBrbG1KbFZuYzAxVFp5Vkhkd0YyWWZWR2JuOTJiblpTWjFKSGQ5a0hkdzFXWg%3D%3D&join_date=&night_count=1"
    facilities = scrape_facility_names_ids(facility_url)
    save_facilities(facilities) #取得してきた施設と施設IDをDBへ保存

    # 希望されている施設IDと名前をDBから取得してきて
    wished_facilities = fetch_wished_facilities()
    messages_each_user = {} 

    # 希望のある施設のみをスクレイピングする
    for wished_facility in wished_facilities:
        user_id = wished_facility["user_id"]
        message = scrape_avl_from_calender(
            facility_id=wished_facility["facility_id"],
            facility_name=wished_facility["facility_name"],
            user_id=user_id,
            is_manual=False  # 定期実行
        )
        if message:
            messages_each_user.setdefault(user_id, []).append(message)

    # 通知をユーザー単位でまとめて送信
    for user_id, msg_list in messages_each_user.items():
        full_message = "\n\n".join(msg_list)
        notify_user(user_id, full_message)
    
if __name__ == "__main__":
    main()
