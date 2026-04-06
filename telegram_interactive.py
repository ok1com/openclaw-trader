"""
Telegram Interactive Bot - AI 대화 + 명령어 시스템
텔레그램에서 메시지를 보내면 AI가 응답하고, 명령어로 매매를 관리
"""
import requests
import json
import time
import threading
from datetime import datetime
import google.generativeai as genai
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    SAFETY,
    WATCHLIST,
    load_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
)
from telegram_bot import TelegramBot
from risk_manager import RiskManager
from market_monitor import get_stock_data, scan_all_stocks, filter_signals


# Gemini 초기화
genai.configure(api_key=GEMINI_API_KEY)

# 종목 별명 매핑 (한글, 영문, 약칭 등)
STOCK_ALIASES = {
    "네이버": "035420",
    "naver": "035420",
    "카카오": "035720",
    "kakao": "035720",
    "삼전": "005930",
    "삼성전자": "005930",
    "하이닉스": "000660",
    "sk하이닉스": "000660",
    "현차": "005380",
    "현대차": "005380",
    "현대자동차": "005380",
    "셀트리온": "068270",
    "포퓨": "003670",
    "포스코퓨처엠": "003670",
    "삼성sdi": "006400",
    "lg화학": "051910",
    "엘지화학": "051910",
}


def find_stock(query):
    """
    종목명/코드/별명으로 종목코드 찾기

    Returns:
        (stock_code, stock_name) or (None, None)
    """
    query = query.strip()
    wl = load_watchlist()

    # 1. 종목코드 직접 입력
    if query.isdigit() and len(query) == 6:
        name = wl.get(query, query)
        return query, name

    # 2. 관심종목에서 정확히 매칭 (대소문자 무시)
    query_lower = query.lower()
    for code, name in wl.items():
        if query_lower == name.lower() or query_lower == code:
            return code, name

    # 3. 관심종목에서 부분 매칭
    for code, name in wl.items():
        if query_lower in name.lower() or name.lower() in query_lower:
            return code, name

    # 4. 별명 매핑
    if query_lower in STOCK_ALIASES:
        code = STOCK_ALIASES[query_lower]
        name = wl.get(code, code)
        return code, name

    return None, None


class InteractiveBot:
    """대화형 텔레그램 봇"""

    def __init__(self):
        self.bot = TelegramBot()
        self.risk_manager = RiskManager()
        self.running = False
        self.last_update_id = 0
        self.chat_history = []  # Gemini 대화 기록

        # 명령어 목록
        self.commands = {
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/scan": self._cmd_scan,
            "/status": self._cmd_status,
            "/portfolio": self._cmd_portfolio,
            "/price": self._cmd_price,
            "/watchlist": self._cmd_watchlist,
            "/add": self._cmd_add,
            "/remove": self._cmd_remove,
            "/analyze": self._cmd_analyze,
            "/safety": self._cmd_safety,
            "/stop": self._cmd_stop,
        }

    def start(self):
        """봇 시작 - 메시지 수신 루프"""
        self.running = True
        print("🤖 Interactive Bot 시작!")
        print("   텔레그램에서 메시지를 보내보세요.")
        print("   종료: Ctrl+C\n")

        # 시작 메시지
        self.bot.send_message(
            "🤖 <b>OpenClaw Trader 봇 활성화!</b>\n\n"
            "명령어 목록: /help\n"
            "자유롭게 주식 관련 질문도 가능합니다."
        )

        # 기존 미읽은 메시지 건너뛰기
        self._skip_old_updates()

        while self.running:
            try:
                self._poll_updates()
            except KeyboardInterrupt:
                print("\n봇 종료...")
                self.bot.send_message("🔌 봇이 종료되었습니다.")
                break
            except Exception as e:
                print(f"폴링 오류: {e}")
                time.sleep(5)

    def _skip_old_updates(self):
        """기존 미처리 메시지 건너뛰기"""
        try:
            url = f"{self.bot.base_url}/getUpdates"
            params = {"offset": -1, "timeout": 1}
            response = requests.get(url, params=params, timeout=5)
            updates = response.json().get("result", [])
            if updates:
                self.last_update_id = updates[-1]["update_id"]
        except Exception:
            pass

    def _poll_updates(self):
        """새 메시지 폴링"""
        url = f"{self.bot.base_url}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 30,  # long polling
        }

        response = requests.get(url, params=params, timeout=35)
        updates = response.json().get("result", [])

        for update in updates:
            self.last_update_id = update["update_id"]
            self._handle_update(update)

    def _handle_update(self, update):
        """메시지 처리"""
        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        user_name = message.get("from", {}).get("first_name", "사용자")

        # 본인 채팅만 처리
        if chat_id != str(self.bot.chat_id):
            return

        if not text:
            return

        print(f"📨 [{user_name}]: {text}")

        # 명령어 처리
        cmd = text.split()[0].lower()
        if cmd in self.commands:
            self.commands[cmd](text)
        else:
            # 일반 대화 → AI 응답
            self._ai_chat(text)

    # ===== 명령어 핸들러 =====

    def _cmd_start(self, text):
        msg = (
            "🤖 <b>OpenClaw Trader에 오신 것을 환영합니다!</b>\n\n"
            "이 봇은 AI 기반 한국 주식 자동매매 시스템입니다.\n\n"
            "📌 <b>주요 기능:</b>\n"
            "• 주식 관련 질문에 AI가 답변\n"
            "• 관심종목 실시간 스캔\n"
            "• AI 매매 신호 분석\n"
            "• 포트폴리오 관리\n\n"
            "명령어 목록: /help"
        )
        self.bot.send_message(msg)

    def _cmd_help(self, text):
        msg = (
            "📋 <b>명령어 목록</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "💬 <b>대화</b>\n"
            "  아무 메시지 → AI가 주식 관련 답변\n\n"
            "📊 <b>시장 분석</b>\n"
            "  /scan → 관심종목 전체 스캔\n"
            "  /price 삼성전자 → 개별 종목 시세\n"
            "  /analyze 005930 → AI 종목 분석\n\n"
            "📋 <b>관심종목 관리</b>\n"
            "  /watchlist → 관심종목 목록\n"
            "  /add 005930 삼성전자 → 종목 추가\n"
            "  /remove 005930 → 종목 삭제\n\n"
            "💰 <b>포트폴리오</b>\n"
            "  /status → 현재 상태 요약\n"
            "  /portfolio → 보유 종목 상세\n"
            "  /safety → 안전장치 설정 확인\n\n"
            "⚙️ <b>시스템</b>\n"
            "  /stop → 봇 종료"
        )
        self.bot.send_message(msg)

    def _cmd_scan(self, text):
        self.bot.send_message("📡 관심종목 스캔 중... 잠시 기다려주세요.")

        try:
            all_data, signals = scan_all_stocks()
            self.bot.send_scan_result(signals)

            if not signals:
                self.bot.send_message("😴 특별한 매매 신호가 없습니다.")
        except Exception as e:
            self.bot.send_message(f"❌ 스캔 오류: {str(e)}")

    def _cmd_status(self, text):
        msg = self.risk_manager.get_status_message()
        self.bot.send_message(msg)

    def _cmd_portfolio(self, text):
        summary = self.risk_manager.get_portfolio_summary()

        if not summary["holdings"]:
            self.bot.send_message("📋 현재 보유 종목이 없습니다.")
            return

        msg = "📋 <b>보유 종목 상세</b>\n━━━━━━━━━━━━━━━━━━\n"
        for h in summary["holdings"]:
            msg += (
                f"\n<b>{h['name']}</b> ({h['code']})\n"
                f"  수량: {h['qty']}주\n"
                f"  평균가: {h['avg_price']:,}원\n"
                f"  평가금: {h['total_value']:,}원\n"
            )

        msg += f"\n\n누적 손익: {summary['total_pnl']:,}원"
        self.bot.send_message(msg)

    def _cmd_price(self, text):
        """개별 종목 시세 조회: /price 삼성전자 또는 /price 005930"""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            self.bot.send_message("사용법: /price 삼성전자 또는 /price 005930")
            return

        query = parts[1].strip()
        stock_code, stock_name = find_stock(query)

        if not stock_code:
            self.bot.send_message(
                f"❌ '{query}'를 찾을 수 없습니다.\n"
                f"종목코드 6자리로 시도해보세요.\n"
                f"예: /price 035420"
            )
            return

        self.bot.send_message(f"📊 {stock_name} 시세 조회 중...")

        try:
            data = get_stock_data(stock_code)

            if "error" in data:
                self.bot.send_message(f"❌ {data['error']}")
                return

            change_emoji = "🔴" if data["change_pct"] < 0 else "🔵" if data["change_pct"] > 0 else "⚪"

            msg = (
                f"📊 <b>{data['name']}</b> ({data['code']})\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"현재가: {data['current_price']:,}원 {change_emoji} {data['change_pct']:+.2f}%\n"
                f"\n<b>기술적 지표</b>\n"
                f"  RSI(14): {data.get('rsi', 'N/A')}\n"
                f"  MACD 크로스: {data.get('macd_cross', 'none')}\n"
                f"  볼린저: {data.get('bb_position', 'N/A')}\n"
                f"  거래량: 평균 대비 {data.get('volume_ratio', 'N/A')}배\n"
                f"\n<b>이동평균</b>\n"
                f"  MA5: {data.get('ma5', 'N/A'):,}원\n"
                f"  MA20: {data.get('ma20', 'N/A'):,}원\n"
            )
            if data.get("ma60"):
                msg += f"  MA60: {data['ma60']:,}원\n"

            self.bot.send_message(msg)

        except Exception as e:
            self.bot.send_message(f"❌ 조회 오류: {str(e)}")

    def _cmd_watchlist(self, text):
        wl = load_watchlist()
        msg = "📋 <b>관심종목 목록</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, (code, name) in enumerate(wl.items(), 1):
            msg += f"  {i}. {name} ({code})\n"
        msg += f"\n총 {len(wl)}개 종목"
        msg += "\n\n추가: /add 종목코드 종목명"
        msg += "\n삭제: /remove 종목코드"
        self.bot.send_message(msg)

    def _cmd_add(self, text):
        """관심종목 추가: /add 005930 삼성전자"""
        parts = text.split(maxsplit=2)

        if len(parts) < 3:
            self.bot.send_message(
                "사용법: /add 종목코드 종목명\n"
                "예시: /add 005930 삼성전자\n"
                "예시: /add 028260 삼성물산"
            )
            return

        code = parts[1].strip()
        name = parts[2].strip()

        # 종목코드 검증
        if not code.isdigit() or len(code) != 6:
            self.bot.send_message("❌ 종목코드는 6자리 숫자여야 합니다.\n예: 005930")
            return

        # Yahoo Finance에서 존재하는 종목인지 확인
        self.bot.send_message(f"🔍 {name}({code}) 확인 중...")
        try:
            data = get_stock_data(code)
            if "error" in data:
                self.bot.send_message(
                    f"⚠️ {name}({code}) 데이터를 가져올 수 없습니다.\n"
                    f"종목코드를 다시 확인해주세요.\n"
                    f"(오류: {data['error']})"
                )
                return
        except Exception:
            pass  # 확인 실패해도 추가는 허용

        success, message = add_to_watchlist(code, name)
        self.bot.send_message(message)

        if success:
            wl = load_watchlist()
            self.bot.send_message(f"📋 현재 관심종목: {len(wl)}개")

    def _cmd_remove(self, text):
        """관심종목 삭제: /remove 005930 또는 /remove 삼성전자"""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            self.bot.send_message(
                "사용법: /remove 종목코드 또는 /remove 종목명\n"
                "예시: /remove 005930\n"
                "예시: /remove 삼성전자"
            )
            return

        query = parts[1].strip()

        # 종목코드 또는 종목명으로 찾기
        wl = load_watchlist()
        code = None

        if query.isdigit() and len(query) == 6:
            code = query
        else:
            # 종목명으로 검색
            for c, n in wl.items():
                if n == query:
                    code = c
                    break

        if not code:
            self.bot.send_message(f"❌ '{query}'를 관심종목에서 찾을 수 없습니다.\n/watchlist 로 확인해보세요.")
            return

        success, message = remove_from_watchlist(code)
        self.bot.send_message(message)

        if success:
            wl = load_watchlist()
            self.bot.send_message(f"📋 현재 관심종목: {len(wl)}개")

    def _cmd_analyze(self, text):
        """AI 종목 분석: /analyze 네이버"""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            self.bot.send_message("사용법: /analyze 삼성전자 또는 /analyze 005930")
            return

        query = parts[1].strip()
        stock_code, stock_name = find_stock(query)

        if not stock_code:
            self.bot.send_message(
                f"❌ '{query}'를 찾을 수 없습니다.\n"
                f"종목코드 6자리로 시도해보세요.\n"
                f"예: /analyze 035420"
            )
            return

        self.bot.send_message(f"🤖 {stock_name} AI 분석 중... (30초~1분 소요)")

        try:
            # 1. 데이터 수집 (코드)
            data = get_stock_data(stock_code)
            if "error" in data:
                self.bot.send_message(f"❌ {data['error']}")
                return

            # 2. Gemini에게 자연어로 분석 요청 (JSON 파싱 없음)
            prompt = f"""당신은 한국 주식시장 전문 트레이더입니다.
아래 종목의 기술적 지표를 분석하고 매매 판단을 해주세요.

📊 종목: {stock_name} ({stock_code})
💰 현재가: {data['current_price']:,}원 ({data['change_pct']:+.2f}%)
📈 거래량: 20일 평균 대비 {data.get('volume_ratio', 'N/A')}배

기술적 지표:
- RSI(14): {data.get('rsi', 'N/A')}
- MACD: {data.get('macd', 'N/A')} / Signal: {data.get('macd_signal', 'N/A')}
- MACD 크로스: {data.get('macd_cross', 'none')}
- 볼린저밴드: {data.get('bb_position', 'N/A')}
- MA5: {data.get('ma5', 'N/A')} / MA20: {data.get('ma20', 'N/A')} / MA60: {data.get('ma60', 'N/A')}

아래 형식으로 답변해주세요 (텔레그램 메시지용, 간결하게):
1. 매매 판단: 매수 / 매도 / 관망 중 하나
2. 확신도: 0~100
3. 판단 근거 (2~3줄)
4. 목표가와 손절가
5. 주의사항"""

            model = genai.GenerativeModel(
                GEMINI_MODEL,
                system_instruction="한국 주식시장 전문 트레이더로서 간결하고 정확하게 답변하세요. 텔레그램 메시지에 맞게 짧게 작성하세요.",
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=800,
                ),
            )

            reply = response.text.strip()

            # 텔레그램 메시지 길이 제한
            if len(reply) > 3800:
                reply = reply[:3800] + "\n\n... (잘림)"

            msg = (
                f"🤖 <b>AI 분석: {stock_name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"현재가: {data['current_price']:,}원 ({data['change_pct']:+.2f}%)\n"
                f"RSI: {data.get('rsi', 'N/A')} | MACD: {data.get('macd_cross', 'none')}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{reply}"
            )

            self.bot.send_message(msg, parse_mode=None)

        except Exception as e:
            self.bot.send_message(f"❌ 분석 오류: {str(e)}")

    def _cmd_safety(self, text):
        msg = (
            "🛡️ <b>안전장치 설정</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"1회 매매 한도: {SAFETY['max_per_trade']:,}원\n"
            f"일일 손실 한도: {SAFETY['daily_loss_limit']:,}원\n"
            f"최대 보유 종목: {SAFETY['max_holdings']}개\n"
            f"매매 전 확인: {'필요' if SAFETY['require_confirmation'] else '자동'}\n"
        )
        self.bot.send_message(msg)

    def _cmd_stop(self, text):
        self.bot.send_message("🔌 봇을 종료합니다...")
        self.running = False

    # ===== AI 대화 =====

    def _ai_chat(self, user_message):
        """Gemini를 이용한 자유 대화"""
        self.bot.send_message("💭 생각하는 중...")

        try:
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                system_instruction=(
                    "당신은 한국 주식시장 전문 AI 어시스턴트 'OpenClaw Trader'입니다.\n"
                    "사용자의 주식 관련 질문에 친절하고 전문적으로 답변합니다.\n"
                    "답변은 간결하게 텔레그램 메시지에 적합한 길이로 해주세요.\n"
                    "한국어로 답변하세요.\n"
                    f"현재 관심종목: {', '.join(WATCHLIST.values())}\n"
                    f"오늘 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}"
                ),
            )

            # 대화 기록 유지 (최근 10개)
            self.chat_history.append({"role": "user", "parts": [user_message]})
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

            chat = model.start_chat(history=self.chat_history[:-1])
            response = chat.send_message(user_message)

            reply = response.text.strip()

            # 대화 기록에 AI 응답 추가
            self.chat_history.append({"role": "model", "parts": [reply]})

            # 텔레그램 메시지 길이 제한 (4096자)
            if len(reply) > 4000:
                reply = reply[:4000] + "\n\n... (메시지가 잘렸습니다)"

            self.bot.send_message(reply, parse_mode=None)
            print(f"🤖 [AI]: {reply[:100]}...")

        except Exception as e:
            self.bot.send_message(f"❌ AI 응답 오류: {str(e)}")
            print(f"AI 오류: {e}")


if __name__ == "__main__":
    bot = InteractiveBot()
    bot.start()
