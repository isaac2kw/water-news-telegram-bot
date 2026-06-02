import os
import re
import json
import html
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, quote_plus

import feedparser
import requests
import markdown


KST = timezone(timedelta(hours=9))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "8"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "8"))

BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
BACKFILL_START_DATE = os.getenv("BACKFILL_START_DATE", "")
BACKFILL_END_DATE = os.getenv("BACKFILL_END_DATE", "")
SEND_TELEGRAM = os.getenv("SEND_TELEGRAM", "true").lower() == "true"

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


# v2 확장 키워드: MBR, 수처리용 분리막, 국내 동향, 학회·전시회 중심.
KEYWORDS.update({
    "submerged membrane": 10,
    "submerged mbr": 10,
    "immersed membrane": 9,
    "immersed mbr": 10,
    "aerobic mbr": 8,
    "anaerobic mbr": 8,
    "anMBR": 8,
    "flat sheet membrane": 7,
    "ceramic membrane": 8,
    "polymeric membrane": 7,
    "membrane fouling": 10,
    "biofouling": 8,
    "fouling control": 8,
    "air scouring": 8,
    "backwash": 7,
    "relaxation": 6,
    "clean-in-place": 7,
    "cip": 7,
    "tss": 4,
    "mlss": 6,
    "srt": 5,
    "hrt": 5,
    "tmp": 7,
    "flux": 6,
    "permeability": 6,
    "permeate": 5,
    "filtrate": 5,
    "sidestream mbr": 8,
    "membrane module": 8,
    "membrane cassette": 8,
    "hollow-fiber membrane": 9,
    "water korea": 7,
    "awwa": 6,
    "wef": 6,
    "weftec": 8,
    "iwa mtc": 8,
    "aquatech": 7,
    "water exhibition": 6,
    "conference": 4,
    "symposium": 4,
    "막여과": 10,
    "막분리": 9,
    "막공정": 9,
    "막오염": 10,
    "분리막 오염": 10,
    "파울링": 10,
    "막세정": 9,
    "공기세정": 8,
    "역세": 7,
    "역세척": 8,
    "투과수": 6,
    "여과수": 6,
    "투과유속": 7,
    "막면적": 6,
    "막모듈": 9,
    "막 카세트": 8,
    "침지식": 9,
    "침지형": 9,
    "평막": 7,
    "세라믹막": 8,
    "고분자막": 7,
    "중공사": 10,
    "중공사막": 10,
    "분리막 생물반응조": 10,
    "막분리활성슬러지": 10,
    "활성슬러지": 7,
    "질산화": 6,
    "탈질": 6,
    "생물학적 처리": 6,
    "총인": 5,
    "총질소": 5,
    "방류수질": 7,
    "하수재이용": 9,
    "물재이용": 9,
    "물 재이용": 9,
    "한국막학회": 8,
    "상하수도협회": 7,
    "물환경학회": 7,
    "워터코리아": 7,
})

NEGATIVE_PATTERNS.extend([
    r"battery separator",
    r"separator film",
    r"lithium",
    r"lithium[- ]?ion",
    r"solid[- ]?state battery",
    r"\bev\b",
    r"electric vehicle",
    r"\bess\b",
    r"electrolyte",
    r"semiconductor",
    r"\boled\b",
    r"display",
    r"dialysis",
    r"hemodialysis",
    r"medical membrane",
    r"blood purification",
    r"automotive stock",
    r"defense stock",
    r"renewable energy target",
    r"grid energy storage",
    r"healthcare network",
    r"community healthcare",
    r"cleantech automotive",
    r"배터리",
    r"2차전지",
    r"이차전지",
    r"전고체",
    r"전해질",
    r"리튬",
    r"전기차",
    r"전기 자동차",
    r"에너지저장",
    r"에너지 저장",
    r"반도체",
    r"디스플레이",
    r"혈액투석",
    r"인공장기",
    r"의료용",
    r"헬스케어",
    r"건강 네트워크",
    r"재생에너지 목표",
    r"태양광 입찰",
])

DOMESTIC_SOURCE_HINTS = [
    "Naver News Korea", "Google News Korea", "Bing News Korea",
    "워터저널", "Water Journal", "한국막학회", "Korean Membrane Society",
    "한국상하수도협회", "KWWA", "WATIS", "Water Korea",
    "환경부", "K-water", "한국환경공단", "산업일보", "에너지데일리",
]

SOURCE_CATALOG = [
    {"group": "국내 전문매체", "name": "워터저널", "url": "https://www.waterjournal.co.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "산업일보", "url": "https://www.industrynews.co.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "에너지데일리 환경·수처리", "url": "https://www.energydaily.co.kr/news/articleList.html?sc_section_code=S1N6&view_type=sm", "status": "웹/기사 소스"},
    {"group": "국내 학회·협회", "name": "한국막학회", "url": "https://www.membrane.or.kr/", "status": "학회/행사 소스"},
    {"group": "국내 학회·협회", "name": "한국상하수도협회", "url": "https://www.kwwa.or.kr/kr/main.do", "status": "협회/정책 소스"},
    {"group": "국내 학회·협회", "name": "한국물환경학회", "url": "https://www.kswe.or.kr/", "status": "학회 소스"},
    {"group": "국내 학회·협회", "name": "대한환경공학회", "url": "https://www.kosenv.or.kr/", "status": "학회 소스"},
    {"group": "국내 학회·협회", "name": "대한상하수도학회", "url": "https://www.ksww.or.kr/", "status": "학회 소스"},
    {"group": "국내 정부·공공", "name": "환경부", "url": "https://www.me.go.kr", "status": "정책 소스"},
    {"group": "국내 정부·공공", "name": "한국환경공단", "url": "https://www.keco.or.kr", "status": "공공 소스"},
    {"group": "국내 정부·공공", "name": "K-water", "url": "https://www.kwater.or.kr", "status": "공공 소스"},
    {"group": "국내 정부·공공", "name": "국가상수도정보시스템 WATIS", "url": "https://www.watis.or.kr/web/user/main.do", "status": "공공 소스"},
    {"group": "국내 전시회", "name": "Water Korea", "url": "https://waterkorea.kr/", "status": "전시회 소스"},
    {"group": "해외 전문매체", "name": "WaterWorld", "url": "https://www.waterworld.com/rss.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Water Online", "url": "https://www.wateronline.com/rss", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Smart Water Magazine", "url": "https://smartwatermagazine.com/rss.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "IWA", "url": "https://iwa-network.org/feed/", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "WaterNewsWire", "url": "https://waternewswire.com/feeds/main.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Global Water Intelligence", "url": "https://www.globalwaterintel.com/", "status": "웹/유료기사 중심"},
    {"group": "해외 학회·협회", "name": "International Desalination Association", "url": "https://idadesal.org", "status": "학회/행사 소스"},
    {"group": "해외 학회·협회", "name": "European Membrane Society", "url": "https://www.emsoc.eu", "status": "학회 소스"},
    {"group": "기업 뉴스룸", "name": "Veolia", "url": "https://www.veolia.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸", "name": "SUEZ", "url": "https://www.suez.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸", "name": "Toray Water Solutions", "url": "https://www.toraywater.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸", "name": "DuPont Water Solutions", "url": "https://www.dupont.com/water.html", "status": "기업 소스"},
    {"group": "기업 뉴스룸", "name": "Mitsubishi Heavy Industries", "url": "https://www.mhi.com/news", "status": "기업 소스"},
    {"group": "검색엔진", "name": "Google News RSS", "url": "https://news.google.com/rss", "status": "RSS 활성"},
    {"group": "검색엔진", "name": "Bing News RSS", "url": "https://www.bing.com/news/search?format=RSS", "status": "RSS 활성"},
    {"group": "검색엔진", "name": "Naver News", "url": "https://search.naver.com/search.naver?where=news", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Yahoo Japan News", "url": "https://news.yahoo.co.jp/", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Yandex", "url": "https://yandex.com/search/", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Baidu", "url": "https://www.baidu.com/", "status": "검색 링크 표시"},
]

SEARCH_QUERY_CONFIG = [
    {"name": "Google News Korea 상하수도", "engine": "google", "region": "domestic", "query": "상하수도 OR 수처리 OR 하수처리 OR 폐수처리 -배터리 -2차전지 -반도체"},
    {"name": "Google News Korea 막여과 MBR", "engine": "google", "region": "domestic", "query": "막여과 OR 분리막 OR MBR OR 중공사막 수처리 -배터리 -2차전지 -리튬"},
    {"name": "Google News Korea 재이용수 PFAS", "engine": "google", "region": "domestic", "query": "재이용수 OR PFAS OR 하수재이용 OR 정수장 OR 하수처리장"},
    {"name": "Google News Global Water", "engine": "google", "region": "global", "query": '"water treatment" OR wastewater OR "water reuse" OR PFAS'},
    {"name": "Google News Global Membrane MBR", "engine": "google", "region": "global", "query": '"membrane filtration" OR MBR OR "membrane bioreactor" OR ultrafiltration -battery -lithium -semiconductor'},
    {"name": "Bing News Korea 상하수도", "engine": "bing", "region": "domestic", "query": "상하수도 수처리 하수처리 폐수처리 -배터리 -2차전지"},
    {"name": "Bing News Korea 막여과 MBR", "engine": "bing", "region": "domestic", "query": "막여과 분리막 MBR 중공사막 수처리 -배터리 -반도체"},
    {"name": "Bing News Global MBR", "engine": "bing", "region": "global", "query": "water treatment wastewater MBR membrane bioreactor PFAS -battery -lithium"},
]

EVENT_CATALOG = [
    {"grade": "S", "name": "WEFTEC", "scope": "해외", "location": "미국", "date": "매년 9~10월", "scale": "대규모/메이저", "url": "https://www.weftec.org/", "note": "북미 최대급 물환경·하수처리 전시회"},
    {"grade": "S", "name": "Aquatech Amsterdam", "scope": "해외", "location": "네덜란드 암스테르담", "date": "격년 개최", "scale": "대규모/메이저", "url": "https://www.aquatechtrade.com/", "note": "글로벌 수처리 전시회"},
    {"grade": "S", "name": "Singapore International Water Week", "scope": "해외", "location": "싱가포르", "date": "격년 개최", "scale": "대규모/메이저", "url": "https://www.siww.com.sg/", "note": "아시아권 메이저 물산업 행사"},
    {"grade": "A", "name": "IWA World Water Congress & Exhibition", "scope": "해외", "location": "국가별 순환", "date": "격년 개최", "scale": "대규모/메이저", "url": "https://iwa-network.org/events/", "note": "IWA 대표 국제 학회·전시"},
    {"grade": "A", "name": "IWA Membrane Technology Conference", "scope": "해외", "location": "국가별 순환", "date": "비정기/학회 일정 확인 필요", "scale": "전문 메이저", "url": "https://iwa-network.org/events/", "note": "수처리용 멤브레인 전문 학회"},
    {"grade": "A", "name": "Water Korea", "scope": "국내", "location": "한국", "date": "매년", "scale": "국내 메이저", "url": "https://waterkorea.kr/", "note": "국내 상하수도 대표 전시회"},
    {"grade": "B", "name": "한국막학회 춘계학술대회", "scope": "국내", "location": "한국", "date": "매년 상반기", "scale": "전문 학회", "url": "https://www.membrane.or.kr/", "note": "분리막 전문 학술행사"},
    {"grade": "B", "name": "한국막학회 추계학술대회", "scope": "국내", "location": "한국", "date": "매년 하반기", "scale": "전문 학회", "url": "https://www.membrane.or.kr/", "note": "분리막 전문 학술행사"},
    {"grade": "B", "name": "대한상하수도학회 학술발표회", "scope": "국내", "location": "한국", "date": "학회 일정 확인 필요", "scale": "전문 학회", "url": "https://www.ksww.or.kr/", "note": "상하수도 분야 학술행사"},
    {"grade": "B", "name": "한국물환경학회 학술대회", "scope": "국내", "location": "한국", "date": "학회 일정 확인 필요", "scale": "전문 학회", "url": "https://www.kswe.or.kr/", "note": "물환경·수질 분야 학술행사"},
]

INCLUDE_KEYWORDS_PUBLIC = sorted(KEYWORDS.keys())
EXCLUDE_PATTERNS_PUBLIC = NEGATIVE_PATTERNS


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


def parse_entry_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")

    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc).astimezone(KST).strftime("%Y-%m-%d")
        except Exception:
            pass

    return datetime.now(KST).strftime("%Y-%m-%d")


def in_backfill_range(date_str):
    if not BACKFILL_MODE:
        return True

    if BACKFILL_START_DATE and date_str < BACKFILL_START_DATE:
        return False

    if BACKFILL_END_DATE and date_str > BACKFILL_END_DATE:
        return False

    return True


def google_news_rss_url(query, hl="ko", gl="KR", ceid="KR:ko"):
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"


def bing_news_rss_url(query):
    return f"https://www.bing.com/news/search?q={quote_plus(query)}&format=RSS"


def build_search_rss_feeds():
    if os.getenv("ENABLE_SEARCH_RSS", "true").lower() != "true":
        return []

    feeds = []

    for item in SEARCH_QUERY_CONFIG:
        engine = item.get("engine")
        query = item.get("query", "")
        name = item.get("name", "Search RSS")
        region = item.get("region", "")

        if not query:
            continue

        if engine == "google":
            if region == "global":
                url = google_news_rss_url(query, hl="en", gl="US", ceid="US:en")
            else:
                url = google_news_rss_url(query, hl="ko", gl="KR", ceid="KR:ko")
        elif engine == "bing":
            url = bing_news_rss_url(query)
        else:
            continue

        feeds.append({
            "name": name,
            "url": url,
            "region": region,
            "type": "search_rss",
        })

    return feeds


def merge_feed_sources():
    configured = load_json(FEEDS_FILE, [])

    if not isinstance(configured, list):
        configured = []

    feeds = []
    seen = set()

    for feed in configured + build_search_rss_feeds():
        url = feed.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        feeds.append(feed)

    return feeds


def is_domestic_article(article):
    source = article.get("source", "")
    domain = article.get("domain", "")
    countries = article.get("countries", []) or []
    title = article.get("title", "")
    summary = article.get("summary", "")

    combined = f"{source} {domain} {' '.join(countries)} {title} {summary}".lower()

    if "한국" in countries or "south korea" in combined or "korea" in combined:
        return True

    if domain.endswith(".kr") or ".kr/" in domain:
        return True

    for hint in DOMESTIC_SOURCE_HINTS:
        if hint.lower() in combined:
            return True

    korean_hits = ["상하수도", "하수처리", "폐수처리", "수처리", "막여과", "중공사막", "환경부", "한국수자원공사", "한국환경공단"]
    return any(k in f"{title} {summary}" for k in korean_hits)


def fetch_articles():
    feeds = merge_feed_sources()
    articles = []
    rss_sleep = float(os.getenv("RSS_SLEEP_SECONDS", "0.35"))

    for feed in feeds:
        name = feed.get("name", "Unknown")
        url = feed.get("url")
        feed_region = feed.get("region", "")
        feed_type = feed.get("type", "rss")

        if not url:
            continue

        parsed = feedparser.parse(url)

        for entry in parsed.entries[:60]:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
            published_date = parse_entry_date(entry)

            if not in_backfill_range(published_date):
                continue

            score, matched = score_article(title, summary)

            if score < MIN_SCORE:
                continue

            article = {
                "date": published_date,
                "title": title,
                "link": link,
                "summary": summary[:900],
                "source": name,
                "domain": get_domain(link),
                "score": score,
                "matched": matched,
                "region": feed_region,
                "source_type": feed_type,
            }

            article["domestic"] = is_domestic_article(article)
            articles.append(article)

        time.sleep(rss_sleep)

    dedup = {}

    for a in sorted(articles, key=lambda x: x["score"], reverse=True):
        key = a.get("link") or f"{a.get('title')}::{a.get('source')}"
        if key and key not in dedup:
            dedup[key] = a

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
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    if "pfas" in keys or "pfas" in text:
        return "PFAS/오염물"

    if (
        "mbr" in keys
        or "membrane bioreactor" in keys
        or "분리막 생물반응조" in keys
        or "막분리활성슬러지" in keys
        or "mbr" in text
    ):
        return "분리막/MBR"

    if (
        "membrane" in keys
        or "hollow fiber" in keys
        or "ultrafiltration" in keys
        or "microfiltration" in keys
        or "막여과" in keys
        or "중공사막" in keys
        or "분리막" in keys
    ):
        return "분리막/막여과"

    if {"conference", "symposium", "water korea", "weftec", "aquatech", "iwa mtc", "한국막학회", "워터코리아"} & keys:
        return "학회/전시회"

    if {"tender", "contract", "award", "expansion", "upgrade", "pilot", "commissioning"} & keys:
        return "프로젝트/수주"

    if {"veolia", "xylem", "toray", "asahi kasei", "pentair", "kovalus", "suez", "dupont", "kubota"} & keys:
        return "기업동향"

    if {"water reuse", "reclaimed water", "재이용수", "물재이용", "물 재이용", "하수재이용"} & keys:
        return "재이용수"

    if {"desalination", "ro", "nf", "담수화", "역삼투"} & keys:
        return "담수화/RO"

    if {"환경부", "regulation", "funding"} & keys:
        return "규제/정책"

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
  PFAS/오염물, 재이용수, 분리막/MBR, 분리막/막여과, 산업폐수, 담수화/RO, 프로젝트/수주, 기업동향, 규제/정책, 학회/전시회, 수처리 산업동향
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

    existing = set((item.get("date"), item.get("link")) for item in history)

    for a in articles:
        article_date = a.get("date") or datetime.now(KST).strftime("%Y-%m-%d")
        key = (article_date, a.get("link"))

        if key in existing:
            continue

        ai = a["ai"]

        history.append({
            "date": article_date,
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
            "domestic": a.get("domestic", False),
            "region": a.get("region", ""),
            "source_type": a.get("source_type", ""),
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


def filter_items_by_month(history, month_key):
    return [x for x in history if x.get("date", "").startswith(month_key)]


def get_month_weeks(month_key):
    items = []
    year, month = map(int, month_key.split("-"))

    current = datetime(year, month, 1, tzinfo=KST)

    while current.month == month:
        iso = current.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"

        if week_key not in items:
            items.append(week_key)

        current += timedelta(days=1)

    return items


def filter_items_by_iso_week(history, week_key):
    result = []

    for x in history:
        date_str = x.get("date", "")

        if not date_str:
            continue

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
            iso = dt.isocalendar()

            if f"{iso.year}-W{iso.week:02d}" == week_key:
                result.append(x)
        except Exception:
            continue

    return result


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



def markdown_to_html(text):
    if not text:
        return ""

    return markdown.markdown(
        text,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html5",
    )


def get_site_base_path():
    repo = os.getenv("GITHUB_REPOSITORY", "")

    if "/" in repo:
        return "/" + repo.split("/", 1)[1].strip("/") + "/"

    return "/"


def rel_url(path_text):
    base = get_site_base_path().rstrip("/")
    path_text = str(path_text).lstrip("/")

    if not path_text:
        return base + "/"

    return f"{base}/{path_text}"


def week_range_label(week_key):
    try:
        year = int(week_key.split("-W", 1)[0])
        week = int(week_key.split("-W", 1)[1])
        start = datetime.fromisocalendar(year, week, 1).replace(tzinfo=KST)
        end = start + timedelta(days=6)
        return f"{start.strftime('%m.%d')}~{end.strftime('%m.%d')}"
    except Exception:
        return ""


def month_label(month_key):
    try:
        year, month = month_key.split("-", 1)
        return f"{year}년 {int(month):02d}월"
    except Exception:
        return month_key


def get_week_key_from_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except Exception:
        return ""


def get_date_label(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
        return f"{date_str} ({weekday})"
    except Exception:
        return date_str


def list_existing_report_keys():
    history = load_json(HISTORY_FILE, [])

    daily_keys = set()
    weekly_keys = set()
    monthly_keys = set()

    for item in history:
        date_str = item.get("date", "")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            daily_keys.add(date_str)
            week_key = get_week_key_from_date(date_str)
            if week_key:
                weekly_keys.add(week_key)
            monthly_keys.add(date_str[:7])

    if REPORTS_DIR.exists():
        for p in REPORTS_DIR.iterdir():
            if p.is_dir() and (p / "index.html").exists():
                daily_keys.add(p.name)

    if WEEKLY_DIR.exists():
        for p in WEEKLY_DIR.iterdir():
            if p.is_dir() and (p / "index.html").exists():
                weekly_keys.add(p.name)

    if MONTHLY_DIR.exists():
        for p in MONTHLY_DIR.iterdir():
            if p.is_dir() and (p / "index.html").exists():
                monthly_keys.add(p.name)

    daily = sorted(daily_keys, reverse=True)[:90]
    weekly = sorted(weekly_keys, reverse=True)[:52]
    monthly = sorted(monthly_keys, reverse=True)[:36]

    return daily, weekly, monthly



def split_visible_hidden(items, visible_count):
    return items[:visible_count], items[visible_count:]


def build_nav_group(title, items, visible_count, url_builder, label_builder, active_class):
    parts = [f'<div class="nav-section-title">{html.escape(title)}</div>']

    if not items:
        parts.append('<div class="nav-empty">아직 생성된 항목이 없습니다.</div>')
        return parts

    visible, hidden = split_visible_hidden(items, visible_count)

    for key in visible:
        url = url_builder(key)
        label = label_builder(key)
        parts.append(f'<a class="nav-link {active_class(url)}" href="{rel_url(url)}">{html.escape(label)}</a>')

    if hidden:
        parts.append('<details class="nav-more"><summary>더보기</summary>')
        for key in hidden:
            url = url_builder(key)
            label = label_builder(key)
            parts.append(f'<a class="nav-link {active_class(url)}" href="{rel_url(url)}">{html.escape(label)}</a>')
        parts.append('</details>')

    return parts


def build_left_nav(active_url=""):
    daily, weekly, monthly = list_existing_report_keys()

    def active_class(url):
        return "active" if active_url.strip("/") == url.strip("/") else ""

    parts = []
    parts.append('<nav class="side-nav">')
    parts.append(f'<a class="nav-home {active_class("")}" href="{rel_url("")}">홈</a>')

    parts.extend(build_nav_group(
        "일일 상세 보고서",
        daily,
        5,
        lambda key: f"reports/{key}/",
        lambda key: get_date_label(key),
        active_class,
    ))

    parts.extend(build_nav_group(
        "주간 업계 동향",
        weekly,
        5,
        lambda key: f"weekly/{key}/",
        lambda key: f"{key} ({week_range_label(key)})" if week_range_label(key) else key,
        active_class,
    ))

    parts.extend(build_nav_group(
        "월간 업계 동향",
        monthly,
        6,
        lambda key: f"monthly/{key}/",
        lambda key: month_label(key),
        active_class,
    ))

    parts.append('<div class="nav-section-title">바로가기</div>')
    quick_links = [
        ("sources/", "정보 출처"),
        ("filters/", "필터링 기준"),
        ("events/", "학회·전시회 일정"),
    ]
    for url, label in quick_links:
        parts.append(f'<a class="nav-link {active_class(url)}" href="{rel_url(url)}">{html.escape(label)}</a>')

    parts.append('</nav>')
    return "\n".join(parts)


def build_toc(toc_items):
    if not toc_items:
        return '<aside class="toc"><div class="toc-title">목차</div><div class="toc-empty">표시할 목차가 없습니다.</div></aside>'

    links = []
    for item_id, label in toc_items:
        links.append(f'<a href="#{html.escape(item_id)}">{html.escape(label)}</a>')

    return f'<aside class="toc"><div class="toc-title">목차</div>{"".join(links)}</aside>'


def make_html_page(title, body_html, path, active_url="", subtitle="", toc_items=None):
    path.mkdir(parents=True, exist_ok=True)
    toc_items = toc_items or []
    nav_html = build_left_nav(active_url)
    toc_html = build_toc(toc_items)

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg:#f4f7fb;
      --panel:#ffffff;
      --ink:#0f172a;
      --muted:#64748b;
      --line:#e2e8f0;
      --brand:#0f4c81;
      --brand-dark:#0b3157;
      --brand-soft:#e0f2fe;
      --accent:#0284c7;
      --warn:#fff7ed;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      background:var(--bg);
      color:var(--ink);
      font-family:Arial, "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
      line-height:1.65;
    }}
    a {{ color:#1d4ed8; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .topbar {{
      position:sticky;
      top:0;
      z-index:20;
      background:linear-gradient(135deg, var(--brand-dark), var(--brand));
      color:#fff;
      border-bottom:1px solid rgba(255,255,255,.14);
    }}
    .topbar-inner {{
      max-width:1480px;
      margin:0 auto;
      padding:18px 24px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:16px;
    }}
    .brand {{
      display:inline-flex;
      align-items:center;
      gap:8px;
      color:#fff;
      font-size:20px;
      font-weight:800;
      letter-spacing:-.02em;
    }}
    .brand:hover {{ text-decoration:none; }}
    .top-date {{ font-size:13px; color:#dbeafe; white-space:nowrap; }}
    .layout {{
      max-width:1480px;
      margin:0 auto;
      padding:24px;
      display:grid;
      grid-template-columns:280px minmax(0, 1fr) 230px;
      gap:22px;
      align-items:start;
    }}
    .side-nav {{
      position:sticky;
      top:82px;
      max-height:calc(100vh - 108px);
      overflow:auto;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:18px;
      padding:16px;
      box-shadow:0 8px 22px rgba(15,23,42,.05);
    }}
    .nav-home {{
      display:block;
      padding:10px 12px;
      border-radius:12px;
      color:var(--ink);
      font-weight:800;
      background:#f8fafc;
      border:1px solid var(--line);
      margin-bottom:14px;
    }}
    .nav-section-title {{
      margin:16px 0 7px;
      font-size:12px;
      font-weight:800;
      color:#475569;
      text-transform:uppercase;
      letter-spacing:.02em;
    }}
    .nav-link {{
      display:block;
      padding:7px 9px;
      border-radius:10px;
      color:#334155;
      font-size:13px;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }}
    .nav-link:hover, .nav-home:hover {{ background:var(--brand-soft); text-decoration:none; }}
    .nav-link.active, .nav-home.active {{ background:#dbeafe; color:#0f4c81; font-weight:800; }}
    .nav-empty {{ color:var(--muted); font-size:12px; padding:6px 2px; }}
    .nav-more summary {{
      cursor:pointer;
      color:#0f4c81;
      font-size:13px;
      font-weight:800;
      padding:7px 9px;
      border-radius:10px;
      background:#f8fafc;
      margin-top:4px;
    }}
    .nav-more[open] summary {{ background:#dbeafe; }}
    .stat-grid {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; margin-bottom:18px; }}
    .stat-card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 4px 14px rgba(15,23,42,.04); }}
    .stat-value {{ font-size:28px; font-weight:900; color:#0f4c81; line-height:1.2; }}
    .stat-label {{ color:var(--muted); font-size:13px; margin-top:6px; }}
    .headline-list {{ margin:0; padding-left:18px; }}
    .headline-list li {{ margin:8px 0; }}
    .source-table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    .source-table th, .source-table td {{ border-bottom:1px solid var(--line); padding:9px 8px; text-align:left; vertical-align:top; }}
    .source-table th {{ color:#475569; background:#f8fafc; }}
    .tag-cloud {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .tag-cloud span {{ display:inline-block; background:#f1f5f9; border:1px solid var(--line); border-radius:999px; padding:5px 10px; font-size:13px; }}
    .content {{ min-width:0; }}
    .hero {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:22px;
      padding:28px;
      margin-bottom:20px;
      box-shadow:0 8px 22px rgba(15,23,42,.05);
    }}
    .hero h1 {{ margin:0; font-size:30px; line-height:1.25; letter-spacing:-.03em; }}
    .hero .subtitle {{ margin-top:10px; color:var(--muted); font-size:15px; }}
    .card {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:18px;
      padding:22px;
      margin-bottom:18px;
      box-shadow:0 4px 14px rgba(15,23,42,.045);
    }}
    .card h2 {{ margin:4px 0 10px; font-size:22px; line-height:1.35; letter-spacing:-.02em; }}
    .card h3 {{ margin:20px 0 8px; font-size:16px; }}
    .report-body {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:18px;
      padding:26px;
      margin-bottom:18px;
      box-shadow:0 4px 14px rgba(15,23,42,.045);
    }}
    .report-body h1, .report-body h2, .report-body h3 {{ letter-spacing:-.02em; }}
    .report-body h1 {{ font-size:26px; }}
    .report-body h2 {{ font-size:22px; margin-top:28px; padding-top:6px; }}
    .report-body h3 {{ font-size:18px; margin-top:24px; }}
    .report-body p {{ margin:9px 0; }}
    .report-body ul, .report-body ol {{ padding-left:22px; }}
    .report-body li {{ margin:6px 0; }}
    .meta {{ color:var(--muted); font-size:13px; }}
    .pill {{
      display:inline-block;
      background:var(--brand-soft);
      color:#075985;
      border-radius:999px;
      padding:3px 10px;
      font-size:13px;
      margin:2px 6px 2px 0;
      font-weight:700;
    }}
    .brief {{ background:#f8fafc; border-left:4px solid var(--brand); padding:11px 13px; border-radius:0 10px 10px 0; }}
    .why {{ background:var(--warn); border-left:4px solid #f97316; padding:11px 13px; border-radius:0 10px 10px 0; }}
    .toc {{
      position:sticky;
      top:82px;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:18px;
      padding:16px;
      box-shadow:0 8px 22px rgba(15,23,42,.05);
    }}
    .toc-title {{ font-size:13px; font-weight:800; color:#475569; margin-bottom:8px; }}
    .toc a {{ display:block; color:#334155; font-size:13px; padding:6px 0; border-bottom:1px solid #f1f5f9; }}
    .toc-empty {{ color:var(--muted); font-size:12px; }}
    .dashboard-grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin-bottom:18px; }}
    .dash-card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 4px 14px rgba(15,23,42,.04); }}
    .dash-card h2 {{ font-size:17px; margin:0 0 10px; }}
    .dash-card a {{ display:block; margin:6px 0; font-size:14px; }}
    @media (max-width:1180px) {{
      .layout {{ grid-template-columns:250px minmax(0, 1fr); }}
      .toc {{ display:none; }}
      .stat-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
    }}
    @media (max-width:820px) {{
      .topbar-inner {{ align-items:flex-start; flex-direction:column; }}
      .layout {{ display:block; padding:14px; }}
      .side-nav {{ position:relative; top:auto; max-height:none; margin-bottom:16px; }}
      .hero {{ padding:22px; }}
      .hero h1 {{ font-size:24px; }}
      .dashboard-grid {{ grid-template-columns:1fr; }}
      .stat-grid {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="{rel_url("")}">💧 상하수도·수처리 뉴스 브리핑</a>
      <div class="top-date">{datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}</div>
    </div>
  </header>
  <div class="layout">
    {nav_html}
    <main class="content">
      <section class="hero">
        <h1>{html.escape(title)}</h1>
        {f'<div class="subtitle">{html.escape(subtitle)}</div>' if subtitle else ''}
      </section>
      {body_html}
    </main>
    {toc_html}
  </div>
</body>
</html>
"""

    (path / "index.html").write_text(html_doc, encoding="utf-8")


def normalize_display_item(item):
    if "ai" in item:
        ai = item.get("ai", {})
        return {
            "date": item.get("date", ""),
            "title": item.get("title", ""),
            "ko_title": ai.get("ko_title", item.get("title", "")),
            "brief": ai.get("brief", ""),
            "summary": ai.get("summary", ""),
            "why_important": ai.get("why_important", ""),
            "category": ai.get("category", guess_category(item)),
            "countries": ai.get("countries", []),
            "companies": ai.get("companies", []),
            "technologies": ai.get("technologies", item.get("matched", [])),
            "policy_alert": ai.get("policy_alert", ""),
            "source": item.get("source", ""),
            "link": item.get("link", ""),
            "score": item.get("score", 0),
        }

    return {
        "date": item.get("date", ""),
        "title": item.get("title", ""),
        "ko_title": item.get("ko_title", item.get("title", "")),
        "brief": item.get("brief", ""),
        "summary": item.get("summary", ""),
        "why_important": item.get("why_important", ""),
        "category": item.get("category", ""),
        "countries": item.get("countries", []),
        "companies": item.get("companies", []),
        "technologies": item.get("technologies", item.get("keywords", [])),
        "policy_alert": item.get("policy_alert", ""),
        "source": item.get("source", ""),
        "link": item.get("link", ""),
        "score": item.get("score", 0),
    }


def build_article_cards(items):
    cards = []

    for i, raw in enumerate(items, 1):
        a = normalize_display_item(raw)
        countries = " ".join(add_country_flag(c) for c in a.get("countries", []))
        companies = ", ".join(a.get("companies", []))
        techs = ", ".join(a.get("technologies", []))
        emoji = emoji_for_category(a.get("category", ""), a.get("technologies", []))
        source_text = a.get("source", "") or "출처 미확인"
        date_text = a.get("date", "") or "날짜 미확인"

        cards.append(f"""
        <section class="card" id="article-{i}">
          <p class="meta">#{i} · {html.escape(date_text)} · {html.escape(source_text)} · 점수 {html.escape(str(a.get('score', 0)))}</p>
          <h2>{emoji} {html.escape(a.get('ko_title', '') or a.get('title', ''))}</h2>
          <p><span class="pill">{html.escape(a.get('category', '') or '분류 없음')}</span></p>
          <p class="brief">{html.escape(a.get('brief', '') or '요약 정보가 없습니다.')}</p>
          <h3>내용 요약</h3>
          <p>{html.escape(a.get('summary', '') or '상세 요약 정보가 없습니다.')}</p>
          <h3>왜 중요한가?</h3>
          <p class="why">{html.escape(a.get('why_important', '') or '중요도 분석 정보가 없습니다.')}</p>
          <p class="meta">국가: {html.escape(countries or '-')}</p>
          <p class="meta">기업: {html.escape(companies or '-')}</p>
          <p class="meta">기술: {html.escape(techs or '-')}</p>
          {f'<p><a href="{html.escape(a.get("link", ""))}" target="_blank" rel="noopener noreferrer">원문 기사 보기</a></p>' if a.get("link") else ''}
        </section>
        """)

    return "".join(cards)


def get_recent_daily_items(target_date, selected_articles, history, max_days=3, limit=12):
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=KST)
    except Exception:
        target_dt = datetime.now(KST)

    allowed_dates = set((target_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max_days))
    pool = []

    for item in selected_articles:
        item_date = item.get("date", target_date)
        if item_date in allowed_dates:
            pool.append(item)

    for item in history:
        if item.get("date", "") in allowed_dates:
            pool.append(item)

    dedup = {}
    for item in sorted(pool, key=lambda x: x.get("score", 0), reverse=True):
        key = item.get("link") or item.get("ko_title") or item.get("title")
        if key and key not in dedup:
            dedup[key] = item

    return list(dedup.values())[:limit]


def create_daily_report(articles, history=None, target_date=None):
    history = history or []
    today = target_date or datetime.now(KST).strftime("%Y-%m-%d")
    report_dir = REPORTS_DIR / today

    display_items = get_recent_daily_items(today, articles, history, max_days=3, limit=max(10, MAX_ITEMS))

    title = f"{today} 상하수도·수처리 상세 분석 보고서"
    subtitle = "당일 기사 우선, 부족 시 최근 3일 이내 관련 기사까지 포함합니다. 뉴스 게시판용 기사는 다른 날짜 보고서와 중복될 수 있습니다."
    active_url = f"reports/{today}/"
    toc_items = [(f"article-{i}", f"기사 {i}") for i in range(1, min(len(display_items), 12) + 1)]

    if display_items:
        body = build_article_cards(display_items)
    else:
        body = '<section class="card">최근 3일 기준 필터 조건에 맞는 뉴스가 없습니다.</section>'

    make_html_page(title, body, report_dir, active_url=active_url, subtitle=subtitle, toc_items=toc_items)

    base_url = get_pages_base_url()
    return f"{base_url}/reports/{today}/" if base_url else f"reports/{today}/"


def create_period_report(period_type, items, key=None):
    now = datetime.now(KST)

    if period_type == "weekly":
        if not key:
            iso = now.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        period_label = week_range_label(key)
        title = f"{key} 상하수도·수처리 주간 업계 동향"
        subtitle = f"기간: {period_label}" if period_label else "주간 누적 동향"
        report_dir = WEEKLY_DIR / key
        report_text = build_trend_report_text(title, items, "weekly")
        url_path = f"weekly/{key}/"
        toc_items = [
            ("executive-summary", "Executive Summary"),
            ("countries", "주요 국가"),
            ("companies", "주요 기업"),
            ("technologies", "주요 기술"),
            ("policy", "규제/정책"),
            ("articles", "주요 기사"),
        ]
    else:
        if not key:
            key = now.strftime("%Y-%m")
        title = f"{month_label(key)} 상하수도·수처리 월간 업계 동향"
        subtitle = f"기간: {key}-01 ~ {key}-말일"
        report_dir = MONTHLY_DIR / key
        report_text = build_trend_report_text(title, items, "monthly")
        url_path = f"monthly/{key}/"
        toc_items = [
            ("executive-summary", "Executive Summary"),
            ("keywords", "이달의 키워드"),
            ("countries", "국가별 동향"),
            ("companies", "기업별 동향"),
            ("technologies", "기술별 동향"),
            ("projects", "주요 프로젝트"),
            ("policy", "규제/정책"),
        ]

    report_html = markdown_to_html(report_text)
    body = f'<section class="report-body">{report_html}</section>'

    make_html_page(title, body, report_dir, active_url=url_path, subtitle=subtitle, toc_items=toc_items)

    base_url = get_pages_base_url()
    return f"{base_url}/{url_path}" if base_url else url_path


def create_backfill_period_reports(history):
    if not BACKFILL_MODE or not BACKFILL_START_DATE:
        return

    month_key = BACKFILL_START_DATE[:7]

    for week_key in get_month_weeks(month_key):
        week_items = filter_items_by_iso_week(history, week_key)

        if not week_items:
            continue

        create_period_report("weekly", week_items, key=week_key)

    month_items = filter_items_by_month(history, month_key)

    if month_items:
        create_period_report("monthly", month_items, key=month_key)


def create_recent_daily_history_pages(history, selected_articles):
    dates = sorted({x.get("date", "") for x in history if re.match(r"^\d{4}-\d{2}-\d{2}$", x.get("date", ""))}, reverse=True)

    for date_key in dates[:14]:
        if date_key == datetime.now(KST).strftime("%Y-%m-%d"):
            continue
        create_daily_report(selected_articles, history, target_date=date_key)



def article_is_domestic(item):
    if item.get("domestic"):
        return True

    countries = item.get("countries", []) or []
    if "한국" in countries or "대한민국" in countries:
        return True

    source = item.get("source", "")
    domain = get_domain(item.get("link", ""))

    test_text = f"{source} {domain} {item.get('title','')} {item.get('ko_title','')} {item.get('summary','')}"
    if domain.endswith(".kr") or ".kr/" in domain:
        return True

    return any(hint.lower() in test_text.lower() for hint in DOMESTIC_SOURCE_HINTS)


def get_dashboard_items(history, limit=5):
    sorted_items = sorted(history, key=lambda x: (x.get("date", ""), x.get("score", 0)), reverse=True)

    global_items = []
    domestic_items = []

    seen_global = set()
    seen_domestic = set()

    for item in sorted_items:
        key = item.get("link") or item.get("ko_title") or item.get("title")
        if not key:
            continue

        if article_is_domestic(item):
            if key not in seen_domestic:
                domestic_items.append(item)
                seen_domestic.add(key)
        else:
            if key not in seen_global:
                global_items.append(item)
                seen_global.add(key)

        if len(global_items) >= limit and len(domestic_items) >= limit:
            break

    return global_items[:limit], domestic_items[:limit]


def build_headline_list(items):
    if not items:
        return '<p class="meta">표시할 뉴스가 아직 없습니다.</p>'

    parts = ['<ol class="headline-list">']
    for item in items:
        title = item.get("ko_title") or item.get("title") or "제목 없음"
        source = item.get("source", "출처 미확인")
        date = item.get("date", "")
        link = item.get("link", "")
        category = item.get("category", "")
        label = f"{title} <span class='meta'>· {html.escape(date)} · {html.escape(source)} · {html.escape(category)}</span>"
        if link:
            parts.append(f'<li><a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{label}</a></li>')
        else:
            parts.append(f'<li>{label}</li>')
    parts.append("</ol>")
    return "\n".join(parts)


def build_event_preview(limit=5):
    rows = []
    for item in EVENT_CATALOG[:limit]:
        rows.append(
            f"<tr><td>{html.escape(item['grade'])}</td><td>{html.escape(item['name'])}</td><td>{html.escape(item['location'])}</td><td>{html.escape(item['date'])}</td><td>{html.escape(item['scale'])}</td></tr>"
        )

    return f"""
    <table class="source-table">
      <thead><tr><th>등급</th><th>행사</th><th>장소</th><th>일정</th><th>규모</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p><a href="{rel_url('events/')}">전체 학회·전시회 일정 보기</a></p>
    """


def create_sources_page():
    groups = {}
    for item in SOURCE_CATALOG:
        groups.setdefault(item["group"], []).append(item)

    sections = []
    for group, items in groups.items():
        rows = []
        for item in items:
            rows.append(
                f"<tr><td>{html.escape(item['name'])}</td><td><a href='{html.escape(item['url'])}' target='_blank' rel='noopener noreferrer'>{html.escape(item['url'])}</a></td><td>{html.escape(item['status'])}</td></tr>"
            )
        sections.append(f"""
        <section class="card" id="{html.escape(group)}">
          <h2>{html.escape(group)}</h2>
          <table class="source-table">
            <thead><tr><th>출처</th><th>URL</th><th>상태</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </section>
        """)

    make_html_page(
        "정보 출처",
        "".join(sections),
        DOCS_DIR / "sources",
        active_url="sources/",
        subtitle="RSS 활성 소스, 웹 참고 소스, 검색엔진 소스를 구분해 정리합니다.",
        toc_items=[(group, group) for group in groups.keys()],
    )


def create_filters_page():
    include_html = '<div class="tag-cloud">' + ''.join(f"<span>{html.escape(k)}</span>" for k in INCLUDE_KEYWORDS_PUBLIC) + '</div>'
    exclude_html = '<div class="tag-cloud">' + ''.join(f"<span>{html.escape(k)}</span>" for k in EXCLUDE_PATTERNS_PUBLIC) + '</div>'

    body = f"""
    <section class="card" id="include">
      <h2>포함 키워드</h2>
      <p class="meta">아래 키워드가 제목·요약에 포함되면 점수가 올라갑니다. MBR, 막여과, 중공사막, 막오염, TMP, Flux 등 수처리용 멤브레인 키워드를 확장했습니다.</p>
      {include_html}
    </section>
    <section class="card" id="exclude">
      <h2>제외 키워드</h2>
      <p class="meta">배터리 분리막, 반도체, 의료용 멤브레인, 자동차/방산 주식 등 수처리와 직접성이 낮은 항목을 제외합니다.</p>
      {exclude_html}
    </section>
    """

    make_html_page(
        "필터링 기준",
        body,
        DOCS_DIR / "filters",
        active_url="filters/",
        subtitle="수집 기사 선별에 사용하는 포함/제외 키워드입니다.",
        toc_items=[("include", "포함 키워드"), ("exclude", "제외 키워드")],
    )


def create_events_page():
    rows = []
    for item in EVENT_CATALOG:
        rows.append(
            f"<tr><td>{html.escape(item['grade'])}</td><td><a href='{html.escape(item['url'])}' target='_blank' rel='noopener noreferrer'>{html.escape(item['name'])}</a></td><td>{html.escape(item['scope'])}</td><td>{html.escape(item['location'])}</td><td>{html.escape(item['date'])}</td><td>{html.escape(item['scale'])}</td><td>{html.escape(item['note'])}</td></tr>"
        )

    body = f"""
    <section class="card" id="events">
      <h2>국내·해외 멤브레인/수처리 학회·전시회</h2>
      <table class="source-table">
        <thead><tr><th>등급</th><th>행사</th><th>구분</th><th>장소</th><th>일정</th><th>규모</th><th>비고</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p class="meta">정확한 개최일·시간·부스 규모는 각 공식 홈페이지 공지를 기준으로 확인해야 합니다.</p>
    </section>
    """

    make_html_page(
        "학회·전시회 일정",
        body,
        DOCS_DIR / "events",
        active_url="events/",
        subtitle="국내외 수처리·멤브레인 업계 주요 학회와 전시회입니다.",
        toc_items=[("events", "행사 목록")],
    )


def create_static_info_pages():
    create_sources_page()
    create_filters_page()
    create_events_page()


def update_docs_index(daily_url, weekly_url, monthly_url):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    history = load_json(HISTORY_FILE, [])
    daily, weekly, monthly = list_existing_report_keys()

    latest_daily = daily[:5]
    latest_weekly = weekly[:5]
    latest_monthly = monthly[:6]

    global_items, domestic_items = get_dashboard_items(history, limit=5)

    total_count = len(history)
    domestic_count = sum(1 for x in history if article_is_domestic(x))
    global_count = max(total_count - domestic_count, 0)
    source_count = len(SOURCE_CATALOG)

    stats = f"""
    <section class="stat-grid">
      <div class="stat-card"><div class="stat-value">{total_count}</div><div class="stat-label">누적 기사</div></div>
      <div class="stat-card"><div class="stat-value">{domestic_count}</div><div class="stat-label">국내 기사</div></div>
      <div class="stat-card"><div class="stat-value">{global_count}</div><div class="stat-label">해외 기사</div></div>
      <div class="stat-card"><div class="stat-value">{source_count}</div><div class="stat-label">관리 출처</div></div>
    </section>
    """

    daily_links = "".join(
        f'<a href="{rel_url(f"reports/{key}/")}">{html.escape(get_date_label(key))} 상세 분석 보고서</a>'
        for key in latest_daily
    ) or '<p class="meta">아직 생성된 일일 보고서가 없습니다.</p>'

    weekly_links = "".join(
        f'<a href="{rel_url(f"weekly/{key}/")}">{html.escape(key)} {html.escape(f"({week_range_label(key)})" if week_range_label(key) else "")}</a>'
        for key in latest_weekly
    ) or '<p class="meta">아직 생성된 주간 리포트가 없습니다.</p>'

    monthly_links = "".join(
        f'<a href="{rel_url(f"monthly/{key}/")}">{html.escape(month_label(key))} 월간 업계 동향</a>'
        for key in latest_monthly
    ) or '<p class="meta">아직 생성된 월간 리포트가 없습니다.</p>'

    body = f"""
    {stats}

    <section class="dashboard-grid" id="reports">
      <div class="dash-card">
        <h2>일일 상세 보고서</h2>
        {daily_links}
      </div>
      <div class="dash-card">
        <h2>주간 업계 동향</h2>
        {weekly_links}
      </div>
      <div class="dash-card">
        <h2>월간 업계 동향</h2>
        {monthly_links}
      </div>
    </section>

    <section class="dashboard-grid" id="headlines">
      <div class="dash-card">
        <h2>세계 주요 뉴스 TOP 5</h2>
        {build_headline_list(global_items)}
      </div>
      <div class="dash-card">
        <h2>국내 주요 뉴스 TOP 5</h2>
        {build_headline_list(domestic_items)}
      </div>
      <div class="dash-card">
        <h2>학회·전시회 일정</h2>
        {build_event_preview(limit=5)}
      </div>
    </section>

    <section class="card" id="source-filter">
      <h2>출처 및 필터링 기준</h2>
      <p>수집 출처와 필터링 키워드를 별도 페이지로 공개합니다.</p>
      <p><a href="{rel_url('sources/')}">정보 출처 보기</a></p>
      <p><a href="{rel_url('filters/')}">필터링 기준 보기</a></p>
      <p><a href="{rel_url('events/')}">학회·전시회 일정 보기</a></p>
    </section>
    """

    make_html_page(
        "상하수도·수처리 뉴스 브리핑",
        body,
        DOCS_DIR,
        active_url="",
        subtitle="국내·해외 수처리 뉴스, 멤브레인/MBR 동향, 학회·전시회 일정을 누적 관리합니다.",
        toc_items=[("reports", "보고서"), ("headlines", "주요 뉴스"), ("source-filter", "출처/필터")],
    )


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

    create_backfill_period_reports(history)
    create_recent_daily_history_pages(history, selected_articles)

    week_items = filter_week_items(history)
    month_items = filter_month_items(history)

    weekly_one_line = build_period_one_line("이번 주 상하수도·수처리 동향", week_items)
    monthly_one_line = build_period_one_line("이번 달 상하수도·수처리 동향", month_items)

    daily_url = create_daily_report(selected_articles, history)
    weekly_url = create_period_report("weekly", week_items)
    monthly_url = create_period_report("monthly", month_items)

    create_static_info_pages()
    update_docs_index(daily_url, weekly_url, monthly_url)

    telegram_text = build_telegram_message(
        selected_articles,
        daily_url,
        weekly_url,
        monthly_url,
        weekly_one_line,
        monthly_one_line,
    )

    if SEND_TELEGRAM:
        send_telegram(telegram_text)

    sent = load_json(SENT_FILE, [])
    sent_links = set(sent)

    for article in selected_articles:
        if article.get("link"):
            sent_links.add(article["link"])

    save_json(SENT_FILE, list(sent_links)[-2000:])


if __name__ == "__main__":
    main()
