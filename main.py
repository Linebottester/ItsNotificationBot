from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
load_dotenv()

import os
import json
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 環境変数からアクセストークンとシークレットを取得
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# アクセストークンの確認
logger.info(f"TOKEN: {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}")
logger.info(f"SECRET: {os.getenv('LINE_CHANNEL_SECRET')}")

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    
    # デバッグ情報を追加
    logger.info("=== WEBHOOK DEBUG ===")
    logger.info(f"受信ボディ: {body}")
    logger.info(f"署名: {signature}")
    
    # JSONとしてパース可能かチェック
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    logger.info("=== MESSAGE EVENT HANDLER ===")
    logger.info("イベントハンドラーが呼び出されました")
    
    try:
        user_id = event.source.user_id
        user_message = event.message.text
        logger.info(f"ユーザーID: {user_id}")
        logger.info(f"メッセージ: {user_message}")
        
        # 返信を送信
        reply_message = f"受信しました：{user_message}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message)
        )
        logger.info("返信送信完了")
        
    except Exception as e:
        logger.error(f"メッセージ処理エラー: {e}")

# 全てのイベントをキャッチするハンドラー（デバッグ用）
@handler.default()
def default_handler(event):
    logger.info("=== DEFAULT HANDLER ===")
    logger.info("デフォルトハンドラーが呼び出されました")
    logger.info(f"イベントタイプ: {type(event)}")
    logger.info(f"イベント内容: {event}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"サーバー起動中... ポート: {port}")
    app.run(host="0.0.0.0", port=port, debug=True)