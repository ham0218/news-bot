import requests
import feedparser
from datetime import datetime, timedelta
import os
from newspaper import Article, Config

# ==========================================
# 1. 기본 설정
# ==========================================
NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['DATABASE_ID']

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ==========================================
# 2. [청소부] 3일 지난 뉴스 자동 삭제
# ==========================================
def delete_old_news():
    print("🧹 [청소 시작] 3일 지난 뉴스를 정리합니다...")
    
    # 오늘 날짜 기준 3일 전 계산
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    
    # 노션에 쿼리: 날짜가 3일 전(포함)보다 과거인 것들
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "날짜",
            "date": {
                "on_or_before": three_days_ago
            }
        }
    }
    
    response = requests.post(query_url, headers=headers, json=payload)
    results = response.json().get("results", [])

    if not results:
        print("   - 삭제할 오래된 뉴스가 없습니다. (깨끗함)")
        return

    for page in results:
        page_id = page["id"]
        # 휴지통으로 보내기 (Archive)
        delete_url = f"https://api.notion.com/v1/pages/{page_id}"
        requests.patch(delete_url, headers=headers, json={"archived": True})
        print(f"   - 🗑️ 삭제 완료 (ID: {page_id})")

# ==========================================
# 3. [본문 추출] 신문 기사 내용 긁어오기
# ==========================================
def get_full_article(url):
    try:
        # 봇 차단 방지용 설정
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'
        config.request_timeout = 10

        article = Article(url, language='ko', config=config)
        article.download()
        article.parse()
        
        # 본문이 너무 짧으면(로그인 필요 등) 에러 메시지
        if len(article.text) < 50:
            return "본문 보안 설정으로 내용을 가져오지 못했습니다. 원문 링크를 확인해주세요."
        return article.text
    except Exception as e:
        return "본문 추출 중 에러가 발생했습니다."

# ==========================================
# 4. [업로드] 노션에 예쁘게 글쓰기
# ==========================================
def create_page(category, title, link, date, content):
    url = "https://api.notion.com/v1/pages"
    
    # 노션 글자수 제한(2000자) 고려해서 자르기
    if len(content) > 1800:
        content = content[:1800] + "\n\n...(중략)... (전체 내용은 아래 링크 확인)"

    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": title}}]},
            "URL": {"url": link},
            "날짜": {"date": {"start": date}},
            "카테고리": {"select": {"name": category}}
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": "자동 추출된 기사 본문입니다."}}],
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
# 5. [메인] 뉴스 수집 시작
# ==========================================
# 먼저 청소부터 하고 시작
delete_old_news()

print("\n📰 [뉴스 수집 시작] 주요 언론사의 핵심 기사 4개씩 가져옵니다...")

# 퀄리티 검증된 RSS 주소 목록
targets = [
    {
        "category": "미국주식",
        "rss": "https://rss.hankyung.com/feed/international" # 한국경제 국제면
    },
    {
        "category": "국내주식",
        "rss": "https://www.mk.co.kr/rss/50200011/" # 매일경제 증권면
    },
    {
        "category": "코인",
        "rss": "https://www.tokenpost.kr/rss" # 토큰포스트
    }
]

for target in targets:
    category = target["category"]
    rss_url = target["rss"]
    
    print(f"\n🔎 [{category}] 뉴스 가져오는 중...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        # 카테고리 당 최신 기사 4개만 가져옴
        count = 0
        MAX_ARTICLES = 4 
        
        for entry in feed.entries:
            if count >= MAX_ARTICLES:
                break
                
            # 날짜 처리
            if hasattr(entry, 'published_parsed'):
                dt = datetime(*entry.published_parsed[:6]).isoformat()
            else:
                dt = datetime.now().isoformat()
            
            # 본문 추출
            full_text = get_full_article(entry.link)
            
            # 노션 저장
            create_page(category, entry.title, entry.link, dt, full_text)
            print(f"   ✅ 저장: {entry.title}")
            
            count += 1

    except Exception as e:
        print(f"   ❌ 에러 발생: {e}")

print("\n🎉 모든 뉴스 배달 완료!")
