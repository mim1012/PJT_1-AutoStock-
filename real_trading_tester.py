"""
실거래 완전 테스트 도구 (개선된 버전)
- 토큰 관리 최적화 (403 오류 방지)
- SES 종목 처리 개선
- API 호출 최적화
"""
import sys
import os
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient
from order_manager import OrderManager
from strategy_pjt1 import TradingStrategy
from config import *

class OptimizedKISAPIClient(KISAPIClient):
    """최적화된 API 클라이언트"""
    
    def __init__(self):
        super().__init__()
        # API 호출 통계
        self.call_stats = defaultdict(int)
        self.last_call_time = {}
        self.cached_prices = {}
        self.cache_timeout = 60  # 1분 캐시
        
    def ensure_token_valid_optimized(self):
        """개선된 토큰 유효성 확인"""
        current_time = time.time()
        
        # 토큰이 없거나 만료 10분 전인 경우에만 새로 발급
        if (not self.access_token or 
            not self.token_expires_at or 
            current_time >= self.token_expires_at - 600):  # 10분 여유
            
            self.logger.info(f"토큰 갱신: 현재시간={datetime.now()}, "
                            f"만료시간={datetime.fromtimestamp(self.token_expires_at) if self.token_expires_at else '없음'}")
            
            # 토큰 발급 전 잠시 대기 (연속 호출 방지)
            if hasattr(self, 'last_token_request'):
                time_since_last = current_time - self.last_token_request
                if time_since_last < 5:  # 5초 내 재요청 방지
                    wait_time = 5 - time_since_last
                    self.logger.info(f"토큰 요청 대기: {wait_time:.1f}초")
                    time.sleep(wait_time)
            
            self.last_token_request = current_time
            success = self.get_access_token()
            
            if success:
                self.logger.info(f"토큰 갱신 성공: 만료={datetime.fromtimestamp(self.token_expires_at)}")
            else:
                self.logger.error("토큰 갱신 실패")
            
            return success
        
        # 기존 토큰 유효
        remaining = int(self.token_expires_at - current_time)
        self.logger.debug(f"기존 토큰 사용 (남은시간: {remaining//60}분)")
        return True
    
    def get_current_price_cached(self, symbol):
        """캐시된 현재가 조회"""
        current_time = time.time()
        cache_key = f"current_{symbol}"
        
        # 캐시 확인
        if cache_key in self.cached_prices:
            price_data = self.cached_prices[cache_key]
            if current_time - price_data['timestamp'] < self.cache_timeout:
                self.logger.debug(f"{symbol} 캐시된 현재가 사용: ${price_data['price']:.2f}")
                return price_data['price']
        
        # API 호출 제한 (초당 1회)
        if symbol in self.last_call_time:
            time_since_last = current_time - self.last_call_time[symbol]
            if time_since_last < 1.0:
                wait_time = 1.0 - time_since_last
                self.logger.debug(f"{symbol} API 호출 대기: {wait_time:.1f}초")
                time.sleep(wait_time)
        
        self.last_call_time[symbol] = time.time()
        
        # 토큰 확인
        if not self.ensure_token_valid_optimized():
            return None
        
        # API 호출
        self.call_stats['current_price'] += 1
        price = self.get_current_price(symbol)
        
        # 캐시 저장
        if price is not None:
            self.cached_prices[cache_key] = {
                'price': price,
                'timestamp': current_time
            }
        
        return price
    
    def get_previous_close_cached(self, symbol):
        """캐시된 전일가 조회"""
        current_time = time.time()
        cache_key = f"previous_{symbol}"
        
        # 캐시 확인 (전일가는 하루 동안 유지)
        if cache_key in self.cached_prices:
            price_data = self.cached_prices[cache_key]
            if current_time - price_data['timestamp'] < 3600:  # 1시간 캐시
                self.logger.debug(f"{symbol} 캐시된 전일가 사용: ${price_data['price']:.2f}")
                return price_data['price']
        
        # API 호출 제한
        if symbol in self.last_call_time:
            time_since_last = current_time - self.last_call_time[symbol]
            if time_since_last < 1.0:
                wait_time = 1.0 - time_since_last
                time.sleep(wait_time)
        
        self.last_call_time[symbol] = time.time()
        
        # 토큰 확인
        if not self.ensure_token_valid_optimized():
            return None
        
        # API 호출
        self.call_stats['previous_close'] += 1
        price = self.get_previous_close(symbol)
        
        # 캐시 저장
        if price is not None:
            self.cached_prices[cache_key] = {
                'price': price,
                'timestamp': current_time
            }
        
        return price

class ImprovedRealTradingTester:
    def __init__(self):
        self.api_client = OptimizedKISAPIClient()
        self.order_manager = OrderManager()
        self.strategy = TradingStrategy()
        # 전략에도 최적화된 클라이언트 적용
        self.strategy.api_client = self.api_client
        
        self.logger = logging.getLogger(__name__)
        
        # 테스트 기록
        self.test_orders = []
        self.initial_balance = None
        self.problem_symbols = set()  # 문제 종목 추적
        
    def analyze_problem_symbol(self, symbol, position_data):
        """문제 종목 상세 분석"""
        self.logger.info(f"\n🔍 {symbol} 종목 상세 분석 시작...")
        
        # 기본 정보
        quantity = int(position_data.get("ovrs_cblc_qty", 0))
        avg_price = float(position_data.get("pchs_avg_pric", 0))
        total_cost = quantity * avg_price
        
        self.logger.info(f"   보유수량: {quantity:,}주")
        self.logger.info(f"   평균매수가: ${avg_price:.2f}")
        self.logger.info(f"   총 매수금액: ${total_cost:,.2f}")
        
        # 현재가 조회 시도 (여러 방법)
        self.logger.info("   현재가 조회 시도 중...")
        
        # 방법 1: 일반 현재가 조회
        current_price = self.api_client.get_current_price_cached(symbol)
        if current_price:
            profit_loss = (current_price - avg_price) * quantity
            profit_rate = ((current_price - avg_price) / avg_price) * 100
            
            self.logger.info(f"   ✅ 현재가 조회 성공: ${current_price:.2f}")
            self.logger.info(f"   평가손익: ${profit_loss:,.2f}")
            self.logger.info(f"   수익률: {profit_rate:.2f}%")
            return current_price
        
        # 방법 2: 전일 종가 조회
        self.logger.info("   현재가 실패 → 전일가 조회 시도...")
        prev_price = self.api_client.get_previous_close_cached(symbol)
        if prev_price:
            self.logger.info(f"   ⚠️ 전일가로 대체: ${prev_price:.2f}")
            return prev_price
        
        # 방법 3: 추정 분석
        self.logger.warning(f"   ❌ {symbol} 모든 가격 조회 실패")
        self.logger.info("   🔎 종목 상태 분석:")
        
        # 종목 코드 패턴 분석
        if len(symbol) <= 3 and symbol.isupper():
            self.logger.info(f"   - 종목코드 형태: 정상 (3자리 이하 대문자)")
        else:
            self.logger.warning(f"   - 종목코드 형태: 비정상 (길이: {len(symbol)})")
        
        # 가능한 원인 분석
        possible_reasons = []
        if avg_price < 1.0:
            possible_reasons.append("페니스톡 (저가주)")
        if quantity > 1000:
            possible_reasons.append("대량 보유")
        
        self.logger.info(f"   - 가능한 원인: {', '.join(possible_reasons) if possible_reasons else '알 수 없음'}")
        
        # 권장 조치
        self.logger.info("   💡 권장 조치:")
        self.logger.info("     1. 한국투자증권 HTS/MTS에서 직접 확인")
        self.logger.info("     2. 고객센터 문의")
        self.logger.info("     3. 가능하다면 수동 매도 시도")
        
        self.problem_symbols.add(symbol)
        return None
    
    def get_detailed_balance_improved(self):
        """개선된 상세 계좌 잔고 조회"""
        print("\n" + "="*70)
        print("💰 상세 계좌 현황 (개선된 버전)")
        print("="*70)
        
        # 토큰 확인
        if not self.api_client.ensure_token_valid_optimized():
            print("❌ API 토큰 문제로 계좌 조회 불가")
            return None
        
        balance = self.api_client.get_account_balance()
        if not balance:
            print("❌ 계좌 조회 실패")
            return None
        
        cash = balance['cash']
        positions = balance['positions']
        
        print(f"💵 예수금: ${cash:,.2f}")
        print(f"📊 보유 종목: {len(positions)}개")
        
        if not positions:
            print("보유 종목이 없습니다.")
            return balance
        
        total_value = cash
        total_profit = 0
        normal_positions = []
        problem_positions = []
        
        print(f"\n{'종목':>8} {'수량':>8} {'매수가':>10} {'현재가':>10} {'수익률':>8} {'수익금':>12} {'총가치':>12} {'상태'}")
        print("-" * 90)
        
        for position in positions:
            try:
                symbol = position["ovrs_pdno"]
                quantity = int(position["ovrs_cblc_qty"])
                avg_price = float(position["pchs_avg_pric"])
                
                if quantity <= 0:
                    continue
                
                # 현재가 조회 (캐시 사용)
                current_price = self.api_client.get_current_price_cached(symbol)
                
                if current_price is None:
                    # 문제 종목 처리
                    problem_positions.append((symbol, position))
                    estimated_value = quantity * avg_price  # 매수가로 추정
                    
                    print(f"{symbol:>8} {quantity:>8} ${avg_price:>9.2f} {'조회실패':>10} {'N/A':>8} {'N/A':>12} ${estimated_value:>11.2f} ❓")
                    continue
                
                # 정상 종목 처리
                profit_rate = ((current_price - avg_price) / avg_price) * 100
                profit_amount = (current_price - avg_price) * quantity
                position_value = current_price * quantity
                
                total_value += position_value
                total_profit += profit_amount
                
                # 상태 표시
                if profit_rate >= 5:
                    status = "🔥"
                elif profit_rate > 0:
                    status = "💰"
                else:
                    status = "📉"
                
                normal_positions.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'profit_rate': profit_rate / 100,
                    'profit_amount': profit_amount,
                    'position_value': position_value
                })
                
                print(f"{symbol:>8} {quantity:>8} ${avg_price:>9.2f} ${current_price:>9.2f} {profit_rate:>7.1f}% ${profit_amount:>11.2f} ${position_value:>11.2f} {status}")
                
            except Exception as e:
                print(f"{symbol:>8} - 처리 오류: {e}")
        
        print("-" * 90)
        print(f"{'총 계좌가치 (정상종목)':>70}: ${total_value:,.2f}")
        print(f"{'총 평가손익 (정상종목)':>70}: ${total_profit:,.2f}")
        
        if total_value > 0:
            total_return = (total_profit / (total_value - total_profit)) * 100
            print(f"{'총 수익률 (정상종목)':>70}: {total_return:.2f}%")
        
        # 문제 종목 상세 분석
        if problem_positions:
            print(f"\n🚨 문제 종목 상세 분석 ({len(problem_positions)}개):")
            for symbol, position_data in problem_positions:
                self.analyze_problem_symbol(symbol, position_data)
        
        # API 호출 통계
        print(f"\n📊 API 호출 통계:")
        for call_type, count in self.api_client.call_stats.items():
            print(f"   {call_type}: {count}회")
        
        # 매도 추천
        self.recommend_sells_improved(normal_positions)
        
        return balance
    
    def recommend_sells_improved(self, positions):
        """개선된 매도 추천"""
        if not positions:
            return
        
        print(f"\n📋 매도 추천 분석:")
        
        # 5% 이상 수익 종목
        high_profit = [p for p in positions if p['profit_rate'] >= 0.05]
        if high_profit:
            print("🔥 즉시 매도 대상 (5% 이상 수익):")
            for pos in high_profit:
                print(f"   {pos['symbol']}: {pos['profit_rate']:.1%} 수익 (${pos['profit_amount']:,.2f})")
        
        # 수익 종목 중 최고
        profit_positions = [p for p in positions if p['profit_rate'] > 0]
        if profit_positions:
            best = max(profit_positions, key=lambda x: x['profit_rate'])
            if best not in high_profit:  # 5% 미만인 경우만
                print("💰 일반 매도 대상 (최고 수익률):")
                print(f"   {best['symbol']}: {best['profit_rate']:.1%} 수익 (${best['profit_amount']:,.2f})")
        
        # 손실 종목 현황
        loss_positions = [p for p in positions if p['profit_rate'] <= 0]
        if loss_positions:
            total_loss = sum(p['profit_amount'] for p in loss_positions)
            print(f"📉 손실 종목 현황 ({len(loss_positions)}개):")
            print(f"   총 손실: ${total_loss:,.2f}")
            print("   → 손실 종목은 매도하지 않음 (전략 규칙)")
    
    def test_sell_order_improved(self, symbol=None, test_mode=True):
        """개선된 매도 주문 테스트"""
        print("\n" + "="*70)
        print("📤 매도 주문 테스트 (개선된 버전)")
        print("="*70)
        
        # 토큰 확인
        if not self.api_client.ensure_token_valid_optimized():
            print("❌ API 토큰 문제로 매도 테스트 불가")
            return False
        
        balance = self.api_client.get_account_balance()
        if not balance or not balance['positions']:
            print("❌ 매도할 보유 종목이 없습니다.")
            return False
        
        # 매도 대상 선정 (문제 종목 제외)
        sell_candidates = []
        
        for position in balance['positions']:
            symbol_code = position["ovrs_pdno"]
            quantity = int(position["ovrs_cblc_qty"])
            avg_price = float(position["pchs_avg_pric"])
            
            if quantity <= 0:
                continue
            
            # 현재가 조회 (최적화된 방법)
            current_price = self.api_client.get_current_price_cached(symbol_code)
            if current_price is None:
                print(f"⚠️ {symbol_code}: 현재가 조회 불가 - 매도 대상에서 제외")
                continue
            
            profit_rate = ((current_price - avg_price) / avg_price)
            
            sell_candidates.append({
                'symbol': symbol_code,
                'quantity': quantity,
                'avg_price': avg_price,
                'current_price': current_price,
                'profit_rate': profit_rate,
                'profit_amount': (current_price - avg_price) * quantity
            })
        
        if not sell_candidates:
            print("❌ 매도 가능한 종목이 없습니다.")
            return False
        
        # 매도 우선순위 결정
        high_profit = [x for x in sell_candidates if x['profit_rate'] >= 0.05]
        
        if high_profit:
            # 5% 이상 수익 종목 중 수익률 최고
            target = max(high_profit, key=lambda x: x['profit_rate'])
            reason = f"고수익 매도 ({target['profit_rate']:.1%})"
        else:
            # 수익 종목 중 최고 선택
            profit_candidates = [x for x in sell_candidates if x['profit_rate'] > 0]
            if profit_candidates:
                target = max(profit_candidates, key=lambda x: x['profit_rate'])
                reason = f"최고수익 매도 ({target['profit_rate']:.1%})"
            else:
                print("❌ 수익 종목이 없어 매도하지 않습니다.")
                return False
        
        print(f"🎯 매도 대상 선정: {target['symbol']}")
        print(f"   수량: {target['quantity']:,}주")
        print(f"   매수가: ${target['avg_price']:.2f}")
        print(f"   현재가: ${target['current_price']:.2f}")
        print(f"   수익률: {target['profit_rate']:.2%}")
        print(f"   예상수익: ${target['profit_amount']:,.2f}")
        print(f"   선정사유: {reason}")
        
        if test_mode:
            print("📝 테스트 모드: 실제 주문하지 않음")
            return True
        
        # 실제 매도 주문 (안전 확인)
        print(f"\n⚠️ 실제 매도 주문을 실행합니다!")
        confirm = input(f"정말로 {target['symbol']} {target['quantity']:,}주를 ${target['current_price']:.2f}에 매도하시겠습니까?\n확인하려면 'YES'를 입력하세요: ")
        
        if confirm != 'YES':
            print("❌ 매도 취소 (정확히 'YES'를 입력하지 않음)")
            return False
        
        print("🔄 매도 주문 실행 중...")
        order_id = self.order_manager.place_order_with_tracking(
            target['symbol'], 
            target['quantity'], 
            target['current_price'], 
            "sell"
        )
        
        if order_id:
            print(f"✅ 매도 주문 성공!")
            print(f"   주문번호: {order_id}")
            print(f"   주문시간: {datetime.now().strftime('%H:%M:%S')}")
            
            self.test_orders.append({
                'type': 'SELL',
                'symbol': target['symbol'],
                'quantity': target['quantity'],
                'price': target['current_price'],
                'order_id': order_id,
                'time': datetime.now(),
                'expected_profit': target['profit_amount']
            })
            return True
        else:
            print("❌ 매도 주문 실패")
            return False
    
    def run_optimized_test(self, test_mode=True):
        """최적화된 완전 테스트 실행"""
        print("🚀 실거래 완전 테스트 (최적화된 버전)")
        print(f"테스트 모드: {'ON (실제 주문 안 함)' if test_mode else 'OFF (실제 주문 실행!)'}")
        print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # 단계별 실행
        try:
            # 1. 초기 계좌 상태
            print("1️⃣ 초기 계좌 상태 조회")
            self.initial_balance = self.get_detailed_balance_improved()
            
            if not self.initial_balance:
                print("❌ 계좌 조회 실패로 테스트 중단")
                return False
            
            # 2. 매도 테스트
            print("\n2️⃣ 매도 전략 테스트")
            sell_success = self.test_sell_order_improved(test_mode=test_mode)
            
            if sell_success and not test_mode:
                print("\n⏳ 매도 주문 처리 대기 (30초)...")
                time.sleep(30)
                
                # 계좌 상태 재조회
                print("\n💰 매도 후 계좌 상태:")
                self.get_detailed_balance_improved()
            
            # 3. 최종 요약
            print("\n3️⃣ 테스트 요약")
            self.print_optimized_summary()
            
            return True
            
        except Exception as e:
            self.logger.error(f"테스트 실행 중 오류: {e}")
            print(f"❌ 테스트 실행 중 오류 발생: {e}")
            return False
    
    def print_optimized_summary(self):
        """최적화된 테스트 요약"""
        print("="*70)
        print("📋 테스트 최종 요약")
        print("="*70)
        
        # API 호출 통계
        print("📊 API 성능 통계:")
        total_calls = sum(self.api_client.call_stats.values())
        print(f"   총 API 호출: {total_calls}회")
        for call_type, count in self.api_client.call_stats.items():
            print(f"   - {call_type}: {count}회")
        
        # 캐시 효율성
        cache_hits = len([k for k, v in self.api_client.cached_prices.items() 
                         if time.time() - v['timestamp'] < self.api_client.cache_timeout])
        print(f"   캐시 적중: {cache_hits}개 항목")
        
        # 문제 종목
        if self.problem_symbols:
            print(f"\n🚨 문제 종목: {len(self.problem_symbols)}개")
            for symbol in self.problem_symbols:
                print(f"   - {symbol}: 가격 조회 불가")
        
        # 실행된 주문
        if self.test_orders:
            print(f"\n📋 실행된 주문: {len(self.test_orders)}건")
            for order in self.test_orders:
                profit_info = f" (예상수익: ${order.get('expected_profit', 0):,.2f})" if 'expected_profit' in order else ""
                print(f"   {order['type']}: {order['symbol']} {order['quantity']:,}주 @ ${order['price']:.2f}{profit_info}")
        else:
            print("\n📋 실행된 주문이 없습니다.")
        
        print(f"\n⏰ 테스트 완료: {datetime.now().strftime('%H:%M:%S')}")

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
        return
    
    tester = ImprovedRealTradingTester()
    
    # 실행 모드 선택
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "real":
            print("⚠️ 실제 주문 모드!")
            print("주의: 실제 주식 매매가 실행됩니다!")
            confirm = input("계속하려면 'CONFIRM'을 입력하세요: ")
            if confirm == "CONFIRM":
                tester.run_optimized_test(test_mode=False)
            else:
                print("❌ 실행 취소")
        elif sys.argv[1] == "balance":
            # 계좌 조회만
            tester.get_detailed_balance_improved()
        elif sys.argv[1] == "sell":
            # 매도만 실행
            print("매도 주문 실행 모드")
            confirm = input("실제 매도를 실행하시겠습니까? (y/N): ")
            if confirm.lower() == 'y':
                tester.test_sell_order_improved(test_mode=False)
            else:
                tester.test_sell_order_improved(test_mode=True)
        else:
            print("사용법:")
            print("  python real_trading_tester.py          # 테스트 모드")
            print("  python real_trading_tester.py balance  # 계좌 조회만")
            print("  python real_trading_tester.py sell     # 매도 테스트")
            print("  python real_trading_tester.py real     # 실제 주문 모드")
    else:
        # 기본값: 안전한 테스트 모드
        tester.run_optimized_test(test_mode=True)

if __name__ == "__main__":
    main()