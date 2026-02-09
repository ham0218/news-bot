import requests
import feedparser
from datetime import datetime, timedelta
import os
from newspaper import Article, Config

# ==========================================
# 1. 설정 및 준비
# ==========================================
NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['DATABASE_ID']

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ==========================================
# 2. 청소부 (3일 지난 뉴스 자동 삭제)
# ==========================================
def delete_old_news():
    print("🧹 [청소] 3일 지난 뉴스를 정리합니다...")
    
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "날짜",
            "date": {"on_or_before": three_days_ago}
        }
    }
    
    response = requests.post(query_url, headers=headers, json=payload)
    results = response.json().get("results", [])

    if not results:
        print("   - 삭제할 오래된 뉴스가 없습니다.")
        return

    for page in results:
        page_id = page["id"]
        requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={"archived": True})
        print(f"   - 🗑️ 삭제됨 (ID: {page_id})")

# ==========================================
# 3. 본문 추출
# ==========================================
def get_full_article(url, summary_fallback=""):
    try:
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        config.request_timeout = 10
        
        article = Article(url, language='ko', config=config)
        article.download()
        article.parse()
        
        if len(article.text) < 50:
            if summary_fallback:
                return f"⚠️ [보안 차단] 기사 본문 스크랩이 막혀 요약본으로 대체합니다.\n\n{summary_fallback}"
            else:
                return "본문 내용을 가져오지 못했습니다. 원문 링크를 확인해주세요."
        return article.text
    except:
        if summary_fallback:
            return f"⚠️ [접속 에러] 본문 대신 요약본을 보여드립니다.\n\n{summary_fallback}"
        return "본문 추출 실패"

# ==========================================
# 4. 노션 업로드 (아이콘 설정 기능 추가됨!)
# ==========================================
def create_page(category, source_name, title, link, date, content, icon_emoji):
    url = "https://api.notion.com/v1/pages"
    
    final_title = f"[{source_name}] {title}"

    if len(content) > 1800:
        content = content[:1800] + "\n...(중략)... (전체 내용은 아래 링크 확인)"

    data = {
        "parent": {"database_id": DATABASE_ID},
        # -----------------------------------------------------
        # [NEW] 여기에 아이콘을 설정하는 코드가 추가되었습니다.
        # -----------------------------------------------------
        "icon": {
            "type": "emoji",
            "emoji": icon_emoji
        },
        "properties": {
            "이름": {"title": [{"text": {"content": final_title}}]},
            "URL": {"url": link},
            "날짜": {"date": {"start": date}},
            "카테고리": {"select": {"name": category}}
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": "기사 내용"}}],
                    "icon": {"emoji": "📰"},
                    "color": "gray_background"
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": content}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": "👉 원문 전체 보러가기: " + link, "link": {"url": link}}}]
                }
            }
        ]
    }
    requests.post(url, headers=headers, json=data)

# ==========================================
# 5. 메인 실행
# ==========================================
delete_old_news()

print("\n📰 [뉴스 수집 시작] 아이콘까지 예쁘게 붙여서 가져옵니다...")

targets = [
    # --- 미국 주식 (성조기) ---
    {
        "category": "미국주식",
        "source": "한경글로벌",
        "rss": "https://rss.hankyung.com/feed/international",
        "icon": "🇺🇸" 
    },
    {
        "category": "미국주식",
        "source": "인베스팅",
        "rss": "https://kr.investing.com/rss/news_285.rss",
        "icon": "🇺🇸"
    },
    
    # --- 국내 주식 (태극기) ---
    {
        "category": "국내주식",
        "source": "한국경제",
        "rss": "https://rss.hankyung.com/feed/stock",
        "icon": "🇰🇷"
    },
    {
        "category": "국내주식",
        "source": "매일경제",
        "rss": "https://www.mk.co.kr/rss/50200011/",
        "icon": "🇰🇷"
    },

    # --- 코인 (동전) ---
    {
        "category": "코인",
        "source": "코인데스크",
        "rss": "https://www.tokenpost.kr/rss",
        "icon": "🪙"
    }
]

for target in targets:
    category = target["category"]
    source = target["source"]
    rss_url = target["rss"]
    icon = target["icon"] # 아이콘 정보 가져오기
    
    print(f"\n🔎 [{category} - {source}] 뉴스 가져오는 중...")
    
    try:
        feed = feedparser.parse(rss_url)
        count = 0
        MAX_ARTICLES = 4 
        
        for entry in feed.entries:
            if count >= MAX_ARTICLES:
                break
                
            if hasattr(entry, 'published_parsed'):
                dt = datetime(*entry.published_parsed[:6]).isoformat()
            else:
                dt = datetime.now().isoformat()
            
            summary_fallback = entry.get('description', '').replace('<p>', '').replace('</p>', '').replace('<br>', '\n')

            full_text = get_full_article(entry.link, summary_fallback)
            
            # create_page 함수에 icon 정보도 같이 넘겨줍니다!
            create_page(category, source, entry.title, entry.link, dt, full_text, icon)
            
            print(f"   ✅ 저장 완료: {icon} [{source}] {entry.title}")
            
            count += 1

    except Exception as e:
        print(f"   ❌ {source} 에러: {e}")

print("\n🎉 모든 뉴스 배달 완료! 노션을 확인해보세요.")
