from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
load_dotenv()

import os

app = Flask(__name__)


# 環境変数からアクセストークンとシークレットを取得
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# アクセストークンの確認
print("TOKEN:", os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
        print("アクセス成功")
    except InvalidSignatureError:
        abort(400)
        print("アクセス失敗")
    
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    print(f"対象のユーザからメッセージを受信しました。ユーザID : {user_id}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
