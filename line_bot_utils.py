# line_bot_utils

from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent
from linebot.models import  TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent, PostbackAction
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    FlexSendMessage,
    QuickReply,
    QuickReplyButton,
    PostbackAction
)

from db_utils import save_followed_userid
from db_utils import get_items_from_db
from db_utils import register_user_selection
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
import requests
import sqlite3
import os
import json
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flaskアプリケーション初期化
app = Flask(__name__)

# 環境変数からアクセストークンとシークレットを取得
load_dotenv()
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("LINE_CHANNEL_SECRET")

if channel_access_token is None or channel_secret is None:
    logger.error("環境変数が正しく設定されていません")
    raise ValueError("LINEのトークンとシークレットが必要です")

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

logger.info(f"TOKEN: {channel_access_token}")
logger.info(f"SECRET: {channel_secret}")

# Renderのルート確認用（ヘルスチェック用途）
@app.route("/", methods=["GET"])
def index():
    return "LINE Bot is running!", 200

# webhookからリクエストが来たときの受け口
@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    logger.info("=== WEBHOOK DEBUG ===")
    logger.info(f"受信ボディ: {body}")
    logger.info(f"署名: {signature}")

    try:
        body_json = json.loads(body)
        logger.info(f"パースされたJSON: {json.dumps(body_json, indent=2, ensure_ascii=False)}")
    except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
    try:
        handler.handle(body, signature)
        logger.info("ハンドラー処理成功")
    except InvalidSignatureError:
        logger.error("署名検証失敗")
        abort(400)
    except Exception as e:
        logger.error(f"ハンドラーエラー: {e}")
        abort(500)

    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    logger.info("=== FOLLOW EVENT HANDLER ===")
    logger.info("フォローイベントが検出されました")

    try:
        user_id = event.source.user_id
        logger.info(f"ユーザーID: {user_id}")

        reply_message = "フォローありがとうございます！\nUserIDを取得しました😊\n通知登録したいときは「希望」と入力してください。"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message)
        )
        logger.info("フォロー返信送信完了")

        save_followed_userid(user_id)

    except Exception as e:
        logger.error(f"フォロー処理エラー: {e}")

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 「希望」と入力されたら施設選択メニューを送信
    if text == "希望":
        flex_message = show_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex_message)
        return
    
    # 日付入力判定
    try:
        from datetime import datetime, date

        parsed_date = datetime.strptime(text, "%m月%d日").date()
        parsed_date = parsed_date.replace(year=date.today().year)

        today = date.today()
        end_date = date(today.year, 9, 30)

        if today <= parsed_date <= end_date:
            facility_id = temporary_selection.get(user_id)
            if facility_id:
                register_user_selection(user_id, facility_id, parsed_date.isoformat())
                reply = f"{parsed_date.strftime('%-m月%-d日')} に希望を登録しました！"
            else:
                reply = "施設が未選択のようです。もう一度「希望」と入力してください。"
        else:
            reply = "指定できるのは今日から翌々月の最終日までの日付です。"

    except ValueError:
        reply = "日付の形式が正しくありません。\n例：「8月15日」のように入力してください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route('/api/latest_data', methods=['GET'])
def get_latest_data():
    DB_PATH = '/opt/render/project/src/facility_data.db'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users") 
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@handler.add(PostbackEvent)
def on_postback(event):
    handle_postback(event)


# Flex Messageでリストを表示しユーザに選択させる
def show_selection_flex():
    items = get_items_from_db()

    contents = []
    for item in items:
        contents.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": item['name'],
                "data": f"select_item_{item['id']}"
            },
            "style": "secondary"
        })
    
    return FlexSendMessage(
        alt_text="選択してください",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "項目を選択してください",
                        "weight": "bold",
                        "size": "lg"
                    }
                ] + contents
            }
        }
    )

# Postback受信時の処理
@handler.add(PostbackEvent)
def on_postback(event):
    data = event.postback.data

    if data.startswith("select_date_"):from datetime import date, timedelta

# ユーザーごとの一時記憶（本番ではDBやRedisが望ましい）
temporary_selection = {}

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    user_id = event.source.user_id

    if data.startswith("select_item_"):
        item_id = data.replace("select_item_", "")
        temporary_selection[user_id] = item_id

        today = date.today()
        reply_options = []
        for offset in range(0, 5):
            day = today + timedelta(days=offset * 7)
            label = day.strftime("%-m月%-d日")
            reply_options.append(QuickReplyButton(
                action=PostbackAction(label=label, data=f"select_date_{day.isoformat()}")
            ))

        message = TextSendMessage(
            text="いつ希望しますか？",
            quick_reply=QuickReply(items=reply_options)
        )
        line_bot_api.reply_message(event.reply_token, message)

    elif data.startswith("select_date_"):
        wish_date = data.replace("select_date_", "")
        facility_id = temporary_selection.get(user_id)

        if facility_id:
            register_user_selection(user_id, facility_id, wish_date)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{wish_date} に希望を登録しました！")
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="施設情報が見つかりませんでした。")
            )

# Flaskアプリ起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)




