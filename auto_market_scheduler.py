# -*- coding: utf-8 -*-
"""
자동 시장 전환 스케줄러

현재 시간 기준으로 활성 시장을 자동 감지하여 실행:
- 한국 장 시간 (09:00-15:30 KST) → 한국 시장만 모니터링
- 미국 장 시간 (09:30-16:00 ET) → 미국 시장만 모니터링
- 둘 다 아닐 경우 → 대기
"""
import logging
import os
import threading
import time
from datetime import datetime, time as dt_time
import pytz
from typing import Optional

from dual_market_scheduler import MarketScheduler
from config import (
    USE_PAPER_TRADING,
    LOG_LEVEL,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT
)
from common.shared_state import get_shared_state


class AutoMarketScheduler:
    """시간대별 자동 시장 전환 스케줄러"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.us_tz = pytz.timezone('US/Eastern')
        self.kr_tz = pytz.timezone('Asia/Seoul')

        # 시장 시간 정의
        self.us_start = dt_time(9, 30)   # 09:30 ET
        self.us_end = dt_time(16, 0)     # 16:00 ET
        self.kr_start = dt_time(9, 0)    # 09:00 KST
        self.kr_end = dt_time(15, 30)    # 15:30 KST

        self.current_scheduler: Optional[MarketScheduler] = None
        self.current_market = None
        self.is_running = False
        self.state = get_shared_state()

    def get_active_market(self) -> Optional[str]:
        """
        현재 활성화된 시장 확인

        Returns:
            'us': 미국 장 시간
            'kr': 한국 장 시간
            None: 둘 다 아님
        """
        now_us = datetime.now(self.us_tz)
        now_kr = datetime.now(self.kr_tz)

        # 주말 제외
        is_us_weekday = now_us.weekday() < 5
        is_kr_weekday = now_kr.weekday() < 5

        # 미국 장 시간 확인
        if is_us_weekday:
            us_time = now_us.time()
            if self.us_start <= us_time <= self.us_end:
                return 'us'

        # 한국 장 시간 확인
        if is_kr_weekday:
            kr_time = now_kr.time()
            if self.kr_start <= kr_time <= self.kr_end:
                return 'kr'

        return None

    def _load_all_symbols(self):
        """KR/US watch_list 심볼 로드"""
        import json, pathlib
        kr_syms, us_syms = [], []
        try:
            kr_path = pathlib.Path(__file__).parent / "kr_stocks_config.json"
            if kr_path.exists():
                data = json.loads(kr_path.read_text(encoding="utf-8"))
                kr_syms = list(data.get("watch_list", [])) + list(data.get("filter_stocks", {}).keys())
        except Exception as e:
            self.logger.warning(f"[TA] KR 종목 로드 실패: {e}")
        try:
            us_path = pathlib.Path(__file__).parent / "stocks_config.json"
            if us_path.exists():
                data = json.loads(us_path.read_text(encoding="utf-8"))
                us_syms = list(data.get("watch_list", [])) + list(data.get("filter_stocks", {}).keys())
        except Exception as e:
            self.logger.warning(f"[TA] US 종목 로드 실패: {e}")
        return list(dict.fromkeys(kr_syms)), list(dict.fromkeys(us_syms))  # 중복 제거

    def _run_ta_preanalysis(self, market: str = "all"):
        """TradingAgents 사전 분석 (백그라운드 스레드로 실행)"""
        try:
            from config import USE_TA_FILTER
        except ImportError:
            USE_TA_FILTER = False
        if not USE_TA_FILTER:
            return

        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.logger.warning("[TA] ANTHROPIC_API_KEY 미설정 → 사전 분석 생략")
            return

        def _worker():
            from common.ta_filter import run_daily_analysis
            kr_syms, us_syms = self._load_all_symbols()
            self.logger.info(f"[TA] 사전 분석 시작 — KR {len(kr_syms)}개, US {len(us_syms)}개")
            run_daily_analysis(
                kr_symbols=kr_syms if market in ("all", "kr") else [],
                us_symbols=us_syms if market in ("all", "us") else [],
            )
            self.logger.info("[TA] 사전 분석 완료 → ta_signals.json 갱신")

        t = threading.Thread(target=_worker, daemon=True, name="ta-preanalysis")
        t.start()

    def _run_eod_scan(self, market: str = "kr"):
        """장 마감 후 검색기 스캔 (백그라운드 스레드).

        확정 종가 기준으로 breakout/역배열 검색기를 돌려
        RESEARCH/eod/eod_{market}_{YYYYMMDD}.md 로 저장한다.
        """
        def _worker():
            try:
                from scripts.eod_scan import run_eod_scan
                self.logger.info(f"[EOD] {market.upper()} 마감 후 검색기 스캔 시작...")
                paths = run_eod_scan(market=market)
                self.logger.info(f"[EOD] {market.upper()} 스캔 완료 → {paths}")
            except Exception as e:
                self.logger.error(f"[EOD] {market.upper()} 스캔 실패: {e}")

        t = threading.Thread(target=_worker, daemon=True, name=f"eod-scan-{market}")
        t.start()

    def switch_market(self, market: str):
        """
        시장 전환

        Args:
            market: 'us' 또는 'kr'
        """
        if self.current_market == market:
            return  # 이미 같은 시장

        # 기존 스케줄러 정리
        if self.current_scheduler:
            self.logger.info(f"[SWITCH] {self.current_market.upper()} 시장 모니터링 종료")
            # 스케줄 클리어는 나중에 추가 가능

        # 새 시장 스케줄러 생성
        self.current_market = market
        self.current_scheduler = MarketScheduler(market)
        self.state.update_market(market)

        market_name = "미국" if market == 'us' else "한국"
        now = datetime.now(self.kr_tz)

        self.logger.info("=" * 60)
        self.logger.info(f"[SWITCH] ✅ {market_name} 시장 모니터링 시작")
        self.logger.info(f"[TIME] 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')} KST")

        if market == 'us':
            now_et = datetime.now(self.us_tz)
            self.logger.info(f"[TIME] 미국 시간: {now_et.strftime('%Y-%m-%d %H:%M:%S')} ET")
            self.logger.info(f"[HOURS] 미국 장: 09:30-16:00 ET")
        else:
            self.logger.info(f"[HOURS] 한국 장: 09:00-15:30 KST")

        self.logger.info("=" * 60)

        # 초기 토큰 체크
        self.current_scheduler.check_and_refresh_token()

    def run_active_market(self):
        """현재 활성 시장의 전략 실행"""
        if not self.current_scheduler:
            return

        if not self.current_scheduler.is_trading_hours():
            self.logger.debug(f"[{self.current_market.upper()}] 운영 시간 외")
            return

        if not self.state.trading_enabled:
            self.logger.info("[GUARD] trading_enabled=False — 전략 실행 스킵")
            return

        # 매도 전략 실행
        self.current_scheduler.execute_sell_strategy()
        self.state.mark_sell()
        time.sleep(2)

        # 매수 전략 실행
        self.current_scheduler.execute_buy_strategy()
        self.state.mark_buy()
        time.sleep(2)

        # 상태 출력
        self.current_scheduler.print_status()

    def start(self):
        """자동 시장 전환 시스템 시작"""
        self.logger.info("=" * 60)
        self.logger.info("=== 자동 시장 전환 시스템 시작 ===")
        self.logger.info("=" * 60)

        # 운영 모드 표시
        if USE_PAPER_TRADING:
            self.logger.warning("[MODE] Paper Trading (모의투자)")
        else:
            self.logger.critical("[MODE] REAL TRADING (실전거래)")
            print("=" * 60)
            print("WARNING: REAL TRADING MODE ACTIVE!")
            print("=" * 60)

        self.is_running = True
        last_check_minute = -1
        last_status_print = time.time()
        _ta_analyzed_today = {"kr": None, "us": None}  # date 문자열로 중복 실행 방지
        _eod_scanned_today = {"kr": None, "us": None}  # 마감 후 검색기 스캔 1일 1회

        # 시작 직후 초기 상태 출력 및 즉시 실행
        initial_market = self.get_active_market()
        if initial_market:
            self.switch_market(initial_market)

            # 시작 직후 즉시 전략 실행
            self.logger.info("[STARTUP] 시작 직후 즉시 매도 전략 실행...")
            if self.state.trading_enabled:
                self.current_scheduler.execute_sell_strategy()
                self.state.mark_sell()
            time.sleep(2)

            self.logger.info("[STARTUP] 시작 직후 즉시 매수 전략 실행...")
            if self.state.trading_enabled:
                self.current_scheduler.execute_buy_strategy()
                self.state.mark_buy()
            time.sleep(2)

            self.current_scheduler.print_status()

            # 다음 주기 안내
            next_sell = 30 - (datetime.now().minute % 30)
            next_buy = 60 - (datetime.now().minute % 60)
            self.logger.info(f"[INFO] 다음 매도 전략: {next_sell}분 후 (매 30분마다)")
            self.logger.info(f"[INFO] 다음 매수 전략: {next_buy}분 후 (매 60분마다)")
            self.logger.info(f"[INFO] 시스템 정상 작동 중 (10초마다 시장 체크)")
        else:
            self.logger.info("[IDLE] 현재 모든 시장 폐장 - 대기 모드")

        try:
            while self.is_running:
                # 1분마다 시장 체크
                current_minute = datetime.now().minute

                if current_minute != last_check_minute:
                    last_check_minute = current_minute

                    # TradingAgents 사전 분석 — KR 08:45 KST, US 09:15 ET
                    _today_kr = datetime.now(self.kr_tz).strftime("%Y-%m-%d")
                    _today_us = datetime.now(self.us_tz).strftime("%Y-%m-%d")
                    _now_kr = datetime.now(self.kr_tz)
                    _now_us = datetime.now(self.us_tz)
                    if (_now_kr.hour == 8 and _now_kr.minute == 45
                            and _today_kr != _ta_analyzed_today["kr"]):
                        _ta_analyzed_today["kr"] = _today_kr
                        self._run_ta_preanalysis(market="kr")
                    if (_now_us.hour == 9 and _now_us.minute == 15
                            and _today_us != _ta_analyzed_today["us"]):
                        _ta_analyzed_today["us"] = _today_us
                        self._run_ta_preanalysis(market="us")

                    # 마감 후 검색기 스캔 — KR 15:40 KST, US 16:10 ET (평일 1회)
                    if (_now_kr.hour == 15 and _now_kr.minute == 40
                            and _now_kr.weekday() < 5
                            and _today_kr != _eod_scanned_today["kr"]):
                        _eod_scanned_today["kr"] = _today_kr
                        self._run_eod_scan(market="kr")
                    if (_now_us.hour == 16 and _now_us.minute == 10
                            and _now_us.weekday() < 5
                            and _today_us != _eod_scanned_today["us"]):
                        _eod_scanned_today["us"] = _today_us
                        self._run_eod_scan(market="us")

                    # 활성 시장 확인
                    active_market = self.get_active_market()

                    if active_market:
                        # 시장 전환 필요 시
                        if active_market != self.current_market:
                            self.switch_market(active_market)

                        # 매 분마다 전략 실행 (실제로는 스케줄 주기에 따라)
                        if current_minute % 30 == 0:  # 30분마다 매도
                            if self.state.trading_enabled:
                                self.current_scheduler.execute_sell_strategy()
                                self.state.mark_sell()
                            else:
                                self.logger.info("[GUARD] trading_enabled=False — 매도 스킵")

                        if current_minute % 60 == 0:  # 60분마다 매수
                            if self.state.trading_enabled:
                                self.current_scheduler.execute_buy_strategy()
                                self.state.mark_buy()
                            else:
                                self.logger.info("[GUARD] trading_enabled=False — 매수 스킵")

                        if current_minute % 30 == 0:  # 30분마다 토큰 체크
                            self.current_scheduler.check_and_refresh_token()

                    else:
                        # 장 시간 외
                        if self.current_scheduler:
                            self.current_scheduler = None
                            self.current_market = None
                            self.state.update_market(None)
                            self.logger.info("[IDLE] 모든 시장 폐장 - 대기 모드")

                # 10분마다 상태 로그
                if time.time() - last_status_print >= 600:
                    now = datetime.now(self.kr_tz)
                    active = self.get_active_market()

                    if active:
                        market_name = "미국" if active == 'us' else "한국"
                        self.logger.info(f"[STATUS] 현재: {market_name} 장 모니터링 중 ({now.strftime('%H:%M')} KST)")
                    else:
                        self.logger.info(f"[STATUS] 대기 중 - 다음 개장 대기 ({now.strftime('%H:%M')} KST)")

                    last_status_print = time.time()

                # CPU 사용률 절감
                time.sleep(10)  # 10초마다 체크

        except KeyboardInterrupt:
            self.logger.info("[STOP] 사용자 중단 요청")
        except Exception as e:
            self.logger.error(f"[ERROR] 시스템 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            self.stop()

    def stop(self):
        """시스템 중지"""
        self.logger.info("=" * 60)
        self.logger.info("=== 자동 시장 전환 시스템 종료 ===")
        self.logger.info("=" * 60)
        self.is_running = False


def main():
    """메인 실행 함수"""
    # 로깅 설정
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        handlers=[file_handler, console_handler]
    )

    # 시작 전 설정 검증 및 확인
    from startup_validator import run_startup_validation
    import sys

    if not run_startup_validation(check_kr=True, check_us=True):
        logging.info("사용자가 시작을 취소했습니다.")
        sys.exit(0)

    # FastAPI 서버를 daemon thread로 기동 (메인 프로세스 종료 시 함께 종료)
    def _start_api_server():
        import uvicorn
        import api_server
        port = int(os.getenv("MOBILE_API_PORT", "8000"))
        uvicorn.run(api_server.app, host="0.0.0.0", port=port, log_level="warning")

    api_thread = threading.Thread(target=_start_api_server, daemon=True, name="api-server")
    api_thread.start()
    logging.getLogger(__name__).info(f"API 서버 시작 (포트: {os.getenv('MOBILE_API_PORT', '8000')})")

    # 자동 시장 전환 스케줄러 시작
    scheduler = AutoMarketScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
