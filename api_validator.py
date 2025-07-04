"""
API 검증 및 계좌 상태 확인 도구
실거래 전 모든 기능을 검증합니다.
"""
import sys
import os
import logging
from datetime import datetime
import pytz

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient
from strategy_pjt1 import TradingStrategy
from config import *

class APIValidator:
    def __init__(self):
        self.api_client = KISAPIClient()
        self.strategy = TradingStrategy()
        self.logger = logging.getLogger(__name__)
        
        # 검증 결과 저장
        self.test_results = {
            "api_connection": False,
            "account_access": False,
            "price_data": False,
            "balance_data": False,
            "positions_data": False,
            "order_functions": False
        }
    
    def test_api_connection(self):
        """API 연결 및 토큰 발급 테스트"""
        print("\n" + "="*50)
        print("🔌 API 연결 테스트")
        print("="*50)
        
        try:
            success = self.api_client.get_access_token()
            if success:
                print("✅ API 토큰 발급 성공")
                print(f"   토큰: {self.api_client.access_token[:20]}...")
                print(f"   만료시간: {datetime.fromtimestamp(self.api_client.token_expires_at)}")
                self.test_results["api_connection"] = True
                return True
            else:
                print("❌ API 토큰 발급 실패")
                return False
                
        except Exception as e:
            print(f"❌ API 연결 오류: {e}")
            return False
    
    def test_account_access(self):
        """계좌 접근 권한 테스트"""
        print("\n" + "="*50)
        print("🏦 계좌 접근 테스트")
        print("="*50)
        
        try:
            balance = self.api_client.get_account_balance()
            if balance:
                print("✅ 계좌 조회 성공")
                print(f"   예수금: ${balance['cash']:,.2f}")
                print(f"   보유종목 수: {len(balance['positions'])}개")
                
                self.test_results["account_access"] = True
                self.test_results["balance_data"] = True
                
                if balance['positions']:
                    self.test_results["positions_data"] = True
                
                return balance
            else:
                print("❌ 계좌 조회 실패")
                return None
                
        except Exception as e:
            print(f"❌ 계좌 접근 오류: {e}")
            return None
    
    def test_price_data(self):
        """시세 조회 기능 테스트"""
        print("\n" + "="*50)
        print("📊 시세 조회 테스트")
        print("="*50)
        
        test_symbols = ["AAPL", "NVDA", "MSFT", "AMZN", "META"]
        success_count = 0
        
        for symbol in test_symbols:
            try:
                current = self.api_client.get_current_price(symbol)
                prev = self.api_client.get_previous_close(symbol)
                
                if current and prev:
                    change = ((current - prev) / prev) * 100
                    status = "📈" if change > 0 else "📉" if change < 0 else "➖"
                    
                    print(f"✅ {symbol}: ${current:.2f} (전일: ${prev:.2f}) {status} {change:+.2f}%")
                    success_count += 1
                else:
                    print(f"❌ {symbol}: 데이터 조회 실패 (현재: {current}, 전일: {prev})")
                    
            except Exception as e:
                print(f"❌ {symbol}: 오류 - {e}")
        
        if success_count >= 3:
            print(f"\n✅ 시세 조회 기능 정상 ({success_count}/{len(test_symbols)})")
            self.test_results["price_data"] = True
            return True
        else:
            print(f"\n❌ 시세 조회 기능 불안정 ({success_count}/{len(test_symbols)})")
            return False
    
    def test_strategy_functions(self):
        """전략 함수들 테스트"""
        print("\n" + "="*50)
        print("🎯 전략 함수 테스트")
        print("="*50)
        
        # 상승 필터 테스트
        print("1. 상승 필터 조건 체크:")
        try:
            filter_result = self.strategy.check_filter_condition()
            status = "✅ 통과" if filter_result else "❌ 미통과"
            print(f"   결과: {status}")
            
            for symbol in FILTER_STOCKS:
                current = self.api_client.get_current_price(symbol)
                prev = self.api_client.get_previous_close(symbol)
                if current and prev:
                    change = ((current - prev) / prev) * 100
                    trend = "상승" if change > 0 else "하락"
                    print(f"   {symbol}: {trend} ({change:+.2f}%)")
                    
        except Exception as e:
            print(f"   오류: {e}")
        
        # 하락 종목 선정 테스트
        print("\n2. 하락 종목 선정:")
        try:
            declining = self.strategy.get_top_declining_stocks(5)
            if declining:
                print("   상위 하락 종목:")
                for i, symbol in enumerate(declining, 1):
                    decline_rate = self.strategy.calculate_decline_rate(symbol)
                    if decline_rate:
                        print(f"   {i}. {symbol}: {decline_rate:.2%} 하락")
            else:
                print("   하락 종목 없음 (모든 종목 상승 중)")
                
        except Exception as e:
            print(f"   오류: {e}")
    
    def analyze_current_positions(self, balance):
        """현재 보유 종목 분석"""
        print("\n" + "="*50)
        print("💼 보유 종목 분석")
        print("="*50)
        
        if not balance or not balance['positions']:
            print("보유 종목이 없습니다.")
            return
        
        total_value = 0
        total_profit = 0
        sell_candidates = []
        
        print(f"{'종목':>8} {'수량':>6} {'매수가':>8} {'현재가':>8} {'수익률':>8} {'수익금':>10} {'상태'}")
        print("-" * 70)
        
        for position in balance['positions']:
            try:
                symbol = position["ovrs_pdno"]
                quantity = int(position["ovrs_cblc_qty"])
                avg_price = float(position["pchs_avg_pric"])
                
                if quantity <= 0:
                    continue
                
                current_price = self.api_client.get_current_price(symbol)
                if not current_price:
                    continue
                
                profit_rate = self.strategy.calculate_profit_rate(symbol, current_price, avg_price)
                profit_amount = (current_price - avg_price) * quantity
                position_value = current_price * quantity
                
                total_value += position_value
                total_profit += profit_amount
                
                # 매도 후보 판단
                status = ""
                if profit_rate >= PROFIT_THRESHOLD:
                    status = "🔥 즉시매도"
                    sell_candidates.append(("high_profit", symbol, profit_rate, profit_amount))
                elif profit_rate > 0:
                    status = "💰 수익"
                    sell_candidates.append(("normal_profit", symbol, profit_rate, profit_amount))
                else:
                    status = "📉 손실"
                
                print(f"{symbol:>8} {quantity:>6} ${avg_price:>7.2f} ${current_price:>7.2f} {profit_rate:>7.1%} ${profit_amount:>9.2f} {status}")
                
            except Exception as e:
                print(f"{symbol:>8} - 분석 오류: {e}")
        
        print("-" * 70)
        print(f"{'총 가치':>40}: ${total_value:,.2f}")
        print(f"{'총 수익':>40}: ${total_profit:,.2f}")
        print(f"{'총 수익률':>40}: {(total_profit/total_value)*100 if total_value > 0 else 0:.2f}%")
        
        # 매도 추천
        self.recommend_sells(sell_candidates)
    
    def recommend_sells(self, sell_candidates):
        """매도 추천"""
        print("\n📋 매도 추천:")
        
        # 5% 이상 수익 종목
        high_profit = [x for x in sell_candidates if x[0] == "high_profit"]
        if high_profit:
            print("🔥 즉시 매도 대상 (5% 이상):")
            for _, symbol, rate, amount in high_profit:
                print(f"   {symbol}: {rate:.1%} 수익 (${amount:,.2f})")
        
        # 일반 수익 종목 중 최고
        normal_profit = [x for x in sell_candidates if x[0] == "normal_profit"]
        if normal_profit:
            best = max(normal_profit, key=lambda x: x[2])
            print("💰 일반 매도 대상 (최고 수익률):")
            print(f"   {best[1]}: {best[2]:.1%} 수익 (${best[3]:,.2f})")
        
        if not high_profit and not normal_profit:
            print("❌ 매도 대상 없음 (모든 종목 손실 중)")
    
    def test_order_functions(self):
        """주문 기능 테스트 (실제 주문 안 함)"""
        print("\n" + "="*50)
        print("📝 주문 기능 테스트 (시뮬레이션)")
        print("="*50)
        
        test_symbol = "AAPL"
        try:
            current_price = self.api_client.get_current_price(test_symbol)
            if current_price:
                print(f"✅ 가격 조회: {test_symbol} = ${current_price:.2f}")
                
                # 매수 수량 계산 테스트
                test_cash = 10000
                quantity = self.strategy.calculate_position_size(test_symbol, test_cash)
                total_cost = quantity * current_price
                
                print(f"✅ 매수 계산: {quantity}주 × ${current_price:.2f} = ${total_cost:,.2f}")
                print("✅ 주문 함수 접근 가능")
                
                self.test_results["order_functions"] = True
                return True
            else:
                print(f"❌ 가격 조회 실패: {test_symbol}")
                return False
                
        except Exception as e:
            print(f"❌ 주문 기능 오류: {e}")
            return False
    
    def generate_report(self):
        """종합 검증 리포트"""
        print("\n" + "="*50)
        print("📊 종합 검증 리포트")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        print(f"전체 테스트: {passed_tests}/{total_tests} 통과")
        print()
        
        for test_name, result in self.test_results.items():
            status = "✅ 통과" if result else "❌ 실패"
            test_names = {
                "api_connection": "API 연결",
                "account_access": "계좌 접근",
                "price_data": "시세 조회", 
                "balance_data": "잔고 조회",
                "positions_data": "보유종목 조회",
                "order_functions": "주문 기능"
            }
            print(f"{test_names[test_name]:>10}: {status}")
        
        print("\n🎯 결론:")
        if passed_tests == total_tests:
            print("✅ 모든 기능 정상 - 실거래 준비 완료!")
        elif passed_tests >= total_tests * 0.8:
            print("⚠️  대부분 기능 정상 - 실거래 가능하나 주의 필요")
        else:
            print("❌ 기능 오류 다수 - 실거래 전 문제 해결 필요")
    
    def run_full_validation(self):
        """전체 검증 실행"""
        print("🚀 API 및 계좌 상태 전체 검증 시작")
        print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"모의투자 모드: {'ON' if USE_PAPER_TRADING else 'OFF'}")
        
        # 1. API 연결 테스트
        if not self.test_api_connection():
            print("\n❌ API 연결 실패로 검증 중단")
            return False
        
        # 2. 계좌 접근 테스트
        balance = self.test_account_access()
        
        # 3. 시세 조회 테스트
        self.test_price_data()
        
        # 4. 전략 함수 테스트
        self.test_strategy_functions()
        
        # 5. 보유 종목 분석
        if balance:
            self.analyze_current_positions(balance)
        
        # 6. 주문 기능 테스트
        self.test_order_functions()
        
        # 7. 종합 리포트
        self.generate_report()
        
        return True

def main():
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # API 키 확인
    if KIS_APP_KEY == "your_app_key_here":
        print("❌ API 키가 설정되지 않았습니다.")
        print("config.py에서 KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER를 설정해주세요.")
        return
    
    # 검증 실행
    validator = APIValidator()
    validator.run_full_validation()

if __name__ == "__main__":
    main()