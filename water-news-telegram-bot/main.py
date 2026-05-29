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

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "10"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))

BASE_DIR = Path(__file__).resolve().parent
FEEDS_FILE = BASE_DIR / "feeds.json"
SENT_FILE = BASE_DIR / "sent_links.json"


KEYWORDS = {
    # 핵심 수처리/분리막
    "mbr": 10,
    "membrane bioreactor": 10,
    "membrane": 8,
    "hollow fiber": 8,
    "pvdf": 8,
    "ultrafiltration": 8,
    "microfiltration": 8,
    "uf": 5,
    "mf": 5,

    # 상하수도/폐수
    "wastewater": 7,
    "sewage": 7,
    "sewer": 6,
    "water reuse": 8,
    "reclaimed water": 8,
    "industrial wastewater": 8,
    "effluent": 6,
    "wwtp": 8,
    "water treatment": 6,
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
    "veolia": 10,
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

    # Korean keywords
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


NEGATIVE_KEYWORDS = [
    "water park", "sports", "swimming", "bottled water",
    "날씨", "워터파크", "수영", "생수", "먹는샘물",
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


def score_article(title, summary):
    text = f"{title} {summary}".lower()

    for neg in NEGATIVE_KEYWORDS:
        if neg.lower() in text:
            return -100

    score = 0
    matched = []

    for kw, point in KEYWORDS.items():
        pattern = kw.lower()
        if pattern in text:
            score += point
            matched.append(kw)

    return score, matched[:6]


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

        for entry in parsed.entries[:30]:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            summary = clean_text(entry.get("summary", ""))

            result = score_article(title, summary)
            if isinstance(result, int):
                score = result
                matched = []
            else:
                score, matched = result

            if score < MIN_SCORE:
                continue

            articles.append({
                "title": title,
                "link": link,
                "summary": summary[:180],
                "source": name,
                "domain": get_domain(link),
                "score": score,
                "matched": matched,
            })

        time.sleep(1)

    # 점수 높은 순, 같은 링크 중복 제거
    dedup = {}
    for a in sorted(articles, key=lambda x: x["score"], reverse=True):
        if a["link"] and a["link"] not in dedup:
            dedup[a["link"]] = a

    return list(dedup.values())


def build_message(articles):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"[상하수도·수처리 뉴스 브리핑]",
        f"발송시각: {now} KST",
        ""
    ]

    if not articles:
        lines.append("오늘 기준 필터 조건에 맞는 신규 뉴스가 없습니다.")
        return "\n".join(lines)

    for i, a in enumerate(articles, 1):
        matched = ", ".join(a["matched"]) if a["matched"] else "-"
        lines.extend([
            f"{i}. {a['title']}",
            f"출처: {a['source']}",
            f"점수: {a['score']} / 키워드: {matched}",
            f"링크: {a['link']}",
            ""
        ])

    return "\n".join(lines)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Telegram 메시지 길이 제한 대비: 3900자 단위 분할
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]

    for chunk in chunks:
        resp = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
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

    msg = build_message(new_articles)
    send_telegram(msg)

    for a in new_articles:
        sent.add(a["link"])

    # 저장 파일이 너무 커지지 않도록 최근 2000개만 유지
    save_json(SENT_FILE, list(sent)[-2000:])


if __name__ == "__main__":
    main()
