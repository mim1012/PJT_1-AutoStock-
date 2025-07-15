"""
모의투자 매수/매도 전략 시뮬레이터
실제 주문 없이 전략 로직만 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from strategy_pjt1 import TradingStrategy
from order_manager import OrderManager
from config import *
from datetime import datetime

class StrategySimulator:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        self.strategy = TradingStrategy()
        self.order_manager = OrderManager()
        
        # 가상 포트폴리오
        self.virtual_cash = 10000.0  # 가상 현금 $10,000
        self.virtual_positions = {}  # 가상 보유 종목
        self.simulation_orders = []  # 시뮬레이션 주문 기록
        
        print("🎯 모의투자 매수/매도 전략 시뮬레이터 시작")
        print(f"💰 가상 자본: ${self.virtual_cash:,.2f}")
        print("="*50)
    
    def test_buy_strategy_simulation(self):
        """매수 전략 시뮬레이션 테스트"""
        print("\n🚀 매수 전략 시뮬레이션 테스트")
        print("="*40)
        
        # 1. 토큰 확인
        if not self.api_client.ensure_token_valid():
            print("❌ API 토큰 준비 실패")
            return False
        
        # 2. 필터 조건 확인
        print("📊 상승 필터 조건 확인 중...")
        filter_passed = self.strategy.check_filter_condition()
        
        if not filter_passed:
            print("❌ 상승 필터 조건 미충족 - 매수 신호 없음")
            return False
        
        print("✅ 상승 필터 조건 충족")
        
        # 3. 하락 종목 선정
        print("📉 하락 종목 선정 중...")
        top_declining = self.strategy.get_top_declining_stocks(3)
        
        if not top_declining:
            print("❌ 하락 종목 없음")
            return False
        
        print(f"📋 선정된 하락 종목: {', '.join(top_declining)}")
        
        # 4. 매수 시뮬레이션
        total_cost = 0
        buy_candidates = []
        
        for symbol in top_declining:
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                print(f"⚠️ {symbol}: 현재가 조회 실패")
                continue
            
            # 매수 수량 계산
            quantity = self.strategy.calculate_position_size(symbol, self.virtual_cash)
            
            if quantity > 0:
                cost = quantity * current_price
                total_cost += cost
                
                buy_candidates.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'cost': cost
                })
                
                print(f"💰 {symbol}: {quantity}주 × ${current_price:.2f} = ${cost:.2f}")
        
        # 5. 매수 실행 가능 여부 확인
        print(f"\n💸 총 매수 비용: ${total_cost:.2f}")
        print(f"💵 가상 현금: ${self.virtual_cash:.2f}")
        
        if total_cost <= self.virtual_cash:
            print("✅ 매수 실행 가능 - 가상 매수 진행")
            
            # 가상 매수 실행
            for candidate in buy_candidates:
                symbol = candidate['symbol']
                self.virtual_positions[symbol] = {
                    'quantity': candidate['quantity'],
                    'avg_price': candidate['price'],
                    'buy_time': datetime.now()
                }
                
                self.simulation_orders.append({
                    'type': 'BUY',
                    'symbol': symbol,
                    'quantity': candidate['quantity'],
                    'price': candidate['price'],
                    'time': datetime.now()
                })
                
                print(f"📝 가상 매수 기록: {symbol} {candidate['quantity']}주 @ ${candidate['price']:.2f}")
            
            self.virtual_cash -= total_cost
            print(f"💰 남은 가상 현금: ${self.virtual_cash:.2f}")
            return True
        else:
            print("❌ 가상 자본 부족 - 매수 불가")
            return False
    
    def test_sell_strategy_simulation(self):
        """매도 전략 시뮬레이션 테스트"""
        print("\n📤 매도 전략 시뮬레이션 테스트")
        print("="*40)
        
        if not self.virtual_positions:
            print("❌ 가상 보유 종목 없음")
            return False
        
        high_profit_targets = []
        normal_profit_targets = []
        
        print("📊 보유 종목 분석:")
        for symbol, position in self.virtual_positions.items():
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                print(f"⚠️ {symbol}: 현재가 조회 실패")
                continue
            
            profit_rate = self.strategy.calculate_profit_rate(symbol, current_price, position['avg_price'])
            profit_amount = (current_price - position['avg_price']) * position['quantity']
            
            status = "🔥" if profit_rate >= PROFIT_THRESHOLD else "💰" if profit_rate > 0 else "📉"
            print(f"{status} {symbol}: {position['quantity']}주 @ ${position['avg_price']:.2f} → ${current_price:.2f} "
                  f"({profit_rate:.1%}, ${profit_amount:+.2f})")
            
            if profit_rate >= PROFIT_THRESHOLD:
                high_profit_targets.append((symbol, position['quantity'], current_price, profit_rate, profit_amount))
            elif profit_rate > 0:
                normal_profit_targets.append((symbol, position['quantity'], current_price, profit_rate, profit_amount))
        
        # 매도 실행 시뮬레이션
        sell_executed = False
        
        # 고수익 매도 (5% 이상)
        for symbol, quantity, price, rate, amount in high_profit_targets:
            print(f"🔥 고수익 가상 매도: {symbol} {quantity}주 @ ${price:.2f} ({rate:.1%})")
            
            # 가상 매도 실행
            self.virtual_cash += quantity * price
            del self.virtual_positions[symbol]
            
            self.simulation_orders.append({
                'type': 'SELL',
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'profit': amount,
                'time': datetime.now()
            })
            
            sell_executed = True
        
        # 일반 매도 (최고 수익률 1개)
        if normal_profit_targets and not high_profit_targets:
            best_target = max(normal_profit_targets, key=lambda x: x[3])
            symbol, quantity, price, rate, amount = best_target
            
            print(f"💰 일반 가상 매도: {symbol} {quantity}주 @ ${price:.2f} ({rate:.1%})")
            
            # 가상 매도 실행
            self.virtual_cash += quantity * price
            del self.virtual_positions[symbol]
            
            self.simulation_orders.append({
                'type': 'SELL',
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'profit': amount,
                'time': datetime.now()
            })
            
            sell_executed = True
        
        if not sell_executed:
            print("❌ 매도 조건을 만족하는 종목 없음")
            return False
        
        print(f"💰 매도 후 가상 현금: ${self.virtual_cash:.2f}")
        return True
    
    def run_complete_simulation(self):
        """완전한 매수/매도 시뮬레이션 실행"""
        print("🎯 완전한 매수/매도 전략 시뮬레이션")
        print("="*50)
        
        # 1. 매수 전략 테스트
        buy_success = self.test_buy_strategy_simulation()
        
        if buy_success:
            print(f"\n⏳ 매수 후 잠시 대기...")
            
            # 2. 매도 전략 테스트
            sell_success = self.test_sell_strategy_simulation()
            
            # 3. 결과 요약
            self.print_simulation_summary()
        else:
            print("\n❌ 매수 조건 미충족으로 시뮬레이션 종료")
    
    def print_simulation_summary(self):
        """시뮬레이션 결과 요약"""
        print("\n📊 시뮬레이션 결과 요약")
        print("="*40)
        
        total_orders = len(self.simulation_orders)
        buy_orders = len([o for o in self.simulation_orders if o['type'] == 'BUY'])
        sell_orders = len([o for o in self.simulation_orders if o['type'] == 'SELL'])
        
        print(f"📋 총 주문 수: {total_orders}개")
        print(f"   📈 매수 주문: {buy_orders}개")
        print(f"   📉 매도 주문: {sell_orders}개")
        print(f"💰 최종 가상 현금: ${self.virtual_cash:.2f}")
        print(f"📦 남은 보유 종목: {len(self.virtual_positions)}개")
        
        # 수익 계산
        total_profit = sum([o.get('profit', 0) for o in self.simulation_orders if o['type'] == 'SELL'])
        if total_profit != 0:
            print(f"💸 총 실현 수익: ${total_profit:+.2f}")
        
        # 주문 내역
        if self.simulation_orders:
            print("\n📜 주문 내역:")
            for i, order in enumerate(self.simulation_orders):
                time_str = order['time'].strftime('%H:%M:%S')
                if order['type'] == 'BUY':
                    print(f"   {i+1}. {time_str} 📈 매수 {order['symbol']} {order['quantity']}주 @ ${order['price']:.2f}")
                else:
                    profit_str = f" (수익: ${order['profit']:+.2f})" if order.get('profit') else ""
                    print(f"   {i+1}. {time_str} 📉 매도 {order['symbol']} {order['quantity']}주 @ ${order['price']:.2f}{profit_str}")

if __name__ == "__main__":
    simulator = StrategySimulator()
    simulator.run_complete_simulation() 