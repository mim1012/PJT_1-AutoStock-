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
    
    def cleanup_orders(self):
        """주문 정리 작업"""
        try:
            self.logger.info("주문 정리 작업 시작")
            self.order_manager.cleanup_old_orders()
            
            # 운영 시간 종료 후 미체결 주문 정리
            if not self.is_trading_hours():
                pending_count = self.order_manager.get_pending_orders_count()
                if pending_count > 0:
                    self.logger.info(f"운영 시간 종료 - 미체결 주문 {pending_count}개 유지")
            
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
        
        self.logger.info("스케줄 설정 완료")
        self.logger.info(f"- 매도 전략: {SELL_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"- 매수 전략: {BUY_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"- 운영 시간: {TRADING_START_TIME} ~ {TRADING_END_TIME} (ET)")
    
    def start(self):
        """스케줄러 시작"""
        self.logger.info("=== 자동매매 시스템 시작 ===")
        
        # 초기 상태 확인
        if not self.is_trading_hours():
            self.logger.warning("현재 운영 시간이 아닙니다. 대기 모드로 실행됩니다.")
        
        self.setup_schedule()
        self.is_running = True
        
        # 초기 상태 출력
        self.print_status()
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)  # 30초마다 스케줄 체크
                
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

