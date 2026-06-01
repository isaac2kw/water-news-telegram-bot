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
HISTORY_FILE = BASE_DIR / "news_history.json"

DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "reports"
WEEKLY_DIR = DOCS_DIR / "weekly"
MONTHLY_DIR = DOCS_DIR / "monthly"


KEYWORDS = {
    "mbr": 10,
    "membrane bioreactor": 10,
    "membrane": 8,
    "hollow fiber": 8,
    "pvdf": 8,
    "ultrafiltration": 8,
    "microfiltration": 8,

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

    "pfas": 10,
    "nutrient removal": 6,
    "nitrogen": 4,
    "phosphorus": 4,
    "ammonia": 4,

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
    r"\bwater park\b",
    r"\bsports\b",
    r"\bswimming\b",
    r"\bbottled water\b",
    r"\bvoting rights\b",
    r"\bshare capital\b",
    r"\bshareholders\b",
    r"\bfinancial results\b",
    r"\bannual general meeting\b",
    r"nombre total de droits de vote",
    r"capital social",
    r"날씨",
    r"워터파크",
    r"수영",
    r"생수",
    r"먹는샘물",
    r"주주총회",
    r"의결권",
    r"자본금",
]


COUNTRY_FLAGS = {
    "미국": "🇺🇸",
    "usa": "🇺🇸",
    "united states": "🇺🇸",
    "중국": "🇨🇳",
    "china": "🇨🇳",
    "일본": "🇯🇵",
    "japan": "🇯🇵",
    "한국": "🇰🇷",
    "south korea": "🇰🇷",
    "korea": "🇰🇷",
    "싱가포르": "🇸🇬",
    "singapore": "🇸🇬",
    "독일": "🇩🇪",
    "germany": "🇩🇪",
    "프랑스": "🇫🇷",
    "france": "🇫🇷",
    "영국": "🇬🇧",
    "uk": "🇬🇧",
    "united kingdom": "🇬🇧",
    "호주": "🇦🇺",
    "australia": "🇦🇺",
    "사우디": "🇸🇦",
    "saudi arabia": "🇸🇦",
    "uae": "🇦🇪",
    "아랍에미리트": "🇦🇪",
    "인도": "🇮🇳",
    "india": "🇮🇳",
    "네덜란드": "🇳🇱",
    "netherlands": "🇳🇱",
    "스페인": "🇪🇸",
    "spain": "🇪🇸",
    "이탈리아": "🇮🇹",
    "italy": "🇮🇹",
    "캐나다": "🇨🇦",
    "canada": "🇨🇦",
    "브라질": "🇧🇷",
    "brazil": "🇧🇷",
    "유럽연합": "🇪🇺",
    "eu": "🇪🇺",
    "european union": "🇪🇺",
}


TECH_EMOJIS = {
    "PFAS": "🧪",
    "Water Reuse": "♻️",
    "MBR": "🧬",
    "Membrane": "🧬",
    "UF": "🧬",
    "MF": "🧬",
    "Desalination": "🌊",
    "Industrial Wastewater": "🏭",
    "Wastewater": "💧",
    "Digital Water": "🤖",
    "Data Center Water": "🖥️",
    "Energy Efficiency": "⚡",
    "Regulation": "⚖️",
    "Project": "🚧",
    "Investment": "💰",
    "Infrastructure Upgrade": "🔧",
}


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

    return score, matched[:10]


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
                "summary": summary[:900],
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


def flag_for_country(country):
    if not country:
        return ""

    key = str(country).strip().lower()
    return COUNTRY_FLAGS.get(key, "")


def add_country_flag(country):
    if not country:
        return ""

    flag = flag_for_country(country)
    if flag:
        return f"{flag} {country}"

    return country


def emoji_for_category(category, technologies=None):
    text = f"{category} {' '.join(technologies or [])}"

    for key, emoji in TECH_EMOJIS.items():
        if key.lower() in text.lower():
            return emoji

    return "💧"


def guess_category(article):
    keys = set(k.lower() for k in article.get("matched", []))

    if "pfas" in keys:
        return "PFAS/오염물"

    if "mbr" in keys or "membrane" in keys or "membrane bioreactor" in keys:
        return "분리막/MBR"

    if {"tender", "contract", "award", "expansion", "upgrade", "pilot", "commissioning"} & keys:
        return "프로젝트/수주"

    if {"veolia", "xylem", "toray", "asahi kasei", "pentair", "kovalus", "suez"} & keys:
        return "기업동향"

    if {"water reuse", "reclaimed water"} & keys:
        return "재이용수"

    return "수처리 산업동향"


def openai_json(prompt, fallback):
    if not OPENAI_API_KEY:
        return fallback

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a Korean water and wastewater industry analyst. Return valid JSON only. Do not invent facts.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=90,
        )

        resp.raise_for_status()
        data = resp.json()
        return json.loads(data["choices"][0]["message"]["content"])

    except Exception as e:
        fallback["api_error"] = str(e)[:180]
        return fallback


def openai_text(prompt, fallback):
    if not OPENAI_API_KEY:
        return fallback

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a Korean water and wastewater industry analyst. Write concise factual Korean analysis only.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.2,
            },
            timeout=90,
        )

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"{fallback} [요약 API 오류: {str(e)[:120]}]"


def summarize_article(article):
    fallback = {
        "ko_title": article["title"],
        "brief": article["summary"][:220] if article["summary"] else "RSS 제목 기준으로 선별되었습니다. 상세 내용은 원문 확인이 필요합니다.",
        "summary": article["summary"][:500] if article["summary"] else "RSS 제목 기준으로 선별되었습니다. 상세 내용은 원문 확인이 필요합니다.",
        "why_important": "수처리 산업 관련 키워드가 포함되어 있어 모니터링 대상으로 분류되었습니다.",
        "category": guess_category(article),
        "countries": [],
        "companies": [],
        "technologies": article.get("matched", []),
        "policy_alert": "",
    }

    prompt = f"""
다음 뉴스 항목을 한국어로 분석하세요.
반드시 JSON만 출력하세요.

필드:
- ko_title: 한국어 제목. 45자 이내.
- brief: 텔레그램용 요약. 2문장. 총 180자 이내.
- summary: 상세 보고서용 요약. 4~6문장. 배경, 주요 내용, 수처리 산업 관련성을 포함. 기사에 없는 수치나 사실을 만들지 말 것.
- why_important: 왜 중요한가. 2문장. 시장, 규제, 기술, 프로젝트 관점 중 관련 있는 이유를 설명. 추측이면 '추측입니다'라고 명시.
- category: 아래 중 하나만 선택.
  PFAS/오염물, 재이용수, 분리막/MBR, 산업폐수, 담수화, 프로젝트/수주, 기업동향, 규제/정책, 수처리 산업동향
- countries: 기사에 명시된 국가명 배열. 예: ["미국", "중국"]. 없으면 [].
- companies: 기사에 명시된 기업명 배열. 없으면 [].
- technologies: 기사에 명시된 기술/키워드 배열. 예: ["PFAS", "Water Reuse", "MBR"].
- policy_alert: 규제/정책 알림이면 1문장 작성. 아니면 빈 문자열.

원문 제목: {article['title']}
출처: {article['source']}
RSS 요약: {article['summary']}
키워드: {', '.join(article['matched'])}
링크: {article['link']}
""".strip()

    parsed = openai_json(prompt, fallback)

    return {
        "ko_title": parsed.get("ko_title", fallback["ko_title"]),
        "brief": parsed.get("brief", fallback["brief"]),
        "summary": parsed.get("summary", fallback["summary"]),
        "why_important": parsed.get("why_important", fallback["why_important"]),
        "category": parsed.get("category", fallback["category"]),
        "countries": parsed.get("countries", fallback["countries"]) or [],
        "companies": parsed.get("companies", fallback["companies"]) or [],
        "technologies": parsed.get("technologies", fallback["technologies"]) or [],
        "policy_alert": parsed.get("policy_alert", fallback["policy_alert"]) or "",
    }


def get_pages_base_url():
    explicit = os.getenv("PAGES_BASE_URL")

    if explicit:
        return explicit.rstrip("/")

    repo = os.getenv("GITHUB_REPOSITORY", "")

    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"

    return ""


def save_news_history(articles):
    history = load_json(HISTORY_FILE, [])
    today = datetime.now(KST).strftime("%Y-%m-%d")

    existing = set((item.get("date"), item.get("link")) for item in history)

    for a in articles:
        key = (today, a.get("link"))

        if key in existing:
            continue

        ai = a["ai"]

        history.append({
            "date": today,
            "title": a.get("title", ""),
            "ko_title": ai.get("ko_title", ""),
            "brief": ai.get("brief", ""),
            "summary": ai.get("summary", ""),
            "why_important": ai.get("why_important", ""),
            "category": ai.get("category", ""),
            "countries": ai.get("countries", []),
            "companies": ai.get("companies", []),
            "technologies": ai.get("technologies", []),
            "policy_alert": ai.get("policy_alert", ""),
            "source": a.get("source", ""),
            "link": a.get("link", ""),
            "score": a.get("score", 0),
            "keywords": a.get("matched", []),
        })

    history = history[-1500:]
    save_json(HISTORY_FILE, history)

    return history


def filter_week_items(history):
    today_dt = datetime.now(KST)
    start = (today_dt - timedelta(days=7)).strftime("%Y-%m-%d")

    return [x for x in history if x.get("date", "") >= start]


def filter_month_items(history):
    month_key = datetime.now(KST).strftime("%Y-%m")

    return [x for x in history if x.get("date", "").startswith(month_key)]


def build_period_one_line(title, items):
    if not items:
        return "누적된 관련 뉴스가 아직 없습니다."

    lines = []

    for x in items[:40]:
        countries = ", ".join(x.get("countries", []))
        companies = ", ".join(x.get("companies", []))
        techs = ", ".join(x.get("technologies", []))
        lines.append(
            f"- {x.get('date')} / {x.get('category')} / 국가:{countries} / 기업:{companies} / 기술:{techs} / {x.get('ko_title')} / {x.get('brief')}"
        )

    prompt = f"""
아래 뉴스 목록을 기준으로 '{title}'을 한국어 한 줄로 요약하세요.

조건:
- 1문장만 작성
- 160자 이내
- 핵심 국가에는 국기 이모지 사용
- 핵심 기술에는 적절한 이모지 사용
- 과장 금지
- 기사에 없는 사실 추측 금지

뉴스 목록:
{chr(10).join(lines)}
""".strip()

    return openai_text(prompt, "누적 뉴스 기준으로 핵심 동향을 요약할 수 없습니다.")


def build_trend_report_text(title, items, report_type):
    if not items:
        return "누적된 관련 뉴스가 아직 없습니다."

    lines = []

    for x in items[:60]:
        countries = ", ".join(x.get("countries", []))
        companies = ", ".join(x.get("companies", []))
        techs = ", ".join(x.get("technologies", []))
        lines.append(
            f"- {x.get('date')} / {x.get('category')} / 국가:{countries} / 기업:{companies} / 기술:{techs} / {x.get('ko_title')} / {x.get('summary')}"
        )

    if report_type == "weekly":
        structure = """
작성 구조:
1. Executive Summary: 3~5문장
2. 주요 국가 TOP3: 국가별 1~2문장
3. 주요 기업 TOP3: 기업별 1~2문장
4. 주요 기술 TOP3: 기술별 1~2문장
5. 규제/정책 변화: 있으면 2~4개, 없으면 '특이사항 없음'
6. 반드시 읽어야 할 기사 TOP3: 제목과 요약 1문장
7. 다음 주 모니터링 포인트: 3~5개
"""
    else:
        structure = """
작성 구조:
1. Executive Summary: 4~6문장
2. 이달의 키워드 TOP5: 키워드별 1문장
3. 국가별 동향 TOP5: 국가별 1~2문장
4. 기업별 동향 TOP5: 기업별 1~2문장
5. 기술별 동향 TOP5: 기술별 1~2문장
6. 주요 프로젝트 TOP5: 프로젝트별 1문장
7. 현재 진행 중인 규제/정책 변화: 있으면 2~5개
8. 향후 예정된 규제/정책 변화: 기사에 명시된 경우만 작성
9. 향후 1~3년 주목 기술: 3~5개
10. 다음 달 모니터링 포인트: 3~5개
"""

    prompt = f"""
아래 뉴스 목록을 기준으로 '{title}' 보고서를 한국어로 작성하세요.

조건:
- 너무 길게 쓰지 말 것
- 핵심 동향 위주
- 국가가 나오면 국기 이모지 사용
- 기술에는 적절한 이모지 사용
- 기사에 없는 사실을 만들지 말 것
- 추측이면 반드시 '추측입니다'라고 명시
- HifilM 영향 분석은 작성하지 말 것

{structure}

뉴스 목록:
{chr(10).join(lines)}
""".strip()

    return openai_text(prompt, "보고서를 생성할 수 없습니다.")


def count_items(items, field):
    result = {}

    for x in items:
        values = x.get(field, [])

        if isinstance(values, str):
            values = [values]

        for v in values:
            if not v:
                continue

            result[v] = result.get(v, 0) + 1

    return sorted(result.items(), key=lambda x: x[1], reverse=True)


def make_html_page(title, body_html, path):
    path.mkdir(parents=True, exist_ok=True)

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, "Noto Sans KR", sans-serif; margin:0; background:#f6f8fb; color:#1f2937; line-height:1.65; }}
    header {{ background:#163b73; color:white; padding:30px 36px; }}
    main {{ max-width:980px; margin:28px auto; padding:0 18px; }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:26px 0 10px; font-size:22px; }}
    h3 {{ margin:18px 0 6px; font-size:17px; }}
    .card {{ background:white; border:1px solid #e5e7eb; border-radius:14px; padding:22px; margin-bottom:18px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
    .summary {{ white-space:pre-wrap; background:white; border:1px solid #e5e7eb; border-radius:14px; padding:22px; margin-bottom:22px; }}
    .pill {{ display:inline-block; background:#e0f2fe; color:#075985; border-radius:999px; padding:3px 10px; font-size:13px; margin-right:6px; }}
    .meta {{ color:#6b7280; font-size:13px; }}
    .why {{ background:#fff7ed; border-left:4px solid #f97316; padding:10px 12px; }}
    .brief {{ background:#f9fafb; border-left:4px solid #163b73; padding:10px 12px; }}
    a {{ color:#1d4ed8; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div>자동 생성 보고서</div>
  </header>
  <main>
    {body_html}
  </main>
</body>
</html>
"""
    (path / "index.html").write_text(html_doc, encoding="utf-8")


def create_daily_report(articles):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    report_dir = REPORTS_DIR / today

    cards = []

    for i, a in enumerate(articles, 1):
        ai = a["ai"]
        countries = " ".join(add_country_flag(c) for c in ai.get("countries", []))
        companies = ", ".join(ai.get("companies", []))
        techs = ", ".join(ai.get("technologies", []))
        emoji = emoji_for_category(ai.get("category", ""), ai.get("technologies", []))

        cards.append(f"""
        <section class="card">
          <p class="meta">#{i} · {html.escape(a.get('source', ''))} · 점수 {a.get('score', 0)}</p>
          <h2>{emoji} {html.escape(ai.get('ko_title', ''))}</h2>
          <p><span class="pill">{html.escape(ai.get('category', ''))}</span></p>
          <p class="brief">{html.escape(ai.get('brief', ''))}</p>
          <h3>내용 요약</h3>
          <p>{html.escape(ai.get('summary', ''))}</p>
          <h3>왜 중요한가?</h3>
          <p class="why">{html.escape(ai.get('why_important', ''))}</p>
          <p class="meta">국가: {html.escape(countries or '-')}</p>
          <p class="meta">기업: {html.escape(companies or '-')}</p>
          <p class="meta">기술: {html.escape(techs or '-')}</p>
          <p><a href="{html.escape(a.get('link', ''))}" target="_blank" rel="noopener noreferrer">원문 기사 보기</a></p>
        </section>
        """)

    title = f"{today} 상하수도·수처리 상세 분석 보고서"

    if cards:
        body = "".join(cards)
    else:
        body = '<section class="card">오늘 기준 필터 조건에 맞는 뉴스가 없습니다.</section>'

    make_html_page(title, body, report_dir)

    base_url = get_pages_base_url()
    return f"{base_url}/reports/{today}/" if base_url else f"reports/{today}/"


def create_period_report(period_type, items):
    now = datetime.now(KST)

    if period_type == "weekly":
        iso = now.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        title = f"{key} 상하수도·수처리 주간 업계 동향"
        report_dir = WEEKLY_DIR / key
        report_text = build_trend_report_text(title, items, "weekly")
        url_path = f"weekly/{key}/"
    else:
        key = now.strftime("%Y-%m")
        title = f"{key} 상하수도·수처리 월간 업계 동향"
        report_dir = MONTHLY_DIR / key
        report_text = build_trend_report_text(title, items, "monthly")
        url_path = f"monthly/{key}/"

    body = f'<section class="summary">{html.escape(report_text)}</section>'

    make_html_page(title, body, report_dir)

    base_url = get_pages_base_url()
    return f"{base_url}/{url_path}" if base_url else url_path


def update_docs_index(daily_url, weekly_url, monthly_url):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    today = datetime.now(KST).strftime("%Y-%m-%d")

    body = f"""
    <section class="card">
      <h2>최신 보고서</h2>
      <p><a href="{html.escape(daily_url)}">{today} 상세 분석 보고서</a></p>
      <p><a href="{html.escape(weekly_url)}">주간 업계 동향</a></p>
      <p><a href="{html.escape(monthly_url)}">월간 업계 동향</a></p>
    </section>
    """

    make_html_page("상하수도·수처리 뉴스 브리핑", body, DOCS_DIR)


def build_policy_alerts(articles):
    alerts = []

    for a in articles:
        alert = a["ai"].get("policy_alert", "")

        if not alert:
            continue

        countries = a["ai"].get("countries", [])
        country_text = " ".join(add_country_flag(c) for c in countries)

        if country_text:
            alerts.append(f"{country_text}\n{alert}")
        else:
            alerts.append(alert)

    return alerts[:3]


def build_telegram_message(articles, daily_url, weekly_url, monthly_url, weekly_one_line, monthly_one_line):
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    lines = [
        "🌍 상하수도·수처리 일간 브리핑",
        f"{today} ({weekday}) 07:00 KST",
        "",
        "━━━━━━━━━━━━━━",
        "",
        "📌 오늘의 한 줄 요약",
        "",
    ]

    if articles:
        first = articles[0]["ai"]
        today_summary = first.get("brief", "오늘 기준 수처리 관련 주요 뉴스가 확인되었습니다.")
        lines.append(today_summary)
    else:
        lines.append("오늘 기준 필터 조건에 맞는 주요 뉴스가 없습니다.")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━",
        "",
        "📅 이번 주 한 줄 요약",
        "",
        weekly_one_line,
        "",
        "━━━━━━━━━━━━━━",
        "",
        "📊 이번 달 한 줄 요약",
        "",
        monthly_one_line,
        "",
        "━━━━━━━━━━━━━━",
        "",
    ])

    if articles:
        count = min(5, len(articles))
        lines.append(f"🎯 반드시 읽어야 할 기사 TOP {count}")
        lines.append("")

        for idx, a in enumerate(articles[:count], 1):
            ai = a["ai"]
            countries = ai.get("countries", [])
            country_prefix = ""

            if countries:
                country_prefix = add_country_flag(countries[0]) + " "

            emoji = emoji_for_category(ai.get("category", ""), ai.get("technologies", []))

            lines.append(f"{idx}. {country_prefix}{ai.get('ko_title', '')}")
            lines.append("")
            lines.append("주제")
            lines.append(f"{emoji} {ai.get('category', '')}")
            lines.append("")
            lines.append("요약")
            lines.append(ai.get("brief", ""))
            lines.append("")
            lines.append("💡 왜 중요한가?")
            lines.append("")
            lines.append(ai.get("why_important", ""))
            lines.append("")
            lines.append("━━━━━━━━━━━━━━")
            lines.append("")
    else:
        lines.append("🎯 반드시 읽어야 할 기사")
        lines.append("")
        lines.append("오늘 기준으로 표시할 주요 기사가 없습니다.")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("")

    alerts = build_policy_alerts(articles)

    if alerts:
        lines.append("⚖️ 규제·정책 알림")
        lines.append("")

        for alert in alerts:
            lines.append(alert)
            lines.append("")

        lines.append("━━━━━━━━━━━━━━")
        lines.append("")

    lines.extend([
        "📖 상세 분석 보고서",
        daily_url,
        "",
        "📅 주간 업계 동향",
        weekly_url,
        "",
        "📊 월간 업계 동향",
        monthly_url,
    ])

    return "\n".join(lines)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]

    for chunk in chunks:
        resp = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        time.sleep(0.5)


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    articles = fetch_articles()
    selected_articles = articles[:MAX_ITEMS]

    for article in selected_articles:
        article["ai"] = summarize_article(article)

    history = save_news_history(selected_articles)

    week_items = filter_week_items(history)
    month_items = filter_month_items(history)

    weekly_one_line = build_period_one_line("이번 주 상하수도·수처리 동향", week_items)
    monthly_one_line = build_period_one_line("이번 달 상하수도·수처리 동향", month_items)

    daily_url = create_daily_report(selected_articles)
    weekly_url = create_period_report("weekly", week_items)
    monthly_url = create_period_report("monthly", month_items)

    update_docs_index(daily_url, weekly_url, monthly_url)

    telegram_text = build_telegram_message(
        selected_articles,
        daily_url,
        weekly_url,
        monthly_url,
        weekly_one_line,
        monthly_one_line,
    )

    send_telegram(telegram_text)

    sent = load_json(SENT_FILE, [])
    sent_links = set(sent)

    for article in selected_articles:
        if article.get("link"):
            sent_links.add(article["link"])

    save_json(SENT_FILE, list(sent_links)[-2000:])


if __name__ == "__main__":
    main()
