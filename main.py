# main.py

from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
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
    
if __name__ == "__main__":
    main()