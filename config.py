import os
from dotenv import load_dotenv
import pathlib
_BASE = pathlib.Path(__file__).parent
load_dotenv(_BASE / 'config' / '.env')

# Upbit API
UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')

# AI API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 투자 프로필
INVESTOR_PROFILE = {
    "investment_range_krw": (5_000_000, 10_000_000),
    "style": "단기 선호, 공격적",
    "goal": "연 20% 수익 + 자산 보호",
    "max_single_buy_ratio": 0.30,       # 1회 최대 투자금의 30%
    "stop_loss_pct": -0.07,             # 손절 -7%
    "take_profit_pct": 0.15,            # 익절 +15%
    "target": "KRW-ETH"
}

# 안전 설정
SAFETY = {
    "require_confirmation": False  # 매매 실행 전 사용자 확인 여부
}

# 스케줄 설정 (현재 사용 안 함)
SCHEDULE = {}

# 리스크 한도
RISK = {
    "max_buy_krw": 3_000_000,           # 1회 최대 300만원
    "daily_loss_limit_krw": 500_000,    # 일일 손실한도 50만원
    "min_order_krw": 5_000              # 최소 주문금액
}

def validate_config():
    required_keys = [
        "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
    ]
    
    # AI API 키는 Gemini 또는 Anthropic 중 하나만 있으면 됨
    if not (GEMINI_API_KEY or ANTHROPIC_API_KEY):
        print("에러: GEMINI_API_KEY 또는 ANTHROPIC_API_KEY 중 하나는 설정되어야 합니다.")
        return False

    for key in required_keys:
        if not globals()[key]: # Access global variables by name
            print(f"에러: {key} 환경 변수가 설정되지 않았습니다. config/.env 파일을 확인하세요.")
            return False
            
    return True

