import pyupbit
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('config/.env')

def get_upbit():
    return pyupbit.Upbit(
        os.getenv('UPBIT_ACCESS_KEY'),
        os.getenv('UPBIT_SECRET_KEY')
    )

def get_balance_krw():
    upbit = get_upbit()
    return upbit.get_balance("KRW")

def get_balance_eth():
    upbit = get_upbit()
    return upbit.get_balance("ETH")

def get_avg_buy_price():
    upbit = get_upbit()
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == 'ETH':
            return float(b.get('avg_buy_price', 0))
    return 0

def buy_eth_krw(amount_krw: float):
    """원화 금액으로 ETH 시장가 매수"""
    upbit = get_upbit()
    result = upbit.buy_market_order("KRW-ETH", amount_krw)
    log_order("BUY", amount_krw, result)
    return result

def sell_eth_ratio(ratio: float):
    """보유 ETH의 ratio 비율만큼 시장가 매도 (0.0~1.0)"""
    upbit = get_upbit()
    eth_balance = get_balance_eth()
    amount = eth_balance * ratio
    result = upbit.sell_market_order("KRW-ETH", amount)
    log_order("SELL", amount, result)
    return result

def sell_eth_all():
    return sell_eth_ratio(1.0)

def log_order(side, amount, result):
    os.makedirs("data", exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "side": side,
        "amount": amount,
        "result": str(result)
    }
    with open(f"data/orders_{datetime.now().strftime('%Y%m%d')}.jsonl", "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
