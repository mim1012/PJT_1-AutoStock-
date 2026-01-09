# -*- coding: utf-8 -*-
"""
듀얼 마켓 스케줄러 (US/KR 동시 운영)

미국 시장: 09:30-16:00 ET (한국 시간 22:30-05:00 또는 23:30-06:00)
한국 시장: 09:00-15:30 KST

두 시장은 시간대가 겹치지 않아 하나의 프로세스에서 동시 운영 가능
"""
import schedule
import time
import logging
from datetime import datetime, time as dt_time
import pytz
import argparse
from typing import Optional

# US 모듈
from us.strategy import USStrategy
from us.config import USConfig

# KR 모듈
from kr.strategy import KRStrategy
from kr.config import KRConfig

from order_manager import OrderManager
from transaction_logger import TransactionLogger
from config import (
    SELL_INTERVAL_MINUTES,
    BUY_INTERVAL_MINUTES,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    LOG_LEVEL,
    KIS_APP_KEY,
    USE_PAPER_TRADING
)


class MarketScheduler:
    """단일 시장 스케줄러 (US 또는 KR)"""

    def __init__(self, market: str):
        """
        Args:
            market: 'us' 또는 'kr'
        """
        self.market = market.lower()
        self.logger = logging.getLogger(f"{__name__}.{self.market.upper()}")

        if self.market == 'us':
            self.strategy = USStrategy()
            self.tz = pytz.timezone('US/Eastern')
            self.start_time = dt_time.fromisoformat(USConfig.TRADING_START_TIME)
            self.end_time = dt_time.fromisoformat(USConfig.TRADING_END_TIME)
            self.transaction_logger = TransactionLogger(prefix="us")
            self.market_name = "미국"
        else:  # kr
            self.strategy = KRStrategy()
            self.tz = pytz.timezone('Asia/Seoul')
            self.start_time = dt_time.fromisoformat(KRConfig.TRADING_START_TIME)
            self.end_time = dt_time.fromisoformat(KRConfig.TRADING_END_TIME)
            self.transaction_logger = TransactionLogger(prefix="kr")
            self.market_name = "한국"

        self.order_manager = OrderManager()
        self._last_broker_reinit_time = 0

    def is_trading_hours(self) -> bool:
        """현재 시간이 해당 시장 운영 시간인지 확인"""
        try:
            now = datetime.now(self.tz)
            current_time = now.time()

            # 주말 체크
            if now.weekday() >= 5:
                return False

            return self.start_time <= current_time <= self.end_time

        except Exception as e:
            self.logger.error(f"운영 시간 확인 오류: {e}")
            return False

    def execute_sell_strategy(self):
        """매도 전략 실행"""
        if not self.is_trading_hours():
            return

        try:
            self.logger.info(f"=== [{self.market_name}] 매도 전략 실행 ===")
            self.transaction_logger.log_strategy_execution("sell", "started", f"{self.market_name} 매도 시작")

            result = self.strategy.execute_sell_strategy()

            self.logger.info(f"=== [{self.market_name}] 매도 전략 완료: {result.get('message', '')} ===")
            self.transaction_logger.log_strategy_execution("sell", "completed", result.get('message', ''))

        except Exception as e:
            self.logger.error(f"[{self.market_name}] 매도 전략 오류: {e}")
            self.transaction_logger.log_strategy_execution("sell", "error", str(e))

    def execute_buy_strategy(self):
        """매수 전략 실행"""
        if not self.is_trading_hours():
            return

        try:
            self.logger.info(f"=== [{self.market_name}] 매수 전략 실행 ===")
            self.transaction_logger.log_strategy_execution("buy", "started", f"{self.market_name} 매수 시작")

            result = self.strategy.execute_buy_strategy()

            self.logger.info(f"=== [{self.market_name}] 매수 전략 완료: {result.get('message', '')} ===")
            self.transaction_logger.log_strategy_execution("buy", "completed", result.get('message', ''))

        except Exception as e:
            self.logger.error(f"[{self.market_name}] 매수 전략 오류: {e}")
            self.transaction_logger.log_strategy_execution("buy", "error", str(e))

    def check_and_refresh_token(self):
        """토큰 상태 확인 및 필요시 재발급"""
        try:
            if not hasattr(self.strategy.api_client, 'token_manager'):
                return

            token_manager = self.strategy.api_client.token_manager
            token_info = token_manager.get_token_info()
            self.logger.debug(f"[{self.market.upper()}_TOKEN] {token_info}")

            # 토큰 유효성 확인
            old_token = token_manager.load_token()
            new_token = token_manager.get_valid_token()

            token_changed = (old_token != new_token)

            if token_changed and hasattr(self.strategy.api_client, 'reinitialize_brokers'):
                self.logger.info(f"[{self.market.upper()}_TOKEN] 브로커 재초기화...")
                if self.strategy.api_client.reinitialize_brokers():
                    self._last_broker_reinit_time = time.time()
                    self.logger.info(f"[{self.market.upper()}_TOKEN] 재초기화 성공")

        except Exception as e:
            self.logger.error(f"[{self.market.upper()}_TOKEN] 토큰 체크 오류: {e}")

    def print_status(self):
        """현재 상태 출력"""
        if not self.is_trading_hours():
            return

        try:
            now = datetime.now(self.tz)
            tz_name = "ET" if self.market == 'us' else "KST"

            self.logger.info(f"=== [{self.market_name}] 상태 ({now.strftime('%H:%M:%S')} {tz_name}) ===")

            # 잔고 요약
            balance = self.strategy.api_client.get_account_balance()
            if balance:
                positions = balance.get('positions', [])
                cash = balance.get('available_cash', 0)

                if self.market == 'us':
                    self.logger.info(f"  예수금: ${cash:,.2f}, 보유: {len(positions)}종목")
                else:
                    self.logger.info(f"  예수금: {cash:,.0f}원, 보유: {len(positions)}종목")

        except Exception as e:
            self.logger.error(f"상태 출력 오류: {e}")


class DualMarketScheduler:
    """US/KR 듀얼 마켓 스케줄러"""

    def __init__(self, markets: list = None):
        """
        Args:
            markets: 운영할 시장 리스트 ['us', 'kr'] (기본: 둘 다)
        """
        self.logger = logging.getLogger(__name__)

        if markets is None:
            markets = ['us', 'kr']

        self.markets = markets
        self.schedulers = {}

        for market in markets:
            self.schedulers[market] = MarketScheduler(market)
            self.logger.info(f"[{market.upper()}] 스케줄러 초기화 완료")

        self.is_running = False
        self.us_tz = pytz.timezone('US/Eastern')
        self.kr_tz = pytz.timezone('Asia/Seoul')

    def _get_current_status(self) -> dict:
        """현재 각 시장 상태 조회"""
        status = {}
        for market, scheduler in self.schedulers.items():
            status[market] = {
                'is_open': scheduler.is_trading_hours(),
                'market_name': scheduler.market_name
            }
        return status

    def setup_schedule(self):
        """스케줄 설정"""
        for market, scheduler in self.schedulers.items():
            # 매도 전략 (30분 주기)
            schedule.every(SELL_INTERVAL_MINUTES).minutes.do(scheduler.execute_sell_strategy)

            # 매수 전략 (60분 주기)
            schedule.every(BUY_INTERVAL_MINUTES).minutes.do(scheduler.execute_buy_strategy)

            # 토큰 체크 (30분 주기)
            schedule.every(30).minutes.do(scheduler.check_and_refresh_token)

            # 상태 출력 (15분 주기)
            schedule.every(15).minutes.do(scheduler.print_status)

            self.logger.info(f"[{market.upper()}] 스케줄 설정 완료")

    def start(self):
        """스케줄러 시작"""
        self.logger.info("=" * 60)
        self.logger.info("=== 듀얼 마켓 자동매매 시스템 시작 ===")
        self.logger.info("=" * 60)

        # 운영 모드 표시
        if USE_PAPER_TRADING:
            self.logger.warning("[MODE] Paper Trading (모의투자)")
        else:
            self.logger.critical("[MODE] REAL TRADING (실전거래)")
            print("=" * 60)
            print("WARNING: REAL TRADING MODE ACTIVE!")
            print("=" * 60)

        # 각 시장 초기 상태 표시
        for market, scheduler in self.schedulers.items():
            now = datetime.now(scheduler.tz)
            tz_name = "ET" if market == 'us' else "KST"
            is_open = scheduler.is_trading_hours()
            status = "개장중" if is_open else "폐장중"

            self.logger.info(f"[{market.upper()}] {scheduler.market_name} 시장: {status}")
            self.logger.info(f"[{market.upper()}] 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')} {tz_name}")
            self.logger.info(f"[{market.upper()}] 운영 시간: {scheduler.start_time} ~ {scheduler.end_time} {tz_name}")

            # 초기 토큰 확인
            scheduler.check_and_refresh_token()

        # 스케줄 설정
        self.setup_schedule()
        self.is_running = True

        # 메인 루프
        last_status_log = time.time()

        try:
            while self.is_running:
                schedule.run_pending()

                # 현재 상태 확인
                status = self._get_current_status()
                any_market_open = any(s['is_open'] for s in status.values())

                # 1시간마다 전체 상태 로그
                if time.time() - last_status_log >= 3600:
                    us_now = datetime.now(self.us_tz)
                    kr_now = datetime.now(self.kr_tz)

                    self.logger.info(f"[STATUS] US: {us_now.strftime('%H:%M')} ET, KR: {kr_now.strftime('%H:%M')} KST")

                    for market, s in status.items():
                        state = "OPEN" if s['is_open'] else "CLOSED"
                        self.logger.info(f"[STATUS] {market.upper()}: {state}")

                    last_status_log = time.time()

                # 슬립 간격 조절
                if any_market_open:
                    time.sleep(30)   # 시장 열림: 30초
                else:
                    time.sleep(300)  # 시장 닫힘: 5분

        except KeyboardInterrupt:
            self.logger.info("사용자에 의한 중단")
        except Exception as e:
            self.logger.error(f"스케줄러 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            self.stop()

    def stop(self):
        """스케줄러 중지"""
        self.logger.info("=" * 60)
        self.logger.info("=== 듀얼 마켓 자동매매 시스템 중지 ===")
        self.logger.info("=" * 60)

        self.is_running = False

        # 각 시장별 요약
        for market, scheduler in self.schedulers.items():
            summary = scheduler.transaction_logger.get_summary()
            self.logger.info(f"[{market.upper()}] 오늘 거래: {summary['total_transactions']}건")
            self.logger.info(f"[{market.upper()}] 매수: {summary['buy_orders']}건, 매도: {summary['sell_orders']}건")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='듀얼 마켓 자동매매 시스템')
    parser.add_argument('--market', type=str, default='both',
                        choices=['us', 'kr', 'both'],
                        help='시장 선택: us, kr, both (기본값)')
    args = parser.parse_args()

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
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        handlers=[file_handler, console_handler]
    )

    logger = logging.getLogger(__name__)

    try:
        # API 키 확인
        if KIS_APP_KEY == "your_app_key_here":
            logger.error("API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            return

        # 시장 선택
        if args.market == 'both':
            markets = ['us', 'kr']
        else:
            markets = [args.market]

        logger.info(f"운영 시장: {', '.join([m.upper() for m in markets])}")

        # 스케줄러 시작
        scheduler = DualMarketScheduler(markets=markets)
        scheduler.start()

    except Exception as e:
        logger.error(f"시스템 시작 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
