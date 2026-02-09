import requests
import feedparser
from datetime import datetime
import os

# 깃허브 시크릿에서 키 가져오기
NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['DATABASE_ID']

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_page(category, title, link, date):
    url = "https://api.notion.com/v1/pages"
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": title}}]},
            "URL": {"url": link},
            "날짜": {"date": {"start": date}},
            "카테고리": {"select": {"name": category}}
        }
    }
    res = requests.post(url, headers=headers, json=data)
    if res.status_code != 200:
        print(f"에러 발생: {res.status_code} {res.text}")

# 뉴스 및 캘린더 RSS 주소
rss_list = {
    "국내주식": "https://news.google.com/rss/search?q=국내주식+OR+코스피&hl=ko&gl=KR&ceid=KR:ko",
    "미국주식": "https://news.google.com/rss/search?q=미국주식+OR+나스닥&hl=ko&gl=KR&ceid=KR:ko",
    "코인": "https://news.google.com/rss/search?q=비트코인+OR+암호화폐&hl=ko&gl=KR&ceid=KR:ko",
    "경제캘린더": "https://www.tokenpost.kr/rss/calendar"
}

print("--- 뉴스 수집 시작 ---")
for category, rss in rss_list.items():
    try:
        feed = feedparser.parse(rss)
        for entry in feed.entries[:3]: # 각 주제별 최신 3개만
            try:
                dt = datetime(*entry.published_parsed[:6]).isoformat()
            except:
                dt = datetime.now().isoformat()

            create_page(category, entry.title, entry.link, dt)
            print(f"[{category}] 저장: {entry.title}")
    except Exception as e:
        print(f"[{category}] 처리 중 오류: {e}")
print("--- 수집 완료 ---")
