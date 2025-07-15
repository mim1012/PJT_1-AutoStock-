"""
실제 모의투자 API 매수/매도 테스트
⚠️ 주의: 실제 모의투자 API를 사용하지만 가상 돈으로 안전합니다!
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from strategy_pjt1 import TradingStrategy
from order_manager import OrderManager
from config import *
from datetime import datetime
import time

class RealPaperTradingTester:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        self.strategy = TradingStrategy()
        self.order_manager = OrderManager()
        
        # 테스트 설정
        self.test_mode = True  # True: 주문 전 확인, False: 자동 실행
        self.max_test_orders = 2  # 최대 테스트 주문 수
        self.test_results = []
        
        print("🔥 실제 모의투자 API 매수/매도 테스트")
        print("="*50)
        print(f"💡 모의투자 모드: {'ON' if USE_PAPER_TRADING else 'OFF'}")
        if not USE_PAPER_TRADING:
            print("⚠️ 경고: 실제 돈으로 거래됩니다!")
            return
        print("✅ 모의투자 모드로 안전하게 테스트합니다.")
        print("="*50)
    
    def check_prerequisites(self):
        """테스트 전 필수 조건 확인"""
        print("\n🔍 테스트 전 필수 조건 확인")
        print("-"*30)
        
        # 1. 모의투자 모드 확인
        if not USE_PAPER_TRADING:
            print("❌ 실제 거래 모드입니다. 안전을 위해 테스트 중단!")
            return False
        
        print("✅ 모의투자 모드 확인")
        
        # 2. API 토큰 확인
        if not self.api_client.ensure_token_valid():
            print("❌ API 토큰 문제")
            return False
        
        print("✅ API 토큰 유효")
        
        # 3. 계좌 조회 확인
        balance = self.api_client.get_account_balance()
        if not balance:
            print("❌ 계좌 조회 실패")
            return False
        
        print("✅ 계좌 조회 성공")
        print(f"   💰 예수금: ${balance['cash']:,.2f}")
        print(f"   📦 보유종목: {len(balance['positions'])}개")
        
        return True
    
    def test_single_buy_order(self, test_symbol="AAPL", test_quantity=1):
        """단일 매수 주문 테스트"""
        print(f"\n🛒 단일 매수 주문 테스트: {test_symbol}")
        print("-"*40)
        
        # 현재가 조회
        current_price = self.api_client.get_current_price(test_symbol)
        if not current_price:
            print(f"❌ {test_symbol} 현재가 조회 실패")
            return False
        
        total_cost = current_price * test_quantity
        print(f"📊 주문 정보:")
        print(f"   종목: {test_symbol}")
        print(f"   수량: {test_quantity}주")
        print(f"   현재가: ${current_price:.2f}")
        print(f"   총 비용: ${total_cost:.2f}")
        
        if self.test_mode:
            confirm = input(f"\n실제로 {test_symbol} {test_quantity}주를 모의투자로 매수하시겠습니까? (y/n): ")
            if confirm.lower() != 'y':
                print("❌ 사용자가 취소했습니다.")
                return False
        
        # 실제 모의투자 매수 주문
        print("🔄 매수 주문 실행 중...")
        order_id = self.order_manager.place_order_with_tracking(
            test_symbol, test_quantity, current_price, "buy"
        )
        
        if order_id:
            print(f"✅ 매수 주문 성공!")
            print(f"   주문번호: {order_id}")
            print(f"   주문시간: {datetime.now().strftime('%H:%M:%S')}")
            
            self.test_results.append({
                'type': 'BUY',
                'symbol': test_symbol,
                'quantity': test_quantity,
                'price': current_price,
                'order_id': order_id,
                'success': True
            })
            return True
        else:
            print("❌ 매수 주문 실패")
            self.test_results.append({
                'type': 'BUY',
                'symbol': test_symbol,
                'success': False
            })
            return False
    
    def test_single_sell_order(self):
        """단일 매도 주문 테스트 (보유 종목 중 선택)"""
        print("\n💰 단일 매도 주문 테스트")
        print("-"*40)
        
        # 보유 종목 조회
        balance = self.api_client.get_account_balance()
        if not balance or not balance['positions']:
            print("❌ 매도할 보유 종목이 없습니다.")
            return False
        
        # 매도 가능한 종목 선택
        sell_candidates = []
        for position in balance['positions']:
            symbol = position["ovrs_pdno"]
            quantity = int(position["ovrs_cblc_qty"])
            avg_price = float(position["pchs_avg_pric"])
            
            if quantity > 0:
                current_price = self.api_client.get_current_price(symbol)
                if current_price:
                    profit_rate = ((current_price - avg_price) / avg_price) * 100
                    sell_candidates.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'profit_rate': profit_rate
                    })
        
        if not sell_candidates:
            print("❌ 매도 가능한 종목이 없습니다.")
            return False
        
        # 첫 번째 종목 선택 (또는 가장 수익률이 높은 것)
        target = max(sell_candidates, key=lambda x: x['profit_rate'])
        
        print(f"📊 매도 대상 종목:")
        print(f"   종목: {target['symbol']}")
        print(f"   수량: {target['quantity']}주")
        print(f"   매수가: ${target['avg_price']:.2f}")
        print(f"   현재가: ${target['current_price']:.2f}")
        print(f"   수익률: {target['profit_rate']:+.1f}%")
        
        if self.test_mode:
            confirm = input(f"\n실제로 {target['symbol']} {target['quantity']}주를 모의투자로 매도하시겠습니까? (y/n): ")
            if confirm.lower() != 'y':
                print("❌ 사용자가 취소했습니다.")
                return False
        
        # 실제 모의투자 매도 주문
        print("🔄 매도 주문 실행 중...")
        order_id = self.order_manager.place_order_with_tracking(
            target['symbol'], target['quantity'], target['current_price'], "sell"
        )
        
        if order_id:
            profit_amount = (target['current_price'] - target['avg_price']) * target['quantity']
            print(f"✅ 매도 주문 성공!")
            print(f"   주문번호: {order_id}")
            print(f"   주문시간: {datetime.now().strftime('%H:%M:%S')}")
            print(f"   예상 수익: ${profit_amount:+.2f}")
            
            self.test_results.append({
                'type': 'SELL',
                'symbol': target['symbol'],
                'quantity': target['quantity'],
                'price': target['current_price'],
                'order_id': order_id,
                'expected_profit': profit_amount,
                'success': True
            })
            return True
        else:
            print("❌ 매도 주문 실패")
            self.test_results.append({
                'type': 'SELL',
                'symbol': target['symbol'],
                'success': False
            })
            return False
    
    def test_strategy_buy_logic(self):
        """전략 기반 매수 로직 테스트"""
        print("\n🧠 전략 기반 매수 로직 테스트")
        print("-"*40)
        
        # 필터 조건 확인
        filter_passed = self.strategy.check_filter_condition()
        print(f"📊 상승 필터 조건: {'✅ 통과' if filter_passed else '❌ 미통과'}")
        
        if not filter_passed:
            print("❌ 상승 필터 조건 미충족으로 매수 중단")
            return False
        
        # 하락 종목 선정
        declining_stocks = self.strategy.get_top_declining_stocks(3)
        if not declining_stocks:
            print("❌ 하락 종목 없음")
            return False
        
        print(f"📉 하락 종목: {', '.join(declining_stocks)}")
        
        # 첫 번째 종목으로 테스트
        test_symbol = declining_stocks[0]
        current_price = self.api_client.get_current_price(test_symbol)
        
        if not current_price:
            print(f"❌ {test_symbol} 현재가 조회 실패")
            return False
        
        # 매수 수량 계산
        balance = self.api_client.get_account_balance()
        quantity = self.strategy.calculate_position_size(test_symbol, balance['cash'])
        
        if quantity <= 0:
            print("❌ 매수 가능 수량 없음")
            return False
        
        print(f"💰 매수 계획:")
        print(f"   종목: {test_symbol}")
        print(f"   수량: {quantity}주")
        print(f"   현재가: ${current_price:.2f}")
        print(f"   총 비용: ${quantity * current_price:.2f}")
        
        if self.test_mode:
            confirm = input(f"\n전략에 따라 {test_symbol}를 모의투자로 매수하시겠습니까? (y/n): ")
            if confirm.lower() != 'y':
                print("❌ 사용자가 취소했습니다.")
                return False
        
        # 실제 매수 실행
        return self.test_single_buy_order(test_symbol, quantity)
    
    def run_comprehensive_test(self):
        """종합 테스트 실행"""
        print("\n🚀 종합 모의투자 테스트 실행")
        print("="*50)
        
        # 1. 전제 조건 확인
        if not self.check_prerequisites():
            print("❌ 전제 조건 미충족으로 테스트 중단")
            return
        
        # 2. 테스트 메뉴
        print("\n🎯 테스트 메뉴:")
        print("   1. 단일 매수 주문 테스트")
        print("   2. 단일 매도 주문 테스트")
        print("   3. 전략 기반 매수 테스트")
        print("   4. 모든 테스트 실행")
        print("   0. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == '1':
            self.test_single_buy_order()
        elif choice == '2':
            self.test_single_sell_order()
        elif choice == '3':
            self.test_strategy_buy_logic()
        elif choice == '4':
            self.test_single_buy_order("AAPL", 1)
            time.sleep(2)
            self.test_single_sell_order()
            time.sleep(2)
            self.test_strategy_buy_logic()
        elif choice == '0':
            print("👋 테스트 종료")
            return
        else:
            print("❌ 잘못된 선택")
            return
        
        # 3. 결과 요약
        self.print_test_summary()
    
    def print_test_summary(self):
        """테스트 결과 요약"""
        print("\n📊 테스트 결과 요약")
        print("="*40)
        
        if not self.test_results:
            print("ℹ️ 실행된 테스트가 없습니다.")
            return
        
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r['success']])
        
        print(f"📋 총 테스트: {total_tests}개")
        print(f"✅ 성공: {successful_tests}개")
        print(f"❌ 실패: {total_tests - successful_tests}개")
        
        print("\n📜 테스트 내역:")
        for i, result in enumerate(self.test_results):
            status = "✅" if result['success'] else "❌"
            symbol = result.get('symbol', 'N/A')
            order_type = result['type']
            
            if result['success']:
                order_id = result.get('order_id', 'N/A')
                print(f"   {i+1}. {status} {order_type} {symbol} (주문번호: {order_id})")
            else:
                print(f"   {i+1}. {status} {order_type} {symbol} (실패)")

if __name__ == "__main__":
    tester = RealPaperTradingTester()
    tester.run_comprehensive_test() 