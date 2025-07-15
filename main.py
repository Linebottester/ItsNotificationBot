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
            logger.info(f"[通知準備] user_id={user_id} → メッセージ: {combined}")  # ← 追加
            try:
                response = line_bot_api.push_message(user_id, TextSendMessage(text=combined))
                logger.info(f"[通知送信成功] user_id={user_id}, 件数: {len(messages)}")
            except Exception as e:
                logger.error(f"[通知送信失敗] user_id={user_id}: {e}")
    else:
        logger.info("[定期実行] user_notificationsにメッセージが1件も入っていません")

    
if __name__ == "__main__":
    main()
