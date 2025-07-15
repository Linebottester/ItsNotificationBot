# main.py

from db_utils import create_tables
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender
from linebot.models import TextSendMessage
from linebot import LineBotApi

import os
import logging

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# アクセストークンを環境変数から取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

# インスタンス生成
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

# サービス起動時に1回だけ実行　各テーブルを作成
# create_tables()

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
    
    # 通知をまとめるためのリスト
    notifications = []
    
    # 希望のある施設のみをスクレイピングする
    for wished_facility in wished_facilities:
        notification = scrape_avl_from_calender(
            facility_id=wished_facility["facility_id"],
            facility_name=wished_facility["facility_name"],  # 通知、ロガーなどに使うので引数として渡しておく
            user_id=wished_facility["user_id"],
            is_manual=False     
        )
        # 通知内容がある場合のみリストに追加
        if notification:
            notifications.append(notification)
    
    # 通知がある場合のみLINEで送信（空きがない場合は通知しない）
    if notifications:
        combined = "\n\n".join(notifications)
        # 各ユーザーに通知を送信
        user_ids = list(set([facility["user_id"] for facility in wished_facilities]))
        for user_id in user_ids:
            line_bot_api.push_message(user_id, TextSendMessage(text=combined))
        logger.info(f"定期実行で通知を送信しました: {len(notifications)}件")
    else:
        logger.info("定期実行: 通知すべき空きはありませんでした")
    
if __name__ == "__main__":
    main()
