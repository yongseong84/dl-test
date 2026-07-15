"""
테스트용 샘플 Chrome History(SQLite) 파일 생성기.

실제 Chrome 방문 기록이 아닌, chrome_history_analyzer.py 동작 검증을 위한
가상 데이터를 만듭니다. 실행하면 같은 폴더에 History_sample 파일이 생성되며,
분석기 실행 후 '파일 직접 선택...'으로 이 파일을 선택해 테스트할 수 있습니다.
"""

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)

CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

def to_chrome_time(dt):
    return int((dt.astimezone(timezone.utc) - CHROME_EPOCH).total_seconds() * 1_000_000)

DB_PATH = str(Path(__file__).resolve().parent / "History_sample")

sites = [
    ("https://www.google.com/search?q={q}", "{q} - Google 검색", "google.com"),
    ("https://search.naver.com/search.naver?query={q}", "{q} : 네이버 통합검색", "naver.com"),
    ("https://www.youtube.com/watch?v={vid}", "재미있는 영상 - YouTube", "www.youtube.com"),
    ("https://github.com/{repo}", "{repo}: 저장소", "github.com"),
    ("https://stackoverflow.com/questions/{qid}", "질문 상세 - Stack Overflow", "stackoverflow.com"),
    ("https://news.naver.com/article/{aid}", "오늘의 뉴스", "news.naver.com"),
    ("https://www.notion.so/{page}", "업무 노트", "www.notion.so"),
    ("https://mail.google.com/mail/u/0/#inbox", "받은편지함 - Gmail", "mail.google.com"),
    ("https://www.coupang.com/vp/products/{pid}", "쿠팡 상품", "www.coupang.com"),
    ("https://developer.mozilla.org/ko/docs/{doc}", "MDN 문서", "developer.mozilla.org"),
]

search_queries = ["파이썬 리스트 정렬", "타입스크립트 제네릭", "강남 맛집", "환율 계산기", "sqlite3 python", "리액트 useEffect", "엑셀 vlookup", "치킨 배달"]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""CREATE TABLE urls(
    id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR,
    visit_count INTEGER DEFAULT 0, typed_count INTEGER DEFAULT 0,
    last_visit_time INTEGER NOT NULL, hidden INTEGER DEFAULT 0)""")
c.execute("""CREATE TABLE visits(
    id INTEGER PRIMARY KEY, url INTEGER NOT NULL, visit_time INTEGER NOT NULL,
    from_visit INTEGER, transition INTEGER DEFAULT 0, segment_id INTEGER,
    visit_duration INTEGER DEFAULT 0)""")
c.execute("""CREATE TABLE keyword_search_terms(
    keyword_id INTEGER NOT NULL, url_id INTEGER NOT NULL,
    lower_term LONGVARCHAR NOT NULL, term LONGVARCHAR NOT NULL)""")

now = datetime.now().astimezone()
url_id = 1
visit_id = 1

for _ in range(400):
    template, title_t, domain = random.choice(sites)
    q = random.choice(search_queries)
    url = template.format(q=q.replace(" ", "+"), vid="abc123", repo="user/project", qid=str(random.randint(1000,99999)),
                           aid=str(random.randint(100000,999999)), page="workspace", pid=str(random.randint(1000,999999)),
                           doc="Web/API")
    title = title_t.format(q=q, repo="user/project")
    days_ago = random.uniform(0, 89)
    hour_bias = random.choices(range(24), weights=[1,1,1,1,1,2,3,5,6,7,6,6,7,6,5,5,6,7,8,7,6,4,3,2])[0]
    visit_dt = now - timedelta(days=days_ago)
    visit_dt = visit_dt.replace(hour=hour_bias, minute=random.randint(0,59), second=random.randint(0,59))
    ct = to_chrome_time(visit_dt)

    c.execute("INSERT INTO urls (id, url, title, visit_count, last_visit_time) VALUES (?,?,?,?,?)",
              (url_id, url, title, 1, ct))
    c.execute("INSERT INTO visits (id, url, visit_time) VALUES (?,?,?)", (visit_id, url_id, ct))

    if domain in ("google.com", "naver.com"):
        c.execute("INSERT INTO keyword_search_terms (keyword_id, url_id, lower_term, term) VALUES (?,?,?,?)",
                   (1, url_id, q.lower(), q))

    url_id += 1
    visit_id += 1

conn.commit()
conn.close()
print("sample history db created:", DB_PATH)
