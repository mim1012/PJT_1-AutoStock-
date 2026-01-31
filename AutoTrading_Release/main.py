# -*- coding: utf-8 -*-
"""
스케줄러 및 메인 실행 로직

새 구조:
- common/: 공통 베이스 클래스
- us/: 미국 주식 전용 모듈
- kr/: 한국 주식 전용 모듈 (Phase 2에서 활성화)

사용법:
- 미국 주식: python main.py (기본)
- 한국 주식: python main.py --market kr (Phase 2에서 지원)
"""
import schedule
import time
import logging
from datetime import datetime, time as dt_time
import pytz
import argparse

# 새 구조의 US 모듈 임포트 시도, 실패 시 기존 모듈 사용
try:
    from us.strategy import USStrategy as TradingStrategy
    from us.config import USConfig
    USE_NEW_STRUCTURE = True
except ImportError:
    from strategy_pjt1 import TradingStrategy
    USE_NEW_STRUCTURE = False

from order_manager import OrderManager
from transaction_logger import TransactionLogger
from config import *

class TradingScheduler:
    def __init__(self):
        self.strategy = TradingStrategy()
        self.order_manager = OrderManager()
        self.transaction_logger = TransactionLogger()
        self.logger = logging.getLogger(__name__)

        # 동부시간 타임존 설정
        self.et_tz = pytz.timezone('US/Eastern')

        # 운영 시간 설정 (ET 기준 고정 시간 - 서머타임 자동 처리)
        # 설정 파일의 시간은 참고용이며, 실제 비교는 ET 기준으로 수행
        self.market_open_et = dt_time(9, 30)   # 09:30 ET
        self.market_close_et = dt_time(16, 0)  # 16:00 ET

        self.is_running = False
    
    def is_trading_hours(self):
        """
        현재 시간이 운영 시간인지 확인 (서머타임 자동 대응)

        미국 시장은 매년 3월 두 번째 일요일~11월 첫 번째 일요일 동안
        서머타임(EDT)을 적용합니다. pytz는 이를 자동으로 처리합니다.

        - 동계시간(EST): 09:30 ET = 23:30 KST
        - 하계시간(EDT): 09:30 ET = 22:30 KST

        Returns:
            bool: 운영 시간이면 True, 아니면 False
        """
        try:
            # 현재 동부시간 (pytz가 자동으로 서머타임 처리)
            et_now = datetime.now(self.et_tz)
            current_time_et = et_now.time()

            # 주말 체크
            if et_now.weekday() >= 5:  # 토요일(5), 일요일(6)
                return False

            # ET 기준으로 운영 시간 체크 (서머타임 자동 반영)
            return self.market_open_et <= current_time_et <= self.market_close_et

        except Exception as e:
            self.logger.error(f"운영 시간 확인 오류: {e}")
            return False
    
    def execute_sell_strategy(self):
        """매도 전략 실행 (30분 주기)"""
        if not self.is_trading_hours():
            self.logger.info("운영 시간 외 - 매도 전략 스킵")
            self.transaction_logger.log_strategy_execution("sell", "skipped", "운영 시간 외")
            return
        
        try:
            self.logger.info("=== 매도 조건 검사 시작 ===")
            self.transaction_logger.log_strategy_execution("sell", "started", "매도 조건 검사 시작")

            result = self.strategy.execute_sell_strategy()

            self.logger.info("=== 매도 조건 검사 완료 ===")
            message = result.get('message', '검사 완료') if isinstance(result, dict) else '검사 완료'
            self.transaction_logger.log_strategy_execution("sell", "completed", f"매도 조건 검사 완료 - {message}")
            
        except Exception as e:
            self.logger.error(f"매도 전략 실행 오류: {e}")
            self.transaction_logger.log_strategy_execution("sell", "error", f"오류: {e}")
    
    def execute_buy_strategy(self):
        """매수 전략 실행 (1시간 주기)"""
        if not self.is_trading_hours():
            self.logger.info("운영 시간 외 - 매수 전략 스킵")
            self.transaction_logger.log_strategy_execution("buy", "skipped", "운영 시간 외")
            return
        
        try:
            self.logger.info("=== 매수 조건 검사 시작 ===")
            self.transaction_logger.log_strategy_execution("buy", "started", "매수 조건 검사 시작")

            result = self.strategy.execute_buy_strategy()

            self.logger.info("=== 매수 조건 검사 완료 ===")
            message = result.get('message', '검사 완료') if isinstance(result, dict) else '검사 완료'
            self.transaction_logger.log_strategy_execution("buy", "completed", f"매수 조건 검사 완료 - {message}")
            
        except Exception as e:
            self.logger.error(f"매수 전략 실행 오류: {e}")
            self.transaction_logger.log_strategy_execution("buy", "error", f"오류: {e}")
    
    def check_and_refresh_token(self):
        """
        토큰 상태 확인 및 필요시 재발급
        재발급 시 KISAPIClient의 브로커도 재초기화
        
        개선사항:
        - 토큰 변경 감지 시 자동 브로커 재초기화
        - 주기적 브로커 재초기화 (24시간 토큰 만료 대비)
        - 상세한 로깅

        주의: 토큰 체크는 시장 폐장 시에도 실행 (다음 개장 대비)
        """
        try:
            # TokenManager를 통해 토큰 상태 확인
            if not hasattr(self.strategy.api_client, 'token_manager') or self.strategy.api_client.token_manager is None:
                self.logger.warning("[TOKEN_CHECK] TokenManager가 없습니다")
                return

            token_manager = self.strategy.api_client.token_manager
            
            # 토큰 정보 로깅
            token_info = token_manager.get_token_info()
            self.logger.info(f"[TOKEN_CHECK] {token_info}")

            # 현재 토큰 저장 (변경 감지용)
            old_token = token_manager.load_token()
            
            # 토큰 유효성 확인 및 필요 시 재발급
            new_token = token_manager.get_valid_token()
            
            # 토큰 변경 감지
            token_changed = (old_token != new_token)

            if old_token is None:
                self.logger.warning("[TOKEN_CHECK] 토큰이 만료되었거나 없음 - 재발급 완료")
                token_changed = True
            elif token_changed:
                self.logger.info("[TOKEN_CHECK] 토큰 변경 감지 (자동 재발급됨)")
            
            # 토큰이 변경되었거나 브로커 재초기화가 필요한 경우
            if token_changed or not hasattr(self, '_last_broker_reinit_time'):
                self.logger.info("[TOKEN_CHECK] 브로커 재초기화 시작...")
                
                # KISAPIClient의 브로커 재초기화
                if hasattr(self.strategy.api_client, 'reinitialize_brokers'):
                    if self.strategy.api_client.reinitialize_brokers():
                        self.logger.info("[TOKEN_CHECK] ✅ 브로커 재초기화 성공")
                        self._last_broker_reinit_time = time.time()
                    else:
                        self.logger.error("[TOKEN_CHECK] ❌ 브로커 재초기화 실패")
                else:
                    self.logger.warning("[TOKEN_CHECK] reinitialize_brokers 메서드 없음")
            else:
                # 토큰 변경 없어도 주기적으로 브로커 재초기화 (24시간 대비)
                time_since_last_reinit = time.time() - getattr(self, '_last_broker_reinit_time', 0)
                
                # 6시간마다 주기적 재초기화 (24시간 토큰 만료 대비)
                if time_since_last_reinit > 6 * 3600:
                    self.logger.info("[TOKEN_CHECK] 주기적 브로커 재초기화 (24시간 토큰 만료 대비)")
                    
                    if hasattr(self.strategy.api_client, 'reinitialize_brokers'):
                        if self.strategy.api_client.reinitialize_brokers():
                            self.logger.info("[TOKEN_CHECK] ✅ 주기적 재초기화 성공")
                            self._last_broker_reinit_time = time.time()
                        else:
                            self.logger.error("[TOKEN_CHECK] ❌ 주기적 재초기화 실패")
                else:
                    # 폐장 시에는 상세 로그 생략
                    if not self.is_trading_hours():
                        self.logger.debug("[TOKEN_CHECK] 토큰 유효, 브로커 정상 (폐장 중)")
                    else:
                        self.logger.info(f"[TOKEN_CHECK] 토큰 유효, 브로커 정상 (다음 재초기화: {(6 * 3600 - time_since_last_reinit) / 3600:.1f}시간 후)")

        except Exception as e:
            self.logger.error(f"[TOKEN_CHECK] 토큰 체크 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def cleanup_orders(self):
        """주문 정리 작업"""
        # 폐장 시에는 주문 정리 스킵 (불필요한 API 호출 방지)
        if not self.is_trading_hours():
            return

        try:
            self.logger.info("주문 정리 작업 시작")
            self.order_manager.cleanup_old_orders()

        except Exception as e:
            self.logger.error(f"주문 정리 오류: {e}")
    
    def print_status(self):
        """현재 상태 출력"""
        if not self.is_trading_hours():
            # 운영 시간 외에는 상태 로그를 생략해 콘솔/파일 로그를 조용히 유지
            return
        
        try:
            et_now = datetime.now(self.et_tz)
            trading_status = "운영중" if self.is_trading_hours() else "운영 시간 외"
            
            order_summary = self.order_manager.get_order_summary()
            transaction_summary = self.transaction_logger.get_summary()
            
            self.logger.info(f"=== 시스템 상태 ({et_now.strftime('%Y-%m-%d %H:%M:%S ET')}) ===")
            self.logger.info(f"거래 상태: {trading_status}")
            self.logger.info(f"미체결 주문: {order_summary['total_pending']}개 (매수: {order_summary['buy_orders']}, 매도: {order_summary['sell_orders']})")
            self.logger.info(f"오늘 거래 기록: 총 {transaction_summary['total_transactions']}건 (매수: {transaction_summary['buy_orders']}, 매도: {transaction_summary['sell_orders']})")
            
            if transaction_summary['total_profit_loss'] != 0:
                self.logger.info(f"오늘 총 손익: ${transaction_summary['total_profit_loss']:.2f}")
            
        except Exception as e:
            self.logger.error(f"상태 출력 오류: {e}")
    
    def setup_schedule(self):
        """스케줄 설정"""
        # 매도 전략 (30분 주기)
        schedule.every(SELL_INTERVAL_MINUTES).minutes.do(self.execute_sell_strategy)

        # 매수 전략 (1시간 주기)
        schedule.every(BUY_INTERVAL_MINUTES).minutes.do(self.execute_buy_strategy)

        # 주문 정리 (10분 주기)
        schedule.every(10).minutes.do(self.cleanup_orders)

        # 상태 출력 (5분 주기)
        schedule.every(5).minutes.do(self.print_status)

        # 토큰 상태 체크 (30분 주기) - 만료 감지 및 브로커 재초기화
        schedule.every(30).minutes.do(self.check_and_refresh_token)

        self.logger.info("스케줄 설정 완료")
        self.logger.info(f"- 매도 전략: {SELL_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"- 매수 전략: {BUY_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"- 토큰 체크: 30분 주기 (자동 재발급 및 브로커 재초기화)")
        self.logger.info(f"- 운영 시간: {TRADING_START_TIME} ~ {TRADING_END_TIME} (ET)")
    
    def start(self):
        """스케줄러 시작"""
        self.logger.info("=== 자동매매 시스템 시작 ===")

        # 시작 시 토큰 상태 확인 및 필요시 재발급
        self.logger.info("시작 전 토큰 상태 확인 중...")
        self.check_and_refresh_token()

        # 초기 상태 확인
        if not self.is_trading_hours():
            et_now = datetime.now(self.et_tz)
            self.logger.warning(f"[폐장 중] 현재 {et_now.strftime('%Y-%m-%d %H:%M:%S ET')} - 대기 모드")
            self.logger.info(f"[폐장 중] 다음 개장: 월-금 {TRADING_START_TIME} ET (한국시간 22:30 또는 23:30)")

        self.setup_schedule()
        self.is_running = True

        # 초기 상태 출력
        self.print_status()

        # 폐장 중 로그 출력 주기 (1시간마다)
        last_closed_log_time = time.time()

        try:
            while self.is_running:
                schedule.run_pending()

                # 폐장 중에는 로그를 1시간마다만 출력
                if not self.is_trading_hours():
                    current_time = time.time()
                    if current_time - last_closed_log_time >= 3600:  # 1시간 = 3600초
                        et_now = datetime.now(self.et_tz)
                        self.logger.info(f"[폐장 중] 대기 중... ({et_now.strftime('%Y-%m-%d %H:%M:%S ET')})")
                        last_closed_log_time = current_time

                    time.sleep(300)  # 폐장 시 5분마다 체크 (절전)
                else:
                    time.sleep(30)   # 개장 시 30초마다 체크 (적극)

        except KeyboardInterrupt:
            self.logger.info("사용자에 의한 중단 요청")
        except Exception as e:
            self.logger.error(f"스케줄러 실행 오류: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """스케줄러 중지"""
        self.logger.info("=== 자동매매 시스템 중지 ===")
        self.is_running = False
        
        # 미체결 주문 현황 출력
        order_summary = self.order_manager.get_order_summary()
        if order_summary['total_pending'] > 0:
            self.logger.info(f"중지 시점 미체결 주문: {order_summary['total_pending']}개")
            for order in order_summary['orders']:
                self.logger.info(f"  - {order['symbol']} {order['type']} {order['quantity']}주 @ ${order['price']} ({order['time']})")
        
        # 오늘 거래 기록 요약 출력
        transaction_summary = self.transaction_logger.get_summary()
        self.logger.info(f"=== 오늘 거래 기록 요약 ===")
        self.logger.info(f"총 거래 건수: {transaction_summary['total_transactions']}건")
        self.logger.info(f"매수 주문: {transaction_summary['buy_orders']}건")
        self.logger.info(f"매도 주문: {transaction_summary['sell_orders']}건")
        self.logger.info(f"성공한 거래: {transaction_summary['successful_trades']}건")
        self.logger.info(f"총 손익: ${transaction_summary['total_profit_loss']:.2f}")
        self.logger.info(f"CSV 파일: {self.transaction_logger.csv_path}")

def main():
    """메인 실행 함수"""
    # 명령줄 인수 파싱
    parser = argparse.ArgumentParser(description='자동매매 시스템')
    parser.add_argument('--market', type=str, default='us', choices=['us', 'kr', 'both'],
                        help='시장 선택: us (미국, 기본값), kr (한국), both (듀얼)')
    args = parser.parse_args()

    # 로깅 설정 (로그 로테이션 적용)
    from logging.handlers import RotatingFileHandler

    # 로테이션 파일 핸들러
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # 루트 로거 설정
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        handlers=[file_handler, console_handler]
    )

    logger = logging.getLogger(__name__)

    try:
        # 설정 확인
        if KIS_APP_KEY == "your_app_key_here":
            logger.error("API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            return

        # 시작 전 설정 검증 (시장 선택에 따라)
        from startup_validator import run_startup_validation
        import sys

        # 시장 선택에 따라 다른 스케줄러 사용
        if args.market == 'kr':
            # 한국 주식만 검증
            if not run_startup_validation(check_kr=True, check_us=False):
                logger.info("사용자가 시작을 취소했습니다.")
                sys.exit(0)

            logger.info("한국 주식 시장 전용 모드로 시작합니다.")
            from dual_market_scheduler import DualMarketScheduler
            scheduler = DualMarketScheduler(markets=['kr'])
            scheduler.start()
            return

        if args.market == 'both':
            # 미국 + 한국 모두 검증
            if not run_startup_validation(check_kr=True, check_us=True):
                logger.info("사용자가 시작을 취소했습니다.")
                sys.exit(0)

            logger.info("듀얼 마켓 모드로 시작합니다 (US + KR)")
            from dual_market_scheduler import DualMarketScheduler
            scheduler = DualMarketScheduler(markets=['us', 'kr'])
            scheduler.start()
            return

        # 미국 주식만 검증 (기본값)
        if not run_startup_validation(check_kr=False, check_us=True):
            logger.info("사용자가 시작을 취소했습니다.")
            sys.exit(0)

        # 모듈 구조 표시
        if USE_NEW_STRUCTURE:
            logger.info("=== 새 모듈 구조 사용 (us/) ===")
            print("Using new module structure (us/)")
        else:
            logger.warning("=== 기존 모듈 구조 사용 (레거시) ===")
            print("Using legacy module structure")

        # 실전거래 모드 확인 및 표시
        if USE_PAPER_TRADING:
            logger.warning("Paper Trading Mode Active")
            print("Paper Trading Mode Active")
        else:
            logger.critical("REAL TRADING MODE ACTIVE!")
            print("REAL TRADING MODE ACTIVE!")
            print("WARNING: Real money trading in progress!")
            print("=" * 50)

        # 스케줄러 시작
        scheduler = TradingScheduler()
        scheduler.start()

    except Exception as e:
        logger.error(f"시스템 시작 오류: {e}")

if __name__ == "__main__":
    main()

