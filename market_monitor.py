import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime

SYMBOL = "KRW-ETH"

def get_current_price(symbol=SYMBOL):
    return pyupbit.get_current_price(symbol)

def get_ohlcv(symbol=SYMBOL, interval="day", count=200):
    return pyupbit.get_ohlcv(symbol, interval=interval, count=count)

def calc_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).iloc[-1]

def calc_macd(df):
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9).mean()
    return macd.iloc[-1], signal.iloc[-1], (macd - signal).iloc[-1]

def calc_bollinger(df, period=20):
    ma = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    return ma.iloc[-1], (ma + 2*std).iloc[-1], (ma - 2*std).iloc[-1]

def get_technical_data(symbol=SYMBOL):
    price = get_current_price(symbol)
    df_day = get_ohlcv(symbol, "day", 200)
    df_4h = get_ohlcv(symbol, "minute240", 200)

    ma50 = df_day['close'].rolling(50).mean().iloc[-1]
    ma200 = df_day['close'].rolling(200).mean().iloc[-1]

    rsi_day = calc_rsi(df_day)
    rsi_4h = calc_rsi(df_4h)
    macd, signal, hist = calc_macd(df_day)
    bb_mid, bb_upper, bb_lower = calc_bollinger(df_day)

    return {
        "price": price,
        "ma50": round(ma50),
        "ma200": round(ma200),
        "rsi_day": round(rsi_day, 1),
        "rsi_4h": round(rsi_4h, 1),
        "macd": round(macd),
        "macd_signal": round(signal),
        "macd_hist": round(hist),
        "bb_upper": round(bb_upper),
        "bb_mid": round(bb_mid),
        "bb_lower": round(bb_lower),
        "golden_cross": ma50 > ma200,
        "timestamp": datetime.now().isoformat()
    }

def get_stock_data(symbol=SYMBOL, interval="day", count=200):
    """
    Fetches OHLCV data for a given symbol.
    """
    return pyupbit.get_ohlcv(symbol, interval=interval, count=count)

def scan_all_stocks():
    # Placeholder: In a real scenario, this would iterate through a list of symbols.
    # For now, it will just get data for the default SYMBOL (KRW-ETH).
    
    all_data = {SYMBOL: get_technical_data(SYMBOL)} # Assuming get_technical_data provides all relevant data
    
    signals = []
    # Simplified signal generation for demonstration
    tech_data = all_data[SYMBOL]
    if tech_data["rsi_day"] < 30: # Example: simple oversold signal
        signals.append({
            "code": SYMBOL,
            "name": "Ethereum (KRW)", # Placeholder name
            "reasons": ["RSI day is below 30"],
            "current_price": tech_data["price"],
            "ma50": tech_data["ma50"],
            "ma200": tech_data["ma200"],
            "rsi_day": tech_data["rsi_day"],
            "rsi_4h": tech_data["rsi_4h"],
            "macd": tech_data["macd"],
            "macd_signal": tech_data["macd_signal"],
            "macd_hist": tech_data["macd_hist"],
            "bb_upper": tech_data["bb_upper"],
            "bb_mid": tech_data["bb_mid"],
            "bb_lower": tech_data["bb_lower"],
            "golden_cross": tech_data["golden_cross"],
        })
        
    return all_data, signals
