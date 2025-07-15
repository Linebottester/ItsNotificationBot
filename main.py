# main.py

from db_utils import create_tables
from db_utils import save_facilities
from db_utils import fetch_wished_facilities
from scraper import scrape_facility_names_ids
from scraper import scrape_avl_from_calender_unified

import logging

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# サービス起動時に1回だけ実行　各テーブルを作成
create_tables()

def main():
    # 必要なimportを追加
    from collections import defaultdict
    
    # 施設の名前とURL一覧を取得
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13TjJjVFBrbG1KbFZuYzAxVFp5Vkhkd0YyWWZWR2JuOTJiblpTWjFKSGQ5a0hkdzFXWg%3D%3D&join_date=&night_count=1"

    facilities = scrape_facility_names_ids(facility_url)
    save_facilities(facilities) #取得してきた施設と施設IDをDBへ保存

    # 希望されている施設IDと名前をDBから取得してきて
    wished_facilities = fetch_wished_facilities()

    # ユーザーごとに結果をまとめるための辞書
    user_results = defaultdict(list)

    # 希望のある施設のみをスクレイピングする
    for wished_facility in wished_facilities:
        result = scrape_avl_from_calender_unified(  # 新しい関数を使用
            facility_id=wished_facility["facility_id"],
            facility_name=wished_facility["facility_name"],
            user_id=wished_facility["user_id"]        
        )
        
        # 結果をユーザーごとに集約
        user_results[wished_facility["user_id"]].append(result)

    # ユーザーごとにまとめて通知を送信
    for user_id, results in user_results.items():
        send_unified_notification(user_id, results)

def send_unified_notification(user_id, results):
    """ユーザーごとに統合された通知を送信"""
    from line_bot_server import notify_user
    from datetime import datetime
    
    available_facilities = []
    no_availability_facilities = []
    
    for result in results:
        if result['available_dates']:
            available_facilities.append(result)
        else:
            no_availability_facilities.append(result)
    
    # 通知メッセージを構築
    if available_facilities:
        message_parts = [" 予約可能な日程をお知らせします！\n"]
        
        for facility_result in available_facilities:
            facility_name = facility_result['facility_name']
            facility_id = facility_result['facility_id']
            date_list = facility_result['available_dates']
            
            # 日付をフォーマット
            formatted_dates = []
            for date_str in date_list:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                weekday = "月火水木金土日"[dt.weekday()]
                formatted_dates.append(f"{dt.month}月{dt.day}日（{weekday}）")
            
            message_parts.append(f" {facility_name}")
            message_parts.append("   " + "、".join(formatted_dates))
            
            calendar_url = f"https://as.its-kenpo.or.jp/apply/empty_calendar?s={facility_id}"
            message_parts.append(f"   予約ページ：{calendar_url}\n")
        
        # 空きがない施設がある場合は追記
        if no_availability_facilities:
            message_parts.append("※以下の施設は現在予約可能な日程がありません：")
            for facility_result in no_availability_facilities:
                message_parts.append(f"  • {facility_result['facility_name']}")
        
        notify_text = "\n".join(message_parts)
        
    else:
        # 全ての施設で空きがない場合
        facility_names = [result['facility_name'] for result in no_availability_facilities]
        notify_text = f"現在、以下の施設には予約可能な日程がありません：\n" + "\n".join([f"• {name}" for name in facility_names])
    
    notify_user(user_id, notify_text)
    logger.info(f"統合通知を送信 user_id={user_id}")
    
if __name__ == "__main__":
    main()
