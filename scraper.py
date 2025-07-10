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

def scrape_avl_from_calender(facility_id, facility_name, user_id): # avl=availabilityの略　綴りミスが多いため
    logger.info(f"[関数呼び出し] scrape_avl_from_calender → facility_id={facility_id}, name={facility_name}, user_id={user_id}")
    
    # 今月、翌月、翌々月の３回転する
    today = datetime.now()
    base_date = today.replace(day=1)

    for i in range(3):
        first_day = base_date + relativedelta(months=i)
        target_year = first_day.year
        target_month = first_day.month

        logger.info(f"[{facility_name}] {target_year}年{target_month}月 スクレイピング開始")

        base_url = "https://linebottester.github.io/kenpo_test_site/test_calendar.html" # !!!!!test用!!!!!
        # base_url = "https://as.its-kenpo.or.jp/apply/empty_calendar" # 本番用
        # https://as.its-kenpo.or.jp/apply/calendar3 # こちらでは認証ページに遷移してしまう

        # Urlの変数部分を定義する　パラメータがすべて空だと保養施設の案内ページに行く # テスト時はずす
        params = {
            's': facility_id, #　各施設のID（と思しき変数）# テスト時はずす
            'join_date': first_day.strftime("%Y-%m-%d"), 
            #'join_date': first_day,#'2025-07-01', # スクレイピングを行う月を指定する,空の時は今月を見に行くようだ
            'night_count':'' # 泊数をしているようだが効いていないように見える
        }

        # 施設ID例
        # s=PUlqTjMwRFpwWlNaMUpIZDlrSGR3MVda 草津温泉　ホテルヴィレッジ
        # s=PWdqTjMwRFpwWlNaMUpIZDlrSGR3MVda ホテル琵琶レイクオーツカ
        # s=PUF6TjMwRFpwWlNaMUpIZDlrSGR3MVda ホテルハーヴェスト南紀田辺

        try:
            response = requests.get(base_url, params=params) #!!!!! test用 !!!!!
            #response = requests.get(base_url, params=params) #本番用
            response.raise_for_status()
            logger.info(f"{target_year}年{target_month}月の施設名:{facility_name}, 施設ID:{facility_id}に対するページ取得成功")
            soup = BeautifulSoup(response.content,"html.parser")

            # 抽出したsoupをdb_utils側の関数に渡して処理を投げる
            parse_and_notify_available_dates(soup, facility_id)
            

        except requests.RequestException as e:
            logging.error(f"{target_year}年{target_month}月の施設名:{facility_name}, 施設ID: {facility_id} の取得に失敗: {e}")

        