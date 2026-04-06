import requests

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        d = r.json()['data'][0]
        return {"value": int(d['value']), "label": d['value_classification']}
    except:
        return {"value": 50, "label": "Neutral"}

def get_onchain():
    # DeFiLlama TVL
    tvl = None
    try:
        r = requests.get("https://api.llama.fi/v2/chains", timeout=5)
        for chain in r.json():
            if chain.get('name', '').lower() == 'ethereum':
                tvl = chain.get('tvl')
                break
    except:
        pass

    return {
        "tvl_usd": tvl,
        "source": "DeFiLlama"
    }

def get_funding_rate():
    # Binance ETH 무기한선물 펀딩비 (시장심리 참고용)
    try:
        r = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "ETHUSDT", "limit": 1},
            timeout=5
        )
        data = r.json()
        if data:
            return float(data[0]['fundingRate'])
    except:
        pass
    return None
