"""
최종 전략 테스트 - 토큰 재사용으로 안정적인 테스트
"""
import sys
import os
import logging
from datetime import datetime, timedelta
import pytz

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from strategy_pjt1 import TradingStrategy
from config import *

class FinalStrategyTester:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        self.strategy = TradingStrategy()
        # 전략에 개선된 클라이언트 적용
        self.strategy.api_client = self.api_client
        
        self.logger = logging.getLogger(__name__)
        self.et_tz = pytz.timezone('US/Eastern')
    
    def is_trading_hours(self):
        """현재 시간이 운영 시간인지 확인"""
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
    
    def get_time_until_trading(self):
        """거래시간까지 남은 시간 계산"""
        try:
            et_now = datetime.now(self.et_tz)
            
            # 주말인 경우 다음 월요일까지
            if et_now.weekday() >= 5:  # 토요일, 일요일
                days_until_monday = 7 - et_now.weekday()
                next_monday = et_now + timedelta(days=days_until_monday)
                trading_start = next_monday.replace(
                    hour=int(TRADING_START_TIME.split(':')[0]),
                    minute=int(TRADING_START_TIME.split(':')[1]),
                    second=0,
                    microsecond=0
                )
                return trading_start - et_now
            
            # 평일인 경우
            today_start = et_now.replace(
                hour=int(TRADING_START_TIME.split(':')[0]),
                minute=int(TRADING_START_TIME.split(':')[1]),
                second=0,
                microsecond=0
            )
            today_end = et_now.replace(
                hour=int(TRADING_END_TIME.split(':')[0]),
                minute=int(TRADING_END_TIME.split(':')[1]),
                second=0,
                microsecond=0
            )
            
            # 거래시간 전
            if et_now < today_start:
                return today_start - et_now
            
            # 거래시간 후 - 다음날까지
            if et_now > today_end:
                tomorrow_start = today_start + timedelta(days=1)
                return tomorrow_start - et_now
            
            # 거래시간 중
            return timedelta(0)
            
        except Exception as e:
            self.logger.error(f"거래시간 계산 오류: {e}")
            return timedelta(0)
    
    def print_trading_time_status(self):
        """거래시간 상태 출력"""
        try:
            et_now = datetime.now(self.et_tz)
            
            if self.is_trading_hours():
                print(f"🟢 현재 거래시간 중 - {et_now.strftime('%Y-%m-%d %H:%M:%S ET')}")
                return True
            else:
                time_until = self.get_time_until_trading()
                
                if time_until.total_seconds() > 0:
                    hours = int(time_until.total_seconds() // 3600)
                    minutes = int((time_until.total_seconds() % 3600) // 60)
                    
                    if et_now.weekday() >= 5:
                        print(f"🔴 주말 - 다음 거래시간까지 {hours}시간 {minutes}분 남음")
                    else:
                        print(f"🟡 거래시간 외 - 다음 거래시간까지 {hours}시간 {minutes}분 남음")
                        print(f"   현재: {et_now.strftime('%H:%M:%S ET')}, "
                              f"거래시간: {TRADING_START_TIME}~{TRADING_END_TIME} ET")
                
                return False
            
        except Exception as e:
            self.logger.error(f"거래시간 상태 출력 오류: {e}")
            return False
    
    def test_filter_condition(self):
        """상승 필터 조건 테스트"""
        print("\n=== 🔍 상승 필터 조건 테스트 ===")
        
        filter_stocks = self.strategy.load_filter_stocks()  # 파일에서 로드
        print(f"필터 종목: {filter_stocks}")
        
        all_rising = True
        
        for symbol in filter_stocks:
            current = self.api_client.get_current_price(symbol)
            prev = self.api_client.get_previous_close(symbol)
            
            if current and prev:
                change_rate = ((current - prev) / prev) * 100
                status = "🔺 상승" if change_rate > 0 else "🔻 하락" if change_rate < 0 else "➖ 동일"
                
                print(f"   {symbol}: ${current:.2f} (전일: ${prev:.2f}) → {change_rate:+.2f}% {status}")
                
                if change_rate <= 0:
                    all_rising = False
            else:
                print(f"   {symbol}: ❌ 가격 조회 실패")
                all_rising = False
        
        print(f"\n필터 결과: {'✅ 조건 충족 (모든 종목 상승)' if all_rising else '❌ 조건 미충족 (일부 종목 하락/동일)'}")
        return all_rising
    
    def test_declining_stocks(self):
        """하락 종목 선정 테스트"""
        print("\n=== 📉 하락 종목 선정 테스트 ===")
        
        watch_list = self.strategy.load_watch_list()
        print(f"관심종목: {watch_list}")
        
        declining_stocks = []
        
        for symbol in watch_list:
            decline_rate = self.strategy.calculate_decline_rate(symbol)
            current = self.api_client.get_current_price(symbol)
            prev = self.api_client.get_previous_close(symbol)
            
            if current and prev and decline_rate and decline_rate > 0:
                declining_stocks.append((symbol, decline_rate))
                print(f"   {symbol}: ${current:.2f} (전일: ${prev:.2f}) → 하락률 {decline_rate:.2%} 📉")
            elif current and prev:
                change_rate = ((current - prev) / prev) * 100
                status = "🔺" if change_rate > 0 else "🔻" if change_rate < 0 else "➖"
                print(f"   {symbol}: ${current:.2f} (전일: ${prev:.2f}) → {change_rate:+.2f}% {status} (하락 아님)")
            else:
                print(f"   {symbol}: ❌ 가격 조회 실패")
        
        # 하락률 순으로 정렬
        declining_stocks.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n📊 하락 종목 순위:")
        if declining_stocks:
            top_3 = declining_stocks[:3]
            for i, (symbol, rate) in enumerate(top_3, 1):
                print(f"   {i}. {symbol}: 하락률 {rate:.2%} 📉")
            return [symbol for symbol, _ in top_3]
        else:
            print("   ❌ 하락 종목 없음")
            return []
    
    def test_buy_strategy(self):
        """매수 전략 완전 테스트"""
        print("\n=== 💰 매수 전략 완전 테스트 ===")
        
        # 1. 필터 조건 확인
        filter_passed = self.test_filter_condition()
        
        if not filter_passed:
            print("❌ 상승 필터 조건 미충족 - 매수 신호 없음")
            return False
        
        # 2. 하락 종목 선정
        top_declining = self.test_declining_stocks()
        
        if not top_declining:
            print("❌ 하락 종목 없음 - 매수 신호 없음")
            return False
        
        # 3. 매수 수량 및 비용 계산
        print(f"\n💰 매수 시뮬레이션:")
        balance = self.api_client.get_account_balance()
        
        if not balance:
            print("❌ 계좌 조회 실패")
            return False
        
        cash = balance['cash']
        print(f"💵 예수금: ${cash:.2f}")
        
        if cash <= 0:
            print("❌ 예수금 부족 - 매수 불가")
            return False
        
        total_cost = 0
        for symbol in top_declining:
            current_price = self.api_client.get_current_price(symbol)
            if current_price:
                quantity = self.strategy.calculate_position_size(symbol, cash)
                cost = quantity * current_price
                total_cost += cost
                
                print(f"   📊 {symbol}: {quantity}주 × ${current_price:.2f} = ${cost:.2f}")
        
        print(f"💰 총 매수 비용: ${total_cost:.2f}")
        
        if total_cost <= cash:
            print("✅ 매수 신호 발생 - 실행 가능")
            return True
        else:
            print("❌ 예수금 부족 - 매수 불가")
            return False
    
    def test_sell_strategy(self):
        """매도 전략 완전 테스트"""
        print("\n=== 📤 매도 전략 완전 테스트 ===")
        
        balance = self.api_client.get_account_balance()
        if not balance or not balance['positions']:
            print("❌ 보유 종목 없음")
            return False
        
        high_profit_targets = []
        normal_profit_targets = []
        
        for position in balance['positions']:
            symbol = position["ovrs_pdno"]
            quantity = int(position["ovrs_cblc_qty"])
            avg_price = float(position["pchs_avg_pric"])
            
            if quantity <= 0:
                continue
            
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                print(f"   ⚠️ {symbol}: 현재가 조회 실패 - 매도 대상 제외")
                continue
            
            profit_rate = ((current_price - avg_price) / avg_price)
            profit_amount = (current_price - avg_price) * quantity
            
            status = "🔥" if profit_rate >= PROFIT_THRESHOLD else "💰" if profit_rate > 0 else "📉"
            print(f"   {status} {symbol}: {quantity}주 @ ${avg_price:.2f} → ${current_price:.2f} "
                  f"({profit_rate:.1%}, ${profit_amount:+.2f})")
            
            if profit_rate >= PROFIT_THRESHOLD:  # 5% 이상
                high_profit_targets.append((symbol, profit_rate, profit_amount))
            elif profit_rate > 0:
                normal_profit_targets.append((symbol, profit_rate, profit_amount))
        
        # 매도 신호 판정
        if high_profit_targets:
            print(f"\n🔥 고수익 매도 신호 ({len(high_profit_targets)}개):")
            for symbol, rate, amount in high_profit_targets:
                print(f"   🔥 {symbol}: {rate:.1%} 수익 (${amount:+.2f})")
            return True
        
        elif normal_profit_targets:
            best = max(normal_profit_targets, key=lambda x: x[1])
            print(f"\n💰 일반 매도 신호:")
            print(f"   💰 {best[0]}: {best[1]:.1%} 수익 (${best[2]:+.2f})")
            return True
        
        else:
            print("\n❌ 매도 신호 없음 (모든 종목 손실 중)")
            return False
    
    def run_complete_test(self):
        """완전한 전략 테스트 실행"""
        print("🚀 최종 전략 완전 테스트")
        print(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # 거래시간 상태 출력
        is_trading_time = self.print_trading_time_status()
        
        # 토큰 확인
        if not self.api_client.ensure_token_valid():
            print("❌ API 토큰 문제")
            return False
        
        print("✅ API 토큰 준비 완료")
        
        # 계좌 상태 확인
        balance = self.api_client.get_account_balance()
        if balance:
            print(f"💰 계좌 상태: 예수금 ${balance['cash']:.2f}, 보유종목 {len(balance['positions'])}개")
        else:
            print("❌ 계좌 조회 실패")
            return False
        
        # 매도 전략 테스트
        sell_signal = self.test_sell_strategy()
        
        # 매수 전략 테스트
        buy_signal = self.test_buy_strategy()
        
        # 최종 결과
        print("\n" + "="*70)
        print("📋 최종 테스트 결과")
        print("="*70)
        print(f"🕐 거래시간: {'✅ 거래시간 중' if is_trading_time else '❌ 거래시간 외'}")
        print(f"📤 매도 신호: {'✅ 발생' if sell_signal else '❌ 없음'}")
        print(f"📥 매수 신호: {'✅ 발생' if buy_signal else '❌ 없음'}")
        
        if sell_signal or buy_signal:
            print("\n🎯 결론: 전략이 정상 작동하며 신호가 감지되었습니다!")
            if not is_trading_time:
                print("⚠️ 단, 현재 거래시간이 아니므로 실제 거래는 거래시간에만 실행됩니다.")
            print("실제 매매를 원한다면 start_auto_trading.py를 사용하세요.")
        else:
            print("\n⏸️ 결론: 현재 매수/매도 조건을 만족하는 상황이 아닙니다.")
        
        return True

def main():
    # 로깅 설정 (간단하게)
    logging.basicConfig(level=logging.WARNING)
    
    tester = FinalStrategyTester()
    tester.run_complete_test()

if __name__ == "__main__":
    main() 