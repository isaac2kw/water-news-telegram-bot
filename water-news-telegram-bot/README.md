# Water News Telegram Bot

매일 오전 7시(KST)에 상하수도·수처리 관련 뉴스를 Telegram으로 발송하는 봇입니다.

## Files

- `main.py`: RSS 수집, 키워드 필터링, Telegram 발송
- `feeds.json`: 수집 대상 RSS 목록
- `sent_links.json`: 이미 발송한 링크 저장
- `.github/workflows/daily.yml`: GitHub Actions 자동 실행 설정

## GitHub Secrets

Repository Settings → Secrets and variables → Actions → New repository secret

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Schedule

GitHub Actions cron은 UTC 기준입니다.

- `0 22 * * *` = 한국시간 매일 오전 7시
