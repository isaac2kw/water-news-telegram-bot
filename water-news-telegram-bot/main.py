import os
import re
import json
import html
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from difflib import SequenceMatcher

import feedparser
import requests
import markdown


KST = timezone(timedelta(hours=9))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# gpt-5 계열 모델은 temperature 커스텀 값을 지원하지 않으므로 전송하지 않습니다.
# gpt-4.1 등 일반 모델은 temperature를 정상 지원합니다.
IS_GPT5_FAMILY = OPENAI_MODEL.startswith("gpt-5")

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "8"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "8"))

BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
BACKFILL_START_DATE = os.getenv("BACKFILL_START_DATE", "")
BACKFILL_END_DATE = os.getenv("BACKFILL_END_DATE", "")
SEND_TELEGRAM = os.getenv("SEND_TELEGRAM", "true").lower() == "true"

# Instagram card-news review email settings.
# Required GitHub Secrets: GMAIL_USER, GMAIL_APP_PASSWORD, CARD_RECIPIENT.
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
CARD_RECIPIENT = os.getenv("CARD_RECIPIENT", GMAIL_USER or "")
FORCE_CARD_NEWS = os.getenv("FORCE_CARD_NEWS", "false").lower() == "true"
CARD_NEWS_ONLY = os.getenv("CARD_NEWS_ONLY", "false").lower() == "true"
CARD_NEWS_TOP_N = int(os.getenv("CARD_NEWS_TOP_N", "5"))

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
FEEDS_FILE = BASE_DIR / "feeds.json"
SENT_FILE = BASE_DIR / "sent_links.json"
HISTORY_FILE = BASE_DIR / "news_history.json"

DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "reports"
WEEKLY_DIR = DOCS_DIR / "weekly"
MONTHLY_DIR = DOCS_DIR / "monthly"
PROJECTS_DIR = DOCS_DIR / "projects"
NUMERIC_DIR = DOCS_DIR / "numeric-news"
CARDS_DIR = DOCS_DIR / "cards"
EVENTS_CACHE_FILE = BASE_DIR / "events_cache.json"
CARD_GUIDE_FILE = BASE_DIR / "card_news_guide.md"


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
    # 국내 전문매체 / 산업지
    {"group": "국내 전문매체", "name": "워터저널", "url": "https://www.waterjournal.co.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "산업일보", "url": "https://www.industrynews.co.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "에너지데일리 환경·수처리", "url": "https://www.energydaily.co.kr/news/articleList.html?sc_section_code=S1N6&view_type=sm", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "투데이에너지", "url": "https://www.todayenergy.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "환경일보", "url": "https://www.hkbs.co.kr/", "status": "웹/기사 소스"},
    {"group": "국내 전문매체", "name": "환경미디어", "url": "https://www.ecomedia.co.kr/", "status": "웹/기사 소스"},

    # 국내 학회·협회
    {"group": "국내 학회·협회", "name": "한국막학회", "url": "https://www.membrane.or.kr/", "status": "학회/행사 소스"},
    {"group": "국내 학회·협회", "name": "한국상하수도협회", "url": "https://www.kwwa.or.kr/kr/main.do", "status": "협회/정책 소스"},
    {"group": "국내 학회·협회", "name": "한국물환경학회", "url": "https://www.kswe.or.kr/", "status": "학회 소스"},
    {"group": "국내 학회·협회", "name": "대한환경공학회", "url": "https://www.kosenv.or.kr/", "status": "학회 소스"},
    {"group": "국내 학회·협회", "name": "대한상하수도학회", "url": "https://www.ksww.or.kr/", "status": "학회 소스"},

    # 국내 정부·공공
    {"group": "국내 정부·공공", "name": "환경부", "url": "https://www.me.go.kr", "status": "정책 소스"},
    {"group": "국내 정부·공공", "name": "한국환경공단", "url": "https://www.keco.or.kr", "status": "공공 소스"},
    {"group": "국내 정부·공공", "name": "K-water", "url": "https://www.kwater.or.kr", "status": "공공 소스"},
    {"group": "국내 정부·공공", "name": "국가상수도정보시스템 WATIS", "url": "https://www.watis.or.kr/web/user/main.do", "status": "공공 소스"},
    {"group": "국내 정부·공공", "name": "물산업플랫폼", "url": "https://www.water.or.kr/", "status": "공공 소스"},
    {"group": "국내 전시회", "name": "Water Korea", "url": "https://waterkorea.kr/", "status": "전시회 소스"},

    # 해외 전문매체 / 기관
    {"group": "해외 전문매체", "name": "WaterWorld", "url": "https://www.waterworld.com/rss.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Water Online", "url": "https://www.wateronline.com/rss", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Smart Water Magazine", "url": "https://smartwatermagazine.com/rss.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "IWA", "url": "https://iwa-network.org/feed/", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "WaterNewsWire", "url": "https://waternewswire.com/feeds/main.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "WaterNewsWire Full Text", "url": "https://waternewswire.com/feeds/full-text.xml", "status": "RSS 활성"},
    {"group": "해외 전문매체", "name": "Water Technology", "url": "https://www.water-technology.net/", "status": "웹/기사 소스"},
    {"group": "해외 전문매체", "name": "Global Water Intelligence", "url": "https://www.globalwaterintel.com/", "status": "웹/유료기사 중심"},
    {"group": "해외 학회·협회", "name": "Water Environment Federation", "url": "https://www.wef.org/", "status": "협회/행사 소스"},
    {"group": "해외 학회·협회", "name": "American Water Works Association", "url": "https://www.awwa.org/", "status": "협회/행사 소스"},
    {"group": "해외 학회·협회", "name": "International Desalination Association", "url": "https://idadesal.org", "status": "학회/행사 소스"},
    {"group": "해외 학회·협회", "name": "European Membrane Society", "url": "https://www.emsoc.eu", "status": "학회 소스"},

    # 글로벌 수처리·분리막 핵심 기업
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Veolia Water Technologies", "url": "https://www.veoliawatertechnologies.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "SUEZ", "url": "https://www.suez.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Toray Industries", "url": "https://www.toray.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Toray Water Solutions", "url": "https://www.toraywater.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "DuPont Water Solutions", "url": "https://www.dupont.com/water.html", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Hydranautics", "url": "https://membranes.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Nitto", "url": "https://www.nitto.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Kovalus Separation Solutions", "url": "https://www.kovalus.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Kubota", "url": "https://www.kubota.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Mitsubishi Chemical Aqua Solutions", "url": "https://www.mcas.co.jp", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Mitsubishi Heavy Industries", "url": "https://www.mhi.com/news", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "Asahi Kasei Microza", "url": "https://www.asahi-kasei.com/microza/", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 핵심", "name": "LG Chem Water Solutions", "url": "https://www.lgwatersolutions.com", "status": "기업 소스"},

    # 글로벌 멤브레인/수처리 유관 기업
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Pentair X-Flow", "url": "https://www.pentair.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Pall Water", "url": "https://www.pall.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "NX Filtration", "url": "https://www.nxfiltration.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Synder Filtration", "url": "https://synderfiltration.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Applied Membranes", "url": "https://www.appliedmembranes.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Axeon Water Technologies", "url": "https://www.axeonwater.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Alfa Laval", "url": "https://www.alfalaval.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 글로벌 유관", "name": "Xylem", "url": "https://www.xylem.com", "status": "기업 소스"},

    # 중국계 수처리·막 기업
    {"group": "기업 뉴스룸 - 중국", "name": "Litree", "url": "https://www.litree.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 중국", "name": "OriginWater", "url": "https://www.originwater.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 중국", "name": "Vontron", "url": "https://www.vontron.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 중국", "name": "Scinor", "url": "https://www.scinor.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 중국", "name": "Memstar", "url": "https://www.memstar.com", "status": "기업 소스"},

    # 국내 경쟁사·유관 기업
    {"group": "기업 뉴스룸 - 국내", "name": "Econity", "url": "https://www.econity.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 국내", "name": "Kolon Industries", "url": "https://www.kolonindustries.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 국내", "name": "BKT", "url": "https://www.bkt21.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 국내", "name": "GS E&C", "url": "https://www.gsenc.com", "status": "기업 소스"},
    {"group": "기업 뉴스룸 - 국내", "name": "Doosan Enerbility", "url": "https://www.doosanenerbility.com", "status": "기업 소스"},

    # 검색엔진
    {"group": "검색엔진", "name": "Google News RSS", "url": "https://news.google.com/rss", "status": "RSS 활성"},
    {"group": "검색엔진", "name": "Bing News RSS", "url": "https://www.bing.com/news/search?format=RSS", "status": "RSS 활성"},
    {"group": "검색엔진", "name": "Naver News", "url": "https://search.naver.com/search.naver?where=news", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Yahoo Japan News", "url": "https://news.yahoo.co.jp/", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Yandex", "url": "https://yandex.com/search/", "status": "검색 링크 표시"},
    {"group": "검색엔진", "name": "Baidu", "url": "https://www.baidu.com/", "status": "검색 링크 표시"},
]

SEARCH_QUERY_CONFIG = [
    # 국내 일반 동향
    {"name": "Google News Korea 상하수도", "engine": "google", "region": "domestic", "query": "상하수도 OR 수처리 OR 하수처리 OR 폐수처리 -배터리 -2차전지 -반도체 -전기차"},
    {"name": "Google News Korea 막여과 MBR", "engine": "google", "region": "domestic", "query": "막여과 OR 분리막 OR MBR OR 중공사막 수처리 -배터리 -2차전지 -리튬 -반도체"},
    {"name": "Google News Korea 재이용수 PFAS", "engine": "google", "region": "domestic", "query": "재이용수 OR PFAS OR 하수재이용 OR 정수장 OR 하수처리장"},
    {"name": "Google News Korea 학회 전시회", "engine": "google", "region": "domestic", "query": "한국막학회 OR 워터코리아 OR 상하수도협회 OR 물환경학회 OR 대한환경공학회"},

    # 국내 사이트 지정 검색
    {"name": "Google Site WaterJournal", "engine": "google", "region": "domestic", "query": "site:waterjournal.co.kr 수처리 OR 하수처리 OR 막여과 OR MBR"},
    {"name": "Google Site Membrane Korea", "engine": "google", "region": "domestic", "query": "site:membrane.or.kr 분리막 OR 막여과 OR MBR OR 학술대회"},
    {"name": "Google Site KWWA", "engine": "google", "region": "domestic", "query": "site:kwwa.or.kr 상하수도 OR 물산업 OR 하수처리 OR 정수"},
    {"name": "Google Site WaterKorea", "engine": "google", "region": "domestic", "query": "site:waterkorea.kr 워터코리아 OR 수처리 OR 상하수도"},
    {"name": "Google Site WATIS", "engine": "google", "region": "domestic", "query": "site:watis.or.kr 상수도 OR 정수장 OR 수처리"},
    {"name": "Google Site K-water", "engine": "google", "region": "domestic", "query": "site:kwater.or.kr 수처리 OR 물재이용 OR 정수장 OR 하수"},

    # 글로벌 일반 동향
    {"name": "Google News Global Water", "engine": "google", "region": "global", "query": '"water treatment" OR wastewater OR "water reuse" OR PFAS -battery -lithium -EV'},
    {"name": "Google News Global Membrane MBR", "engine": "google", "region": "global", "query": '"membrane filtration" OR MBR OR "membrane bioreactor" OR ultrafiltration -battery -lithium -semiconductor -dialysis'},
    {"name": "Google News Global PFAS", "engine": "google", "region": "global", "query": 'PFAS "water treatment" OR PFAS "drinking water" OR PFAS wastewater'},
    {"name": "Google News Global Water Reuse", "engine": "google", "region": "global", "query": '"water reuse" OR "reclaimed water" OR "wastewater reuse"'},
    {"name": "Google News Global Desalination", "engine": "google", "region": "global", "query": 'desalination OR reverse osmosis OR "RO membrane" -battery -hydrogen'},

    # Bing 보조 검색
    {"name": "Bing News Korea 상하수도", "engine": "bing", "region": "domestic", "query": "상하수도 수처리 하수처리 폐수처리 -배터리 -2차전지 -전기차"},
    {"name": "Bing News Korea 막여과 MBR", "engine": "bing", "region": "domestic", "query": "막여과 분리막 MBR 중공사막 수처리 -배터리 -반도체"},
    {"name": "Bing News Global MBR", "engine": "bing", "region": "global", "query": "water treatment wastewater MBR membrane bioreactor PFAS -battery -lithium -semiconductor"},
    {"name": "Bing News Global UF MF", "engine": "bing", "region": "global", "query": "ultrafiltration microfiltration membrane wastewater water reuse -battery -dialysis"},

    # 기업 지정 검색 - 글로벌 핵심
    {"name": "Google Company Toray", "engine": "google", "region": "global", "query": "Toray membrane water treatment OR Toray MBR OR Toray ultrafiltration"},
    {"name": "Google Company DuPont Water", "engine": "google", "region": "global", "query": "DuPont Water Solutions membrane OR ultrafiltration OR PFAS"},
    {"name": "Google Company Hydranautics", "engine": "google", "region": "global", "query": "Hydranautics membrane water treatment OR reverse osmosis"},
    {"name": "Google Company LG Chem Water", "engine": "google", "region": "global", "query": "LG Chem Water Solutions membrane OR reverse osmosis"},
    {"name": "Google Company Kubota MBR", "engine": "google", "region": "global", "query": "Kubota MBR wastewater membrane"},
    {"name": "Google Company Mitsubishi membrane", "engine": "google", "region": "global", "query": "Mitsubishi membrane water treatment OR MBR"},
    {"name": "Google Company Asahi Kasei Microza", "engine": "google", "region": "global", "query": "Asahi Kasei Microza membrane water treatment"},
    {"name": "Google Company Veolia", "engine": "google", "region": "global", "query": "Veolia water technologies membrane OR MBR OR wastewater"},
    {"name": "Google Company SUEZ", "engine": "google", "region": "global", "query": "SUEZ water technologies membrane OR MBR OR wastewater"},
    {"name": "Google Company Kovalus", "engine": "google", "region": "global", "query": "Kovalus membrane water treatment OR wastewater"},
    {"name": "Google Company NX Filtration", "engine": "google", "region": "global", "query": "NX Filtration membrane water treatment OR hollow fiber"},

    # 기업 지정 검색 - 국내/중국
    {"name": "Google Company Econity", "engine": "google", "region": "domestic", "query": "Econity OR 에코니티 MBR OR 분리막 OR 수처리"},
    {"name": "Google Company Kolon", "engine": "google", "region": "domestic", "query": "Kolon OR 코오롱 분리막 수처리 OR 막여과"},
    {"name": "Google Company Litree", "engine": "google", "region": "global", "query": "Litree membrane water treatment ultrafiltration"},
    {"name": "Google Company OriginWater", "engine": "google", "region": "global", "query": "OriginWater membrane MBR wastewater"},
    {"name": "Google Company Scinor", "engine": "google", "region": "global", "query": "Scinor membrane water treatment ultrafiltration"},
    {"name": "Google Company Vontron", "engine": "google", "region": "global", "query": "Vontron membrane water treatment reverse osmosis"},
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


EVENT_SEARCH_QUERY_CONFIG = [
    {"name": "Google Events Global Water", "engine": "google", "region": "global", "query": "water conference 2026 OR water exhibition 2026 OR wastewater conference 2026 OR membrane conference 2026"},
    {"name": "Google Events Global Next Year", "engine": "google", "region": "global", "query": "water conference 2027 OR water exhibition 2027 OR wastewater conference 2027 OR membrane conference 2027"},
    {"name": "Google Events Korea", "engine": "google", "region": "domestic", "query": "수처리 전시회 2026 OR 상하수도 학회 2026 OR 분리막 학회 2026 OR 워터코리아 2026"},
    {"name": "Google Events Korea Next Year", "engine": "google", "region": "domestic", "query": "수처리 전시회 2027 OR 상하수도 학회 2027 OR 분리막 학회 2027 OR 워터코리아 2027"},
]

INCLUDE_KEYWORDS_PUBLIC = sorted(KEYWORDS.keys())
EXCLUDE_PATTERNS_PUBLIC = NEGATIVE_PATTERNS


TOP_NEWS_LIMIT = 10
DAILY_REPORT_LOOKBACK_DAYS = int(os.getenv("DAILY_REPORT_LOOKBACK_DAYS", "2"))
DASHBOARD_YEAR_WINDOW = int(os.getenv("DASHBOARD_YEAR_WINDOW", "2"))
ARTICLE_MAX_AGE_DAYS = int(os.getenv("ARTICLE_MAX_AGE_DAYS", "730"))
IMAGE_FETCH_TIMEOUT = int(os.getenv("IMAGE_FETCH_TIMEOUT", "7"))
ENABLE_OG_IMAGE_FETCH = os.getenv("ENABLE_OG_IMAGE_FETCH", "false").lower() == "true"
SHOW_ARTICLE_IMAGES = os.getenv("SHOW_ARTICLE_IMAGES", "false").lower() == "true"
PROJECT_NEWS_LIMIT = int(os.getenv("PROJECT_NEWS_LIMIT", "10"))
NUMERIC_NEWS_LIMIT = int(os.getenv("NUMERIC_NEWS_LIMIT", "10"))
EVENT_YEAR_WINDOW = int(os.getenv("EVENT_YEAR_WINDOW", "2"))

COMPANY_ENGLISH_MAP = {
    "토레이": "Toray",
    "도레이": "Toray",
    "알파라발": "Alfa Laval",
    "베올리아": "Veolia",
    "수에즈": "SUEZ",
    "자일럼": "Xylem",
    "듀폰": "DuPont",
    "하이드라나우틱스": "Hydranautics",
    "니토": "Nitto",
    "코발루스": "Kovalus",
    "코크": "Koch",
    "미쓰비시": "Mitsubishi",
    "미쓰비시중공업": "Mitsubishi Heavy Industries",
    "미쓰비시케미칼": "Mitsubishi Chemical",
    "쿠보타": "Kubota",
    "에코니티": "Econity",
    "코오롱": "Kolon",
    "코오롱인더스트리": "Kolon Industries",
    "롯데케미칼": "Lotte Chemical",
    "웅진케미칼": "Woongjin Chemical",
    "아사히카세이": "Asahi Kasei",
    "아사히 카세이": "Asahi Kasei",
    "마이크로자": "Microza",
    "펜테어": "Pentair",
    "싸인더": "Synder Filtration",
    "신더": "Synder Filtration",
    "엔엑스필트레이션": "NX Filtration",
    "에보닉": "Evonik",
    "리트리": "Litree",
    "오리진워터": "OriginWater",
    "본트론": "Vontron",
    "싸이노어": "Scinor",
    "시노어": "Scinor",
    "멤스타": "Memstar",
    "두산에너빌리티": "Doosan Enerbility",
    "지에스건설": "GS E&C",
}

# 해외 지명 영문 사전 (사후 치환 안전망)
# 무한히 많은 지명을 모두 등록할 수 없으므로, 근본 해결은 프롬프트의 영문 유지 규칙입니다.
# 이 사전은 자주 등장하는 주요 해외 지명만 보조로 잡습니다.
LOCATION_ENGLISH_MAP = {
    "도쿄": "Tokyo",
    "오사카": "Osaka",
    "요코하마": "Yokohama",
    "나고야": "Nagoya",
    "버팔로": "Buffalo",
    "뉴욕": "New York",
    "캘리포니아": "California",
    "텍사스": "Texas",
    "플로리다": "Florida",
    "헨더슨": "Henderson",
    "보이시": "Boise",
    "런던": "London",
    "파리": "Paris",
    "베를린": "Berlin",
    "암스테르담": "Amsterdam",
    "로테르담": "Rotterdam",
    "싱가포르": "Singapore",
    "두바이": "Dubai",
    "아부다비": "Abu Dhabi",
    "리야드": "Riyadh",
    "베이징": "Beijing",
    "상하이": "Shanghai",
    "광저우": "Guangzhou",
    "선전": "Shenzhen",
}


COMPANY_COUNTRY_MAP = {
    "Toray": "🇯🇵",
    "Kubota": "🇯🇵",
    "Mitsubishi": "🇯🇵",
    "Asahi Kasei": "🇯🇵",
    "Microza": "🇯🇵",
    "Nitto": "🇯🇵",
    "Veolia": "🇫🇷",
    "SUEZ": "🇫🇷",
    "Alfa Laval": "🇸🇪",
    "DuPont": "🇺🇸",
    "Hydranautics": "🇺🇸",
    "Kovalus": "🇺🇸",
    "Koch": "🇺🇸",
    "Pall": "🇺🇸",
    "Xylem": "🇺🇸",
    "Applied Membranes": "🇺🇸",
    "Axeon": "🇺🇸",
    "Pentair": "🇬🇧",
    "NX Filtration": "🇳🇱",
    "Synder Filtration": "🇺🇸",
    "LG Chem": "🇰🇷",
    "Econity": "🇰🇷",
    "Kolon": "🇰🇷",
    "BKT": "🇰🇷",
    "GS E&C": "🇰🇷",
    "Doosan Enerbility": "🇰🇷",
    "Litree": "🇨🇳",
    "OriginWater": "🇨🇳",
    "Vontron": "🇨🇳",
    "Scinor": "🇨🇳",
    "Memstar": "🇨🇳",
}

COUNTRY_NAME_TO_FLAG = {
    "미국": "🇺🇸", "USA": "🇺🇸", "United States": "🇺🇸",
    "일본": "🇯🇵", "Japan": "🇯🇵",
    "한국": "🇰🇷", "대한민국": "🇰🇷", "Korea": "🇰🇷", "South Korea": "🇰🇷",
    "중국": "🇨🇳", "China": "🇨🇳",
    "프랑스": "🇫🇷", "France": "🇫🇷",
    "싱가포르": "🇸🇬", "Singapore": "🇸🇬",
    "네덜란드": "🇳🇱", "Netherlands": "🇳🇱",
    "영국": "🇬🇧", "United Kingdom": "🇬🇧", "UK": "🇬🇧",
    "스웨덴": "🇸🇪", "Sweden": "🇸🇪",
    "독일": "🇩🇪", "Germany": "🇩🇪",
    "스페인": "🇪🇸", "Spain": "🇪🇸",
    "캐나다": "🇨🇦", "Canada": "🇨🇦",
    "말레이시아": "🇲🇾", "Malaysia": "🇲🇾",
    "사우디": "🇸🇦", "Saudi Arabia": "🇸🇦",
    "호주": "🇦🇺", "Australia": "🇦🇺",
}

COUNTRY_NAME_TO_CODE = {
    "미국": "us", "USA": "us", "United States": "us", "US": "us",
    "일본": "jp", "Japan": "jp", "JP": "jp",
    "한국": "kr", "대한민국": "kr", "Korea": "kr", "South Korea": "kr", "KR": "kr",
    "중국": "cn", "China": "cn", "CN": "cn",
    "프랑스": "fr", "France": "fr", "FR": "fr",
    "싱가포르": "sg", "Singapore": "sg", "SG": "sg",
    "네덜란드": "nl", "Netherlands": "nl", "NL": "nl",
    "영국": "gb", "United Kingdom": "gb", "UK": "gb", "GB": "gb",
    "스웨덴": "se", "Sweden": "se", "SE": "se",
    "독일": "de", "Germany": "de", "DE": "de",
    "스페인": "es", "Spain": "es", "ES": "es",
    "캐나다": "ca", "Canada": "ca", "CA": "ca",
    "말레이시아": "my", "Malaysia": "my", "MY": "my",
    "사우디": "sa", "Saudi Arabia": "sa", "SA": "sa",
    "호주": "au", "Australia": "au", "AU": "au",
}

COMPANY_COUNTRY_CODE_MAP = {
    "Toray": "jp", "Kubota": "jp", "Mitsubishi": "jp", "Asahi Kasei": "jp", "Microza": "jp", "Nitto": "jp",
    "Veolia": "fr", "SUEZ": "fr", "Alfa Laval": "se",
    "DuPont": "us", "Hydranautics": "us", "Kovalus": "us", "Koch": "us", "Pall": "us", "Xylem": "us", "Applied Membranes": "us", "Axeon": "us", "Synder Filtration": "us",
    "Pentair": "gb", "NX Filtration": "nl",
    "LG Chem": "kr", "Econity": "kr", "Kolon": "kr", "BKT": "kr", "GS E&C": "kr", "Doosan Enerbility": "kr",
    "Litree": "cn", "OriginWater": "cn", "Vontron": "cn", "Scinor": "cn", "Memstar": "cn",
}

COUNTRY_CODE_TO_KOREAN = {
    "us": "미국", "jp": "일본", "kr": "대한민국", "cn": "중국", "fr": "프랑스", "sg": "싱가포르",
    "nl": "네덜란드", "gb": "영국", "se": "스웨덴", "de": "독일", "es": "스페인", "ca": "캐나다",
    "my": "말레이시아", "sa": "사우디", "au": "호주",
}

PROJECT_STAGE_KEYWORDS = {
    "입찰": "입찰", "발주": "발주", "수주": "수주", "계약": "계약", "착공": "착공", "준공": "준공",
    "설계": "설계", "기본설계": "기본설계", "실시설계": "실시설계", "공사": "공사", "증설": "증설",
    "신설": "신설", "개선": "개선", "현대화": "현대화", "upgrade": "Upgrade", "contract": "Contract",
    "tender": "Tender", "award": "Award", "commissioning": "Commissioning", "construction": "Construction",
}


GENERIC_THUMBNAIL_SVG = "data:image/svg+xml;utf8," + quote_plus("<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'><rect width='640' height='360' fill='#e0f2fe'/><path d='M80 230c80-55 150-55 230 0s150 55 250 0' fill='none' stroke='#0f4c81' stroke-width='18' opacity='.22' stroke-linecap='round'/><text x='320' y='183' text-anchor='middle' font-family='Arial' font-size='30' fill='#0f4c81' font-weight='700'>Water News</text></svg>")

PROJECT_KEYWORDS = [
    "프로젝트", "사업", "수주", "입찰", "발주", "계약", "EPC", "턴키", "증설", "신설", "개선", "현대화",
    "하수처리장", "폐수처리장", "정수장", "재이용수", "처리시설", "contract", "tender", "award",
    "project", "expansion", "upgrade", "commissioning", "construction", "plant", "facility",
]

SPEC_VALUE_PATTERNS = [
    r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:m3/day|m³/day|㎥/일|m3\/d|MLD|MGD|톤/일|ton/day|tons/day)",
    r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:억원|백만원|million|billion|USD|KRW|달러)",
    r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:LMH|m/d|bar|kPa|mg/L|ppm|%)",
    r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:명|visitors|attendees|exhibitors|개사|booths)",
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

def normalize_image_url(url):
    if not url:
        return ""
    url = html.unescape(str(url).strip())
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://") or url.startswith("https://") or url.startswith("data:image"):
        return url
    return ""


def extract_entry_image(entry):
    for key in ("media_thumbnail", "media_content"):
        values = entry.get(key) or []
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict):
                    url = normalize_image_url(item.get("url"))
                    if url:
                        return url
    for link in entry.get("links", []) or []:
        if not isinstance(link, dict):
            continue
        href = normalize_image_url(link.get("href"))
        ltype = str(link.get("type", "")).lower()
        rel = str(link.get("rel", "")).lower()
        if href and ("image" in ltype or rel in {"enclosure", "thumbnail"}):
            return href
    for key in ("image", "thumbnail"):
        value = entry.get(key)
        if isinstance(value, dict):
            url = normalize_image_url(value.get("href") or value.get("url"))
            if url:
                return url
        elif isinstance(value, str):
            url = normalize_image_url(value)
            if url:
                return url
    return ""


def fetch_og_image(url):
    if not ENABLE_OG_IMAGE_FETCH or not url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; HifilM-WaterNewsBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=IMAGE_FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        text = resp.text[:250000]
        patterns = [
            r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
            r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image[\"']",
            r"<meta[^>]+name=[\"']twitter:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
            r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+name=[\"']twitter:image[\"']",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                return normalize_image_url(m.group(1))
    except Exception:
        return ""
    return ""


def enrich_article_images(articles, limit=20):
    for article in articles[:limit]:
        if not article.get("image"):
            article["image"] = fetch_og_image(article.get("link", ""))
    return articles



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



def replace_company_names_with_english(text):
    if not text:
        return ""
    out = str(text)
    # 회사명 + 해외 지명 사전을 통합하고, 긴 키부터 치환해 부분 문자열 충돌을 방지합니다.
    # 예: "미쓰비시중공업"을 "미쓰비시"보다 먼저 치환해 "Mitsubishi중공업" 깨짐을 막습니다.
    combined = {**COMPANY_ENGLISH_MAP, **LOCATION_ENGLISH_MAP}
    for ko, en in sorted(combined.items(), key=lambda x: len(x[0]), reverse=True):
        out = out.replace(ko, en)
    return out


def normalize_company_list(companies):
    result = []
    for c in companies or []:
        name = replace_company_names_with_english(str(c).strip())
        if name and name not in result:
            result.append(name)
    return result


def parse_date_safe(date_str):
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").replace(tzinfo=KST)
    except Exception:
        return None


def is_recent_dashboard_item(item):
    dt = parse_date_safe(item.get("date", ""))
    if not dt:
        return False
    current_year = datetime.now(KST).year
    return dt.year >= current_year - (DASHBOARD_YEAR_WINDOW - 1)


def dashboard_sort_score(item):
    dt = parse_date_safe(item.get("date", ""))
    now = datetime.now(KST)
    if dt:
        age_days = max((now - dt).days, 0)
        recency_bonus = max(0, 730 - age_days) / 730 * 100
        date_key = dt.strftime("%Y-%m-%d")
    else:
        recency_bonus = 0
        date_key = ""
    return (recency_bonus + float(item.get("score", 0)), date_key)


def extract_date_context_from_text(*values):
    text = " ".join(str(v or "") for v in values)
    text = clean_text(text)
    patterns = [
        r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}",
        r"20\d{2}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일",
        r"20\d{2}\s*년\s*\d{1,2}\s*월",
        r"\d{1,2}\s*월\s*\d{1,2}\s*일",
        r"\d{1,2}/\d{1,2}/20\d{2}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}",
    ]
    found = []
    for pattern in patterns:
        for m in re.findall(pattern, text, flags=re.IGNORECASE):
            value = re.sub(r"\s+", " ", str(m)).strip()
            if value and value not in found:
                found.append(value)
    return found[:5]


def get_article_date_context(item):
    explicit = item.get("date_context") or item.get("event_date") or item.get("article_date_context")
    if isinstance(explicit, list):
        explicit = ", ".join(str(x) for x in explicit if x)
    if explicit:
        return str(explicit)
    extracted = extract_date_context_from_text(item.get("title", ""), item.get("ko_title", ""), item.get("summary", ""), item.get("brief", ""))
    if extracted:
        return ", ".join(extracted)
    if item.get("date"):
        return f"기사 기준일: {item.get('date')}"
    return "일정 정보 확인 필요"


def normalize_for_similarity(text):
    text = replace_company_names_with_english(clean_text(text or "")).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"20\d{2}|\d{1,2}월|\d{1,2}일|\d+", " ", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", text)
    tokens = [t for t in text.split() if len(t) >= 2]
    stopwords = {
        "뉴스", "기사", "발표", "추진", "관련", "통해", "대한", "위한", "및", "으로", "에서", "하고", "하는", "된다", "선정", "공개", "실시", "도입", "개발", "시장", "전망", "성장",
        "the", "and", "for", "with", "from", "into", "about", "water", "news", "report", "says", "announces", "announced", "launches", "released", "market", "growth"
    }
    return [t for t in tokens if t not in stopwords]


def token_similarity(a, b):
    ta = set(normalize_for_similarity(a))
    tb = set(normalize_for_similarity(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def article_similarity(a, b):
    a_text = f"{a.get('ko_title','')} {a.get('title','')} {a.get('brief','')} {a.get('summary','')}"
    b_text = f"{b.get('ko_title','')} {b.get('title','')} {b.get('brief','')} {b.get('summary','')}"
    token_score = token_similarity(a_text, b_text)
    title_a = " ".join(normalize_for_similarity(f"{a.get('ko_title','')} {a.get('title','')}"))
    title_b = " ".join(normalize_for_similarity(f"{b.get('ko_title','')} {b.get('title','')}"))
    seq_score = SequenceMatcher(None, title_a, title_b).ratio() if title_a and title_b else 0.0
    return max(token_score, seq_score)


def article_identity_key(item):
    title = item.get("ko_title") or item.get("title") or ""
    title_key = " ".join(normalize_for_similarity(title))[:120]
    if title_key:
        return title_key
    link = item.get("link", "")
    if link:
        return link.strip().lower()
    return ""


def dedupe_similar_articles(items, limit=None, threshold=0.58):
    result = []
    seen_keys = set()

    ordered = sorted(items, key=dashboard_sort_score, reverse=True)
    for item in ordered:
        key = article_identity_key(item)
        if key and key in seen_keys:
            continue

        duplicate = False
        for existing in result:
            if article_similarity(item, existing) >= threshold:
                duplicate = True
                break

        if duplicate:
            continue

        result.append(item)
        if key:
            seen_keys.add(key)

        if limit and len(result) >= limit:
            break

    return result


def extract_numeric_specs_from_text(text):
    specs = []
    text = clean_text(text or "")
    for pattern in SPEC_VALUE_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            value = str(match).strip()
            if value and value not in specs:
                specs.append(value)
    return specs[:8]


def merge_specs(*values):
    specs = []
    for value in values:
        if isinstance(value, list):
            candidates = value
        elif isinstance(value, str):
            candidates = extract_numeric_specs_from_text(value)
        else:
            candidates = []
        for candidate in candidates:
            candidate = str(candidate).strip()
            if candidate and candidate not in specs:
                specs.append(candidate)
    return specs[:10]

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

            dt = parse_date_safe(published_date)
            if dt and not BACKFILL_MODE:
                age_days = (datetime.now(KST) - dt).days
                if age_days > ARTICLE_MAX_AGE_DAYS:
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
                "specs": extract_numeric_specs_from_text(f"{title} {summary}"),
                "image": extract_entry_image(entry),
            }

            article["domestic"] = is_domestic_article(article)
            articles.append(article)

        time.sleep(rss_sleep)

    return dedupe_similar_articles(articles, threshold=0.70)

def flag_for_country(country):
    if not country:
        return ""

    key = str(country).strip().lower()
    return COUNTRY_FLAGS.get(key, "")


def country_code_from_country(country):
    if not country:
        return ""
    value = str(country).strip()
    lower = value.lower()
    for name, code in COUNTRY_NAME_TO_CODE.items():
        if lower == name.lower() or name.lower() in lower:
            return code
    return ""


def flag_img_html(code):
    if not code:
        return ""
    code = str(code).lower().strip()
    if not re.fullmatch(r"[a-z]{2}", code):
        return ""
    return f'<img class="flag-icon" src="https://flagcdn.com/24x18/{html.escape(code)}.png" alt="{html.escape(code.upper())}" loading="lazy">'


def country_display_html(country):
    if not country:
        return ""
    country_text = str(country).strip()
    code = country_code_from_country(country_text)
    if not code and country_text in {"한국", "대한민국"}:
        code = "kr"
    if code:
        label = COUNTRY_CODE_TO_KOREAN.get(code, country_text)
        return f'<span class="flag-label">{flag_img_html(code)}<span>{html.escape(label)}</span></span>'
    return html.escape(country_text)


def add_country_flag(country):
    if not country:
        return ""
    country_text = str(country).strip()
    code = country_code_from_country(country_text)
    emoji = COUNTRY_NAME_TO_FLAG.get(country_text, "") or flag_for_country(country_text)
    if emoji:
        return f"{emoji} {country_text}"
    return country_text


def company_country_code(company):
    if not company:
        return ""
    company = replace_company_names_with_english(str(company).strip())
    for name, code in sorted(COMPANY_COUNTRY_CODE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if name.lower() in company.lower():
            return code
    return ""


def company_display_html(company):
    if not company:
        return ""
    company = replace_company_names_with_english(str(company).strip())
    code = company_country_code(company)
    if code:
        return f'<span class="flag-label">{flag_img_html(code)}<span>{html.escape(company)}</span></span>'
    return html.escape(company)


def add_company_flag(company):
    if not company:
        return ""
    company = replace_company_names_with_english(str(company).strip())
    for name, flag in sorted(COMPANY_COUNTRY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if name.lower() in company.lower():
            return f"{flag} {company}"
    return company


def format_companies_with_flags(companies):
    result = []
    for company in normalize_company_list(companies or []):
        flagged = add_company_flag(company)
        if flagged and flagged not in result:
            result.append(flagged)
    return result


def country_flag_from_text(text):
    text = str(text or "")
    for name, flag in COUNTRY_NAME_TO_FLAG.items():
        if name.lower() in text.lower():
            return flag
    return ""


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
        payload = {
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
        }
        if not IS_GPT5_FAMILY:
            payload["temperature"] = 0.2

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
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
        payload = {
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
        }
        if not IS_GPT5_FAMILY:
            payload["temperature"] = 0.2

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )

        resp.raise_for_status()
        data = resp.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"{fallback} [요약 API 오류: {str(e)[:120]}]"


def summarize_article(article):
    fallback_specs = extract_numeric_specs_from_text(f"{article.get('title','')} {article.get('summary','')}")
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
        "date_context": get_article_date_context(article),
        "specs": fallback_specs,
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
- companies: 기사에 명시된 기업명 배열. 없으면 []. 기업명은 가능한 공식 영문명으로 작성. 예: Toray, Econity, Veolia, DuPont.
- technologies: 기사에 명시된 기술/키워드 배열. 예: ["PFAS", "Water Reuse", "MBR"].
- policy_alert: 규제/정책 알림이면 1문장 작성. 아니면 빈 문자열.
- date_context: 기사에 명시된 발표일, 개최일, 사업 일정, 준공일, 개발 발표 시점, 입찰 일정이 있으면 작성. 없으면 기사 발행일 기준으로 작성.
- specs: 기사에 명시된 수치·사양 배열. 처리장 용량, m3/day, m³/day, 톤/일, MLD, MGD, 사업비, CAPEX, 막면적, Flux, TMP, MLSS, HRT, SRT, 참석자 규모 등. 기사에 없으면 []. 절대 만들지 말 것.

중요:
- 기업명, 해외 지명, 해외 기관명, 브랜드명, 제품명 등 영어가 원문인 고유명사는 한국어로 음역하지 말고 반드시 영문 원문 그대로 표기하세요. 예: Toray(토레이/도레이 금지), Veolia, SUEZ, Buffalo(버팔로 금지), Tokyo(도쿄 금지), Henderson, Boise. 이 규칙은 ko_title, brief, summary, why_important 등 모든 텍스트 필드에 동일하게 적용됩니다.
- 단, 한국 국내 지명·기관·지자체 등 한국어가 정식 명칭인 대상은 한글로 표기하세요. 예: 환경부, 한국상하수도협회, 예산군, 서울, 부산.
- 처리장, 정수장, 하수처리장, 공장, 프로젝트, 전시회, 학회가 나오면 장소·날짜·규모·용량·사업비 등 숫자 정보를 우선 추출하세요.
- 수치가 기사에 없으면 specs는 []로 두세요.

원문 제목: {article['title']}
출처: {article['source']}
RSS 요약: {article['summary']}
키워드: {', '.join(article['matched'])}
링크: {article['link']}
""".strip()

    parsed = openai_json(prompt, fallback)
    parsed_specs = parsed.get("specs", fallback["specs"]) or []

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
        "date_context": parsed.get("date_context", fallback.get("date_context", get_article_date_context(article))) or get_article_date_context(article),
        "specs": merge_specs(parsed_specs, fallback_specs, article.get("title", ""), article.get("summary", "")),
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
            "date_context": ai.get("date_context", get_article_date_context(a)),
            "specs": merge_specs(ai.get("specs", []), a.get("specs", []), a.get("title", ""), a.get("summary", "")),
            "source": a.get("source", ""),
            "link": a.get("link", ""),
            "score": a.get("score", 0),
            "keywords": a.get("matched", []),
            "domestic": a.get("domestic", False),
            "region": a.get("region", ""),
            "source_type": a.get("source_type", ""),
            "image": a.get("image", ""),
        })

    cutoff = (datetime.now(KST) - timedelta(days=ARTICLE_MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    history = [x for x in history if not x.get("date") or x.get("date", "") >= cutoff]
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
        ("projects/", "프로젝트·수주 동향"),
        ("numeric-news/", "수치 포함 기사"),
        ("events/", "학회·전시회 일정"),
        ("sources/", "정보 출처"),
        ("filters/", "필터링 기준"),
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


def make_html_page(title, body_html, path, active_url="", subtitle="", toc_items=None, right_html=None):
    path.mkdir(parents=True, exist_ok=True)
    toc_items = toc_items or []
    nav_html = build_left_nav(active_url)
    # 오른쪽 사이드바는 제거하고 중앙 콘텐츠 폭을 넓힙니다.
    toc_html = ""

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
      max-width:2200px;
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
      max-width:2200px;
      margin:0 auto;
      padding:24px;
      display:grid;
      grid-template-columns:260px minmax(0, 1fr);
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
    .flag-label {{ display:inline-flex; align-items:center; gap:5px; white-space:nowrap; vertical-align:middle; }}
    .flag-icon {{ width:18px; height:13px; object-fit:cover; border-radius:2px; box-shadow:0 0 0 1px rgba(15,23,42,.12); vertical-align:-2px; }}
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
    .news-grid {{ display:grid; grid-template-columns:1fr; gap:18px; margin-bottom:18px; }}
    .news-card {{ min-height:420px; }}
    .headline-title {{ font-weight:800; color:#0f172a; }}
    .headline-list li {{ margin:10px 0 14px; padding-bottom:10px; border-bottom:1px solid #f1f5f9; }}
    .headline-specs {{ display:inline-block; margin-top:4px; padding:3px 8px; border-radius:999px; background:#f0f9ff; color:#075985; font-size:12px; font-weight:700; }}
    .event-mini-grid {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:14px; }}
    .event-mini-card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:#fff; }}
    .event-mini-card h3 {{ margin:8px 0 6px; font-size:15px; line-height:1.35; }}
    .event-grade {{ display:inline-block; padding:3px 9px; border-radius:999px; font-size:12px; font-weight:900; color:#fff; background:#64748b; }}
    .grade-S {{ background:#7c3aed; }}
    .grade-A {{ background:#2563eb; }}
    .grade-B {{ background:#64748b; }}
    .dash-card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 4px 14px rgba(15,23,42,.04); }}
    .dash-card h2 {{ font-size:17px; margin:0 0 10px; }}
    .dash-card a {{ display:block; margin:6px 0; font-size:14px; }}
    .right-rail {{ position:sticky; top:82px; display:flex; flex-direction:column; gap:16px; }}
    .rail-card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:16px; box-shadow:0 8px 22px rgba(15,23,42,.05); }}
    .rail-card h2 {{ font-size:17px; margin:0 0 10px; }}
    .compact-table {{ width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }}
    .compact-table th, .compact-table td {{ border-bottom:1px solid var(--line); padding:7px 6px; vertical-align:top; overflow-wrap:anywhere; }}
    .compact-table th {{ color:#475569; background:#f8fafc; text-align:left; }}
    .compact-list {{ margin:0; padding-left:18px; font-size:13px; }}
    .compact-list li {{ margin:7px 0; }}
    .trend-grid {{ display:grid; grid-template-columns:repeat(6, minmax(0, 1fr)); gap:12px; }}
    .trend-item {{ text-align:center; border:1px solid var(--line); border-radius:16px; padding:12px; background:#fff; }}
    .trend-key {{ display:block; font-weight:800; color:#0f4c81; }}
    .trend-val {{ display:block; color:var(--muted); font-size:12px; margin-top:3px; }}
    @media (max-width:1480px) {{
      .layout {{ grid-template-columns:240px minmax(0, 1fr); }}
      .news-grid {{ grid-template-columns:1fr; }}
      .event-mini-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
      .toc, .right-rail {{ display:none; }}
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
      .news-grid {{ grid-template-columns:1fr; }}
      .event-mini-grid {{ grid-template-columns:1fr; }}
      .trend-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
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
        specs = merge_specs(ai.get("specs", []), item.get("specs", []), item.get("title", ""), item.get("summary", ""))
        return {
            "date": item.get("date", ""),
            "title": replace_company_names_with_english(item.get("title", "")),
            "ko_title": replace_company_names_with_english(ai.get("ko_title", item.get("title", ""))),
            "brief": replace_company_names_with_english(ai.get("brief", "")),
            "summary": replace_company_names_with_english(ai.get("summary", "")),
            "why_important": replace_company_names_with_english(ai.get("why_important", "")),
            "category": ai.get("category", guess_category(item)),
            "countries": ai.get("countries", []),
            "companies": normalize_company_list(ai.get("companies", [])),
            "technologies": ai.get("technologies", item.get("matched", [])),
            "policy_alert": ai.get("policy_alert", ""),
            "date_context": ai.get("date_context", get_article_date_context(item)),
            "specs": specs,
            "source": item.get("source", ""),
            "link": item.get("link", ""),
            "score": item.get("score", 0),
            "domestic": item.get("domestic", False),
            "image": item.get("image", ""),
        }

    specs = merge_specs(item.get("specs", []), item.get("title", ""), item.get("summary", ""))
    return {
        "date": item.get("date", ""),
        "title": replace_company_names_with_english(item.get("title", "")),
        "ko_title": replace_company_names_with_english(item.get("ko_title", item.get("title", ""))),
        "brief": replace_company_names_with_english(item.get("brief", "")),
        "summary": replace_company_names_with_english(item.get("summary", "")),
        "why_important": replace_company_names_with_english(item.get("why_important", "")),
        "category": item.get("category", ""),
        "countries": item.get("countries", []),
        "companies": normalize_company_list(item.get("companies", [])),
        "technologies": item.get("technologies", item.get("keywords", [])),
        "policy_alert": item.get("policy_alert", ""),
        "date_context": item.get("date_context", get_article_date_context(item)),
        "specs": specs,
        "source": item.get("source", ""),
        "link": item.get("link", ""),
        "score": item.get("score", 0),
        "domestic": item.get("domestic", False),
        "image": item.get("image", ""),
    }

def build_article_cards(items):
    cards = []

    for i, raw in enumerate(items, 1):
        a = normalize_display_item(raw)
        countries = " ".join(add_country_flag(c) for c in a.get("countries", []))
        companies = ", ".join(format_companies_with_flags(a.get("companies", [])))
        techs = ", ".join(a.get("technologies", []))
        emoji = emoji_for_category(a.get("category", ""), a.get("technologies", []))
        source_text = a.get("source", "") or "출처 미확인"
        date_text = a.get("date", "") or "날짜 미확인"

        cards.append(f"""
        <section class="card" id="article-{i}">
          <p class="meta">#{i} · 기사일: {html.escape(date_text)} · {html.escape(source_text)} · 점수 {html.escape(str(a.get('score', 0)))}</p>
          <h2>{emoji} {html.escape(a.get('ko_title', '') or a.get('title', ''))}</h2>
          <p class="meta">발표/일정: {html.escape(a.get('date_context', '') or get_article_date_context(a))}</p>
          <p><span class="pill">{html.escape(a.get('category', '') or '분류 없음')}</span></p>
          <p class="brief">{html.escape(a.get('brief', '') or '요약 정보가 없습니다.')}</p>
          <h3>내용 요약</h3>
          <p>{html.escape(a.get('summary', '') or '상세 요약 정보가 없습니다.')}</p>
          <h3>왜 중요한가?</h3>
          <p class="why">{html.escape(a.get('why_important', '') or '중요도 분석 정보가 없습니다.')}</p>
          <p class="meta">국가: {countries or '-'}</p>
          <p class="meta">기업: {companies or '-'}</p>
          <p class="meta">기술: {html.escape(techs or '-')}</p>
          {f'<p><a href="{html.escape(a.get("link", ""))}" target="_blank" rel="noopener noreferrer">원문 기사 보기</a></p>' if a.get("link") else ''}
        </section>
        """)

    return "".join(cards)


def get_recent_daily_items(target_date, selected_articles, history, max_days=DAILY_REPORT_LOOKBACK_DAYS, limit=12):
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=KST)
    except Exception:
        target_dt = datetime.now(KST)

    allowed_dates = set((target_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max_days))
    pool = []

    for item in selected_articles:
        item_date = item.get("date", target_date)
        if item_date in allowed_dates:
            pool.append(normalize_display_item(item))

    for item in history:
        if item.get("date", "") in allowed_dates:
            pool.append(normalize_display_item(item))

    return dedupe_similar_articles(pool, limit=limit, threshold=0.70)

def create_daily_report(articles, history=None, target_date=None):
    history = history or []
    today = target_date or datetime.now(KST).strftime("%Y-%m-%d")
    report_dir = REPORTS_DIR / today

    display_items = get_recent_daily_items(today, articles, history, max_days=DAILY_REPORT_LOOKBACK_DAYS, limit=max(10, MAX_ITEMS))

    title = f"{today} 상하수도·수처리 상세 분석 보고서"
    subtitle = f"최근 {DAILY_REPORT_LOOKBACK_DAYS}일 기사까지 사용합니다. 같은 내용의 중복 기사는 자동 제외합니다."
    active_url = f"reports/{today}/"
    toc_items = [(f"article-{i}", f"기사 {i}") for i in range(1, min(len(display_items), 12) + 1)]

    if display_items:
        body = build_article_cards(display_items)
    else:
        body = '<section class="card">당일 기준 필터 조건에 맞는 뉴스가 없습니다.</section>'

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


def get_dashboard_items(history, limit=TOP_NEWS_LIMIT):
    normalized = [normalize_display_item(x) for x in history]
    recent_items = [x for x in normalized if is_recent_dashboard_item(x)]
    pool_source = recent_items if recent_items else normalized
    sorted_items = sorted(pool_source, key=dashboard_sort_score, reverse=True)

    global_pool = []
    domestic_pool = []

    for item in sorted_items:
        if article_is_domestic(item):
            domestic_pool.append(item)
        else:
            global_pool.append(item)

    global_items = dedupe_similar_articles(global_pool, limit=limit, threshold=0.55)
    domestic_items = dedupe_similar_articles(domestic_pool, limit=limit, threshold=0.55)

    return global_items, domestic_items

def infer_companies_for_item(item):
    a = normalize_display_item(item)
    companies = normalize_company_list(a.get("companies", []))
    text = replace_company_names_with_english(f"{a.get('title','')} {a.get('ko_title','')} {a.get('summary','')} {a.get('brief','')}")
    for name in sorted(COMPANY_COUNTRY_MAP.keys(), key=len, reverse=True):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE):
            if name not in companies:
                companies.append(name)
    return companies[:5]


def display_countries_with_flags(item):
    a = normalize_display_item(item)
    countries = []
    for c in a.get("countries", []) or []:
        label = add_country_flag(c)
        if label and label not in countries:
            countries.append(label)
    if not countries and article_is_domestic(a):
        countries.append("🇰🇷 대한민국")
    return countries


def build_headline_list(items, show_images=False):
    if not items:
        return '<p class="meta">표시할 뉴스가 아직 없습니다.</p>'

    parts = ['<ol class="headline-list compact no-thumbs">']
    for idx, item in enumerate(items, 1):
        a = normalize_display_item(item)
        title = a.get("ko_title") or a.get("title") or "제목 없음"
        source = a.get("source", "출처 미확인")
        date = a.get("date", "")
        link = a.get("link", "")
        category = a.get("category", "")
        specs = a.get("specs", []) or []
        countries_html = [country_display_html(c) for c in a.get("countries", []) or []]
        if not countries_html and article_is_domestic(a):
            countries_html = [country_display_html("대한민국")]
        companies_html = [company_display_html(c) for c in infer_companies_for_item(a)]
        date_context = a.get("date_context", "") or get_article_date_context(a)
        technologies = a.get("technologies", []) or []

        first_line_parts = countries_html + companies_html + [html.escape(f"기사일 {date}"), html.escape(f"발표/일정 {date_context}")]
        second_line_parts = [html.escape(f"출처 {source}"), html.escape(category)] + [html.escape(str(t)) for t in technologies[:4]]
        first_line = " · ".join(x for x in first_line_parts if x)
        second_line = " · ".join(x for x in second_line_parts if x)

        specs_html = ""
        if specs:
            specs_html = "<div class='headline-specs'>" + " · ".join(html.escape(str(x)) for x in specs[:4]) + "</div>"

        title_inner = f'<span class="headline-rank">{idx}</span><span class="headline-title-row">{html.escape(title)}</span>'
        title_html = f'<a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{title_inner}</a>' if link else title_inner
        parts.append('<li><div class="headline-item no-thumb"><div>' + title_html + '<div class="headline-meta-row">' + first_line + '</div><div class="headline-meta-row">' + second_line + '</div>' + specs_html + '</div></div></li>')

    parts.append("</ol>")
    return "\n".join(parts)

def build_event_preview(limit=5):
    return build_events_table(get_event_items(limit=limit), compact=True) + f'<p><a href="{rel_url("events/")}">전체 학회·전시회 일정 보기</a></p>'

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
    events = update_events_cache()
    body = f"""
    <section class="card" id="events">
      <h2>국내·해외 멤브레인/수처리 학회·전시회</h2>
      <p class="meta">현재 연도와 내년 연도 중심으로 표시합니다. 일정·장소가 확정되지 않은 행사는 미정으로 표시합니다.</p>
      {build_events_table(events)}
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




def is_project_item(item):
    a = normalize_display_item(item)
    text = f"{a.get('title','')} {a.get('ko_title','')} {a.get('summary','')} {a.get('brief','')} {a.get('category','')} {' '.join(a.get('technologies', []))} {' '.join(a.get('specs', []))}".lower()
    if "프로젝트/수주" in a.get("category", ""):
        return True
    return any(k.lower() in text for k in PROJECT_KEYWORDS)


def detect_project_stage(item):
    a = normalize_display_item(item)
    text = f"{a.get('title','')} {a.get('ko_title','')} {a.get('summary','')} {a.get('brief','')} {a.get('date_context','')}".lower()
    for key, label in PROJECT_STAGE_KEYWORDS.items():
        if key.lower() in text:
            return label
    return "확인 필요"


def get_project_location(item):
    a = normalize_display_item(item)
    countries = a.get("countries", []) or []
    if countries:
        return " ".join(add_country_flag(c) for c in countries[:2])
    text = f"{a.get('title','')} {a.get('ko_title','')} {a.get('summary','')} {a.get('brief','')}"
    flag = country_flag_from_text(text)
    if flag:
        return flag
    return "확인 필요"


def get_project_items(history, limit=PROJECT_NEWS_LIMIT):
    pool = [normalize_display_item(x) for x in history if is_recent_dashboard_item(x) and is_project_item(x)]
    return dedupe_similar_articles(pool, limit=limit, threshold=0.58)


def get_numeric_items(history, limit=NUMERIC_NEWS_LIMIT):
    pool = []
    for x in history:
        a = normalize_display_item(x)
        if not is_recent_dashboard_item(a):
            continue
        if a.get("specs"):
            pool.append(a)
    return dedupe_similar_articles(pool, limit=limit, threshold=0.58)


def format_specs_short(specs, max_items=3):
    specs = [str(s).strip() for s in (specs or []) if str(s).strip()]
    if not specs:
        return "-"
    return " · ".join(specs[:max_items])


def build_projects_table(items, compact=False):
    if not items:
        return '<p class="meta">표시할 프로젝트·수주 동향이 아직 없습니다.</p>'
    cls = "compact-table" if compact else "source-table"
    rows = []
    for raw in items:
        a = normalize_display_item(raw)
        title = a.get("ko_title") or a.get("title") or "제목 없음"
        link = a.get("link", "")
        title_html = f'<a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a>' if link else html.escape(title)
        rows.append(f"""
        <tr>
          <td>{title_html}</td>
          <td>{html.escape(get_project_location(a))}</td>
          <td>{html.escape(format_specs_short(a.get('specs'), 2))}</td>
          <td>{html.escape(a.get('date_context') or get_article_date_context(a))}</td>
          <td>{html.escape(detect_project_stage(a))}</td>
          <td>{html.escape(a.get('source','출처 미확인'))}</td>
        </tr>
        """)
    return f"""
    <table class="{cls}">
      <thead><tr><th>프로젝트명</th><th>지역</th><th>사업비/용량</th><th>기간·날짜</th><th>단계</th><th>출처</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def build_numeric_table(items, compact=False):
    if not items:
        return '<p class="meta">수치가 포함된 기사가 아직 없습니다.</p>'
    cls = "compact-table" if compact else "source-table"
    rows = []
    for raw in items:
        a = normalize_display_item(raw)
        title = a.get("ko_title") or a.get("title") or "제목 없음"
        link = a.get("link", "")
        title_html = f'<a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a>' if link else html.escape(title)
        rows.append(f"""
        <tr>
          <td>{title_html}</td>
          <td>{html.escape(format_specs_short(a.get('specs'), 4))}</td>
          <td>{html.escape(a.get('date',''))}</td>
          <td>{html.escape(a.get('date_context') or get_article_date_context(a))}</td>
          <td>{html.escape(a.get('source','출처 미확인'))}</td>
        </tr>
        """)
    return f"""
    <table class="{cls}">
      <thead><tr><th>기사 제목</th><th>핵심 수치</th><th>기사일</th><th>기간·날짜</th><th>출처</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def build_keyword_trends(history, days=7, limit=6):
    cutoff = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
    counts = {}
    for item in history:
        if item.get("date", "") < cutoff:
            continue
        for key in item.get("keywords", []) + item.get("technologies", []):
            key = str(key).strip()
            if not key or len(key) > 32:
                continue
            counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    if not top:
        return '<p class="meta">최근 키워드 집계가 아직 없습니다.</p>'
    items = []
    for key, val in top:
        items.append(f'<div class="trend-item"><span class="trend-key">{html.escape(key)}</span><span class="trend-val">{val}건</span></div>')
    return '<div class="trend-grid">' + ''.join(items) + '</div>'


def fetch_event_candidates_from_search(limit=12):
    if os.getenv("ENABLE_EVENT_SEARCH", "true").lower() != "true":
        return []
    feeds = []
    for item in EVENT_SEARCH_QUERY_CONFIG:
        query = item.get("query", "")
        if not query:
            continue
        if item.get("engine") == "google":
            url = google_news_rss_url(query, hl="ko" if item.get("region") == "domestic" else "en", gl="KR" if item.get("region") == "domestic" else "US", ceid="KR:ko" if item.get("region") == "domestic" else "US:en")
        else:
            url = bing_news_rss_url(query)
        feeds.append({"name": item.get("name", "Event Search"), "url": url, "region": item.get("region", "")})
    candidates = []
    current_year = datetime.now(KST).year
    allowed_years = {str(current_year), str(current_year + 1)}
    for feed in feeds:
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries[:20]:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
            combined = f"{title} {summary}"
            if not any(y in combined for y in allowed_years):
                continue
            score, matched = score_article(title, summary)
            if score < 4 and not re.search(r"conference|exhibition|expo|학회|전시회|컨퍼런스", combined, re.I):
                continue
            candidates.append({
                "grade": "후보",
                "name": replace_company_names_with_english(title[:90]),
                "scope": "국내" if feed.get("region") == "domestic" else "해외",
                "location": "미정",
                "date": ", ".join(extract_date_context_from_text(combined)) or "미정",
                "scale": "확인 필요",
                "url": entry.get("link", ""),
                "note": "검색 기반 신규 행사 후보",
                "source": feed.get("name", "Event Search"),
            })
    return dedupe_similar_articles(candidates, limit=limit, threshold=0.60)


def update_events_cache():
    current_year = datetime.now(KST).year
    allowed_years = {str(current_year), str(current_year + 1)}
    static_items = []
    for item in EVENT_CATALOG:
        copied = dict(item)
        # 연도가 명시되지 않은 정기행사는 현재연도/내년 목록에서도 보이도록 유지합니다.
        copied["source"] = copied.get("source", "공식/기본 등록")
        static_items.append(copied)
    candidates = fetch_event_candidates_from_search(limit=12)
    merged = static_items + candidates
    save_json(EVENTS_CACHE_FILE, {"updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"), "events": merged})
    return merged


def get_event_items(limit=None):
    data = load_json(EVENTS_CACHE_FILE, {})
    events = data.get("events") if isinstance(data, dict) else None
    if not events:
        events = update_events_cache()
    current_year = datetime.now(KST).year
    allowed_years = {str(current_year), str(current_year + 1)}
    filtered = []
    for item in events:
        text = f"{item.get('name','')} {item.get('date','')} {item.get('note','')}"
        if any(y in text for y in allowed_years) or not re.search(r"20\d{2}", text):
            filtered.append(item)
    result = filtered[:limit] if limit else filtered
    return result


def build_events_table(items, compact=False):
    if not items:
        return '<p class="meta">표시할 학회·전시회 일정이 없습니다.</p>'
    cls = "compact-table" if compact else "source-table"
    rows = []
    for item in items:
        name = item.get("name", "")
        url = item.get("url", "")
        name_html = f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{html.escape(name)}</a>' if url else html.escape(name)
        rows.append(f"""
        <tr>
          <td>{html.escape(item.get('grade',''))}</td>
          <td>{name_html}</td>
          <td>{html.escape(item.get('scope',''))}</td>
          <td>{html.escape(item.get('location','미정'))}</td>
          <td>{html.escape(item.get('date','미정'))}</td>
          <td>{html.escape(item.get('scale','확인 필요'))}</td>
          <td>{html.escape(item.get('note',''))}</td>
        </tr>
        """)
    return f"""
    <table class="{cls}">
      <thead><tr><th>등급</th><th>행사</th><th>구분</th><th>장소</th><th>일정</th><th>규모</th><th>비고</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def build_right_rail(history):
    projects = get_project_items(history, limit=5)
    numeric = get_numeric_items(history, limit=5)
    events = get_event_items(limit=5)
    return f"""
    <aside class="right-rail">
      <section class="rail-card" id="rail-projects">
        <h2>프로젝트·수주 TOP 5</h2>
        {build_projects_table(projects, compact=True)}
        <p><a href="{rel_url('projects/')}">더보기</a></p>
      </section>
      <section class="rail-card" id="rail-numeric">
        <h2>수치 포함 기사 TOP 5</h2>
        {build_numeric_table(numeric, compact=True)}
        <p><a href="{rel_url('numeric-news/')}">더보기</a></p>
      </section>
      <section class="rail-card" id="rail-events">
        <h2>학회·전시회 일정 TOP 5</h2>
        {build_events_table(events, compact=True)}
        <p><a href="{rel_url('events/')}">더보기</a></p>
      </section>
    </aside>
    """


def create_projects_page(history):
    items = get_project_items(history, limit=60)
    body = f"""
    <section class="card" id="projects">
      <h2>프로젝트·수주 동향</h2>
      <p class="meta">사업비, 처리용량, 지역, 기간·날짜, 단계, 출처를 함께 표시합니다. 기회점수는 사용하지 않습니다.</p>
      {build_projects_table(items)}
    </section>
    """
    make_html_page("프로젝트·수주 동향", body, PROJECTS_DIR, active_url="projects/", subtitle="상하수도·수처리 프로젝트, 발주, 수주, 증설, 개선 관련 기사만 모아 표시합니다.", toc_items=[("projects", "프로젝트·수주")])


def create_numeric_page(history):
    items = get_numeric_items(history, limit=80)
    body = f"""
    <section class="card" id="numeric-news">
      <h2>수치가 포함된 주요 기사</h2>
      <p class="meta">사업비, 처리용량, Flux, TMP, MLSS, 제거율, 참석자 수 등 정량 정보가 포함된 기사만 모읍니다.</p>
      {build_numeric_table(items)}
    </section>
    """
    make_html_page("수치 포함 기사", body, NUMERIC_DIR, active_url="numeric-news/", subtitle="기술 벤치마킹과 시장규모 판단에 필요한 숫자 중심 기사입니다.", toc_items=[("numeric-news", "수치 기사")])
def build_today_detail_preview(history, limit=TOP_NEWS_LIMIT):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    today_items = [normalize_display_item(x) for x in history if x.get("date") == today]
    today_items = dedupe_similar_articles(today_items, limit=limit, threshold=0.70)
    if not today_items:
        return '<p class="meta">오늘 날짜로 누적된 상세 기사 제목이 아직 없습니다.</p>'

    lead = normalize_display_item(today_items[0])
    title = lead.get("ko_title") or lead.get("title") or "제목 없음"
    brief = lead.get("brief") or lead.get("summary") or "요약 정보가 없습니다."
    source = lead.get("source", "출처 미확인")
    date = lead.get("date", today)
    category = lead.get("category", "")
    specs = lead.get("specs", []) or []
    countries_html = [country_display_html(c) for c in lead.get("countries", []) or []]
    if not countries_html and article_is_domestic(lead):
        countries_html = [country_display_html("대한민국")]
    companies_html = [company_display_html(c) for c in infer_companies_for_item(lead)]
    date_context = lead.get("date_context") or get_article_date_context(lead)
    specs_html = ""
    if specs:
        specs_html = "<div class='headline-specs'>" + " · ".join(html.escape(str(x)) for x in specs[:4]) + "</div>"
    link = lead.get("link", "")
    title_block = f'<a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a>' if link else html.escape(title)
    meta_parts = countries_html + companies_html + [html.escape(f"기사일 {date}"), html.escape(f"발표/일정 {date_context}")]
    meta_line = " · ".join(x for x in meta_parts if x)
    source_line = "출처 " + html.escape(source) + " · " + html.escape(category)
    more_html = build_headline_list(today_items[1:limit], show_images=False) if len(today_items) > 1 else ""
    return '<div class="article-card today-lead no-image"><div class="article-card-body"><p><span class="pill">' + html.escape(category or '분류 없음') + '</span></p><h2>' + title_block + '</h2><p>' + html.escape(brief) + '</p><p class="meta meta-line">' + meta_line + '</p><p class="meta meta-line">' + source_line + '</p>' + specs_html + '</div></div>' + more_html

def update_docs_index(daily_url, weekly_url, monthly_url):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    history = load_json(HISTORY_FILE, [])
    global_items, domestic_items = get_dashboard_items(history, limit=TOP_NEWS_LIMIT)
    project_items = get_project_items(history, limit=PROJECT_NEWS_LIMIT)
    numeric_items = get_numeric_items(history, limit=NUMERIC_NEWS_LIMIT)

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

    body = f"""
    <section class="card" id="today-detail">
      <h2>오늘의 상세 분석 기사</h2>
      <p class="meta">일일 상세 보고서에 포함되는 기사 제목입니다. 중복 내용은 자동 제외합니다.</p>
      {build_today_detail_preview(history, limit=TOP_NEWS_LIMIT)}
      <p><a href="{html.escape(daily_url)}">오늘 상세 분석 보고서 전체 보기</a></p>
    </section>

    <section class="news-grid" id="headlines">
      <div class="dash-card news-card">
        <h2>세계 주요 뉴스 TOP 10</h2>
        {build_headline_list(global_items)}
      </div>
      <div class="dash-card news-card">
        <h2>국내 주요 뉴스 TOP 10</h2>
        {build_headline_list(domestic_items)}
      </div>
    </section>

    <section class="card" id="projects-preview">
      <h2>프로젝트·수주 동향</h2>
      <p class="meta">사업비, 처리용량, 지역, 기간·날짜, 단계, 출처를 함께 표시합니다.</p>
      {build_projects_table(project_items, compact=False)}
      <p><a href="{rel_url('projects/')}">프로젝트·수주 동향 전체 보기</a></p>
    </section>

    <section class="card" id="numeric-preview">
      <h2>수치가 포함된 주요 기사</h2>
      <p class="meta">사업비, 처리용량, Flux, TMP, MLSS, 제거율 등 정량 정보가 포함된 기사입니다.</p>
      {build_numeric_table(numeric_items, compact=False)}
      <p><a href="{rel_url('numeric-news/')}">수치 포함 기사 전체 보기</a></p>
    </section>

    <section class="card" id="events-preview">
      <h2>국내·해외 학회 및 전시회 일정</h2>
      <p class="meta">현재 연도와 내년 연도 중심으로 행사 성격, 위치, 일정, 규모 등급과 비고를 표시합니다.</p>
      {build_event_preview(limit=5)}
    </section>

    <section class="card" id="keyword-trends">
      <h2>주요 키워드 트렌드 최근 7일</h2>
      {build_keyword_trends(history, days=7, limit=6)}
    </section>

    <section class="card" id="collection-stats">
      <h2>수집 현황</h2>
      {stats}
    </section>

    <section class="dashboard-grid" id="source-filter">
      <div class="dash-card">
        <h2>정보 출처</h2>
        <p>RSS, 검색엔진, 국내외 학회·협회, 기업 뉴스룸을 구분해 정리합니다.</p>
        <p><a href="{rel_url('sources/')}">정보 출처 보기</a></p>
      </div>
      <div class="dash-card">
        <h2>필터링 기준</h2>
        <p>MBR, 막여과, PFAS, 재이용수 등 포함 키워드와 배터리·반도체 제외 키워드를 공개합니다.</p>
        <p><a href="{rel_url('filters/')}">필터링 기준 보기</a></p>
      </div>
      <div class="dash-card">
        <h2>보고서 바로가기</h2>
        <p><a href="{html.escape(weekly_url)}">최신 주간 업계 동향</a></p>
        <p><a href="{html.escape(monthly_url)}">최신 월간 업계 동향</a></p>
      </div>
    </section>
    """

    make_html_page(
        "상하수도·수처리 뉴스 브리핑",
        body,
        DOCS_DIR,
        active_url="",
        subtitle="국내·해외 수처리 뉴스, 멤브레인/MBR 동향, 프로젝트·수주, 수치 기사, 학회·전시회 일정을 누적 관리합니다.",
        toc_items=[("today-detail", "오늘 상세 기사"), ("headlines", "주요 뉴스"), ("projects-preview", "프로젝트·수주"), ("numeric-preview", "수치 기사"), ("events-preview", "학회·전시회"), ("keyword-trends", "키워드 트렌드"), ("collection-stats", "수집 현황"), ("source-filter", "출처/필터")],
        right_html=build_right_rail(history),
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
        today_summary = replace_company_names_with_english(
            first.get("brief", "오늘 기준 수처리 관련 주요 뉴스가 확인되었습니다.")
        )
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

            ko_title = replace_company_names_with_english(ai.get("ko_title", ""))
            brief = replace_company_names_with_english(ai.get("brief", ""))
            why_important = replace_company_names_with_english(ai.get("why_important", ""))

            lines.append(f"{idx}. {country_prefix}{ko_title}")
            lines.append("")
            lines.append("주제")
            lines.append(f"{emoji} {ai.get('category', '')}")
            lines.append("")
            lines.append("요약")
            lines.append(brief)
            lines.append("")
            lines.append("💡 왜 중요한가?")
            lines.append("")
            lines.append(why_important)
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


def should_generate_cards(now=None):
    """월요일(0)과 목요일(3)에 카드뉴스 PNG를 생성합니다. FORCE_CARD_NEWS=true이면 요일과 무관하게 생성합니다."""
    if FORCE_CARD_NEWS:
        return True
    now = now or datetime.now(KST)
    return now.weekday() in (0, 3)


def sanitize_gmail_app_password(value):
    """Google 앱 비밀번호 표시 형식의 공백/비분리 공백을 제거합니다."""
    return re.sub(r"\s+", "", str(value or "").replace("\u00a0", ""))


def get_card_date_range(now=None):
    """월요일이면 목~일(4일), 목요일이면 월~수(3일) 범위를 반환합니다. 중첩 방지."""
    now = now or datetime.now(KST)
    weekday = now.weekday()

    if FORCE_CARD_NEWS:
        start = now - timedelta(days=7)
        end = now - timedelta(days=1)
    elif weekday == 0:
        start = now - timedelta(days=4)
        end = now - timedelta(days=1)
    elif weekday == 3:
        start = now - timedelta(days=3)
        end = now - timedelta(days=1)
    else:
        return None, None

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def load_articles_in_range(start_date, end_date):
    """news_history.json에서 날짜 범위 내 기사를 추출합니다."""
    history = load_json(HISTORY_FILE, [])
    results = []
    for item in history:
        d = item.get("date", "")
        if start_date <= d <= end_date:
            results.append(item)
    return results


def call_claude_for_cards(articles_data, date_str, start_date, end_date):
    """Claude API를 호출해 커버 + 본문 HTML 카드를 생성합니다."""
    api_key = ANTHROPIC_API_KEY
    if not api_key:
        print("ANTHROPIC_API_KEY not set; skipping Claude card generation.")
        return None

    guide_text = ""
    if CARD_GUIDE_FILE.exists():
        guide_text = CARD_GUIDE_FILE.read_text(encoding="utf-8")

    simplified = []
    for a in articles_data:
        ai = a.get("ai", {}) or {}
        simplified.append({
            "title": a.get("title", ""),
            "ko_title": ai.get("ko_title", ""),
            "brief": ai.get("brief", ""),
            "why_important": ai.get("why_important", ""),
            "category": ai.get("category", ""),
            "countries": ai.get("countries", []),
            "companies": ai.get("companies", []),
            "technologies": ai.get("technologies", []),
            "specs": ai.get("specs", []),
            "date": a.get("date", ""),
            "source": a.get("source", ""),
        })

    system_prompt = f"""당신은 HifilM INC.의 인스타그램 수처리 뉴스 카드뉴스 디자이너입니다.
아래 제작 가이드를 반드시 따라 HTML 카드를 생성하십시오.

<card_news_guide>
{guide_text}
</card_news_guide>

중요 규칙:
1. 동향(수처리 산업동향)/기술(분리막, MBR, PFAS 등)/규제(규제/정책) 기사만 선정합니다.
2. 프로젝트/수주, 학회/전시회, 산업폐수(증설/건설), 교육/홍보 기사는 제외합니다.
3. 영문 카드뉴스입니다. 고유명사(기업, 지명, 기관)는 영문 유지하고 옐로우(#DDA11D)로 강조합니다.
4. 커버 1장 + 본문 카드(선정 기사 수만큼, 최대 5장)를 제작합니다.
5. 각 카드는 완전한 HTML 문서입니다 (<!DOCTYPE html> 포함).
6. 각 카드 사이에 ===CARD_SEPARATOR=== 구분자를 넣습니다.
7. 첫 번째 카드는 커버(id="cover"), 이후는 id="card_01", "card_02" 순서입니다.
8. 규격: 1080x1080px. 가이드의 색상(#0075C1, #DDA11D, #00205D 등), 로고(Hifil 블루 + M 옐로우), 푸터(좌: HifilM INC., 중앙: Water Treatment, 우: 비움) 규칙을 정확히 적용합니다.
9. 커버: 10칸 고정, 제목 한 줄 강제(fitTitles 스크립트 포함), 고유명사 옐로우, 출처/페이지번호 없음.
10. 본문: 상단 카테고리 라벨 + 제목 + 좌측 구분선(160px, 4px, 블루) + 기사 성격에 맞는 인포그래픽(SVG 직접 제작) + 사실 박스 + 푸터.
11. HTML 코드만 출력합니다. 설명이나 마크다운 코드블록은 넣지 마십시오.
"""

    user_message = f"""다음 기사 데이터로 {date_str} 발행 카드뉴스를 제작해 주세요.
수집 기간: {start_date} ~ {end_date}

기사 데이터:
{json.dumps(simplified, ensure_ascii=False, indent=2)}
"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-opus-4-7",
                "max_tokens": 16000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as exc:
        print(f"Claude API call failed: {exc}")
        return None


def generate_card_news(articles, date_str, top_n=None):
    """Claude API로 카드뉴스 HTML을 받아 Playwright로 1080x1080 2x PNG 캡처합니다."""
    top_n = top_n or CARD_NEWS_TOP_N
    cards_dir = CARDS_DIR / date_str
    cards_dir.mkdir(parents=True, exist_ok=True)

    start_date, end_date = get_card_date_range()
    if start_date is None:
        print("Not a card-news day; skipping.")
        return []

    range_articles = load_articles_in_range(start_date, end_date)
    if not range_articles:
        range_articles = articles

    targets = range_articles[:top_n * 2]
    if not targets:
        print("No articles for card news; skipping.")
        return []

    print(f"Calling Claude API for card news ({start_date} ~ {end_date}, {len(targets)} articles)...")
    html_output = call_claude_for_cards(targets, date_str, start_date, end_date)
    if not html_output:
        print("Claude returned no HTML; skipping card generation.")
        return []

    html_output = re.sub(r"^```html\s*", "", html_output.strip())
    html_output = re.sub(r"\s*```$", "", html_output.strip())

    cards = [c.strip() for c in html_output.split("===CARD_SEPARATOR===") if c.strip()]
    if not cards:
        print("No card HTML segments found; skipping.")
        return []

    html_paths = []
    for idx, card_html in enumerate(cards):
        name = "cover" if idx == 0 else f"card_{idx:02d}"
        path = cards_dir / f"{name}.html"
        path.write_text(card_html, encoding="utf-8")
        html_paths.append(path)

    png_paths = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1080, "height": 1080},
                device_scale_factor=2,
            )
            for html_path in html_paths:
                png_path = html_path.with_suffix(".png")
                page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                page.wait_for_timeout(1000)
                if "cover" in html_path.name:
                    try:
                        page.evaluate("if(typeof fitTitles==='function') fitTitles()")
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
                page.screenshot(path=str(png_path), full_page=False)
                png_paths.append(png_path)
            browser.close()
    except Exception as exc:
        print(f"Card PNG generation failed: {exc}")
        return []

    print(f"Generated {len(png_paths)} card-news PNGs (Claude API) in {cards_dir}")
    return png_paths


def send_card_email(png_paths, date_str):
    """카드뉴스 PNG를 Gmail SMTP로 검수용 이메일에 첨부해 발송합니다."""
    gmail_user = GMAIL_USER
    gmail_pass = sanitize_gmail_app_password(GMAIL_APP_PASSWORD)
    recipient = CARD_RECIPIENT or gmail_user

    if not png_paths:
        print("No card PNG files to email; skipping.")
        return

    if not gmail_user or not gmail_pass or not recipient:
        print("Gmail email credentials not set; skipping card email.")
        return

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg["Subject"] = f"Water News Cards - {date_str}"

    body = (
        f"카드뉴스 {date_str} 검수용입니다.\n\n"
        "첨부 PNG를 확인하고 인스타그램 게시 여부를 판단해 주세요.\n"
        "이 이메일은 GitHub Actions에서 자동 발송되었습니다."
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for png in png_paths:
        png = Path(png)
        if not png.exists():
            continue
        with png.open("rb") as f:
            img = MIMEImage(f.read(), name=png.name)
        msg.attach(img)

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as server:
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.send_message(msg)

    print(f"Card email sent to {recipient}")


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

    # 카드뉴스 전용 모드: 기존 history에서 기사를 읽어 Claude API로 카드 생성 후 이메일 발송만 수행합니다.
    if CARD_NEWS_ONLY:
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        start_date, end_date = get_card_date_range()
        if not start_date:
            print("get_card_date_range returned None; exiting card-news-only mode.")
            return
        print(f"Card-news-only mode: {start_date} ~ {end_date}")
        range_articles = load_articles_in_range(start_date, end_date)
        if not range_articles:
            print(f"No articles found in range {start_date} ~ {end_date}; exiting.")
            return
        card_pngs = generate_card_news(range_articles, today_str)
        send_card_email(card_pngs, today_str)
        return

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
    create_projects_page(history)
    create_numeric_page(history)
    update_docs_index(daily_url, weekly_url, monthly_url)

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    if FORCE_CARD_NEWS:
        card_pngs = generate_card_news(selected_articles, today_str)
        send_card_email(card_pngs, today_str)

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
