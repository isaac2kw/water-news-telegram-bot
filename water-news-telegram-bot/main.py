import os
import re
import json
import html
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests


KST = timezone(timedelta(hours=9))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "8"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "8"))

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
FEEDS_FILE = BASE_DIR / "feeds.json"
SENT_FILE = BASE_DIR / "sent_links.json"
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "reports"


KEYWORDS = {
    # 핵심 수처리/분리막
    "mbr": 10,
    "membrane bioreactor": 10,
    "membrane": 8,
    "hollow fiber": 8,
    "pvdf": 8,
    "ultrafiltration": 8,
    "microfiltration": 8,

    # 상하수도/폐수
    "wastewater": 8,
    "sewage": 8,
    "sewer": 6,
    "water reuse": 9,
    "reclaimed water": 9,
    "industrial wastewater": 8,
    "effluent": 6,
    "wwtp": 8,
    "water treatment": 7,
    "drinking water": 5,

    # 오염물/정책
    "pfas": 8,
    "nutrient removal": 6,
    "nitrogen": 4,
    "phosphorus": 4,
    "ammonia": 4,

    # 사업/프로젝트
    "tender": 5,
    "contract": 5,
    "award": 5,
    "expansion": 5,
    "upgrade": 5,
    "commissioning": 5,
    "pilot": 5,
    "demonstration": 5,
    "funding": 4,
    "investment": 4,

    # 경쟁사/업계
    "veolia": 8,
    "suez": 8,
    "xylem": 8,
    "toray": 8,
    "asahi kasei": 8,
    "microza": 8,
    "mitsubishi": 7,
    "pentair": 7,
    "kovalus": 8,
    "puron": 8,
    "dupont": 7,
    "filmtec": 7,
    "kubota": 7,

    # Korean
    "상하수도": 10,
    "하수처리": 10,
    "폐수처리": 10,
    "수처리": 8,
    "물산업": 8,
    "분리막": 10,
    "중공사막": 10,
    "재이용수": 8,
    "방류수": 6,
    "고도처리": 7,
    "정수처리": 6,
    "하수처리장": 8,
    "폐수처리장": 8,
    "환경부": 5,
}

NEGATIVE_PATTERNS = [
    r"\bwater park\b", r"\bsports\b", r"\bswimming\b", r"\bbottled water\b",
    r"\bvoting rights\b", r"\bshare capital\b", r"\bshareholders\b",
    r"\bfinancial results\b", r"\bannual general meeting\b",
    r"nombre total de droits de vote", r"capital social",
    r"날씨", r"워터파크", r"수영", r"생수", r"먹는샘물", r"주주총회", r"의결권", r"자본금",
]


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def keyword_match(text, keyword):
    text_l = text.lower()
    kw = keyword.lower()

    # 짧은 약어는 단어 경계로만 매칭한다. 예: nombre 안의 mbr 오탐 방지
    if kw in {"mbr", "uf", "mf"}:
        return re.search(rf"(?<![a-zA-Z0-9]){re.escape(kw)}(?![a-zA-Z0-9])", text_l) is not None

    return kw in text_l


def score_article(title, summary):
    text = f"{title} {summary}"
    text_l = text.lower()

    for pattern in NEGATIVE_PATTERNS:
        if re.search(pattern, text_l, flags=re.IGNORECASE):
            return -100, []

    score = 0
    matched = []
    for kw, point in KEYWORDS.items():
        if keyword_match(text, kw):
            score += point
            matched.append(kw)

    return score, matched[:8]


def get_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def fetch_articles():
    feeds = load_json(FEEDS_FILE, [])
    articles = []

    for feed in feeds:
        name = feed.get("name", "Unknown")
        url = feed.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url)

        for entry in parsed.entries[:40]:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            summary = clean_text(entry.get("summary", ""))

            score, matched = score_article(title, summary)
            if score < MIN_SCORE:
                continue

            articles.append({
                "title": title,
                "link": link,
                "summary": summary[:500],
                "source": name,
                "domain": get_domain(link),
                "score": score,
                "matched": matched,
            })

        time.sleep(1)

    dedup = {}
    for a in sorted(articles, key=lambda x: x["score"], reverse=True):
        if a["link"] and a["link"] not in dedup:
            dedup[a["link"]] = a

    return list(dedup.values())


def summarize_korean(article):
    fallback = {
        "ko_title": article["title"],
        "summary": article["summary"][:160] if article["summary"] else "RSS 제목 기준으로 선별됨. 상세 내용은 원문 확인 필요.",
        "relevance": ", ".join(article["matched"]) if article["matched"] else "수처리 관련 키워드 매칭",
        "category": guess_category(article),
    }

    if not OPENAI_API_KEY:
        return fallback

    prompt = f"""
아래 뉴스 항목을 한국어로 요약하세요.
반드시 JSON만 출력하세요.
필드:
- ko_title: 한국어 제목 1문장
- summary: 한국어 요약 2문장. 사실만 작성. 원문에 없는 수치/내용 추측 금지.
- relevance: 상하수도/수처리/분리막 산업 관점의 관련성 1문장
- category: 아래 중 하나만 선택: 정책/규제, 프로젝트/수주, 분리막/MBR, 기업동향, PFAS/오염물, 기타

원문 제목: {article['title']}
출처: {article['source']}
RSS 요약: {article['summary']}
키워드: {', '.join(article['matched'])}
링크: {article['link']}
""".strip()

    try:
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "input": prompt,
                "text": {"format": {"type": "json_object"}},
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        output_text = ""
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text += content.get("text", "")

        parsed = json.loads(output_text)
        return {
            "ko_title": parsed.get("ko_title", fallback["ko_title"]),
            "summary": parsed.get("summary", fallback["summary"]),
            "relevance": parsed.get("relevance", fallback["relevance"]),
            "category": parsed.get("category", fallback["category"]),
        }
    except Exception as e:
        fallback["summary"] = f"{fallback['summary']} [요약 API 오류: {str(e)[:120]}]"
        return fallback


def guess_category(article):
    keys = set(k.lower() for k in article.get("matched", []))
    if "pfas" in keys:
        return "PFAS/오염물"
    if "mbr" in keys or "membrane" in keys or "membrane bioreactor" in keys:
        return "분리막/MBR"
    if {"tender", "contract", "award", "expansion", "upgrade", "pilot"} & keys:
        return "프로젝트/수주"
    if {"veolia", "xylem", "toray", "asahi kasei", "pentair", "kovalus"} & keys:
        return "기업동향"
    return "기타"


def get_pages_base_url():
    explicit = os.getenv("PAGES_BASE_URL")
    if explicit:
        return explicit.rstrip("/")

    repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    return ""


def create_report(articles):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    report_dir = REPORTS_DIR / today
    report_dir.mkdir(parents=True, exist_ok=True)

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    rows = []
    for i, a in enumerate(articles, 1):
        s = a["ai"]
        rows.append(f"""
        <section class="card">
          <div class="rank">#{i}</div>
          <h2>{html.escape(s['ko_title'])}</h2>
          <p class="meta">출처: {html.escape(a['source'])} · 점수: {a['score']} · 분류: {html.escape(s['category'])}</p>
          <p>{html.escape(s['summary'])}</p>
          <p class="relevance">관련성: {html.escape(s['relevance'])}</p>
          <p class="keywords">키워드: {html.escape(', '.join(a['matched']))}</p>
          <p><a href="{html.escape(a['link'])}" target="_blank">원문 기사 보기</a></p>
        </section>
        """)

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>상하수도·수처리 뉴스 브리핑 - {today}</title>
  <style>
    body {{ font-family: Arial, "Noto Sans KR", sans-serif; margin: 0; background:#f6f8fb; color:#1f2937; }}
    header {{ background:#163b73; color:white; padding:28px 36px; }}
    main {{ max-width: 980px; margin: 28px auto; padding: 0 18px; }}
    .card {{ background:white; border:1px solid #e5e7eb; border-radius:14px; padding:22px; margin-bottom:16px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:6px 0 10px; font-size:21px; }}
    .meta, .keywords {{ color:#6b7280; font-size:14px; }}
    .relevance {{ background:#eef6ff; padding:12px; border-radius:10px; }}
    .rank {{ color:#f97316; font-weight:bold; }}
    a {{ color:#1d4ed8; }}
  </style>
</head>
<body>
  <header>
    <h1>상하수도·수처리 뉴스 브리핑</h1>
    <div>{today} / 자동 생성 보고서</div>
  </header>
  <main>
    {''.join(rows) if rows else '<p>신규 뉴스가 없습니다.</p>'}
  </main>
</body>
</html>
"""
    (report_dir / "index.html").write_text(html_doc, encoding="utf-8")

    # docs/index.html도 갱신
    index_html = f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>상하수도 뉴스 브리핑</title></head>
<body>
<h1>상하수도·수처리 뉴스 브리핑</h1>
<p>Latest report: <a href="./reports/{today}/">reports/{today}/</a></p>
</body>
</html>
"""
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")

    base_url = get_pages_base_url()
    return f"{base_url}/reports/{today}/" if base_url else f"reports/{today}/"


def build_telegram_message(articles, report_url):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    lines = [
        f"[상하수도·수처리 뉴스 브리핑]",
        f"{today}",
        "",
    ]

    if not articles:
        lines.append("오늘 기준 필터 조건에 맞는 신규 뉴스가 없습니다.")
        return "\n".join(lines)

    lines.append(f"오늘의 주요 뉴스 {len(articles)}건")
    lines.append("")

    for i, a in enumerate(articles[:5], 1):
        lines.append(f"{i}. {a['ai']['ko_title']}")
        lines.append(f"   - {a['ai']['category']} / {a['source']}")
    lines.append("")
    lines.append("상세 분석 보고서 보기:")
    lines.append(report_url)

    return "\n".join(lines)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]

    for chunk in chunks:
        resp = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": False,
        }, timeout=30)
        resp.raise_for_status()
        time.sleep(0.5)


def main():
    sent = set(load_json(SENT_FILE, []))
    articles = fetch_articles()

    new_articles = []
    for a in articles:
        if a["link"] not in sent:
            new_articles.append(a)
        if len(new_articles) >= MAX_ITEMS:
            break

    for a in new_articles:
        a["ai"] = summarize_korean(a)

    report_url = create_report(new_articles)
    msg = build_telegram_message(new_articles, report_url)
    send_telegram(msg)

    for a in new_articles:
        sent.add(a["link"])

    save_json(SENT_FILE, list(sent)[-2000:])


if __name__ == "__main__":
    main()
