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
# 2. 3일 지난 뉴스 자동 삭제
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
        print("   - 삭제할 뉴스가 없습니다.")
        return

    for page in results:
        page_id = page["id"]
        requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={"archived": True})
        print(f"   - 🗑️ 삭제됨 (ID: {page_id})")

# ==========================================
# 3. 본문 추출 (보안 강화 사이트 대응)
# ==========================================
def get_full_article(url, summary_fallback=""):
    try:
        # 인베스팅닷컴 같은 곳은 봇을 막으므로 사람인 척 위장
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'
        config.request_timeout = 15
        
        article = Article(url, language='ko', config=config)
        article.download()
        article.parse()
        
        # 본문이 너무 짧으면(차단됨) RSS 요약본이라도 리턴
        if len(article.text) < 50:
            if summary_fallback:
                return f"⚠️ [보안 차단] 본문 추출이 막혀 요약본으로 대체합니다.\n\n{summary_fallback}"
            else:
                return "본문 보안 설정으로 내용을 가져오지 못했습니다. 원문 링크를 확인해주세요."
        return article.text
    except:
        # 에러 나면 요약본 리턴
        if summary_fallback:
            return f"⚠️ [접속 에러] 본문 대신 요약본을 보여드립니다.\n\n{summary_fallback}"
        return "본문을 가져올 수 없습니다."

# ==========================================
# 4. 노션 업로드
# ==========================================
def create_page(category, source_name, title, link, date, content):
    url = "https://api.notion.com/v1/pages"
    
    # 제목에 출처 표시
    final_title = f"[{source_name}] {title}"

    # 본문 길이 자르기
    if len(content) > 1800:
        content = content[:1800] + "\n...(중략)... (전체 내용은 아래 링크 확인)"

    data = {
        "parent": {"database_id": DATABASE_ID},
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
# 5. 메인 실행 (인베스팅닷컴 추가됨)
# ==========================================
delete_old_news()

print("\n📰 뉴스 수집 시작...")

targets = [
    {
        "category": "미국주식",
        "source": "인베스팅", # 인베스팅닷컴 한국판 (증시 뉴스)
        "rss": "https://kr.investing.com/rss/news_285.rss" 
    },
    {
        "category": "국내주식",
        "source": "매일경제", # 매일경제 증권
        "rss": "https://www.mk.co.kr/rss/50200011/"
    },
    {
        "category": "코인",
        "source": "토큰포스트", # 코인 전문
        "rss": "https://www.tokenpost.kr/rss"
    }
]

for target in targets:
    category = target["category"]
    source = target["source"]
    rss_url = target["rss"]
    
    print(f"\n🔎 [{category}] 가져오는 중 ({source})...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        count = 0
        MAX_ARTICLES = 4
        
        for entry in feed.entries:
            if count >= MAX_ARTICLES:
                break
                
            # 날짜
            if hasattr(entry, 'published_parsed'):
                dt = datetime(*entry.published_parsed[:6]).isoformat()
            else:
                dt = datetime.now().isoformat()
            
            # RSS에 포함된 짧은 요약 (혹시 본문 못 가져올 때 대비용)
            summary_fallback = entry.get('description', '')
            # HTML 태그 제거 (간단히)
            summary_fallback = summary_fallback.replace('<p>', '').replace('</p>', '').replace('<br>', '\n')

            # 본문 추출 시도
            full_text = get_full_article(entry.link, summary_fallback)
            
            # 노션 저장
            create_page(category, source, entry.title, entry.link, dt, full_text)
            print(f"   ✅ 저장: [{source}] {entry.title}")
            
            count += 1

    except Exception as e:
        print(f"   ❌ 에러: {e}")

print("\n🎉 완료!")
