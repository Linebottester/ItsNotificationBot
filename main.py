# main.py

from db_utils import create_tables
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender
from db_utils import fetch_wished_facilities
from linebot.models import TextSendMessage
from linebot import LineBotApi
import logging
from dotenv import load_dotenv
import os

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# LINE Bot 認証情報
load_dotenv()
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
if not channel_access_token or not channel_secret:
    raise ValueError("LINEの認証情報が環境変数にありません")

line_bot_api = LineBotApi(channel_access_token)

# サービス起動時に1回だけ実行　各テーブルを作成
create_tables()

def main():
    
    # 施設の名前とURL一覧を取得
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13TjJjVFBrbG1KbFZuYzAxVFp5Vkhkd0YyWWZWR2JuOTJiblpTWjFKSGQ5a0hkdzFXWg%3D%3D&join_date=&night_count=1"
    # "https://linebottester.github.io/kenpo_test_site/test_calendar.html" # テスト用

    # 施設名と施設IDを取得する　毎回見に行くのはナンセンスな気がする　月初めのみに限定すべきか
    #　if isfirst == 1 or datetime.today().day == 1:　#　例えばこんな感じとか
    # isfirst = 0 # 実行後0にする

    facilities = scrape_facility_names_ids(facility_url)
    save_facilities(facilities) #取得してきた施設と施設IDをDBへ保存

    # 希望されている施設IDと名前をDBから取得してきて
    wished_facilities = fetch_wished_facilities()

    # 希望のある施設のみをスクレイピングする
    for wished_facility in wished_facilities:
        result = scrape_avl_from_calender(
            facility_id=wished_facility["facility_id"],
            facility_name=wished_facility["facility_name"],
            user_id=wished_facility["user_id"],
            is_manual=False
        )
        
        # 通知メッセージが返ってきた場合のみ送信
        if result:
            try:
                line_bot_api.push_message(
                    wished_facility["user_id"],
                    TextSendMessage(text=result)
                )
                logger.info(f"[定期通知送信完了] user_id={wished_facility['user_id']} → {wished_facility['facility_name']}")
            except Exception as e:
                logger.error(f"[定期通知失敗] user_id={wished_facility['user_id']} → {e}")
    
if __name__ == "__main__":
    main()
