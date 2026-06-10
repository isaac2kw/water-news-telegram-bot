# HifilM 수처리 뉴스 카드뉴스 제작 가이드

이 문서는 HifilM 인스타그램 "수처리 뉴스 브리핑" 카드뉴스(커버 + 피드)를 처음 만드는 사람이 동일한 결과물을 만들 수 있도록 작성한 표준 가이드입니다. 디자인 규칙, 제작 방식, 코드 구조, 콘텐츠 작성 원칙을 모두 포함합니다.

---

## 1. 개요

### 1.1 카드뉴스란
매일 자동 수집되는 수처리·멤브레인 뉴스(GitHub Pages 포털 기준)를 인스타그램용 카드 이미지로 만든 콘텐츠입니다. 한 세트는 다음으로 구성됩니다.

- 커버 1장: 그날의 헤드라인 목록
- 피드(본문) N장: 개별 기사 + 인포그래픽

### 1.2 데이터 출처
- 포털: https://isaac2kw.github.io/water-news-telegram-bot/
- 일일 상세 보고서: `/reports/YYYY-MM-DD/`
- 각 기사는 ko_title(한국어 제목), brief(한 줄 요약), category(분류), countries(국가), companies(기업), technologies(기술), specs(수치) 필드를 가짐

### 1.3 중요 원칙: 사실 정확성
카드뉴스는 외부에 공개 발행됩니다. 따라서 다음을 반드시 지킵니다.

- 카드의 텍스트·수치는 기사 제목/요약에 근거해야 하며, 없는 사실을 만들지 않습니다.
- 제목을 영문으로 옮길 때 수치(예: 1억 달러 → $100M)는 원문과 대조해 확인합니다.
- 인포그래픽의 막대 높이 등은 시각적 표현일 뿐 실측 비율이 아니므로, 수치 비교로 오해되지 않게 합니다.
- 발행 전 사람 검수를 거칩니다.

---

## 2. 브랜드 기준 (공통)

### 2.1 색상
| 이름 | HEX | 용도 |
| --- | --- | --- |
| 메인 블루 | `#0075C1` | 로고 "Hifil", 강조선, 번호, 카테고리 |
| 옐로우 | `#DDA11D` | 로고 "M", 고유명사 강조 |
| 네이비 | `#00205D` | 제목, 본문 기본 텍스트 |
| 틴트(연블루) | `#E6F1FB` | 배지·아이콘 박스 배경 |
| 카드 배경 | `#F5F7FA` | 인포그래픽 박스 배경 |
| 라인 | `#B5D4F4` | 구분선 |
| 회색 텍스트 | `#888780` | 날짜, 보조 정보 |

### 2.2 로고 규칙 (절대 불변)
- 표기: `Hifil`(블루 `#0075C1`) + `M`(옐로우 `#DDA11D`) + `INC.`(네이비, 선택)
- "M"은 반드시 옐로우. 이 규칙은 어떤 카드에서도 바뀌지 않습니다.

### 2.3 규격
- 크기: 1080 x 1080px (정사각형, 인스타그램 피드 표준)
- 출력 해상도: 2배(device_scale_factor=2) → 실제 2160 x 2160px PNG
- 폰트: Helvetica Neue / Helvetica / Arial (모던 산세리프)
- 좌우 여백: 90px 기준

### 2.4 푸터 (공통)
- 좌측: 로고 (`HifilM INC.`)
- 중앙: `Water Treatment` (블루, letter-spacing 2px)
- 우측: 비워둠 (페이지 넘버 넣지 않음)
- 푸터 위 1px 구분선(`#B5D4F4`)

---

## 3. 커버 페이지 규칙

> 아래 5가지는 확정 규칙입니다. 반드시 지킵니다.

### 3.1 핵심 5규칙
1. **10칸 고정**: 헤드라인 영역은 기사 개수와 무관하게 항상 10칸으로 고정합니다. 기사가 5개면 위 5칸만 채우고 나머지 5칸은 빈 공간으로 둡니다. 기사 수에 따라 칸 높이가 늘어나거나 줄어들지 않습니다.
2. **제목 한 줄 강제**: 헤드라인 제목은 무조건 한 줄입니다. 길어서 줄바꿈이 생기면 그 항목의 폰트 크기를 줄여서 한 줄을 유지합니다(기본 27px → 최소 16px까지 자동 축소).
3. **고유명사 옐로우 강조**: 제목 안의 대명사·고유명사·국가·지역·기업·기관명은 옐로우(`#DDA11D`)로 강조하고, 그 외 텍스트는 네이비(`#00205D`)로 표기합니다.
4. **출처 표기 삭제**: 'SOURCE / Google News Global Water / HifilM Water News Portal' 같은 출처 문구는 커버에 넣지 않습니다.
5. **페이지 넘버 삭제**: 우측 하단 페이지 번호는 넣지 않습니다.

### 3.2 커버 레이아웃 (위에서 아래로)
1. 상단 중앙 배지: `DAILY WATER NEWS` (틴트 배경 알약형, 블루 텍스트, letter-spacing 6px)
2. 타이틀: `Water News Briefing`
   - 컬러 공식: 메인 단어 블루 + 중간 네이비 + 강조 단어 옐로우 (예: Water=블루, News=네이비, Briefing=옐로우)
   - 폰트 약 78px, 굵게(700)
3. 타이틀 아래 중앙 구분선: 가로 160px, 높이 4px, 블루
4. 날짜 줄: `JUNE 4, 2026 · THU · TOP HEADLINES` (회색, letter-spacing 3px)
5. 헤드라인 목록(10칸 고정): 각 칸은 `번호(블루) + 점 + 제목 + 국기` 한 줄
6. 푸터(공통 규칙)

### 3.3 옐로우 강조 대상 판단 기준
- 강조함: 국가(USA), 도시·지역(Buffalo, Tokyo), 기업(Toray, Veolia), 기관(Ministry of Labor), 인명
- 모호한 경우 결정 필요: 약어(WWTP, ISC), 수치($100M)
  - 현재 시안은 약어·수치도 강조했으나, 운영 규칙은 담당자가 확정합니다.
  - 자동화 시에는 기업명·지명 사전(아래 5장)에 등록된 단어만 자동으로 옐로우 처리하는 방식을 권장합니다.

---

## 4. 피드(본문) 카드 규칙

### 4.1 본문 카드 레이아웃 (위에서 아래로)
1. 상단 라벨: `점 + 카테고리(영문 대문자) + 배지(국가/구분)` (블루)
2. 제목: 네이비 기본, 고유명사는 블루 또는 옐로우 강조 (커버와 톤 일치)
3. 타이틀 아래 좌측 구분선: 가로 160px, 높이 4px, 블루
4. 인포그래픽 영역: 기사 성격에 맞는 형태(아래 4.2)
5. 보조 정보: 핵심 사실 박스 또는 태그
6. 푸터(공통 규칙)

### 4.2 기사 유형별 인포그래픽 (중요)
기사 내용에 맞는 인포그래픽을 넣습니다. 기사 성격별 권장 형태는 다음과 같습니다.

| 기사 유형 | 인포그래픽 형태 | 예시 |
| --- | --- | --- |
| 협약·계약·파트너십 | 관계도 (양쪽 노드 + 중앙 연결) | Buffalo 협약: 지자체 ↔ 처리시설 |
| 투자·사업비·규모 | 막대 차트 또는 수치 강조 | Henderson $100M 투자 |
| 오염·이동경로·공정 | 플로우 다이어그램 (단계별 화살표) | PFAS: 매립지 → 처리장 → 위험 |
| 기술·성능·비교 | 2단 비교 또는 스펙 표 | 막 성능 비교 |
| 일정·행사 | 타임라인 | 학회/전시회 일정 |

- 아이콘은 SVG로 직접 그립니다(외부 이미지·저작권 자산 사용 금지).
- 인포그래픽은 정보 전달이 목적이며, 없는 수치를 시각화하지 않습니다.

### 4.3 본문 카드 세로 공간 주의
- 콘텐츠가 푸터(상단 약 985px 지점)를 침범하지 않도록 합니다.
- 인포그래픽 + 사실 박스가 길면 차트 높이·여백·폰트를 줄여 맞춥니다.
- 항목이 많으면 차트 높이를 300px 이하로 제한하는 것이 안전합니다.

---

## 5. 텍스트 작성 원칙 (영문화)

### 5.1 영문 카드뉴스
카드뉴스는 영문으로 제작합니다(타겟: MZ세대 엔지니어, 영문 표기 친숙).

### 5.2 고유명사 영문 유지 규칙
- 기업명, 해외 지명, 해외 기관명, 브랜드명, 제품명은 영문 원문 그대로 표기합니다.
  - 예: Toray(토레이/도레이 아님), Veolia, SUEZ, Buffalo(버팔로 아님), Tokyo(도쿄 아님)
- 한국 국내 지명·기관·지자체 등 한국어가 정식 명칭인 대상은 한글로 표기할 수 있습니다.
  - 예: 환경부, 한국상하수도협회, 예산군
  - 단, 커버를 전부 영문으로 통일할 경우 Yesan County처럼 영문화할 수 있으며, 이 범위는 담당자가 확정합니다.

### 5.3 자동화 연동 (참고)
- 본 카드뉴스의 텍스트는 포털 백엔드(`main.py`)의 기업명·지명 영문 치환 사전과 동일한 기준을 따릅니다.
- `COMPANY_ENGLISH_MAP`(기업명), `LOCATION_ENGLISH_MAP`(해외 지명)에 등록된 항목이 영문화·강조 대상의 기준이 됩니다.

---

## 6. 제작 방식 (기술)

### 6.1 방식: HTML/CSS + Playwright 스크린샷
카드는 HTML/CSS로 디자인한 뒤 Playwright(헤드리스 브라우저)로 PNG를 캡처합니다. 기존 포털의 HTML 생성 파이프라인과 자연스럽게 연결되고, 무료이며 GitHub Actions 안에서 동작합니다.

### 6.2 환경 준비
```bash
pip install playwright
playwright install chromium
```

### 6.3 캡처 스크립트 (기본형)
```python
from playwright.sync_api import sync_playwright
from pathlib import Path

html_path = Path("cards.html").resolve()

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={"width": 1080, "height": 1080},
        device_scale_factor=2,   # 2배 해상도
    )
    page.goto(f"file://{html_path}")
    page.wait_for_timeout(1800)  # 웹폰트 로딩 대기
    # 커버는 제목 한 줄 맞춤 함수 재실행
    page.evaluate("fitTitles()")
    page.wait_for_timeout(400)
    # 카드별 캡처 (각 카드 div에 고유 id 부여)
    page.query_selector("#cover").screenshot(path="cover.png")
    browser.close()
```

### 6.4 제목 한 줄 자동 축소 스크립트 (커버 필수)
커버 HTML 안에 아래 스크립트를 포함합니다. 제목이 칸 너비를 넘으면 폰트를 0.5px씩 줄여 한 줄을 유지합니다.
```javascript
function fitTitles(){
  const titles = document.querySelectorAll('.hl-title');
  titles.forEach(t=>{
    let size = 27;      // 기본 폰트(px)
    const min = 16;     // 최소 폰트(px)
    t.style.fontSize = size + 'px';
    while(t.scrollWidth > t.clientWidth && size > min){
      size -= 0.5;
      t.style.fontSize = size + 'px';
    }
  });
}
fitTitles();
```
- 제목 요소에는 `white-space:nowrap; overflow:hidden;` CSS가 적용되어 있어야 합니다.

### 6.5 10칸 고정 구조 (커버 필수)
- 헤드라인 컨테이너를 고정 높이 영역으로 잡고, 각 칸에 `flex:1`을 주어 10등분합니다.
- 기사가 10개 미만이면 빈 칸 요소(`<div class="hl empty"></div>`)로 채우되, `visibility:hidden`으로 숨겨 자리만 유지합니다.
- 이렇게 하면 기사 수와 무관하게 칸 위치·높이가 항상 동일합니다.

### 6.6 출력 경로 (자동화 시)
- `docs/cards/YYYY-MM-DD/cover.png`
- `docs/cards/YYYY-MM-DD/card_01.png` ~ `card_NN.png`

### 6.7 콘텐츠 안전 (이미지 생성 시)
- 실재 인물 사진, 브랜드 캐릭터, 라이선스 자산, 기존 작품 복제는 사용하지 않습니다.
- 아이콘·일러스트는 SVG로 직접 제작합니다.

---

## 7. 제작 체크리스트

발행 전 다음을 확인합니다.

- [ ] 규격 1080x1080px, 2배 해상도로 출력했는가
- [ ] 로고 "M"이 옐로우인가
- [ ] 커버가 10칸 고정인가 (기사 적어도 칸 안 늘어남)
- [ ] 커버 제목이 모두 한 줄인가 (넘침 없음)
- [ ] 고유명사가 옐로우, 나머지 네이비인가
- [ ] 커버에 출처 문구가 없는가
- [ ] 커버 우측 하단에 페이지 번호가 없는가
- [ ] 본문 인포그래픽이 기사 성격에 맞는가
- [ ] 본문 콘텐츠가 푸터를 침범하지 않는가
- [ ] 텍스트의 수치·고유명사가 원문과 일치하는가 (사람 검수)
- [ ] 푸터 중앙에 "Water Treatment"가 있는가

---

## 8. 참고: 색상 코드 요약 (복붙용)

```css
:root{
  --main-blue:#0075C1;  /* 로고 Hifil, 강조선, 번호 */
  --yellow:#DDA11D;     /* 로고 M, 고유명사 강조 */
  --navy:#00205D;       /* 제목, 본문 텍스트 */
  --tint:#E6F1FB;       /* 배지·아이콘 배경 */
  --card-bg:#F5F7FA;    /* 인포그래픽 박스 */
  --line:#B5D4F4;       /* 구분선 */
  --gray-light:#888780; /* 날짜·보조 */
}
```

---

## 9. HTML 템플릿 (필수 참조)

> 아래 HTML 코드는 확정된 디자인 템플릿입니다. 카드 생성 시 이 HTML 구조와 CSS를 그대로 사용하고, 기사 데이터만 교체합니다. 색상, 레이아웃, 클래스명, 푸터 구조를 변경하지 마십시오.

### 9.1 공통 CSS (모든 카드에 적용)

각 카드는 독립된 HTML 문서입니다. 아래 CSS를 각 카드의 `<style>` 안에 포함합니다.

```html
<style>
  :root{
    --main-blue:#0075C1;
    --yellow:#DDA11D;
    --navy:#00205D;
    --tint:#E6F1FB;
    --card-bg:#F5F7FA;
    --line:#B5D4F4;
    --gray-light:#888780;
  }
  *{margin:0;padding:0;box-sizing:border-box;}
  body{
    margin:0;padding:0;
    font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;
  }
  .card{
    width:1080px;height:1080px;background:#ffffff;position:relative;
    overflow:hidden;
  }
  .pad{padding:0 90px;}

  /* 공통 푸터 */
  .footer{
    position:absolute;left:0;right:0;bottom:46px;padding:0 90px;
  }
  .footer .line{height:1px;background:var(--line);margin-bottom:22px;}
  .footer .row{display:flex;align-items:center;justify-content:space-between;}
  .logo{font-size:26px;font-weight:700;letter-spacing:.2px;}
  .logo .h{color:var(--main-blue);}
  .logo .m{color:var(--yellow);}
  .logo .inc{color:var(--navy);}
  .footer .center{color:var(--main-blue);font-size:22px;font-weight:600;letter-spacing:2px;}
  .footer .right{width:120px;}

  /* 커버 전용 */
  .badge{
    display:inline-block;background:var(--tint);color:var(--main-blue);
    font-size:22px;font-weight:700;letter-spacing:6px;
    padding:13px 30px;border-radius:27px;
  }
  .cover-top{padding-top:96px;text-align:center;}
  .title{font-size:78px;font-weight:700;margin-top:34px;line-height:1.05;}
  .title .b{color:var(--main-blue);}
  .title .n{color:var(--navy);}
  .title .y{color:var(--yellow);}
  .divider{width:160px;height:4px;background:var(--main-blue);margin:30px auto 0;}
  .dateline{
    color:var(--gray-light);font-size:22px;letter-spacing:3px;
    margin-top:26px;text-align:center;font-weight:600;
  }
  .hl-wrap{
    position:absolute;left:0;right:0;top:470px;bottom:150px;
    padding:0 90px;display:flex;flex-direction:column;
  }
  .hl{
    flex:1;display:flex;align-items:center;gap:22px;
    border-bottom:1px solid #eef2f6;
  }
  .hl .num{
    color:var(--main-blue);font-size:30px;font-weight:700;
    min-width:42px;text-align:right;
  }
  .hl .dot{width:7px;height:7px;border-radius:50%;background:var(--line);flex:0 0 auto;}
  .hl-title{
    flex:1;color:var(--navy);font-size:27px;font-weight:600;
    white-space:nowrap;overflow:hidden;
  }
  .hl-title .y{color:var(--yellow);font-weight:700;}
  .flag{
    flex:0 0 auto;font-size:16px;font-weight:700;color:#5a6573;
    border:1px solid var(--line);border-radius:6px;padding:3px 9px;letter-spacing:1px;
  }
  .hl.empty{visibility:hidden;}

  /* 본문 카드 전용 */
  .label{
    display:flex;align-items:center;gap:12px;padding-top:96px;
    color:var(--main-blue);font-size:24px;font-weight:700;letter-spacing:3px;
  }
  .label .ldot{width:10px;height:10px;border-radius:50%;background:var(--main-blue);}
  .label .lbadge{
    margin-left:6px;background:var(--tint);color:var(--main-blue);
    font-size:18px;letter-spacing:2px;padding:5px 14px;border-radius:20px;
  }
  .ctitle{
    margin-top:34px;color:var(--navy);font-size:56px;font-weight:700;line-height:1.18;
  }
  .ctitle .b{color:var(--main-blue);}
  .ctitle .y{color:var(--yellow);}
  .cdivider{width:160px;height:4px;background:var(--main-blue);margin-top:30px;}
  .info{margin-top:48px;}
  .facts{
    position:absolute;left:90px;right:90px;bottom:150px;
    display:flex;gap:18px;
  }
  .fact{
    flex:1;background:var(--card-bg);border-radius:16px;padding:26px 24px;
  }
  .fact .k{color:var(--gray-light);font-size:18px;letter-spacing:1px;margin-bottom:10px;}
  .fact .v{color:var(--navy);font-size:26px;font-weight:700;line-height:1.25;}
  .fact .v .b{color:var(--main-blue);}
  .fact .v .y{color:var(--yellow);}
</style>
```

### 9.2 커버 HTML 템플릿

배지, 타이틀, 날짜, 10칸 헤드라인, 푸터, fitTitles 스크립트를 포함합니다. 기사 데이터만 교체합니다.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<!-- 위 9.1의 CSS를 <style> 태그 안에 넣습니다 -->
</head>
<body>
<div class="card" id="cover">
  <div class="cover-top">
    <span class="badge">TRENDS · TECH · POLICY</span>
    <div class="title"><span class="b">Water</span> <span class="n">News</span> <span class="y">Briefing</span></div>
    <div class="divider"></div>
    <div class="dateline">{{DATE}} · {{DAY}} · WEEKLY PICKS</div>
  </div>

  <div class="hl-wrap">
    <!-- 기사 수만큼 채우고, 나머지는 class="hl empty"로 10칸 맞춤 -->
    <div class="hl">
      <span class="num">1</span><span class="dot"></span>
      <span class="hl-title">제목 (고유명사는 <span class="y">옐로우</span>)</span>
      <span class="flag">US</span>
    </div>
    <!-- ... 2~N번 반복 ... -->
    <!-- 빈 칸 예시 -->
    <div class="hl empty"><span class="num">6</span><span class="dot"></span><span class="hl-title">placeholder</span><span class="flag">-</span></div>
    <!-- ... 10번까지 ... -->
  </div>

  <div class="footer">
    <div class="line"></div>
    <div class="row">
      <div class="logo"><span class="h">Hifil</span><span class="m">M</span>&nbsp;<span class="inc">INC.</span></div>
      <div class="center">Water Treatment</div>
      <div class="right"></div>
    </div>
  </div>
</div>

<script>
function fitTitles(){
  const titles = document.querySelectorAll('.hl-title');
  titles.forEach(t=>{
    let size = 27;
    const min = 16;
    t.style.fontSize = size + 'px';
    while(t.scrollWidth > t.clientWidth && size > min){
      size -= 0.5;
      t.style.fontSize = size + 'px';
    }
  });
}
fitTitles();
</script>
</body>
</html>
```

### 9.3 본문 카드 HTML 템플릿

카테고리 라벨 + 제목 + 구분선 + 인포그래픽(SVG) + 사실 박스 + 푸터 구조입니다.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<!-- 위 9.1의 CSS를 <style> 태그 안에 넣습니다 -->
</head>
<body>
<div class="card" id="card_01">
  <div class="pad">
    <div class="label"><span class="ldot"></span>{{CATEGORY}}<span class="lbadge">{{COUNTRY}}</span></div>
    <div class="ctitle">제목 (<span class="b">기술 키워드 블루</span>, <span class="y">고유명사 옐로우</span>)</div>
    <div class="cdivider"></div>
    <div class="info">
      <!-- 기사 성격에 맞는 SVG 인포그래픽을 여기에 넣습니다 -->
      <!-- 협약/파트너십 → 관계도 (양쪽 rect + 중앙 circle) -->
      <!-- 투자/규모 → 막대 차트 -->
      <!-- 오염/공정 → 플로우 다이어그램 (rect + polygon 화살표) -->
      <!-- 기술/비교 → 2단 비교 카드 -->
      <!-- SVG는 width="900" height="300~340" viewBox 기준 -->
      <!-- 색상은 반드시 가이드 색상만 사용: #0075C1, #DDA11D, #00205D, #E6F1FB, #F5F7FA, #B5D4F4 -->
      <svg width="900" height="340" viewBox="0 0 900 340" xmlns="http://www.w3.org/2000/svg">
        <!-- 인포그래픽 내용 -->
      </svg>
    </div>
  </div>
  <div class="facts">
    <div class="fact"><div class="k">CATEGORY</div><div class="v"><span class="b">값</span></div></div>
    <div class="fact"><div class="k">FOCUS</div><div class="v">값</div></div>
    <div class="fact"><div class="k">FIGURES</div><div class="v">값</div></div>
  </div>
  <div class="footer">
    <div class="line"></div>
    <div class="row">
      <div class="logo"><span class="h">Hifil</span><span class="m">M</span>&nbsp;<span class="inc">INC.</span></div>
      <div class="center">Water Treatment</div>
      <div class="right"></div>
    </div>
  </div>
</div>
</body>
</html>
```

### 9.4 절대 준수 사항

- 배경은 반드시 `#ffffff` (흰색). 어두운 배경, 그라데이션 배경을 사용하지 마십시오.
- CSS 변수(`--main-blue`, `--yellow` 등)와 클래스명을 그대로 사용합니다.
- 로고: `<span class="h">Hifil</span><span class="m">M</span>` — "M"은 반드시 옐로우.
- 푸터: 좌측 로고, 중앙 "Water Treatment", 우측 비움. 이 구조를 변경하지 마십시오.
- 커버: 10칸 고정, fitTitles 스크립트 포함, 출처/페이지번호 없음.
- SVG 인포그래픽: 가이드 색상만 사용, 외부 이미지 없음, rect/circle/polygon/text만 사용.
- 각 카드는 완전한 독립 HTML 문서 (<!DOCTYPE html> 포함).
