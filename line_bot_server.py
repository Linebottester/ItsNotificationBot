#line_bot_server.py

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from main import main
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, PostbackEvent, FollowEvent, UnfollowEvent
)
from linebot.exceptions import InvalidSignatureError
from scraper import scrape_avl_from_calender
from db_utils import (
    get_items_from_db, save_followed_userid,
    register_user_selection,fetch_wished_facilities,
    remove_user_from_db,cancell_user_selection,
    fetch_user_wished_facilities_for_cancel
)

import os
import logging
import threading
import time


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

# main.py定期実行用関数
def periodic_check():
    while True:
        try:
            main() 
            logger.info("定期スクレイピングが実行されました")
        except Exception as e:
            logger.error(f"定期処理エラー: {e}")
        time.sleep(8 * 60 * 60)  # 8時間待つ
        # time.sleep(60)  # 60秒待つ（テスト用）

# 定期実行スレッドの起動
threading.Thread(target=periodic_check, daemon=True).start()


# 共通エンドポイント：ヘルスチェック
@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "LINE Bot & DB API が稼働中です！"})

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
    try:
        user_id = event.source.user_id
        save_followed_userid(user_id)
        
        welcome_message = (
            "フォローありがとうございます！\n"
            "希望施設を登録したいときは「希望」、\n"
            "予約状況を確認したいときは「確認」と送ってください😊"
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_message)
        )
        
    except Exception as e:
        logger.error(f"フォローイベント処理エラー: {e}")
        # エラー時の応答
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="申し訳ございません。エラーが発生しました。")
        )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "希望":
        flex = show_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex)
        return
    
    if text == "解除":
    
        wished_facilities = wished_facilities = fetch_user_wished_facilities_for_cancel(user_id)
        if not wished_facilities:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="解除できる施設がありません。「希望」と入力して登録をおこなってください"))
            return

        flex = show_cancell_flex(wished_facilities)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    if text == "確認":
        try:
            wished_facilities = fetch_wished_facilities()
            if not wished_facilities:
                reply = "希望施設が登録されていません。先に「希望」と入力して登録をしてください。"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return

            notifications = []
            for wished_facility in wished_facilities:
                notification = scrape_avl_from_calender(
                    facility_id=wished_facility["facility_id"],
                    facility_name=wished_facility["facility_name"],
                    user_id=wished_facility["user_id"],
                    is_manual=True
                )
                if notification:
                    notifications.append(notification)
            if notifications:
                combined = "\n\n".join(notifications)
            else:
                combined = "希望施設に空きはありませんでした。"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=combined))
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
            TextSendMessage(text=f"{facility_name} を予約希望施設として登録しました！\n続けて確認したいときは「確認」と入力してください"))
        
    if data.startswith("cancel_item_"):
        facility_id = data.replace("cancel_item_", "")
        facility_name = next((item["name"] for item in get_items_from_db() if item["id"] == facility_id), None)
        cancell_user_selection(user_id, facility_id)
        logger.info(f"[希望解除完了] user={user_id}, facility={facility_id}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{facility_name} を希望リストから解除しました\n通知は届かなくなるのでご注意ください"))
            

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

def show_cancell_flex(wished_facilities):
    contents = [{
        "type": "button",
        "action": {
            "type": "postback",
            "label": item["facility_name"],
            "data": f"cancel_item_{item['facility_id']}"
        },
        "style": "primary",
        "color": "#FF6666"
    } for item in wished_facilities]

    return FlexSendMessage(
        alt_text="登録解除する施設を選択してください",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "登録解除する施設を選んでください", "weight": "bold", "size": "lg"}
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

# フォローを外した（ブロック）ユーザのデータを消す
@handler.add(UnfollowEvent)
def handle_unfollow(event):
    user_id = event.source.user_id
    logger.info(f"UnfollowEvent 受信: user_id={user_id}")

    # DBからユーザー情報を削除する処理をここに書く
    remove_user_from_db(user_id)


# Flask起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)