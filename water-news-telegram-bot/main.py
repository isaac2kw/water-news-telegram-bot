import os, re, json, html, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
import feedparser, requests

KST = timezone(timedelta(hours=9))
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
MAX_ITEMS = int(os.getenv('MAX_ITEMS', '8'))
MIN_SCORE = int(os.getenv('MIN_SCORE', '8'))

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
FEEDS_FILE = BASE_DIR / 'feeds.json'
SENT_FILE = BASE_DIR / 'sent_links.json'
DOCS_DIR = REPO_ROOT / 'docs'
REPORTS_DIR = DOCS_DIR / 'reports'

KEYWORDS = {
    'mbr':10, 'membrane bioreactor':10, 'membrane':8, 'hollow fiber':8, 'pvdf':8,
    'ultrafiltration':8, 'microfiltration':8, 'wastewater':8, 'sewage':8, 'sewer':6,
    'water reuse':9, 'reclaimed water':9, 'industrial wastewater':8, 'effluent':6,
    'wwtp':8, 'water treatment':7, 'drinking water':5, 'pfas':8, 'nutrient removal':6,
    'nitrogen':4, 'phosphorus':4, 'ammonia':4, 'tender':5, 'contract':5,
    'award':5, 'expansion':5, 'upgrade':5, 'commissioning':5, 'pilot':5,
    'demonstration':5, 'funding':4, 'investment':4, 'veolia':8, 'suez':8,
    'xylem':8, 'toray':8, 'asahi kasei':8, 'microza':8, 'mitsubishi':7,
    'pentair':7, 'kovalus':8, 'puron':8, 'dupont':7, 'filmtec':7, 'kubota':7,
    '상하수도':10, '하수처리':10, '폐수처리':10, '수처리':8, '물산업':8,
    '분리막':10, '중공사막':10, '재이용수':8, '방류수':6, '고도처리':7,
    '정수처리':6, '하수처리장':8, '폐수처리장':8, '환경부':5,
}
NEGATIVE_PATTERNS = [
    r'\bwater park\b', r'\bsports\b', r'\bswimming\b', r'\bbottled water\b',
    r'\bvoting rights\b', r'\bshare capital\b', r'\bshareholders\b',
    r'\bfinancial results\b', r'\bannual general meeting\b',
    r'nombre total de droits de vote', r'capital social',
    r'날씨', r'워터파크', r'수영', r'생수', r'먹는샘물', r'주주총회', r'의결권', r'자본금',
]

def load_json(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def clean_text(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

def keyword_match(text, kw):
    t, k = text.lower(), kw.lower()
    if k in {'mbr','uf','mf'}:
        return re.search(rf'(?<![a-zA-Z0-9]){re.escape(k)}(?![a-zA-Z0-9])', t) is not None
    return k in t

def score_article(title, summary):
    text = f'{title} {summary}'
    low = text.lower()
    for p in NEGATIVE_PATTERNS:
        if re.search(p, low, flags=re.I): return -100, []
    score, matched = 0, []
    for kw, point in KEYWORDS.items():
        if keyword_match(text, kw):
            score += point; matched.append(kw)
    return score, matched[:8]

def domain(url):
    try: return urlparse(url).netloc.replace('www.', '')
    except Exception: return ''

def fetch_articles():
    articles = []
    for feed in load_json(FEEDS_FILE, []):
        parsed = feedparser.parse(feed.get('url', ''))
        for entry in parsed.entries[:40]:
            title = clean_text(entry.get('title', ''))
            link = entry.get('link', '')
            summary = clean_text(entry.get('summary', ''))
            score, matched = score_article(title, summary)
            if score >= MIN_SCORE:
                articles.append({'title':title, 'link':link, 'summary':summary[:800], 'source':feed.get('name','Unknown'), 'domain':domain(link), 'score':score, 'matched':matched})
        time.sleep(1)
    dedup = {}
    for a in sorted(articles, key=lambda x: x['score'], reverse=True):
        if a['link'] and a['link'] not in dedup: dedup[a['link']] = a
    return list(dedup.values())

def guess_category(a):
    k = set(x.lower() for x in a.get('matched', []))
    if 'pfas' in k: return 'PFAS/오염물'
    if {'mbr','membrane','membrane bioreactor'} & k: return '분리막/MBR'
    if {'tender','contract','award','expansion','upgrade','pilot','commissioning'} & k: return '프로젝트/수주'
    if {'veolia','xylem','toray','asahi kasei','pentair','kovalus','suez'} & k: return '기업동향'
    return '수처리 산업동향'

def summarize_korean(a):
    fallback = {'ko_title':a['title'], 'brief':(a['summary'][:120] or 'RSS 제목 기준으로 선별되었습니다.'), 'summary':(a['summary'][:350] or '상세 내용은 원문 확인이 필요합니다.'), 'relevance':', '.join(a['matched']) or '수처리 관련 키워드 매칭', 'impact':'업계 동향 확인 필요', 'category':guess_category(a)}
    if not OPENAI_API_KEY: return fallback
    prompt = f'''다음 수처리/상하수도 관련 뉴스 항목을 한국어로 정리하세요. 반드시 JSON만 출력하세요.
필드: ko_title(한국어 제목 35자 이내), brief(텔레그램용 1문장 요약 70자 이내), summary(상세 보고서용 2~3문장), relevance(수처리 산업 관련성 1문장), impact(확인 포인트 1문장. 추측이면 추측입니다 명시), category(정책/규제, 프로젝트/수주, 분리막/MBR, 기업동향, PFAS/오염물, 수처리 산업동향 중 하나)
원문 제목: {a['title']}
출처: {a['source']}
RSS 요약: {a['summary']}
키워드: {', '.join(a['matched'])}
링크: {a['link']}'''
    try:
        r = requests.post('https://api.openai.com/v1/chat/completions', headers={'Authorization':f'Bearer {OPENAI_API_KEY}', 'Content-Type':'application/json'}, json={'model':OPENAI_MODEL, 'messages':[{'role':'system','content':'You are a Korean water and wastewater industry analyst. Return valid JSON only.'},{'role':'user','content':prompt}], 'response_format':{'type':'json_object'}, 'temperature':0.2}, timeout=60)
        r.raise_for_status()
        p = json.loads(r.json()['choices'][0]['message']['content'])
        return {key:p.get(key, fallback[key]) for key in fallback}
    except Exception as e:
        fallback['summary'] += f' [요약 API 오류: {str(e)[:120]}]'
        return fallback

def pages_base_url():
    explicit = os.getenv('PAGES_BASE_URL')
    if explicit: return explicit.rstrip('/')
    repo = os.getenv('GITHUB_REPOSITORY', '')
    if '/' in repo:
        owner, name = repo.split('/', 1)
        return f'https://{owner}.github.io/{name}'
    return ''

def create_report(articles):
    today = datetime.now(KST).strftime('%Y-%m-%d')
    report_dir = REPORTS_DIR / today
    report_dir.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / '.nojekyll').write_text('', encoding='utf-8')
    cards = []
    for i, a in enumerate(articles, 1):
        s = a['ai']
        cards.append(f'''<section class="card"><div class="top"><span class="rank">#{i}</span><span class="cat">{html.escape(s['category'])}</span><span class="src">{html.escape(a['source'])}</span></div><h2>{html.escape(s['ko_title'])}</h2><p class="brief">{html.escape(s['brief'])}</p><h3>내용 요약</h3><p>{html.escape(s['summary'])}</p><h3>수처리 산업 관련성</h3><p>{html.escape(s['relevance'])}</p><h3>확인 포인트</h3><p>{html.escape(s['impact'])}</p><p class="kw">점수: {a['score']} / 키워드: {html.escape(', '.join(a['matched']))}</p><p><a href="{html.escape(a['link'])}" target="_blank" rel="noopener noreferrer">원문 기사 보기</a></p></section>''')
    html_doc = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>상하수도·수처리 뉴스 브리핑 - {today}</title><style>body{{font-family:Arial,"Noto Sans KR",sans-serif;margin:0;background:#f6f8fb;color:#1f2937;line-height:1.65}}header{{background:#163b73;color:white;padding:30px 36px}}main{{max-width:980px;margin:28px auto;padding:0 18px}}h1{{margin:0 0 8px;font-size:28px}}h2{{margin:8px 0 10px;font-size:22px}}h3{{margin:18px 0 6px;font-size:15px;color:#374151}}.card{{background:white;border:1px solid #e5e7eb;border-radius:14px;padding:22px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}.top{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}.rank{{color:#f97316;font-weight:bold}}.cat{{background:#e0f2fe;color:#075985;border-radius:999px;padding:3px 10px;font-size:13px}}.src,.kw{{color:#6b7280;font-size:13px}}.brief{{background:#f9fafb;border-left:4px solid #163b73;padding:10px 12px}}a{{color:#1d4ed8}}</style></head><body><header><h1>상하수도·수처리 뉴스 브리핑</h1><div>{today} 자동 생성 보고서</div></header><main>{''.join(cards) if cards else '<div class="card">신규 뉴스가 없습니다.</div>'}</main></body></html>'''
    (report_dir / 'index.html').write_text(html_doc, encoding='utf-8')
    (DOCS_DIR / 'index.html').write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>상하수도·수처리 뉴스 브리핑</title></head><body><h1>상하수도·수처리 뉴스 브리핑</h1><p>최신 보고서: <a href="./reports/{today}/">{today} 보고서 보기</a></p></body></html>', encoding='utf-8')
    base = pages_base_url()
    return f'{base}/reports/{today}/' if base else f'reports/{today}/'

def build_telegram_message(articles, report_url):
    today = datetime.now(KST).strftime('%Y-%m-%d')
    lines = [f'[상하수도·수처리 뉴스 브리핑]', today, '']
    if not articles:
        lines.append('오늘 기준 필터 조건에 맞는 신규 뉴스가 없습니다.')
        return '\n'.join(lines)
    lines += [f'오늘 확인할 주요 뉴스 {min(5, len(articles))}건입니다.', '']
    for i, a in enumerate(articles[:5], 1):
        s = a['ai']
        lines += [f'{i}. {s["ko_title"]}', f'   주제: {s["category"]}', f'   요약: {s["brief"]}', '']
    lines += ['상세 분석 보고서 보기', report_url]
    return '\n'.join(lines)

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID: raise RuntimeError('TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.')
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    for chunk in [text[i:i+3900] for i in range(0, len(text), 3900)]:
        r = requests.post(url, data={'chat_id':CHAT_ID, 'text':chunk, 'disable_web_page_preview':False}, timeout=30)
        r.raise_for_status(); time.sleep(0.5)

def main():
    sent = set(load_json(SENT_FILE, []))
    articles = fetch_articles()
    new_articles = []
    for a in articles:
        if a['link'] not in sent: new_articles.append(a)
        if len(new_articles) >= MAX_ITEMS: break
    for a in new_articles: a['ai'] = summarize_korean(a)
    report_url = create_report(new_articles)
    send_telegram(build_telegram_message(new_articles, report_url))
    for a in new_articles: sent.add(a['link'])
    save_json(SENT_FILE, list(sent)[-2000:])

if __name__ == '__main__':
    main()
