import os
import asyncio
import logging
import pathlib
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# ... existing code ...

async def send_message_to_chat(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return
    bot = Bot(BOT_TOKEN)
    for chunk in chunk_message(message):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=chunk)
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")

_BASE = pathlib.Path(__file__).parent
load_dotenv(_BASE / 'config' / '.env')
logging.basicConfig(level=logging.INFO)

from order_executor import OrderExecutor

_executor = OrderExecutor()
get_balance_krw = _executor.get_balance_krw
get_balance_eth = _executor.get_balance_eth
get_avg_buy_price = _executor.get_avg_buy_price
buy_eth_krw = _executor.buy_eth_krw
sell_eth_ratio = _executor.sell_eth_ratio
sell_eth_all = _executor.sell_eth_all
from market_monitor import get_current_price
from ai_analyst import run_full_analysis
from risk_manager import calc_position, check_stop_loss, check_take_profit
from scoring_engine import calculate_final_score, format_score_report
from data_fetcher import get_fear_greed, get_funding_rate
from market_monitor import get_technical_data

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 스케줄러 인스턴스 (전역)
_scheduler = None

def get_balances_dict():
    return {
        "krw": get_balance_krw(),
        "eth": get_balance_eth(),
        "avg_buy_price": get_avg_buy_price()
    }

def chunk_message(text, max_len=4000):
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]

# ===== 명령어 핸들러 =====

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """🤖 ETH 트레이딩 봇 v2.0

📊 분석
/analyze - AI 전체 분석 (Gemini+Claude+스코어링)
/score - 수치 기반 빠른 판단
/price - 현재가 + 손익
/status - 잔고 + 포지션 상세

💰 매매
/buy [금액] - ETH 매수 (예: /buy 500000)
/sell [비율%] - ETH 매도 (예: /sell 50)
/sell all - 전량 매도

⚙️ 시스템
/monitor on - 자동 모니터링 시작
/monitor off - 자동 모니터링 중지
/history - 최근 AI 신호 내역"""
    await update.message.reply_text(msg)

async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    price = get_current_price()
    avg = get_avg_buy_price()
    pnl = ((price - avg) / avg * 100) if avg else 0
    sl_price = round(avg * 0.93) if avg else 0
    tp_price = round(avg * 1.15) if avg else 0

    await update.message.reply_text(
        f"📊 ETH 현재가: {price:,}원\n"
        f"📌 평단가: {avg:,}원\n"
        f"{'🟢' if pnl >= 0 else '🔴'} 손익: {pnl:+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛑 손절가(-7%): {sl_price:,}원\n"
        f"🎯 익절가(+15%): {tp_price:,}원"
    )

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    krw = get_balance_krw()
    eth = get_balance_eth()
    avg = get_avg_buy_price()
    price = get_current_price()

    pos = calc_position(krw, eth, avg, price)
    sl = check_stop_loss(pos)
    tp = check_take_profit(pos)

    status_icon = "🟢"
    if sl['type'] == 'STOP_LOSS':
        status_icon = "🚨"
    elif sl['type'] == 'STOP_WARNING':
        status_icon = "⚠️"
    elif tp['type'] == 'TAKE_PROFIT':
        status_icon = "🎯"
    elif tp['type'] == 'PROFIT_NEAR':
        status_icon = "📈"

    msg = (
        f"💼 포지션 현황 {status_icon}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"원화: {pos['krw']:,.0f}원\n"
        f"ETH: {pos['eth']:.6f}개\n"
        f"ETH 가치: {pos['eth_value']:,.0f}원\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"평단가: {pos['avg_price']:,}원\n"
        f"현재가: {pos['current_price']:,}원\n"
        f"{'🟢' if pos['pnl_krw'] >= 0 else '🔴'} 손익: {pos['pnl_krw']:+,.0f}원 ({pos['pnl_pct']:+.2f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"총 자산: {pos['total_asset']:,.0f}원\n"
        f"ETH 비중: {pos['eth_ratio']:.1f}%\n"
        f"🛑 손절가: {pos['stop_loss_price']:,}원\n"
        f"🎯 익절가: {pos['take_profit_price']:,}원"
    )
    await update.message.reply_text(msg)

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """수치 기반 빠른 판단"""
    await update.message.reply_text("📐 스코어링 계산 중...")
    try:
        tech = get_technical_data()
        fg = get_fear_greed()
        funding_rate = get_funding_rate()

        krw = get_balance_krw()
        eth = get_balance_eth()
        avg = get_avg_buy_price()

        pos = calc_position(krw, eth, avg, tech['price'])
        result = calculate_final_score(tech, fg, funding_rate, pos['pnl_pct'])
        report = format_score_report(result)

        msg = (
            f"📐 수치 기반 판단\n"
            f"ETH: {tech['price']:,.0f}원 | 손익: {pos['pnl_pct']:+.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{report}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 스코어링 오류: {e}")

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 AI 전체 분석 시작... (1~2분 소요)")
    try:
        balances = get_balances_dict()
        result = run_full_analysis(balances)

        # 1. 스코어링 결과
        score_msg = f"📐 [수치 기반 판단]\n{'━'*30}\n{result['score_report']}"
        await update.message.reply_text(score_msg)

        # 2. Gemini 분석 (분할)
        header = f"📊 [Gemini 1차 분석]\n{'='*30}\n"
        for chunk in chunk_message(header + result['gemini']):
            await update.message.reply_text(chunk)

        # 3. Claude 검증
        claude_msg = f"🤖 [2차 검증]\n{'='*30}\n{result['claude']}"
        await update.message.reply_text(claude_msg)

    except Exception as e:
        await update.message.reply_text(f"❌ 분석 오류: {e}")

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("사용법: /buy [금액(원)] 예) /buy 500000")
        return
    try:
        amount = float(args[0])
        if amount < 5000:
            await update.message.reply_text("❌ 최소 주문금액은 5,000원입니다.")
            return
        if amount > 3_000_000:
            await update.message.reply_text("❌ 1회 최대 매수는 300만원입니다.")
            return

        await update.message.reply_text(f"🟢 ETH {amount:,.0f}원 매수 주문 실행 중...")
        result = buy_eth_krw(amount)
        await update.message.reply_text(f"✅ 매수 완료!\n결과: {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ 매수 오류: {e}")

async def cmd_sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("사용법: /sell [비율%] 또는 /sell all")
        return
    try:
        if args[0].lower() == 'all':
            await update.message.reply_text("🔴 ETH 전량 매도 실행 중...")
            result = sell_eth_all()
        else:
            ratio = float(args[0]) / 100
            if not 0 < ratio <= 1:
                await update.message.reply_text("❌ 비율은 1~100 사이로 입력하세요.")
                return
            await update.message.reply_text(f"🔴 ETH {float(args[0]):.0f}% 매도 실행 중...")
            result = sell_eth_ratio(ratio)
        await update.message.reply_text(f"✅ 매도 완료!\n결과: {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ 매도 오류: {e}")

async def cmd_monitor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _scheduler
    args = ctx.args
    if not args:
        status = "실행중" if (_scheduler and _scheduler.running) else "중지됨"
        await update.message.reply_text(f"모니터 상태: {status}\n/monitor on 또는 /monitor off")
        return

    if args[0].lower() == 'on':
        if _scheduler and _scheduler.running:
            await update.message.reply_text("이미 실행 중입니다.")
            return
        from scheduler import TradingScheduler

        bot = ctx.bot
        chat_id = update.effective_chat.id

        def send_fn(msg):
            asyncio.run_coroutine_threadsafe(
                bot.send_message(chat_id=chat_id, text=msg),
                asyncio.get_event_loop()
            )

        _scheduler = TradingScheduler(telegram_send_fn=send_fn)
        _scheduler.start()
        await update.message.reply_text(
            "✅ 자동 모니터링 시작!\n"
            "• 가격 체크: 1분마다\n"
            "• 손절(-7%)/익절(+15%) 알림\n"
            "• 정기 분석: 09:00, 13:00, 21:00"
        )

    elif args[0].lower() == 'off':
        if _scheduler:
            _scheduler.stop()
        await update.message.reply_text("⏹ 자동 모니터링 중지됨")

async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """최근 AI 신호 내역"""
    import json
    signal_file = _BASE / 'data' / 'signals.jsonl'
    if not signal_file.exists():
        await update.message.reply_text("저장된 신호가 없습니다.")
        return

    lines = signal_file.read_text().strip().split('\n')
    recent = lines[-10:]  # 최근 10개

    msg_lines = ["📜 최근 AI 신호 내역", "━" * 30]
    for line in reversed(recent):
        try:
            d = json.loads(line)
            ts = d['timestamp'][:16].replace('T', ' ')
            msg_lines.append(
                f"{ts} | {d['price']:,.0f}원 | "
                f"점수:{d['final_score']:+.1f} | {d['action']}"
            )
        except:
            continue

    await update.message.reply_text('\n'.join(msg_lines))

# ===== 메인 =====

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("sell", cmd_sell))
    app.add_handler(CommandHandler("monitor", cmd_monitor))
    app.add_handler(CommandHandler("history", cmd_history))
    print("ETH 자동매매 봇 v2.0 시작!")
    app.run_polling()

if __name__ == "__main__":
    main()
