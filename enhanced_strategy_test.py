"""
향상된 전략 테스트 모드 - 거래시간 무관 테스트 가능
"""
import sys
import os
import time
import logging
from datetime import datetime, timedelta
import pytz
import schedule

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy_pjt1 import TradingStrategy
from kis_api import KISAPIClient
from config import *

class EnhancedStrategyTester:
    def __init__(self, ignore_trading_hours=False):
        self.strategy = TradingStrategy()
        self.api_client = self.strategy.api_client
        self.logger = logging.getLogger(__name__)
        self.et_tz = pytz.timezone('US/Eastern')
        
        # 테스트 설정
        self.ignore_trading_hours = ignore_trading_hours  # 거래시간 무시 옵션
        
        # 시뮬레이션용 가상 잔고
        self.virtual_cash = 10000  # $10,000 가상 예수금
        self.virtual_positions = {}  # 가상 보유종목
        
        # 마지막 실행 시간 기록
        self.last_buy_check = None
        self.last_sell_check = None
        
        # 테스트 통계
        self.test_stats = {
            'buy_signals': 0,
            'sell_signals': 0,
            'filter_failures': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
    
    def is_trading_hours(self):
        """현재 시간이 운영 시간인지 확인 (테스트 모드에서는 무시 가능)"""
        if self.ignore_trading_hours:
            self.logger.debug("🧪 테스트 모드: 거래시간 체크 무시")
            return True
            
        try:
            et_now = datetime.now(self.et_tz)
            current_time = et_now.time()
            
            # 주말 체크
            if et_now.weekday() >= 5:  # 토요일(5), 일요일(6)
                return False
            
            # 운영 시간 체크
            start_time = datetime.strptime(TRADING_START_TIME, "%H:%M").time()
            end_time = datetime.strptime(TRADING_END_TIME, "%H:%M").time()
            
            return start_time <= current_time <= end_time
            
        except Exception as e:
            self.logger.error(f"운영 시간 확인 오류: {e}")
            return False
    
    def test_buy_signals(self):
        """매수 신호 테스트 (실제 주문 없음)"""
        if not self.is_trading_hours():
            if not self.ignore_trading_hours:
                self.logger.info("⏸️  운영 시간 외 - 매수 테스트 스킵")
                return
            else:
                self.logger.info("🧪 테스트 모드: 운영 시간 외이지만 테스트 진행")
            
        self.logger.info("\n=== 매수 전략 테스트 (60분 주기) ===")
        self.last_buy_check = datetime.now()
        self.test_stats['api_calls'] += 1
        
        # 1. 상승 필터 조건 확인
        filter_passed = self.strategy.check_filter_condition()
        if not filter_passed:
            self.logger.info("❌ 상승 필터 조건 미충족 - 매수 신호 없음")
            self.test_stats['filter_failures'] += 1
            self.display_detailed_decline_analysis()
            return
        
        self.logger.info("✅ 상승 필터 조건 충족")
        
        # 2. 상위 하락 종목 선정
        top_declining = self.strategy.get_top_declining_stocks(3)
        if not top_declining:
            self.logger.info("❌ 하락 종목 없음 - 매수 신호 없음")
            self.display_detailed_decline_analysis()
            return
        
        self.logger.info(f"📉 상위 하락 종목: {', '.join(top_declining)}")
        
        # 각 종목의 하락률 표시
        for symbol in top_declining:
            decline_rate = self.strategy.calculate_decline_rate(symbol)
            if decline_rate and decline_rate > 0:
                self.logger.info(f"   {symbol}: 하락률 {decline_rate:.2%}")
        
        # 3. 각 종목별 매수 신호 확인
        buy_signals_found = False
        for symbol in top_declining:
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                continue
            
            # 매수 수량 계산 (가상)
            quantity = self.strategy.calculate_position_size(symbol, self.virtual_cash)
            
            if quantity > 0:
                total_cost = quantity * current_price
                self.logger.info(f"💰 매수 신호 발견: {symbol}")
                self.logger.info(f"   - 현재가: ${current_price:.2f}")
                self.logger.info(f"   - 수량: {quantity}주")
                self.logger.info(f"   - 예상 비용: ${total_cost:.2f}")
                
                # 🚫 실제 주문은 실행하지 않음 (테스트 모드)
                self.logger.info(f"   - 📝 테스트 모드: 실제 주문 실행 안함")
                
                # 가상 매수 실행
                self.virtual_positions[symbol] = {
                    'quantity': quantity,
                    'avg_price': current_price,
                    'buy_time': datetime.now()
                }
                self.virtual_cash -= total_cost
                buy_signals_found = True
                self.test_stats['buy_signals'] += 1
        
        if not buy_signals_found:
            self.logger.info("❌ 조건을 만족하는 매수 신호 없음")
    
    def test_sell_signals(self):
        """매도 신호 테스트 (실제 주문 없음)"""
        if not self.is_trading_hours():
            if not self.ignore_trading_hours:
                self.logger.info("⏸️  운영 시간 외 - 매도 테스트 스킵")
                return
            else:
                self.logger.info("🧪 테스트 모드: 운영 시간 외이지만 테스트 진행")
            
        self.logger.info("\n=== 매도 전략 테스트 (30분 주기) ===")
        self.last_sell_check = datetime.now()
        self.test_stats['api_calls'] += 1
        
        # 실제 보유종목 조회
        balance = self.api_client.get_account_balance()
        if not balance or not balance.get("positions"):
            self.logger.info("보유 종목 없음")
            return
        
        high_profit_signals = []
        normal_profit_signals = []
        
        for position in balance["positions"]:
            symbol = position["ovrs_pdno"]
            quantity = int(position["ovrs_cblc_qty"])
            avg_buy_price = float(position["pchs_avg_pric"])
            
            if quantity <= 0:
                continue
            
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                continue
            
            profit_rate = self.strategy.calculate_profit_rate(symbol, current_price, avg_buy_price)
            profit_amount = (current_price - avg_buy_price) * quantity
            
            signal_info = {
                'symbol': symbol,
                'quantity': quantity,
                'avg_price': avg_buy_price,
                'current_price': current_price,
                'profit_rate': profit_rate,
                'profit_amount': profit_amount
            }
            
            if profit_rate >= PROFIT_THRESHOLD:  # 5% 이상
                high_profit_signals.append(signal_info)
            elif profit_rate > 0:
                normal_profit_signals.append(signal_info)
        
        # 고수익 매도 신호
        if high_profit_signals:
            self.logger.info("🔥 고수익 매도 신호 (5% 이상):")
            for signal in high_profit_signals:
                self.logger.info(f"   {signal['symbol']}: {signal['quantity']}주")
                self.logger.info(f"   - 매수가: ${signal['avg_price']:.2f}")
                self.logger.info(f"   - 현재가: ${signal['current_price']:.2f}")
                self.logger.info(f"   - 수익률: {signal['profit_rate']:.2%}")
                self.logger.info(f"   - 예상 수익: ${signal['profit_amount']:.2f}")
                self.logger.info(f"   - 📝 테스트 모드: 실제 주문 실행 안함")
                self.test_stats['sell_signals'] += 1
        
        # 일반 매도 신호 (수익률 가장 높은 1개)
        if normal_profit_signals:
            normal_profit_signals.sort(key=lambda x: x['profit_rate'], reverse=True)
            best_signal = normal_profit_signals[0]
            self.logger.info("📈 일반 매도 신호 (최고 수익률):")
            self.logger.info(f"   {best_signal['symbol']}: {best_signal['quantity']}주")
            self.logger.info(f"   - 매수가: ${best_signal['avg_price']:.2f}")
            self.logger.info(f"   - 현재가: ${best_signal['current_price']:.2f}")
            self.logger.info(f"   - 수익률: {best_signal['profit_rate']:.2%}")
            self.logger.info(f"   - 예상 수익: ${best_signal['profit_amount']:.2f}")
            self.logger.info(f"   - 📝 테스트 모드: 실제 주문 실행 안함")
            self.test_stats['sell_signals'] += 1
        
        if not high_profit_signals and not normal_profit_signals:
            self.logger.info("❌ 매도 신호 없음 (모든 종목 손실 중)")
    
    def display_status(self):
        """현재 상태 표시"""
        et_now = datetime.now(self.et_tz)
        trading_status = "운영중" if self.is_trading_hours() else "운영 시간 외"
        
        if self.ignore_trading_hours:
            trading_status += " (🧪 테스트 모드)"
        
        self.logger.info(f"\n⏰ 현재 시간: {et_now.strftime('%Y-%m-%d %H:%M:%S ET')} [{trading_status}]")
        
        # 다음 실행 예정 시간
        if self.last_buy_check:
            next_buy = self.last_buy_check + timedelta(minutes=BUY_INTERVAL_MINUTES)
            self.logger.info(f"   다음 매수 체크: {next_buy.strftime('%H:%M:%S')}")
        
        if self.last_sell_check:
            next_sell = self.last_sell_check + timedelta(minutes=SELL_INTERVAL_MINUTES)
            self.logger.info(f"   다음 매도 체크: {next_sell.strftime('%H:%M:%S')}")
        
        # 필터 종목 상태
        self.logger.info("\n📊 필터 종목 상태:")
        for symbol in FILTER_STOCKS:
            current = self.api_client.get_current_price(symbol)
            prev = self.api_client.get_previous_close(symbol)
            if current and prev:
                change = ((current - prev) / prev) * 100
                decline_rate = self.strategy.calculate_decline_rate(symbol)
                
                status = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
                decline_status = f" (하락률: {decline_rate:.2%})" if decline_rate and decline_rate > 0 else ""
                
                self.logger.info(f"   {symbol}: ${current:.2f} ({status} {change:+.2f}%){decline_status}")
    
    def display_detailed_decline_analysis(self):
        """상세 하락률 분석 표시"""
        self.logger.info("\n📉 하락률 상세 분석:")
        
        watch_list = self.strategy.load_watch_list()
        declining_stocks = []
        
        for symbol in watch_list:
            current = self.api_client.get_current_price(symbol)
            prev = self.api_client.get_previous_close(symbol)
            decline_rate = self.strategy.calculate_decline_rate(symbol)
            
            if current and prev:
                change_rate = ((current - prev) / prev) * 100
                
                status = "📈" if change_rate > 0 else "📉" if change_rate < 0 else "➖"
                
                self.logger.info(f"   {symbol}: ${current:.2f} (전일: ${prev:.2f})")
                self.logger.info(f"      변동률: {status} {change_rate:+.2f}%")
                
                if decline_rate and decline_rate > 0:
                    self.logger.info(f"      하락률: {decline_rate:.2%} ← 매수 대상")
                    declining_stocks.append((symbol, decline_rate))
                else:
                    self.logger.info(f"      하락률: 0% (상승 중)")
            elif current is None and prev is None:
                self.logger.info(f"   {symbol}: 데이터 조회 불가")
            else:
                self.logger.info(f"   {symbol}: 일부 데이터 없음 (현재가: {current}, 전일가: {prev})")
        
        if declining_stocks:
            declining_stocks.sort(key=lambda x: x[1], reverse=True)
            self.logger.info(f"\n🎯 하락 종목 순위: {declining_stocks}")
        else:
            self.logger.info(f"\n❌ 하락 종목 없음 (모든 종목 상승 중)")
    
    def print_test_summary(self):
        """테스트 요약 출력"""
        runtime = datetime.now() - self.test_stats['start_time']
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"🧪 테스트 요약 리포트")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"📊 실행 통계:")
        self.logger.info(f"   - 테스트 시간: {runtime}")
        self.logger.info(f"   - API 호출 횟수: {self.test_stats['api_calls']}")
        self.logger.info(f"   - 매수 신호 발생: {self.test_stats['buy_signals']}회")
        self.logger.info(f"   - 매도 신호 발생: {self.test_stats['sell_signals']}회")
        self.logger.info(f"   - 필터 조건 실패: {self.test_stats['filter_failures']}회")
        
        self.logger.info(f"\n💰 가상 잔고 현황:")
        self.logger.info(f"   - 현금: ${self.virtual_cash:.2f}")
        self.logger.info(f"   - 가상 보유종목: {len(self.virtual_positions)}개")
        
        if self.virtual_positions:
            total_value = self.virtual_cash
            for symbol, pos in self.virtual_positions.items():
                current_price = self.api_client.get_current_price(symbol)
                if current_price:
                    position_value = pos['quantity'] * current_price
                    profit = (current_price - pos['avg_price']) * pos['quantity']
                    total_value += position_value
                    
                    self.logger.info(f"     {symbol}: {pos['quantity']}주 @ ${pos['avg_price']:.2f} "
                                   f"(현재: ${current_price:.2f}, 손익: ${profit:.2f})")
            
            self.logger.info(f"   - 총 포트폴리오 가치: ${total_value:.2f}")
        
        self.logger.info(f"\n🎯 테스트 모드 특징:")
        self.logger.info(f"   - ✅ 실제 주문 실행 없음")
        self.logger.info(f"   - ✅ 전략 로직 완전 테스트")
        self.logger.info(f"   - ✅ 거래시간 무관 테스트 가능")
        self.logger.info(f"   - ✅ API 연결 및 데이터 조회 검증")
    
    def run_once_test(self):
        """한 번만 테스트 실행"""
        self.logger.info("🧪 향상된 전략 테스트 - 단일 실행 모드")
        self.logger.info(f"거래시간 무시: {'ON' if self.ignore_trading_hours else 'OFF'}")
        
        self.display_status()
        self.display_detailed_decline_analysis()
        self.test_buy_signals()
        self.test_sell_signals()
        self.print_test_summary()
    
    def run_continuous_test(self, interval_minutes=5):
        """지속적인 테스트 실행"""
        self.logger.info("🧪 향상된 전략 테스트 - 지속 실행 모드")
        self.logger.info(f"테스트 주기: {interval_minutes}분")
        self.logger.info(f"거래시간 무시: {'ON' if self.ignore_trading_hours else 'OFF'}")
        self.logger.info("실제 주문은 실행되지 않습니다.\n")
        
        try:
            while True:
                self.display_status()
                self.test_buy_signals()
                self.test_sell_signals()
                
                self.logger.info(f"\n다음 테스트까지 {interval_minutes}분 대기...")
                self.logger.info("-" * 70)
                
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            self.logger.info("\n테스트 중단")
            self.print_test_summary()

def main():
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # API 키 확인
    if KIS_APP_KEY == "your_app_key_here":
        logging.error("API 키가 설정되지 않았습니다.")
        return
    
    # 실행 모드 선택
    import sys
    ignore_time = False
    
    if len(sys.argv) > 1:
        if "--ignore-time" in sys.argv:
            ignore_time = True
            sys.argv.remove("--ignore-time")
    
    # 테스터 생성
    tester = EnhancedStrategyTester(ignore_trading_hours=ignore_time)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "once":
            # 한 번만 테스트
            tester.run_once_test()
        else:
            # 사용자 정의 간격으로 테스트
            try:
                interval = int(sys.argv[1])
                tester.run_continuous_test(interval)
            except ValueError:
                print("사용법: python enhanced_strategy_test.py [once|분단위] [--ignore-time]")
    else:
        # 기본값: 한 번만 실행
        tester.run_once_test()

if __name__ == "__main__":
    main() 