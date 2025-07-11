# scraper.py

from bs4 import BeautifulSoup
from db_utils import parse_and_notify_available_dates
from urllib.parse import quote
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
import logging
import requests

# ロガー設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def scrape_facility_names_ids(url):
    logger.info(f'施設名、施設ID取得スクレイピング開始:{url}')
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info('ページの取得に成功しました')
    except requests.RequestException as e:
        logger.error(f'ページ取得エラー:{e}')
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    facilities = []

    logger.info('施設情報の抽出を開始します')
    for li in soup.select('ul#top_tabs > li'):
        href = li.get('data-href')
        span = li.find('span')
        if href and span:
            match = re.search(r's=([A-Za-z0-9]+)', href)
            facility_id = match.group(1) if match else None
            facility_name = span.text.strip()
            logger.debug(f'抽出された施設: ID={facility_id}, 名前={facility_name}')
            facilities.append({'id': facility_id, 'name': facility_name})
        else:
            logger.warning('不完全な<li>要素が検出されました。')
        
    logger.info(f'抽出完了: {len(facilities)} 件の施設を取得しました')
    return facilities

def scrape_avl_from_calender(facility_id, facility_name, user_id):
    logger.info(f"[関数呼び出し] scrape_avl_from_calender → facility_id={facility_id}, name={facility_name}, user_id={user_id}")
    
    today = datetime.now()
    base_date = today.replace(day=1)
    all_available_dates = set()  # 重複排除のため set を使用

    for i in range(3):
        first_day = base_date + relativedelta(months=i)
        target_year = first_day.year
        target_month = first_day.month

        logger.info(f"[{facility_name}] {target_year}年{target_month}月 スクレイピング開始")
        
        base_url = "https://linebottester.github.io/kenpo_test_site/test_calendar.html" # !!!!!test用!!!!!
                # base_url = "https://as.its-kenpo.or.jp/apply/empty_calendar" # 本番用
                # https://as.its-kenpo.or.jp/apply/calendar3 # こちらでは認証ページに遷移してしまう

                # Urlの変数部分を定義する　パラメータがすべて空だと保養施設の案内ページに行く
        params = {
            's': facility_id, #　各施設のID（と思しき変数）# テスト時はずす
            # 'join_date': first_day.strftime("%Y-%m-%d"), 
            'join_date': first_day,#'2025-07-01', # スクレイピングを行う月を指定する,空の時は今月を見に行くようだ
            'night_count':'' # 泊数をしているようだが効いていないように見える
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            logger.info(f"{target_year}年{target_month}月の施設名:{facility_name}, 施設ID:{facility_id}に対するページ取得成功")
            soup = BeautifulSoup(response.content, "html.parser")

            # 月単位の空き日を抽出し、重複排除セットに追加
            dates = extract_available_dates(soup, facility_id)
            all_available_dates.update(dates)

        except requests.RequestException as e:
            logger.error(f"{target_year}年{target_month}月の施設名:{facility_name}, 施設ID:{facility_id} の取得に失敗: {e}")

    # 全体の空き日をまとめて通知
    if all_available_dates:
        notify_user_about_dates(sorted(all_available_dates), facility_name, facility_id, user_id)
    else:
        logger.info(f"{facility_id} に空き日程はありません")

def extract_available_dates(soup, facility_id):
    logger = logging.getLogger(__name__)
    available_dates = []

    for td in soup.find_all("td", attrs={"data-join-time": True, "data-night-count": "1"}):
        status_icon = td.find("span", class_="icon")
        if status_icon:
            status_text = status_icon.get_text(strip=True)
            join_date = td["data-join-time"]
            if status_text != "☓":
                logger.info(f"空きあり: {facility_id} {join_date} 状態: {status_text}")
                available_dates.append(join_date)
            else:
                logger.debug(f"満室: {facility_id} {join_date} 状態: {status_text}")
    return available_dates

def notify_user_about_dates(date_list, facility_name, facility_id, user_id):
    from line_bot_server import notify_user
    logger = logging.getLogger(__name__)

    formatted_dates = []
    for date_str in date_list:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = "月火水木金土日"[dt.weekday()]
        formatted_dates.append(f"{dt.month}月{dt.day}日（{weekday}）")

    notify_text = f"{facility_name}の次の日程に空きがあります。\n" + "、".join(formatted_dates)
    notify_user(user_id, notify_text)
    logger.info(f"{facility_id} に空き通知を送信 → {notify_text}")



        