# main.py

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from db_utils import save_facilities, fetch_wished_facilities
from scraper import scrape_facility_names_ids, scrape_avl_from_calender
from linebot import LineBotApi
from linebot.models import TextSendMessage

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# LINE Bot API 初期化
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def main():
    facility_url = "https://as.its-kenpo.or.jp/apply/empty_calendar?s=PT13T..."  # ←フルURLをここに貼ってください

    facilities = scrape_facility_names_ids(facility_url)
    save_facilities(facilities)
    wished_facilities = fetch_wished_facilities()

    user_notifications = {}

    for wished in wished_facilities:
        user_id = wished["user_id"]
        msg = scrape_avl_from_calender(
            facility_id=wished["facility_id"],
            facility_name=wished["facility_name"],
            user_id=user_id,
            is_manual=False
        )
        if msg:
            user_notifications.setdefault(user_id, []).append(msg)

    if user_notifications:
        for user_id, messages in user_notifications.items():
            combined = "\n\n".join(messages)
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=combined))
                logger.info(f"[定期通知] user_id={user_id} に送信成功: {len(messages)}件")
            except Exception as e:
                logger.error(f"[通知失敗] user_id={user_id}: {e}")
    else:
        logger.info("[定期実行] 空き無し。通知は行われません")

    
if __name__ == "__main__":
    main()
