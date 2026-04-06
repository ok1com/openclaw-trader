"""
Scoring Engine v2.1 - 수치 기반 매매 판단 시스템
각 지표에 가중치를 적용하여 최종 점수(-100 ~ +100) 산출

v2.1 변경점 (vs v2.0):
  - FG 극단적 하단(0~8) 점수 강화: +95 → +100
  - MACD 가중치 15% → 20% (추세 전환 감지 강화)
  - MA 가중치 15% → 17% (장기 추세 비중 상향)
  - FG 가중치 20% → 15% (심리 단독으로 기술적 약세 상쇄 방지)
  - 볼린저 가중치 10% → 8% (보조지표 성격)
  - 홀드 구간 확대: -4~+4 → -7~+7 (잦은 신호 변경 방지)

판단 구간:
  +30 이상  → 강력 매수 🟢🟢
  +15 ~ +29 → 매수 🟢
  +8  ~ +14 → 약매수 🟢
  -7  ~ +7  → 홀드 🟡
  -14 ~ -8  → 약매도 🔴
  -29 ~ -15 → 매도 🔴
  -30 이하  → 강력 매도 🔴🔴

각 지표 원점수는 -100 ~ +100 (양수=매수, 음수=매도)
"""


def score_rsi(rsi_day, rsi_4h):
    """
    RSI 점수 (-100 ~ +100). 연속 구간으로 보간.
    ──────────────────────────────────
    RSI ≤ 20  → +100 (극단적 과매도, 반등 임박)
    RSI  25   → +80
    RSI  30   → +50  (과매도 진입)
    RSI  40   → +15
    RSI  45~55→   0  (중립)
    RSI  60   → -15
    RSI  70   → -50  (과매수 진입)
    RSI  75   → -80
    RSI ≥ 80  → -100 (극단적 과매수)
    ──────────────────────────────────
    """
    def _score(rsi):
        # 선형 보간 테이블 (RSI, score)
        table = [
            (20, 100), (25, 80), (30, 50), (35, 25), (40, 10),
            (45, 0), (50, 0), (55, 0),
            (60, -10), (65, -25), (70, -50), (75, -80), (80, -100),
        ]
        if rsi <= table[0][0]:
            return table[0][1]
        if rsi >= table[-1][0]:
            return table[-1][1]
        for i in range(len(table) - 1):
            r0, s0 = table[i]
            r1, s1 = table[i + 1]
            if r0 <= rsi <= r1:
                t = (rsi - r0) / (r1 - r0)
                return round(s0 + t * (s1 - s0))
        return 0

    # 일봉 60%, 4시간 40%
    return round(_score(rsi_day) * 0.6 + _score(rsi_4h) * 0.4)


def score_macd(macd, signal, hist):
    """
    MACD 점수 (-100 ~ +100)
    ──────────────────────────────────
    hist > 0 & MACD > Signal & 강모멘텀 → +100 (강세)
    hist > 0 & MACD > Signal             → +70
    hist > 0 & MACD < Signal             → +20  (약세 전환 중)
    hist < 0 & MACD < Signal & 강모멘텀 → -100 (약세)
    hist < 0 & MACD < Signal             → -70
    hist < 0 & MACD > Signal             → -20  (강세 전환 중)
    ──────────────────────────────────
    """
    score = 0
    # 히스토그램 방향 (±40)
    score += 40 if hist > 0 else -40
    # MACD vs Signal (±30)
    score += 30 if macd > signal else -30
    # 모멘텀 강도 (±30) - 히스토그램 크기가 시그널의 50% 이상이면 강한 추세
    if abs(hist) > abs(signal) * 0.5:
        score += 30 if hist > 0 else -30
    return max(-100, min(100, score))


def score_ma(price, ma50, ma200, golden_cross):
    """
    이동평균 점수 (-100 ~ +100)
    ──────────────────────────────────
    골든크로스 + 가격>MA50 + 가격>MA200        → +80 ~ +100
    골든크로스 + 가격<MA50                      → +20 (조정 중)
    데드크로스 + 가격<MA50 + 가격<MA200         → -80 ~ -100
    데드크로스 + 가격>MA50                      → -20 (반등 시도)
    괴리율 >15% → 과열 보정 -20
    괴리율 <-15% → 저평가 보정 +20
    ──────────────────────────────────
    """
    score = 0
    score += 40 if golden_cross else -40
    score += 20 if price > ma50 else -20
    score += 20 if price > ma200 else -20
    # 괴리율 보정 (±20, 기준 완화: 15%)
    gap_pct = (price - ma50) / ma50 * 100 if ma50 else 0
    if gap_pct > 15:
        score -= 20
    elif gap_pct < -15:
        score += 20
    return max(-100, min(100, score))


def score_bollinger(price, bb_upper, bb_mid, bb_lower):
    """
    볼린저밴드 점수 (-100 ~ +100)
    ──────────────────────────────────
    밴드 내 위치 = (가격 - 하단) / (상단 - 하단)
    위치 ≥ 1.0 → -80 (상단 돌파, 과매수)
    위치  0.85 → -50
    위치  0.5  →   0 (중앙)
    위치  0.15 → +50
    위치 ≤ 0.0 → +80 (하단 이탈, 과매도)
    ──────────────────────────────────
    """
    if bb_upper == bb_lower:
        return 0
    position = (price - bb_lower) / (bb_upper - bb_lower)
    if position >= 1.0:
        return -80
    elif position >= 0.85:
        return round(-50 - (position - 0.85) / 0.15 * 30)
    elif position <= 0.0:
        return 80
    elif position <= 0.15:
        return round(50 + (0.15 - position) / 0.15 * 30)
    else:
        # 0.15 ~ 0.85 → 선형 보간 (+50 ~ -50)
        return round(50 - (position - 0.15) / 0.70 * 100)


def score_fear_greed(value):
    """
    공포탐욕지수 점수 (-100 ~ +100). 역발상 투자 기반 선형 보간.
    ──────────────────────────────────
    FG  0 → +100 (시장 패닉 = 최고 매수 기회)
    FG 10 → +90
    FG 15 → +75  ← 현재 12이면 여기 근처
    FG 25 → +50
    FG 40 → +15
    FG 50 →   0  (중립)
    FG 60 → -15
    FG 75 → -50
    FG 85 → -75
    FG 90 → -90
    FG100 → -100 (극단적 탐욕 = 최고 매도 기회)
    ──────────────────────────────────
    """
    # 선형 보간 테이블 (FG값, score)
    # v2.1: 0~8 구간 강화 (극단적 패닉에서 더 강한 매수 신호)
    table = [
        (0, 100), (5, 98), (8, 95), (10, 90), (15, 75),
        (20, 60), (25, 50), (30, 35), (35, 20), (40, 10),
        (45, 5), (50, 0), (55, -5), (60, -15), (65, -30),
        (70, -40), (75, -55), (80, -70), (85, -80), (90, -90),
        (100, -100),
    ]
    if value <= table[0][0]:
        return table[0][1]
    if value >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        v0, s0 = table[i]
        v1, s1 = table[i + 1]
        if v0 <= value <= v1:
            t = (value - v0) / (v1 - v0)
            return round(s0 + t * (s1 - s0))
    return 0


def score_funding_rate(rate):
    """
    펀딩비 점수 (-100 ~ +100)
    ──────────────────────────────────
    rate ≤ -0.01  → +80 (과도한 숏 = 쇼트스퀴즈 기대)
    rate  -0.005  → +40
    rate   0.0    → +5  (약간의 숏 = 건전)
    rate  +0.0001 → -5  (미미한 롱, 거의 중립)
    rate  +0.005  → -40
    rate ≥ +0.01  → -80 (과도한 롱 = 하락 경고)
    ──────────────────────────────────
    """
    if rate is None:
        return 0
    # 선형 보간
    table = [
        (-0.02, 100), (-0.01, 80), (-0.005, 40), (-0.001, 15),
        (0.0, 5), (0.0001, -5), (0.001, -15),
        (0.005, -40), (0.01, -80), (0.02, -100),
    ]
    if rate <= table[0][0]:
        return table[0][1]
    if rate >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        r0, s0 = table[i]
        r1, s1 = table[i + 1]
        if r0 <= rate <= r1:
            t = (rate - r0) / (r1 - r0)
            return round(s0 + t * (s1 - s0))
    return 0


def score_pnl_position(pnl_pct, stop_loss=-7, take_profit=15):
    """
    현재 손익 기반 점수 (-100 ~ +100)
    ──────────────────────────────────
    PnL ≤ -7%    → -100 (손절 도달, 즉시 매도)
    PnL   -5%    → -70  (손절 근접, 강한 주의)
    PnL   -3%    → -30  (손실 확대 중)
    PnL    0%    → +10  (본전 근처, 약간 추가매수 고려)
    PnL   +3%    → +15  (수익 초기, 홀드)
    PnL   +7%    → +5   (수익 확대, 중립적 홀드)
    PnL  +10.5%  → -30  (익절 근접, 부분 매도 고려)
    PnL  +15%    → -80  (익절 도달, 매도)
    PnL  +20%    → -100 (과익절, 즉시 매도)
    ──────────────────────────────────
    """
    table = [
        (-10, -100), (-7, -100), (-5, -70), (-3, -30), (-1, 0),
        (0, 10), (3, 15), (5, 10), (7, 5), (10, -10),
        (12, -30), (15, -80), (20, -100),
    ]
    if pnl_pct <= table[0][0]:
        return table[0][1]
    if pnl_pct >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        p0, s0 = table[i]
        p1, s1 = table[i + 1]
        if p0 <= pnl_pct <= p1:
            t = (pnl_pct - p0) / (p1 - p0)
            return round(s0 + t * (s1 - s0))
    return 0


# ===== 가중치 설정 v2.1 (합계 = 100%) =====
# 설계 원칙: 기술적 지표(RSI+MACD+MA) 합산 > 심리지표(FG) 단독
# → 기술적으로 명확한 약세/강세 시 심리 하나로 뒤집히지 않음
WEIGHTS = {
    "rsi": 0.20,           # RSI: 과매수/과매도 판단의 핵심 (유지)
    "macd": 0.20,          # MACD: 추세 전환 감지 (15→20%, 핵심 추세지표)
    "ma": 0.17,            # 이동평균: 장기 추세 방향 (15→17%)
    "bollinger": 0.08,     # 볼린저: 변동성 내 위치 (10→8%, 보조지표)
    "fear_greed": 0.15,    # 공포탐욕: 역발상 투자 (20→15%, 단독 상쇄 방지)
    "funding_rate": 0.10,  # 펀딩비: 레버리지 포지션 편향 (유지)
    "pnl_position": 0.10,  # 현재손익: 리스크 관리 (유지)
}
# 기술적 합산: RSI(20)+MACD(20)+MA(17)+BB(8) = 65%
# 심리/외부:   FG(15)+Funding(10) = 25%
# 리스크:      PnL(10) = 10%
# 합계 검증
assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001, f"가중치 합계 오류: {sum(WEIGHTS.values())}"


def calculate_final_score(tech, fg, funding_rate, pnl_pct):
    """
    최종 종합 점수 계산

    Returns:
        dict: 각 지표 점수, 가중 점수, 최종 점수, 판단
    """
    scores = {}
    weighted = {}

    # 개별 점수 계산
    scores['rsi'] = score_rsi(tech['rsi_day'], tech['rsi_4h'])
    scores['macd'] = score_macd(tech['macd'], tech['macd_signal'], tech['macd_hist'])
    scores['ma'] = score_ma(tech['price'], tech['ma50'], tech['ma200'], tech['golden_cross'])
    scores['bollinger'] = score_bollinger(
        tech['price'], tech['bb_upper'], tech['bb_mid'], tech['bb_lower']
    )
    scores['fear_greed'] = score_fear_greed(fg['value'])
    scores['funding_rate'] = score_funding_rate(funding_rate)
    scores['pnl_position'] = score_pnl_position(pnl_pct)

    # 가중 점수
    for key, raw in scores.items():
        w = WEIGHTS.get(key, 0)
        weighted[key] = round(raw * w, 1)

    final_score = round(sum(weighted.values()), 1)

    # 판단 기준 (7단계, v2.1: 홀드 구간 -7~+7으로 확대)
    if final_score >= 30:
        action = "강력 매수"
        emoji = "🟢🟢"
    elif final_score >= 15:
        action = "매수"
        emoji = "🟢"
    elif final_score >= 8:
        action = "약매수"
        emoji = "🟢"
    elif final_score >= -7:
        action = "홀드"
        emoji = "🟡"
    elif final_score >= -14:
        action = "약매도"
        emoji = "🔴"
    elif final_score >= -29:
        action = "매도"
        emoji = "🔴"
    else:
        action = "강력 매도"
        emoji = "🔴🔴"

    # 근거 정렬 (기여도 순)
    reasons = sorted(weighted.items(), key=lambda x: abs(x[1]), reverse=True)

    return {
        "scores": scores,
        "weighted": weighted,
        "weights": WEIGHTS,
        "final_score": final_score,
        "action": action,
        "emoji": emoji,
        "top_reasons": reasons[:7],
    }


def format_score_report(result):
    """점수 리포트 텍스트 생성"""
    lines = []
    lines.append(f"{result['emoji']} 최종 판단: {result['action']} (점수: {result['final_score']:+.1f})")
    lines.append("━" * 35)
    lines.append("📊 판단 구간: 강매수≥+30 | 매수≥+15 | 약매수≥+8 | 홀드 -7~+7 | 약매도≤-8 | 매도≤-15 | 강매도≤-30")
    lines.append("━" * 35)
    lines.append("지표별 점수 (원점수 × 가중치 = 기여도):")
    lines.append("")

    name_map = {
        'rsi': 'RSI',
        'macd': 'MACD',
        'ma': '이동평균',
        'bollinger': '볼린저밴드',
        'fear_greed': '공포탐욕지수',
        'funding_rate': '펀딩비',
        'pnl_position': '현재손익',
    }

    reason_map = {
        'rsi': '(일봉+4H RSI 종합)',
        'macd': '(히스토그램+크로스+모멘텀)',
        'ma': '(MA50/200+골든크로스+괴리율)',
        'bollinger': '(밴드 내 위치 0~1)',
        'fear_greed': '(역발상: 공포=매수, 탐욕=매도)',
        'funding_rate': '(선물 롱/숏 편향)',
        'pnl_position': '(현재 손익 대비 손절/익절)',
    }

    for key, weighted_val in result['top_reasons']:
        raw = result['scores'][key]
        w = result['weights'].get(key, 0)
        name = name_map.get(key, key)
        reason = reason_map.get(key, '')
        bar_len = int(abs(weighted_val) / 2)
        bar = "█" * bar_len if weighted_val >= 0 else "▓" * bar_len
        sign = "+" if weighted_val >= 0 else ""
        lines.append(f"  {name:8s}: {raw:+4d} × {w*100:.0f}% = {sign}{weighted_val:.1f}  {bar}  {reason}")

    lines.append("")
    lines.append(f"종합: {result['final_score']:+.1f} / ±100")
    return "\n".join(lines)
