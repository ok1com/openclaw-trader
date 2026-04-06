"""
Scheduler - 자동 분석 + 손절/익절 모니터링
"""
import threading
import time
import json
from datetime import datetime
import pathlib

_BASE = pathlib.Path(__file__).parent

from market_monitor import get_current_price, get_technical_data
from data_fetcher import get_fear_greed, get_funding_rate
from order_executor import get_balance_krw, get_balance_eth, get_avg_buy_price
from risk_manager import calc_position, check_stop_loss, check_take_profit, load_state, save_state
from scoring_engine import calculate_final_score, format_score_report


class TradingScheduler:
    def __init__(self, telegram_send_fn=None):
        self.running = False
        self.telegram_send = telegram_send_fn
        self.monitor_interval = 60      # 1분마다 가격 체크
        self.analysis_times = ["09:00", "13:00", "21:00"]  # 분석 시간
        self.last_analysis_date = {}
        self.last_alert = {}

    def start(self):
        """스케줄러 시작"""
        self.running = True
        # 모니터링 스레드
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        # 스케줄 스레드
        self.schedule_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.schedule_thread.start()
        print(f"[Scheduler] 시작됨 - 모니터링 {self.monitor_interval}초 / 분석 {self.analysis_times}")

    def stop(self):
        self.running = False
        print("[Scheduler] 중지됨")

    def _monitor_loop(self):
        """1분마다 가격 + 손절/익절 체크"""
        while self.running:
            try:
                self._check_position()
            except Exception as e:
                print(f"[Monitor] 오류: {e}")
            time.sleep(self.monitor_interval)

    def _schedule_loop(self):
        """정해진 시간에 자동 분석"""
        while self.running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            for t in self.analysis_times:
                key = f"{today}_{t}"
                if current_time == t and key not in self.last_analysis_date:
                    self.last_analysis_date[key] = True
                    try:
                        self._run_scheduled_analysis()
                    except Exception as e:
                        print(f"[Schedule] 분석 오류: {e}")

            time.sleep(30)  # 30초마다 체크

    def _check_position(self):
        """포지션 모니터링"""
        price = get_current_price()
        if not price:
            return

        krw = get_balance_krw()
        eth = get_balance_eth()
        avg = get_avg_buy_price()

        if not eth or eth < 0.0001:
            return

        pos = calc_position(krw, eth, avg, price)

        # 손절 체크
        sl = check_stop_loss(pos)
        if sl['type'] in ('STOP_LOSS', 'STOP_WARNING'):
            alert_key = f"sl_{datetime.now().strftime('%Y%m%d_%H')}"
            if alert_key not in self.last_alert:
                self.last_alert[alert_key] = True
                self._send_alert(sl['message'])
                if sl['triggered']:
                    self._send_alert("💡 /sell all 로 전량 매도를 고려하세요.")

        # 익절 체크
        tp = check_take_profit(pos)
        if tp['type'] in ('TAKE_PROFIT', 'PROFIT_NEAR'):
            alert_key = f"tp_{datetime.now().strftime('%Y%m%d_%H')}"
            if alert_key not in self.last_alert:
                self.last_alert[alert_key] = True
                self._send_alert(tp['message'])
                if tp['triggered']:
                    self._send_alert("💡 /sell 50 으로 절반 익절을 고려하세요.")

    def _run_scheduled_analysis(self):
        """스케줄 분석 실행"""
        print(f"[Schedule] 자동 분석 시작 {datetime.now()}")

        tech = get_technical_data()
        fg = get_fear_greed()
        funding_rate = get_funding_rate()

        krw = get_balance_krw()
        eth = get_balance_eth()
        avg = get_avg_buy_price()
        price = tech['price']

        pos = calc_position(krw, eth, avg, price)
        score_result = calculate_final_score(tech, fg, funding_rate, pos['pnl_pct'])

        # 리포트 생성
        report = format_score_report(score_result)
        msg = (
            f"⏰ 정기 분석 ({datetime.now().strftime('%H:%M')})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ETH: {price:,.0f}원 ({pos['pnl_pct']:+.2f}%)\n"
            f"자산: {pos['total_asset']:,.0f}원\n\n"
            f"{report}"
        )
        self._send_alert(msg)

        # 분석 결과 저장
        self._save_analysis(score_result, tech, fg, pos)

    def _save_analysis(self, score_result, tech, fg, pos):
        """분석 결과 저장"""
        data_dir = _BASE / 'data'
        data_dir.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "price": tech['price'],
            "final_score": score_result['final_score'],
            "action": score_result['action'],
            "scores": score_result['scores'],
            "pnl_pct": pos['pnl_pct'],
            "total_asset": pos['total_asset'],
            "fg_value": fg['value'],
        }
        log_file = data_dir / "analysis_history.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _send_alert(self, message):
        """텔레그램 알림 전송"""
        print(f"[Alert] {message}")
        if self.telegram_send:
            try:
                self.telegram_send(message)
            except Exception as e:
                print(f"[Alert] 전송 실패: {e}")
