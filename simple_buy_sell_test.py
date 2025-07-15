"""
매수/매도 메서드 간단 테스트
토큰 문제 해결 + 기본 기능 검증
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from config import *
from datetime import datetime

class SimpleBuySellTester:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        
        print("🎯 매수/매도 메서드 간단 테스트")
        print("="*40)
        print(f"모의투자 모드: {'ON' if USE_PAPER_TRADING else 'OFF'}")
        
        if not USE_PAPER_TRADING:
            print("⚠️ 실제 거래 모드! 주의하세요!")
        else:
            print("✅ 모의투자 모드 (안전)")
        print("="*40)
    
    def fix_token_issue(self):
        """토큰 문제 해결"""
        print("\n🔧 토큰 문제 해결 중...")
        
        # 1. 기존 토큰 삭제
        try:
            if os.path.exists('api_token.json'):
                print("🗑️ 기존 토큰 파일 삭제")
                os.remove('api_token.json')
        except:
            pass
        
        # 2. 새 토큰 발급
        print("🔑 새 토큰 발급 시도...")
        success = self.api_client.ensure_token_valid()
        
        if success:
            print("✅ 토큰 발급 성공!")
            return True
        else:
            print("❌ 토큰 발급 실패!")
            return False
    
    def test_account_balance(self):
        """계좌 잔고 테스트"""
        print("\n💰 계좌 잔고 조회 테스트")
        print("-" * 30)
        
        try:
            balance = self.api_client.get_account_balance()
            
            if balance:
                print("✅ 계좌 조회 성공!")
                print(f"   💵 예수금: ${balance['cash']:,.2f}")
                print(f"   📦 보유종목: {len(balance['positions'])}개")
                
                # 보유 종목 간단 출력
                if balance['positions']:
                    print("\n📋 보유 종목:")
                    for i, pos in enumerate(balance['positions'][:3]):  # 최대 3개만
                        symbol = pos.get('ovrs_pdno', 'N/A')
                        qty = pos.get('ovrs_cblc_qty', '0')
                        avg_price = float(pos.get('pchs_avg_pric', '0'))
                        
                        print(f"   {i+1}. {symbol}: {qty}주 @ ${avg_price:.2f}")
                
                return balance
            else:
                print("❌ 계좌 조회 실패")
                return None
                
        except Exception as e:
            print(f"❌ 계좌 조회 오류: {e}")
            return None
    
    def test_current_price(self, symbol="AAPL"):
        """현재가 조회 테스트"""
        print(f"\n📊 현재가 조회 테스트 ({symbol})")
        print("-" * 30)
        
        try:
            price = self.api_client.get_current_price(symbol)
            
            if price:
                print(f"✅ {symbol} 현재가: ${price:.2f}")
                return price
            else:
                print(f"❌ {symbol} 현재가 조회 실패")
                return None
                
        except Exception as e:
            print(f"❌ 현재가 조회 오류: {e}")
            return None
    
    def test_buy_method(self, symbol="AAPL", quantity=1):
        """매수 메서드 테스트"""
        print(f"\n🛒 매수 메서드 테스트 ({symbol})")
        print("-" * 30)
        
        # 현재가 조회
        current_price = self.test_current_price(symbol)
        if not current_price:
            print("❌ 현재가 조회 실패로 매수 테스트 중단")
            return False
        
        total_cost = current_price * quantity
        print(f"💰 매수 예정:")
        print(f"   종목: {symbol}")
        print(f"   수량: {quantity}주")
        print(f"   예상 비용: ${total_cost:.2f}")
        
        # 사용자 확인
        confirm = input(f"\n실제로 {symbol} {quantity}주를 매수하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ 사용자 취소")
            return False
        
        try:
            # 매수 주문 실행
            print("🔄 매수 주문 실행 중...")
            order_id = self.api_client.place_order(symbol, quantity, current_price, "buy")
            
            if order_id:
                print(f"✅ 매수 주문 성공!")
                print(f"   주문번호: {order_id}")
                print(f"   주문시간: {datetime.now().strftime('%H:%M:%S')}")
                return True
            else:
                print("❌ 매수 주문 실패")
                return False
                
        except Exception as e:
            print(f"❌ 매수 주문 오류: {e}")
            return False
    
    def test_sell_method(self):
        """매도 메서드 테스트"""
        print(f"\n💰 매도 메서드 테스트")
        print("-" * 30)
        
        # 계좌 조회
        balance = self.test_account_balance()
        if not balance or not balance['positions']:
            print("❌ 매도할 보유 종목 없음")
            return False
        
        # 매도 가능 종목 선택
        print("\n📋 매도 가능 종목:")
        valid_positions = []
        
        for i, pos in enumerate(balance['positions']):
            symbol = pos.get('ovrs_pdno', 'N/A')
            qty = int(pos.get('ovrs_cblc_qty', '0'))
            avg_price = float(pos.get('pchs_avg_pric', '0'))
            
            if qty > 0:
                current_price = self.api_client.get_current_price(symbol)
                if current_price:
                    profit_rate = ((current_price - avg_price) / avg_price) * 100
                    valid_positions.append({
                        'symbol': symbol,
                        'quantity': qty,
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'profit_rate': profit_rate
                    })
                    
                    print(f"   {len(valid_positions)}. {symbol}: {qty}주 @ ${avg_price:.2f} → ${current_price:.2f} ({profit_rate:+.1f}%)")
        
        if not valid_positions:
            print("❌ 매도 가능한 종목 없음")
            return False
        
        # 종목 선택
        try:
            choice = int(input(f"\n매도할 종목 선택 (1-{len(valid_positions)}): ")) - 1
            if 0 <= choice < len(valid_positions):
                target = valid_positions[choice]
            else:
                print("❌ 잘못된 선택")
                return False
        except ValueError:
            print("❌ 숫자를 입력하세요")
            return False
        
        # 매도 확인
        print(f"\n💰 매도 예정:")
        print(f"   종목: {target['symbol']}")
        print(f"   수량: {target['quantity']}주")
        print(f"   현재가: ${target['current_price']:.2f}")
        print(f"   예상 수익률: {target['profit_rate']:+.1f}%")
        
        confirm = input(f"\n실제로 {target['symbol']} {target['quantity']}주를 매도하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ 사용자 취소")
            return False
        
        try:
            # 매도 주문 실행
            print("🔄 매도 주문 실행 중...")
            order_id = self.api_client.place_order(
                target['symbol'], 
                target['quantity'], 
                target['current_price'], 
                "sell"
            )
            
            if order_id:
                profit_amount = (target['current_price'] - target['avg_price']) * target['quantity']
                print(f"✅ 매도 주문 성공!")
                print(f"   주문번호: {order_id}")
                print(f"   주문시간: {datetime.now().strftime('%H:%M:%S')}")
                print(f"   예상 수익: ${profit_amount:+.2f}")
                return True
            else:
                print("❌ 매도 주문 실패")
                return False
                
        except Exception as e:
            print(f"❌ 매도 주문 오류: {e}")
            return False
    
    def run_simple_test(self):
        """간단한 매수/매도 테스트 실행"""
        print("\n🚀 간단한 매수/매도 테스트 시작")
        print("="*40)
        
        # 1. 토큰 문제 해결
        if not self.fix_token_issue():
            print("❌ 토큰 문제 해결 실패")
            return
        
        # 2. 기본 기능 확인
        print("\n🔍 기본 기능 확인")
        balance = self.test_account_balance()
        if not balance:
            print("❌ 기본 기능 확인 실패")
            return
        
        # 3. 테스트 메뉴
        print("\n🎯 테스트 메뉴:")
        print("   1. 매수 메서드 테스트")
        print("   2. 매도 메서드 테스트")
        print("   3. 현재가 조회 테스트")
        print("   0. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == '1':
            symbol = input("매수할 종목 (기본값: AAPL): ").strip() or "AAPL"
            try:
                quantity = int(input("매수 수량 (기본값: 1): ") or "1")
                self.test_buy_method(symbol, quantity)
            except ValueError:
                print("❌ 잘못된 수량 입력")
        
        elif choice == '2':
            self.test_sell_method()
        
        elif choice == '3':
            symbol = input("조회할 종목 (기본값: AAPL): ").strip() or "AAPL"
            self.test_current_price(symbol)
        
        elif choice == '0':
            print("👋 테스트 종료")
        
        else:
            print("❌ 잘못된 선택")

if __name__ == "__main__":
    tester = SimpleBuySellTester()
    tester.run_simple_test() 