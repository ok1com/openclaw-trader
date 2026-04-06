"""
OpenClaw Trader - 메인 실행 파일
전체 매매 파이프라인: 스캔 → AI분석 → 리스크검증 → 매매실행 → 알림
"""
import json
import sys
import time
from datetime import datetime
from config import SAFETY, SCHEDULE, validate_config
from market_monitor import scan_all_stocks, get_stock_data
from ai_analyst import analyze_stock, analyze_signals
from risk_manager import RiskManager
from order_executor import OrderExecutor, format_order_message
from telegram_bot import TelegramBot


def run_trading_pipeline():
    """
    전체 매매 파이프라인 실행

    1. 시장 스캔 (관심종목 데이터 수집)
    2. 신호 감지 (기술적 지표 기반)
    3. AI 분석 (Gemini 1차 → Claude 2차)
    4. 리스크 검증
    5. 매매 실행 (사용자 확인 후)
    6. 결과 알림
    """
    print(f"\n{'='*50}")
    print(f"🚀 OpenClaw Trader 파이프라인 시작")
    print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    bot = TelegramBot()
    executor = OrderExecutor()

    # === 1단계: 시장 스캔 ===
    print("📡 [1/5] 시장 스캔 중...")
    all_data, signals = scan_all_stocks()

    if not signals:
        print("😴 매매 신호 없음. 파이프라인 종료.")
        bot.send_message("📡 스캔 완료: 매매 신호 없음")
        return

    # 신호 알림
    bot.send_scan_result(signals)
    print(f"🚨 {len(signals)}개 종목에서 신호 감지")

    # === 2단계: AI 분석 ===
    print("\n🤖 [2/5] AI 분석 중...")
    analysis_results = analyze_signals(signals, all_data)

    # 매매 가능한 결과만 필터링
    actionable = [
        r for r in analysis_results
        if r.get("final_action") in ("buy", "sell")
    ]

    if not actionable:
        print("🤔 AI 판단: 실행할 매매 없음")
        bot.send_message("🤖 AI 분석 완료: 실행할 매매 없음")
        return

    print(f"📊 {len(actionable)}개 매매 신호 확인됨")

    # === 3~5단계: 각 매매 신호별 실행 ===
    for result in actionable:
        action = result["final_action"]
        stock_code = result["stock_code"]
        stock_name = result["stock_name"]
        price = result["current_price"]

        print(f"\n{'─'*40}")
        print(f"💡 {stock_name}: {action.upper()} (확신도 {result['final_confidence']})")

        # 텔레그램 알림 및 확인 대기
        bot.send_trade_alert(result)

        if SAFETY["require_confirmation"]:
            print("⏳ 사용자 확인 대기 중 (5분)...")
            confirmation = bot.wait_for_confirmation(timeout=300)

            if confirmation == "cancel":
                print("❌ 사용자가 취소함")
                bot.send_message(f"❌ {stock_name} {action} 취소됨")
                continue
            elif confirmation == "timeout":
                print("⏰ 확인 시간 초과")
                bot.send_message(f"⏰ {stock_name} {action} 시간 초과로 취소됨")
                continue

        # 주문 실행
        print(f"📨 [4/5] 주문 실행 중: {stock_name} {action}...")
        order_result = executor.execute_order(
            action=action,
            stock_code=stock_code,
            stock_name=stock_name,
            price=price,
        )

        # 결과 알림
        bot.send_order_result(order_result)
        print(f"{'✅' if order_result.get('success') else '❌'} "
              f"{format_order_message(order_result)}")

    # === 일일 요약 ===
    print(f"\n📋 [5/5] 일일 요약...")
    risk_manager = RiskManager()
    bot.send_daily_summary(risk_manager.get_status_message())

    print(f"\n{'='*50}")
    print(f"✅ 파이프라인 완료")
    print(f"{'='*50}")


def run_scan_only():
    """스캔만 실행 (매매 없음)"""
    print("📡 스캔 전용 모드...")
    bot = TelegramBot()
    all_data, signals = scan_all_stocks()
    bot.send_scan_result(signals)

    if signals:
        print("\n🚨 감지된 신호:")
        for s in signals:
            print(f"  {s['name']}: {', '.join(s['reasons'])}")


def run_status():
    """현재 상태 확인"""
    rm = RiskManager()
    print(rm.get_status_message())

    executor = OrderExecutor()
    balance = executor.get_account_balance()
    if "error" not in balance:
        print(f"\n💰 계좌 잔고:")
        print(json.dumps(balance, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 설정 검증
    if not validate_config():
        print("\n⚠️ 설정을 먼저 완료해주세요. config/.env 파일을 확인하세요.")
        sys.exit(1)

    # 실행 모드 선택
    mode = sys.argv[1] if len(sys.argv) > 1 else "trade"

    if mode == "trade":
        run_trading_pipeline()
    elif mode == "scan":
        run_scan_only()
    elif mode == "status":
        run_status()
    else:
        print("사용법:")
        print("  python main.py trade   - 전체 매매 파이프라인")
        print("  python main.py scan    - 스캔만 (매매 없음)")
        print("  python main.py status  - 현재 상태 확인")
