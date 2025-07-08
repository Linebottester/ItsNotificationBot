#line_bot_server.py

from flask import Flask, request, jsonify, abort
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from main import main
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, QuickReply, QuickReplyButton,
    PostbackEvent, PostbackAction, FollowEvent
)
from linebot.exceptions import InvalidSignatureError

from db_utils import (
    get_items_from_db, save_followed_userid,
    register_user_selection
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

temporary_selection = {} #　希望入力時、一時的に記憶するための変数

# SQLite DB 接続関数
def get_db_connection(db_name="facility_data.db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, db_name)
    logger.info(f"[DB接続] パス: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# main.py定期実行用関数
def periodic_check():
    while True:
        try:
            main()  # ← これで定期実行される！
            print("定期スクレイピングが実行されました")
        except Exception as e:
            print(f"定期処理エラー: {e}")
        # time.sleep(8 * 60 * 60)  # 8時間待つ
        time.sleep(60)  # 60秒待つ（テスト用）


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
        TextSendMessage(text="フォローありがとうございます！希望施設があれば「希望」と送ってください😊")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "希望":
        flex = show_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex)
        return

    try:
        parsed_date = datetime.strptime(text, "%m月%d日").date().replace(year=date.today().year)
        if parsed_date < date.today():
            raise ValueError("過去の日付")

        facility_id = temporary_selection.get(user_id)
        if facility_id:
            register_user_selection(user_id, facility_id, parsed_date.isoformat())
            reply = f"{parsed_date.strftime('%-m月%-d日')} に希望を登録しました！"
        else:
            reply = "施設がまだ選択されていません。「希望」と入力して選んでください。"

    except ValueError:
        reply = "日付の形式が正しくありません。例：「8月5日」のように入力してください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    if data.startswith("select_item_"):
        facility_id = data.replace("select_item_", "")
        temporary_selection[user_id] = facility_id

        today = date.today()
        options = [
            QuickReplyButton(action=PostbackAction(label=(today + timedelta(days=i)).strftime("%-m月%-d日"),
                                                   data=f"select_date_{(today + timedelta(days=i)).isoformat()}"))
            for i in range(5)
        ]
        msg = TextSendMessage(text="いつ希望しますか？", quick_reply=QuickReply(items=options))
        line_bot_api.reply_message(event.reply_token, msg)

    elif data.startswith("select_date_"):
        wish_date = data.replace("select_date_", "")
        facility_id = temporary_selection.get(user_id)
        if facility_id:
            register_user_selection(user_id, facility_id, wish_date)
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{wish_date} に希望を登録しました！"))
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="施設情報が見つかりませんでした。"))

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
        alt_text="項目を選択してください",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "項目を選択してください", "weight": "bold", "size": "lg"}
                ] + contents
            }
        }
    )
# 定期実行スレッドの起動
threading.Thread(target=periodic_check, daemon=True).start()

# Flask起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)