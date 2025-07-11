#line_bot_server.py

from flask import Flask, request, jsonify
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from main import main
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, PostbackEvent, FollowEvent
)
from linebot.exceptions import InvalidSignatureError
from scraper import scrape_avl_from_calender
from db_utils import (
    get_items_from_db, save_followed_userid,
    register_user_selection,fetch_wished_facilities
)

import threading
import time
import os
import logging
import sqlite3


# Flask アプリ作成
app = Flask(__name__)

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# LINE Bot 認証情報
load_dotenv()
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
if not channel_access_token or not channel_secret:
    raise ValueError("LINEの認証情報が環境変数にありません")

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# SQLite DB 接続関数
def get_db_connection(db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)
    logger.info(f"[DB接続] パス: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# main.py定期実行用関数 開発中につき停止
"""
def periodic_check():
    while True:
        try:
            main() 
            Logger.info("定期スクレイピングが実行されました")
        except Exception as e:
            Logger.error(f"定期処理エラー: {e}")
        time.sleep(8 * 60 * 60)  # 8時間待つ
        # time.sleep(60)  # 60秒待つ（テスト用）

# 定期実行スレッドの起動
threading.Thread(target=periodic_check, daemon=True).start()
"""

# 共通エンドポイント：ヘルスチェック
@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "LINE Bot & DB API が稼働中です！"})

# DB管理エンドポイント群
@app.route("/tables")
def list_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row["name"] for row in cursor.fetchall()]
        return jsonify({"tables": tables})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()

@app.route("/table/<table_name>")
def show_table_contents(table_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        return jsonify({"data": [dict(row) for row in rows]})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()

# LINE Webhook 受信
@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    logger.info(f"[Webhook] 受信Body:\n{body}")
    try:
        handler.handle(body, signature)
        return "OK"
    except InvalidSignatureError:
        logger.error("[Webhook] 署名検証失敗")
        return "Invalid signature", 400
    except Exception as e:
        logger.error(f"[Webhook] ハンドラーエラー: {e}")
        return "Error", 500

# LINE Botイベントハンドラ
@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    save_followed_userid(user_id)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="フォローありがとうございます！希望施設を登録したいときは「希望」、\n予約状況を確認したいときは「確認」と送ってください😊")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "希望":
        flex = show_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex)
        return

    if text == "確認":
        try:
            wished_facilities = fetch_wished_facilities()
            for wished_facility in wished_facilities:
                scrape_avl_from_calender(
                    facility_id=wished_facility["facility_id"],
                    facility_name=wished_facility["facility_name"],
                    user_id=wished_facility["user_id"]
                )
            logger.info("手動スクレイピングが実行されました")
        except Exception as e:
            logger.error(f"手動処理エラー: {e}")
        return

    # どちらにも当てはまらない場合
    reply = "施設を選ぶには「希望」、予約状況を確認するには「確認」と入力してください。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    if data.startswith("select_item_"):
        facility_id = data.replace("select_item_", "")
        facility_name = next((item["name"] for item in get_items_from_db() if item["id"] == facility_id), None)
        register_user_selection(user_id, facility_id)
        logger.info(f"[希望登録完了] user={user_id}, facility={facility_id}")
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=f"{facility_name} を予約希望施設として登録しました！"))

# Flex Message生成
def show_selection_flex():
    items = get_items_from_db()
    contents = [{
        "type": "button",
        "action": {
            "type": "postback",
            "label": item["name"],
            "data": f"select_item_{item['id']}"
        },
        "style": "secondary"
    } for item in items]

    return FlexSendMessage(
        alt_text="希望の施設を選択してください",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "希望の施設を選択してください", "weight": "bold", "size": "lg"}
                ] + contents
            }
        }
    )

# 通知希望者に通知を送る
def notify_user(user_id: str, message: str):
    logger = logging.getLogger(__name__)
    logger.info(f"notify_user() 呼び出し: user_id={user_id}, message={message}")

    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not access_token:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN が未設定または空です")
        return

    try:
        line_bot_api = LineBotApi(access_token)
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
        logger.info(f"通知送信完了: user_id={user_id}")
    except Exception as e:
        logger.error(f"LINE通知送信エラー: {e}")

# Flask起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)