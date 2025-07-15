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
    
    # 施設の名前とURL一覧を取得
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13TjJjVFBrbG1KbFZuYzAxVFp5Vkhkd0YyWWZWR2JuOTJiblpTWjFKSGQ5a0hkdzFXWg%3D%3D&join_date=&night_count=1"
    # "https://linebottester.github.io/kenpo_test_site/test_calendar.html" # テスト用

    # 施設名と施設IDを取得する　毎回見に行くのはナンセンスな気がする　月初めのみに限定すべきか

    facilities = scrape_facility_names_ids(facility_url)
    save_facilities(facilities) #取得してきた施設と施設IDをDBへ保存

    # 希望されている施設IDと名前をDBから取得してきて
    wished_facilities = fetch_wished_facilities()

    notifications = []
    # 希望のある施設のみをスクレイピングする
    for wished_facility in wished_facilities:
        result = scrape_avl_from_calender(
            facility_id=wished_facility["facility_id"],
            facility_name=wished_facility["facility_name"],  # 通知、ロガーなどに使うので引数として渡しておく
            user_id=wished_facility["user_id"]        
        )
        
        notifications.append(result)

        from line_bot_server import stack_notify  # ImportError対策
        stack_notify(notifications)

if __name__ == "__main__":
    main()
