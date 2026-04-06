import os
import json
import google.generativeai as genai
import requests as _requests
from dotenv import load_dotenv
import pathlib
_BASE = pathlib.Path(__file__).parent
from market_monitor import get_technical_data
from data_fetcher import get_fear_greed, get_onchain, get_funding_rate

load_dotenv(_BASE / 'config' / '.env')

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def _build_simple_prompt(tech_data, stock_name, stock_code):
    current_price = tech_data['price']
    return f"""
    당신은 편견 없는 전문 주식 애널리스트입니다.
    {stock_name} ({stock_code}) 에 대한 다음 기술적 데이터를 분석하여 매수/홀드/매도 최종 판단을 해주세요.
    투자자 프로필: 단기 선호, 공격적 리스크 성향
    
    === 기술적 지표 ===
    현재가: {current_price:,}원
    RSI (일봉): {tech_data['rsi_day']} / RSI (4시간): {tech_data['rsi_4h']}
    MACD: {tech_data['macd']} / Signal: {tech_data['macd_signal']} / Hist: {tech_data['macd_hist']}
    MA50: {tech_data['ma50']:,}원 / MA200: {tech_data['ma200']:,}원
    골든크로스 여부: {tech_data['golden_cross']}
    볼린저밴드 상단: {tech_data['bb_upper']:,} / 중단: {tech_data['bb_mid']:,} / 하단: {tech_data['bb_lower']:,}원

    아래 순서대로 분석해줘:

    ## 1. 기술적 분석 요약
    - 현재 가격 위치, RSI, MACD, 이동평균선, 볼린저밴드 등 핵심 지표 해석

    ## 2. 매수/홀드/매도 최종 판단
    - **종합 신호**: 매수 / 홀드 / 매도 중 하나
    - **신호 근거 2가지** (수치 기반으로 제시)
    - **반대 의견 1가지** (구체적 수치로)
    - **구체적 액션 플랜**:
      - 진입 가격대, 손절가, 익절가 구체적으로 제시 (최소 1개 이상)

    분석은 한국어로, 전문적이지만 명확하게 작성해줘.
    """

def analyze_stock(stock_code, all_market_data):
    """
    Performs AI analysis for a single stock based on its technical data.
    """
    print(f"  🤖 AI 분석 중: {stock_code}")
    tech_data = all_market_data.get(stock_code)
    if not tech_data:
        return {"stock_code": stock_code, "status": "no_data", "message": "기술적 데이터 없음"}

    stock_name = stock_code_to_name.get(stock_code, stock_code)
    
    prompt = _build_simple_prompt(tech_data, stock_name, stock_code)
    gemini_result = analyze_with_gemini(prompt)

    final_action = "hold"
    final_confidence = 0.5
    if "매수" in gemini_result:
        final_action = "buy"
    elif "매도" in gemini_result:
        final_action = "sell"

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "current_price": tech_data['price'],
        "final_action": final_action,
        "final_confidence": final_confidence,
        "gemini_analysis": gemini_result,
        "technical_data": tech_data,
        "status": "success"
    }

stock_code_to_name = {
    "KRW-ETH": "Ethereum (KRW)",
}

def analyze_signals(signals, all_market_data):
    """
    Analyzes a list of trading signals using AI.
    """
    results = []
    for signal in signals:
        stock_code = signal["code"]
        analysis = analyze_stock(stock_code, all_market_data)
        results.append(analysis)
    return results

def build_prompt(tech, fg, onchain, funding_rate, balances):
    current_price = tech['price']
    avg_price = balances.get('avg_buy_price', 0)
    pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price else 0

    return f"""
당신은 편견 없는 전문 크립토 애널리스트입니다.
투자자 프로필: 투자금 500~1000만원, 단기 선호, 공격적 리스크 성향
투자 목표: 연 20% 수익 + 자산 보호
분석 원칙: 사실 기반, 반대 의견 반드시 포함

=== 현재 시장 데이터 ===
ETH 현재가: {current_price:,}원
평단가: {avg_price:,}원 (현재 손익: {pnl_pct:+.2f}%)
원화 잔고: {balances.get('krw', 0):,.0f}원
ETH 보유량: {balances.get('eth', 0):.4f}개

=== 기술적 지표 ===
RSI (일봉): {tech['rsi_day']} / RSI (4시간): {tech['rsi_4h']}
MACD: {tech['macd']} / Signal: {tech['macd_signal']} / Hist: {tech['macd_hist']}
MA50: {tech['ma50']:,}원 / MA200: {tech['ma200']:,}원
골든크로스 여부: {tech['golden_cross']} (False=데드크로스)
볼린저밴드 상단: {tech['bb_upper']:,} / 중단: {tech['bb_mid']:,} / 하단: {tech['bb_lower']:,}원

=== 시장 심리 ===
공포탐욕지수: {fg['value']} ({fg['label']})
ETH 선물 펀딩비: {funding_rate}
이더리움 TVL: ${onchain.get('tvl_usd', 'N/A'):,.0f}

아래 순서대로 분석해줘:

## 1. 현재 시장 상황 & 기술적 분석
- 현재가 {current_price:,}원 기준, 최근 30일 고점/저점 대비 위치 (%)
- RSI {tech['rsi_day']}와 MACD 히스토그램 {tech['macd_hist']} 종합 해석
- 볼린저밴드 내 위치: 상단 {tech['bb_upper']:,} / 중단: {tech['bb_mid']:,} / 하단: {tech['bb_lower']:,}
- 단기(1~4주) / 중기(3~6개월) 가격 시나리오 (구체적 가격 범위 제시)

## 2. 온체인 & 네트워크 심층 지표
아래 항목을 각각 분석 (최신 데이터 기반):
- **TVL**: ${onchain.get('tvl_usd', 'N/A'):,.0f} → 최근 추세 (증가/감소/정체)
- **거래소 유입/유출 (Exchange Inflow/Outflow)**: 고래들이 거래소로 보내는지(매도 압력) vs 빼는지(보유 의지)
- **실현 손익 비율 (SOPR)**: 1 이상이면 수익 실현 구간, 1 미만이면 손절 구간
- **장기보유자(LTH) vs 단기보유자(STH) 비율**: 스마트머니 방향
- **스테이킹 비율**: 총 ETH 대비 스테이킹 비율과 수익률 변화
- **가스피(Gas Fee)**: 네트워크 수요와 ETH 소각률에 미치는 영향
- **종합**: 온체인 지표가 강세/약세 어느 쪽을 더 지지하는지 결론

## 3. 펀더멘털 & 로드맵
- Dencun 이후 Pectra(Prague+Electra) 업그레이드 진행 현황과 예상 일정
- EIP-4844 blob 이후 L2 수수료 변화가 ETH 가치 축적에 미친 실제 영향
- 업그레이드가 ETH 가격과 네트워크 수요에 미칠 영향 (낙관/중립/비관 각 확률)

## 4. 경쟁 구도 (구체적 체인별 비교)
아래 체인과 ETH를 DeFi TVL, 일일 트랜잭션, 개발자 활동 기준으로 비교:
- **L1**: Solana, BNB Chain, Aptos, Sui
- **L2 (ETH 생태계)**: Arbitrum, Base, Optimism, zkSync
- 분야별 ETH 경쟁력: DeFi / NFT / RWA(실물자산 토큰화) / AI 에이전트
- ETH의 구조적 약점과 경쟁 우위 각 2가지

## 5. 가격 시나리오 (기준: 현재가 {current_price:,}원)
현재가 기준으로 6개월 / 12개월 후 예상 가격:
| 시나리오 | 6개월 후 | 12개월 후 | 핵심 변수 |
|---------|---------|---------|---------|
| 낙관 | ?원 | ?원 | ETF 대규모 유입, 금리인하 |
| 중립 | ?원 | ?원 | 현상 유지 |
| 비관 | ?원 | ?원 | 규제 강화, 매크로 악화 |
각 시나리오의 확률도 제시 (예: 낙관 25%, 중립 50%, 비관 25%)

## 6. 매수/홀드/매도 최종 판단
- **종합 신호**: 매수 / 홀드 / 매도 중 하나
- **신호 근거 3가지** (수치 기반으로 제시)
- **반대 의견 2가지** (반드시 포함, 구체적 수치로)
- **구체적 액션 플랜**:
  - 현재 원화 {balances.get('krw', 0):,.0f}원 중 얼마를 투입할지
  - 진입 가격대, 손절가, 익절가 구체적으로 제시
  - 분할 매수라면 몇 회, 각 금액과 가격 조건

분석은 한국어로, 전문적이지만 명확하게 작성해줘.
"""

def analyze_with_gemini(prompt):
    model = genai.GenerativeModel('gemini-3.1-pro-preview')
    response = model.generate_content(prompt)
    return response.text

def verify_with_openrouter(gemini_analysis, tech, fg):
    load_dotenv(_BASE / 'config' / '.env', override=True)
    api_key = os.getenv('OPENROUTER_API_KEY')

    response = _requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-haiku-4.5",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": f"""아래는 Gemini AI의 ETH 시장 분석입니다.
당신은 독립적인 2차 검증자로서 핵심만 요약해주세요.

Gemini 분석:
{gemini_analysis}

현재 데이터:
- ETH가: {tech['price']:,}원
- RSI: {tech['rsi_day']} (일봉)
- 공포탐욕지수: {fg['value']} ({fg['label']})

검증 결과를 아래 형식으로 출력:
✅ 동의하는 핵심 포인트 (2개)
⚠️ 주의할 점 또는 보완 의견 (1개)
🎯 최종 액션 권고: [매수/홀드/매도] - 이유 한 줄"""
            }]
        },
        timeout=60
    )
    data = response.json()
    return data['choices'][0]['message']['content']

def run_full_analysis(balances):
    from scoring_engine import calculate_final_score, format_score_report
    from risk_manager import calc_position

    print("데이터 수집 중...")
    tech = get_technical_data()
    fg = get_fear_greed()
    onchain = get_onchain()
    funding_rate = get_funding_rate()

    # 수치 기반 스코어링
    print("스코어링 계산 중...")
    pos = calc_position(
        balances.get('krw', 0), balances.get('eth', 0),
        balances.get('avg_buy_price', 0), tech['price']
    )
    score_result = calculate_final_score(tech, fg, funding_rate, pos['pnl_pct'])
    score_report = format_score_report(score_result)

    print("Gemini 1차 분석 중...")
    prompt = build_prompt(tech, fg, onchain, funding_rate, balances)
    gemini_result = analyze_with_gemini(prompt)

    print("OpenRouter 2차 검증 중...")
    verify_result = verify_with_openrouter(gemini_result, tech, fg)

    # 분석 결과 저장
    _save_signal(score_result, tech, fg, pos)

    return {
        "tech": tech,
        "fg": fg,
        "score": score_result,
        "score_report": score_report,
        "gemini": gemini_result,
        "claude": verify_result,
    }

def _save_signal(score_result, tech, fg, pos):
    """AI 신호 저장"""
    import json
    from datetime import datetime
    data_dir = _BASE / 'data'
    data_dir.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "price": tech['price'],
        "final_score": score_result['final_score'],
        "action": score_result['action'],
        "scores": score_result['scores'],
        "fg_value": fg['value'],
        "pnl_pct": pos['pnl_pct'],
    }
    with open(data_dir / "signals.jsonl", 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
