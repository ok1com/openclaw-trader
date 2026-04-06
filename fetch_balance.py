#!/usr/bin/env python3
"""업비트 잔고 조회 → data/balance.json 저장"""
import json, uuid, hashlib, os, time
from datetime import datetime
import jwt  # PyJWT
import requests
from pathlib import Path

# config 로드
BASE = Path(__file__).parent
import sys
sys.path.insert(0, str(BASE))
from config import UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY

def fetch_balance():
    """업비트 계좌 잔고 조회"""
    payload = {
        'access_key': UPBIT_ACCESS_KEY,
        'nonce': str(uuid.uuid4()),
    }
    jwt_token = jwt.encode(payload, UPBIT_SECRET_KEY, algorithm='HS256')
    headers = {'Authorization': f'Bearer {jwt_token}'}

    resp = requests.get('https://api.upbit.com/v1/accounts', headers=headers)
    resp.raise_for_status()
    return resp.json()

def save_balance():
    """잔고 조회 후 JSON 저장"""
    accounts = fetch_balance()

    krw_acc = next((a for a in accounts if a['currency'] == 'KRW'), None)
    eth_acc = next((a for a in accounts if a['currency'] == 'ETH'), None)

    krw_balance = float(krw_acc['balance']) if krw_acc else 0
    eth_balance = float(eth_acc['balance']) if eth_acc else 0
    eth_locked = float(eth_acc.get('locked', 0)) if eth_acc else 0
    eth_avg_price = float(eth_acc['avg_buy_price']) if eth_acc else 0

    # 현재가 조회
    ticker = requests.get('https://api.upbit.com/v1/ticker?markets=KRW-ETH').json()[0]
    current_price = ticker['trade_price']

    eth_total = eth_balance + eth_locked
    eth_eval = eth_total * current_price
    total_asset = krw_balance + eth_eval
    pnl_pct = ((current_price - eth_avg_price) / eth_avg_price * 100) if eth_avg_price > 0 else 0
    pnl_krw = (current_price - eth_avg_price) * eth_total if eth_avg_price > 0 else 0

    data = {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(time.time()),
        'krw_balance': round(krw_balance),
        'eth_balance': round(eth_total, 4),
        'eth_locked': round(eth_locked, 4),
        'eth_avg_price': round(eth_avg_price),
        'current_price': current_price,
        'eth_eval': round(eth_eval),
        'total_asset': round(total_asset),
        'pnl_pct': round(pnl_pct, 2),
        'pnl_krw': round(pnl_krw),
        # 전체 계좌 정보
        'all_accounts': [
            {
                'currency': a['currency'],
                'balance': a['balance'],
                'locked': a.get('locked', '0'),
                'avg_buy_price': a.get('avg_buy_price', '0'),
            }
            for a in accounts if float(a['balance']) > 0 or float(a.get('locked', 0)) > 0
        ]
    }

    out_path = BASE / 'data' / 'balance.json'
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[{data['updated_at']}] 잔고 저장 완료: 총 {total_asset:,.0f}원 (ETH {eth_total:.4f}개, KRW {krw_balance:,.0f}원)")
    return data

if __name__ == '__main__':
    save_balance()
