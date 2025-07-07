# line_bot_utils

from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
from db_utils import save_followed_userid
from db_utils import get_items_from_db
from db_utils import register_user_selection
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
    text = event.message.text.strip()

    if event.message.text == "希望":
        flex_message = show_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex_message)

@app.route('/api/latest_data', methods=['GET'])
def get_latest_data():
    DB_PATH = '/opt/render/project/src/facility_data.db'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users") 
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

# Flex Messageでリストを表示しユーザに選択させる
def show_selection_flex(items):
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
def handle_postback(event):
    if event.postback.data.startswith("select_item_"):
        item_id = event.postback.data.replace("select_item_", "")
        # 選択されたアイテムをDBに登録する処理
        register_user_selection(event.source.user_id, item_id)


# Flaskアプリ起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)




