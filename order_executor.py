import pyupbit
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('config/.env')

class OrderExecutor:
    def __init__(self):
        # Initialize anything needed for the executor, e.g., API keys, etc.
        pass

    def _get_upbit(self):
        return pyupbit.Upbit(
            os.getenv('UPBIT_ACCESS_KEY'),
            os.getenv('UPBIT_SECRET_KEY')
        )

    def get_account_balance(self):
        # This will return KRW balance and any other crypto balances
        upbit = self._get_upbit()
        balances = upbit.get_balances()
        if balances:
            return {
                "krw_balance": next((float(b['balance']) for b in balances if b['currency'] == 'KRW'), 0.0),
                "other_assets": [
                    {"currency": b['currency'], "balance": float(b['balance']), "avg_buy_price": float(b.get('avg_buy_price', 0))}
                    for b in balances if b['currency'] != 'KRW'
                ]
            }
        return {"error": "Failed to retrieve account balance."}


    def get_balance_krw(self):
        upbit = self._get_upbit()
        return upbit.get_balance("KRW")

    def get_balance_eth(self):
        upbit = self._get_upbit()
        return upbit.get_balance("ETH")

    def get_avg_buy_price(self):
        upbit = self._get_upbit()
        balances = upbit.get_balances()
        for b in balances:
            if b['currency'] == 'ETH':
                return float(b.get('avg_buy_price', 0))
        return 0

    def buy_eth_krw(self, amount_krw: float):
        """원화 금액으로 ETH 시장가 매수"""
        upbit = self._get_upbit()
        result = upbit.buy_market_order("KRW-ETH", amount_krw)
        self._log_order("BUY", amount_krw, result)
        return result

    def sell_eth_ratio(self, ratio: float):
        """보유 ETH의 ratio 비율만큼 시장가 매도 (0.0~1.0)"""
        upbit = self._get_upbit()
        eth_balance = self.get_balance_eth()
        amount = eth_balance * ratio
        result = upbit.sell_market_order("KRW-ETH", amount)
        self._log_order("SELL", amount, result)
        return result

    def sell_eth_all(self):
        return self.sell_eth_ratio(1.0)

    def _log_order(self, side, amount, result):
        os.makedirs("data", exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "side": side,
            "amount": amount,
            "result": str(result)
        }
        with open(f"data/orders_{datetime.now().strftime('%Y%m%d')}.jsonl", "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def execute_order(self, action: str, stock_code: str, stock_name: str, price: float):
        """
        주문 실행 (실제 매매 로직)
        main.py에서 호출되는 메서드.
        """
        # Simplified for now. In a real scenario, you'd implement actual trading logic.
        # This will depend on the specific exchange API (e.g., Upbit, Binance)
        # and whether it's a test/mock or real trade.
        print(f"Executing order for {stock_name} ({stock_code}): {action} at {price}")

        # Example: if action is 'buy' and stock_code is 'KRW-ETH'
        if action == "buy" and stock_code == "KRW-ETH":
            # For simplicity, let's assume a fixed amount to buy for now
            # In a real system, this amount would be determined by risk management
            amount_krw_to_buy = 5000 # Example: Buy 5000 KRW worth of ETH
            order_result = self.buy_eth_krw(amount_krw_to_buy)
            if order_result and "uuid" in order_result:
                return {"success": True, "action": "BUY", "stock_name": stock_name, "amount": amount_krw_to_buy, "message": f"매수 주문 완료: {stock_name}"}
            else:
                return {"success": False, "action": "BUY", "stock_name": stock_name, "message": f"매수 주문 실패: {order_result}"}
        elif action == "sell" and stock_code == "KRW-ETH":
            # Example: Sell 50% of holdings
            sell_ratio = 0.5
            order_result = self.sell_eth_ratio(sell_ratio)
            if order_result and "uuid" in order_result:
                 return {"success": True, "action": "SELL", "stock_name": stock_name, "amount": f"{sell_ratio*100}%", "message": f"매도 주문 완료: {stock_name}"}
            else:
                return {"success": False, "action": "SELL", "stock_name": stock_name, "message": f"매도 주문 실패: {order_result}"}
        else:
            return {"success": False, "action": action, "stock_name": stock_name, "message": f"Unsupported action or stock: {action} {stock_code}"}


def format_order_message(order_result: dict) -> str:
    """주문 결과를 보기 좋게 포맷팅"""
    if order_result.get("success"):
        return (f"✅ {order_result['stock_name']} {order_result['action']} 성공: "
                f"{order_result.get('amount', 'N/A')} {order_result.get('message', '')}")
    else:
        return (f"❌ {order_result['stock_name']} {order_result['action']} 실패: "
                f"{order_result.get('message', '')}")
