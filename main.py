# -*- coding: utf-8 -*-
"""
스케줄러 및 메인 실행 로직
"""
import schedule
import time
import logging
from datetime import datetime, time as dt_time
import pytz
from strategy_pjt1 import TradingStrategy
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
        
        # 운영 시간 설정
        self.start_time = dt_time.fromisoformat(TRADING_START_TIME)
        self.end_time = dt_time.fromisoformat(TRADING_END_TIME)
        
        self.is_running = False
    
    def is_trading_hours(self):
        """현재 시간이 운영 시간인지 확인"""
        try:
            # 현재 동부시간
            et_now = datetime.now(self.et_tz)
            current_time = et_now.time()
            
            # 주말 체크
            if et_now.weekday() >= 5:  # 토요일(5), 일요일(6)
                return False
            
            # 운영 시간 체크
            return self.start_time <= current_time <= self.end_time
            
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
            self.logger.info("=== 매도 전략 실행 시작 ===")
            self.transaction_logger.log_strategy_execution("sell", "started", "매도 전략 실행 시작")
            
            self.strategy.execute_sell_strategy()
            
            self.logger.info("=== 매도 전략 실행 완료 ===")
            self.transaction_logger.log_strategy_execution("sell", "completed", "매도 전략 실행 완료")
            
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
            self.logger.info("=== 매수 전략 실행 시작 ===")
            self.transaction_logger.log_strategy_execution("buy", "started", "매수 전략 실행 시작")
            
            self.strategy.execute_buy_strategy()
            
            self.logger.info("=== 매수 전략 실행 완료 ===")
            self.transaction_logger.log_strategy_execution("buy", "completed", "매수 전략 실행 완료")
            
        except Exception as e:
            self.logger.error(f"매수 전략 실행 오류: {e}")
            self.transaction_logger.log_strategy_execution("buy", "error", f"오류: {e}")
    
    def check_and_refresh_token(self):
        """
        토큰 상태 확인 및 필요시 재발급
        재발급 시 KISAPIClient의 브로커도 재초기화

        주의: 토큰 체크는 시장 폐장 시에도 실행 (다음 개장 대비)
        """
        try:
            # TokenManager를 통해 토큰 상태 확인
            if not hasattr(self.strategy.api_client, 'token_manager') or self.strategy.api_client.token_manager is None:
                return

            token_manager = self.strategy.api_client.token_manager

            # 현재 토큰 유효성 확인
            current_token = token_manager.load_token()

            if current_token is None:
                self.logger.warning("[TOKEN_CHECK] 토큰이 만료되었거나 없음 - 재발급 시도")

                # 새 토큰 발급 시도
                new_token = token_manager.get_valid_token(force_refresh=True)

                if new_token:
                    self.logger.info("[TOKEN_CHECK] 새 토큰 발급 성공 - 브로커 재초기화")

                    # KISAPIClient의 브로커 재초기화
                    if hasattr(self.strategy.api_client, 'reinitialize_brokers'):
                        if self.strategy.api_client.reinitialize_brokers():
                            self.logger.info("[TOKEN_CHECK] 브로커 재초기화 성공")
                        else:
                            self.logger.error("[TOKEN_CHECK] 브로커 재초기화 실패")
                    else:
                        self.logger.warning("[TOKEN_CHECK] reinitialize_brokers 메서드 없음")
                else:
                    self.logger.error("[TOKEN_CHECK] 토큰 재발급 실패 (24시간 제한 가능)")
            else:
                # 폐장 시에는 토큰 유효성만 확인하고 상세 로그 생략
                if not self.is_trading_hours():
                    self.logger.debug("[TOKEN_CHECK] 토큰 유효 (폐장 중)")

        except Exception as e:
            self.logger.error(f"토큰 체크 오류: {e}")

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
    # 로깅 설정
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # 설정 확인
        if KIS_APP_KEY == "your_app_key_here":
            logger.error("API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            return
        
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

