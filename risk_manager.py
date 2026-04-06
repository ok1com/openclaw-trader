"""
Risk Manager - 손절/익절 모니터링 + 포지션 관리
"""
import json
import os
from datetime import datetime
import pathlib
from config import RISK # Added import for RISK

_BASE = pathlib.Path(__file__).parent
DATA_DIR = _BASE / 'data'
STATE_FILE = DATA_DIR / 'risk_state.json'


def load_state():
    """리스크 상태 로드"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "daily_loss": 0,
        "daily_date": datetime.now().strftime("%Y-%m-%d"),
        "trades_today": 0,
        "alerts_sent": [],
    }


def save_state(state):
    """리스크 상태 저장"""
    DATA_DIR.mkdir(exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def calc_position(krw, eth, avg_price, current_price):
    """포지션 계산"""
    eth_value = eth * current_price
    total_asset = krw + eth_value
    pnl_krw = (current_price - avg_price) * eth if avg_price else 0
    pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price else 0
    eth_ratio = (eth_value / total_asset * 100) if total_asset else 0

    return {
        "krw": krw,
        "eth": eth,
        "avg_price": avg_price,
        "current_price": current_price,
        "eth_value": eth_value,
        "total_asset": total_asset,
        "pnl_krw": pnl_krw,
        "pnl_pct": pnl_pct,
        "eth_ratio": eth_ratio,
        "stop_loss_price": round(avg_price * 0.93) if avg_price else 0,
        "take_profit_price": round(avg_price * 1.15) if avg_price else 0,
    }


def check_stop_loss(position, stop_pct=-7):
    """손절 체크"""
    if position['pnl_pct'] <= stop_pct:
        return {
            "triggered": True,
            "type": "STOP_LOSS",
            "message": f"🚨 손절 도달! 현재 {position['pnl_pct']:+.2f}% (한도: {stop_pct}%)",
            "pnl_pct": position['pnl_pct'],
        }
    elif position['pnl_pct'] <= stop_pct * 0.7:
        return {
            "triggered": False,
            "type": "STOP_WARNING",
            "message": f"⚠️ 손절 근접! 현재 {position['pnl_pct']:+.2f}% (한도: {stop_pct}%)",
            "pnl_pct": position['pnl_pct'],
        }
    return {"triggered": False, "type": "OK"}


def check_take_profit(position, profit_pct=15):
    """익절 체크"""
    if position['pnl_pct'] >= profit_pct:
        return {
            "triggered": True,
            "type": "TAKE_PROFIT",
            "message": f"🎯 익절 도달! 현재 {position['pnl_pct']:+.2f}% (목표: +{profit_pct}%)",
            "pnl_pct": position['pnl_pct'],
        }
    elif position['pnl_pct'] >= profit_pct * 0.7:
        return {
            "triggered": False,
            "type": "PROFIT_NEAR",
            "message": f"📈 익절 근접! 현재 {position['pnl_pct']:+.2f}% (목표: +{profit_pct}%)",
            "pnl_pct": position['pnl_pct'],
        }
    return {"triggered": False, "type": "OK"}


def check_daily_loss_limit(state, new_loss=0, limit=500_000):
    """일일 손실 한도 체크"""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get('daily_date') != today:
        state['daily_loss'] = 0
        state['daily_date'] = today
        state['trades_today'] = 0
        state['alerts_sent'] = []

    state['daily_loss'] += new_loss
    if state['daily_loss'] >= limit:
        return {
            "exceeded": True,
            "message": f"🛑 일일 손실한도 초과! {state['daily_loss']:,.0f}원 / {limit:,.0f}원",
        }
    return {"exceeded": False}


def validate_order(side, amount_krw, position, state):
    """주문 유효성 검증"""
    errors = []

    if side == "BUY":
        if amount_krw > 3_000_000:
            errors.append(f"1회 최대 매수 300만원 초과 ({amount_krw:,.0f}원)")
        if amount_krw < 5_000:
            errors.append(f"최소 주문금액 5,000원 미만 ({amount_krw:,.0f}원)")
        if amount_krw > position['krw']:
            errors.append(f"원화 잔고 부족 (잔고: {position['krw']:,.0f}원)")

        daily_check = check_daily_loss_limit(state)
        if daily_check['exceeded']:
            errors.append(daily_check['message'])

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": []}


def log_trade(side, amount, price, result):
    """거래 기록 저장"""
    DATA_DIR.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "side": side,
        "amount": amount,
        "price": price,
        "result": str(result),
    }
    log_file = DATA_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_trade_history(days=7):
    """최근 거래 내역 조회"""
    trades = []
    for f in sorted(DATA_DIR.glob("trades_*.jsonl"), reverse=True)[:days]:
        with open(f) as fp:
            for line in fp:
                if line.strip():
                    trades.append(json.loads(line))
    return trades

class RiskManager:
    def __init__(self):
        self.state = load_state()
        self._check_daily_reset()

    def _check_daily_reset(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get('daily_date') != today:
            self.state['daily_loss'] = 0
            self.state['daily_date'] = today
            self.state['trades_today'] = 0
            self.state['alerts_sent'] = []
            save_state(self.state)

    def get_status_message(self):
        self._check_daily_reset() # Ensure state is up-to-date
        message = f"📊 리스크 관리 현황 ({self.state['daily_date']})\n"
        message += f"  - 일일 손실: {self.state['daily_loss']:,.0f}원\n"
        message += f"  - 금일 거래 횟수: {self.state['trades_today']}회\n"
        
        # Add a check against configured daily loss limit
        daily_loss_limit = RISK.get("daily_loss_limit_krw", 500_000)
        if self.state['daily_loss'] >= daily_loss_limit:
            message += f"  🛑 일일 손실한도 초과! ({daily_loss_limit:,.0f}원)\n"
        elif self.state['daily_loss'] > daily_loss_limit * 0.7:
             message += f"  ⚠️ 일일 손실한도 근접! ({self.state['daily_loss']:,.0f}원 / {daily_loss_limit:,.0f}원)\n"

        if self.state['alerts_sent']:
            message += "  🚨 발송된 알림: " + ", ".join(self.state['alerts_sent']) + "\n"
        
        return message

    def record_trade_result(self, trade_result):
        self._check_daily_reset()
        if trade_result.get("success"):
            self.state['trades_today'] += 1
            # Assuming trade_result has 'profit_loss' field for daily loss tracking
            profit_loss = trade_result.get("profit_loss", 0)
            if profit_loss < 0:
                self.state['daily_loss'] += abs(profit_loss)
            save_state(self.state)

    def is_daily_loss_limit_exceeded(self):
        self._check_daily_reset()
        daily_loss_limit = RISK.get("daily_loss_limit_krw", 500_000)
        return self.state['daily_loss'] >= daily_loss_limit