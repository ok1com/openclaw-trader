#!/bin/bash
# ETH Dashboard 자동 배포 스크립트
# 사용법: ./deploy.sh 또는 자동 실행 (fswatch)

cd /Users/macgmini4/openclaw-trader

# 변경된 파일이 있는지 확인
if git diff --quiet && git diff --cached --quiet; then
  echo "변경사항 없음, 스킵"
  exit 0
fi

# 변경된 파일 목록
CHANGED=$(git diff --name-only)
echo "📦 변경 감지: $CHANGED"

# 배포 전 잔고 갱신
source /Users/macgmini4/openclaw-trader/venv/bin/activate 2>/dev/null
python /Users/macgmini4/openclaw-trader/fetch_balance.py 2>/dev/null

# 스테이징 + 커밋 + 푸시
git add dashboard.html data/balance.json fetch_balance.py config.py market_monitor.py data_fetcher.py order_executor.py ai_analyst.py risk_manager.py scoring_engine.py main.py scheduler.py telegram_bot.py telegram_interactive.py .gitignore 2>/dev/null
git commit -m "auto-deploy: $(date '+%Y-%m-%d %H:%M')" --quiet
git push origin main --quiet

if [ $? -eq 0 ]; then
  echo "✅ GitHub Pages 배포 완료 (1~2분 후 반영)"
else
  echo "❌ push 실패"
fi
