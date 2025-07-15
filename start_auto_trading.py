"""
실전 매매 모드 - 실제 주문 실행 (완전 자동화)
⚠️ 주의: 이 파일은 실제 돈으로 거래합니다!
"""
import sys
import os
import time
import logging
from datetime import datetime, timedelta
import pytz
import schedule
import yfinance as yf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient
from token_manager import TokenManager
from strategy_pjt1 import TradingStrategy
from order_manager import OrderManager
from config import *
from logging.handlers import RotatingFileHandler
from utils_balance import print_positions_table

# blance02.py의 API키 설정
KIS_APP_KEY = "PS9Yr8VDczEhRt6kbhrAExgLO9mno70zMJvp"
KIS_APP_SECRET = "2mfGKemkM4CTyvkQ1oquImEb+uUKwrflzTn23wjWJ5/PoFu5dwIW1OoyKYCoY2lPxl7L7ukzQqZD8PylBkYA1/SLFQ4r110XH6YCajAcMCzQnQekj1xBNGAaZo8zltZgX7YkomUzoBKV+8kopKGm3c9+juaQU+NJfM4vwMuyk8wkGFiK4v8="
KIS_ACCOUNT_NUMBER = "64721801-01"

class ProductionTradingSystem:
    def __init__(self):
        # KIS API 클라이언트 및 토큰 매니저 직접 사용 (원래 방식)
        self.api_client = KISAPIClient()
        self.token_manager = TokenManager()
        self.strategy = TradingStrategy()
        self.order_manager = OrderManager()
        self.logger = logging.getLogger(__name__)
        self.et_tz = pytz.timezone('US/Eastern')
        # 실전 매매 통계
        self.trading_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'buy_orders': 0,
            'sell_orders': 0,
            'start_time': datetime.now(),
            'last_balance_check': None
        }
        # 안전 장치
        self.safety_checks = {
            'max_daily_orders': 50,  # 하루 최대 주문 수
            'min_account_balance': 10,  # 최소 계좌 잔고 ($)
            'max_position_size': 0.4,  # 단일 종목 최대 비중 (40%)
        }
        self.is_running = False
        self.last_time_check = None

    def safe_float(self, val):
        try:
            if val is None or str(val).strip() == '':
                return 0.0
            return float(val)
        except Exception:
            return 0.0
    
    def get_current_price_with_fallback(self, symbol):
        """현재가 조회 (KIS API 실패 시 yfinance로 대체)"""
        try:
            # 1. 토큰 유효성 확인 및 발급
            token = self.token_manager.get_valid_token()
            if token:
                self.api_client.access_token = token
            
            # 2. 먼저 KIS API로 시도
            price = self.api_client.get_current_price(symbol)
            if price and price > 0:
                self.logger.debug(f"[가격][KIS] {symbol}: ${price:.2f}")
                return price
            
            # 3. KIS API 실패 시 yfinance로 대체
            self.logger.warning(f"[가격][대체] {symbol} KIS API 실패, yfinance 시도")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                if current_price > 0:
                    self.logger.info(f"[가격][yfinance] {symbol}: ${current_price:.2f}")
                    return current_price
                else:
                    self.logger.warning(f"[가격][오류] {symbol} yfinance 가격이 0 이하")
                    return None
            else:
                self.logger.warning(f"[가격][오류] {symbol} yfinance 데이터 없음")
                return None
        except Exception as e:
            self.logger.error(f"[가격][오류] {symbol} 조회 실패: {e}")
            return None
    
    def get_balance_with_kis_api(self):
        """KIS API 직접 사용으로 잔고 조회 (원래 방식)"""
        try:
            # 토큰 유효성 확인 및 발급
            token = self.token_manager.get_valid_token()
            if token:
                self.api_client.access_token = token
            
            balance = self.api_client.get_account_balance()
            if not balance:
                self.logger.error("[잔고][오류] KIS API 잔고 조회 실패")
                return None
            
            return balance
            
        except Exception as e:
            self.logger.error(f"[잔고][오류] 조회 실패: {e}")
            return None
    
    def display_comprehensive_balance(self):
        """종합 계좌 현황 출력 (보유종목별 수익률 포함)"""
        try:
            balance = self.get_balance_with_kis_api()
            if not balance:
                self.logger.error("[잔고][오류] 조회 실패")
                return

            print("\n" + "="*80)
            print("📊 종합 계좌 현황")
            print("="*80)

            # 1. 계좌 요약 정보
            cash = float(balance.get("cash", 0))
            print(f"💰 예수금: ${cash:,.2f}")

            # 2. 보유 종목 상세 정보 (수익률 포함)
            positions = balance.get("positions", [])
            if positions:
                print(f"\n[보유종목 상세] ({len(positions)}개)")
                print_positions_table(positions)
            else:
                print("\n📭 보유 종목: 없음")
            print("="*80)
        except Exception as e:
            self.logger.error(f"[잔고][오류] 상세 출력 실패: {e}")
    
    def display_detailed_balance(self):
        """blance02.py 방식의 상세 잔고 출력"""
        try:
            balance = self.get_balance_with_kis_api()
            if not balance:
                self.logger.error("[잔고][오류] 조회 실패")
                return
            
            print("\n" + "="*60)
            print("📊 상세 계좌 현황 (blance02.py 방식)")
            print("="*60)
            
            # 예수금 출력
            print(f"💰 사용가능 외화: ${balance.get('available_cash', 0):,.2f}")
            self.logger.info(f"[잔고][예수금] ${balance.get('available_cash', 0):,.2f}")
            
            # 보유 종목 출력
            positions = balance.get("positions", [])
            if positions:
                print(f"\n📈 보유 종목 ({len(positions)}개):")
                for p in positions:
                    name = p.get("ovrs_item_name", "-").strip()  # name → ovrs_item_name
                    symbol = p.get("ovrs_pdno", "-")  # symbol → ovrs_pdno
                    qty = p.get("ovrs_cblc_qty", "-")  # quantity → ovrs_cblc_qty
                    current_price = p.get("ovrs_now_pric1", "-")  # current_price → ovrs_now_pric1
                    print(f"   {symbol} | {name} | 수량: {qty} | 현재가: ${current_price}")
            else:
                print("\n📈 보유 종목: 없음")
            
            # 종합 정보
            print(f"\n📊 종합 정보:")
            print(f"   총 평가 금액: ${balance.get('total_eval_amt', 0):,.2f}")
            print(f"   총 매입 금액: ${balance.get('total_purchase_amt', 0):,.2f}")
            print(f"   📈 수익률: {balance.get('profit_rate', 'N/A'):.2f}%")
            
            self.logger.info(f"[잔고][종합] 평가금액: ${balance.get('total_eval_amt', 0):,.2f}, 매입금액: ${balance.get('total_purchase_amt', 0):,.2f}, 수익률: {balance.get('profit_rate', 'N/A'):.2f}%")
            
        except Exception as e:
            self.logger.error(f"[잔고][오류] 상세 출력 실패: {e}")
    
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
            self.logger.error(f"[시간][오류] 운영시간 확인 실패: {e}")
            return False
    
    def get_time_until_trading(self):
        """거래시간까지 남은 시간 계산"""
        try:
            et_now = datetime.now(self.et_tz)
            
            # 주말인 경우 다음 월요일까지
            if et_now.weekday() >= 5:  # 토요일, 일요일
                days_until_monday = 7 - et_now.weekday()
                next_monday = et_now + timedelta(days=days_until_monday)
                next_monday = next_monday.replace(hour=11, minute=30, second=0, microsecond=0)
                return next_monday - et_now
            
            # 평일인 경우
            today_start = et_now.replace(
                hour=int(TRADING_START_TIME.split(':')[0]),
                minute=int(TRADING_START_TIME.split(':')[1]),
                second=0, microsecond=0
            )
            
            if et_now < today_start:
                # 오늘 거래시간이 아직 안됨
                return today_start - et_now
            else:
                # 오늘 거래시간이 끝났으므로 다음 거래일까지
                next_trading_day = et_now + timedelta(days=1)
                while next_trading_day.weekday() >= 5:  # 주말 제외
                    next_trading_day += timedelta(days=1)
                
                next_trading_day = next_trading_day.replace(
                    hour=int(TRADING_START_TIME.split(':')[0]),
                    minute=int(TRADING_START_TIME.split(':')[1]),
                    second=0, microsecond=0
                )
                return next_trading_day - et_now
            
        except Exception as e:
            self.logger.error(f"[시간][오류] 거래시간 계산 실패: {e}")
            return timedelta(hours=0)
    
    def print_time_status(self):
        """현재 시간 상태 출력"""
        try:
            et_now = datetime.now(self.et_tz)
            current_time_str = et_now.strftime("%Y-%m-%d %H:%M:%S ET")
            
            if self.is_trading_hours():
                self.logger.info(f"[시간][상태] 현재 거래시간: {current_time_str}")
            else:
                time_until = self.get_time_until_trading()
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                self.logger.info(f"[시간][상태] 거래시간 외: {current_time_str} | 거래시간까지 {hours}시간 {minutes}분 남음")
            
        except Exception as e:
            self.logger.error(f"[시간][오류] 상태 출력 실패: {e}")
    
    def safety_check(self):
        """안전 점검"""
        try:
            # 1. 계좌 잔고 확인
            balance = self.get_balance_with_kis_api()
            if not balance:
                self.logger.error("[안전][오류] 계좌 조회 실패")
                return False
            
            # 최소 예수금 제한 제거
            # if balance['cash'] < self.safety_checks['min_account_balance']:
            #     self.logger.error(f"[안전][오류] 예수금 부족: ${balance['cash']:.2f}")
            #     return False
            
            # 2. 일일 주문 수 제한 확인
            if self.trading_stats['total_orders'] >= self.safety_checks['max_daily_orders']:
                self.logger.error(f"[안전][오류] 일일 주문 한도 초과: {self.trading_stats['total_orders']}건")
                return False
            
            self.logger.debug("[안전][통과] 안전 점검 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"[안전][오류] 안전 점검 실패: {e}")
            return False

    def display_account_status(self):
        """계좌 상태 출력 (2시간마다 자동 실행)"""
        try:
            self.logger.info("[계좌][주기] 2시간마다 계좌 현황 출력")
            self.display_comprehensive_balance()
            self.trading_stats['last_balance_check'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"[계좌][오류] 상태 출력 실패: {e}")

    def simple_balance_display(self):
        """간단한 예수금과 보유종목만 표시 (현재가 조회 없음)"""
        try:
            print("\n" + "="*60)
            print("💰 간단 계좌 현황")
            print("="*60)
            
            # 계좌 잔고 조회 (blance02.py 방식)
            balance = self.get_balance_with_kis_api()
            if not balance:
                print("❌ 계좌 조회 실패")
                return
            
            # 예수금 표시
            cash = balance.get('available_cash', 0)
            print(f"💵 사용가능 외화: ${cash:,.2f}")
            
            # 보유 종목 기본 정보만 표시 (현재가 조회 없음)
            positions = balance.get('positions', [])
            if positions:
                print(f"📈 보유 종목: {len(positions)}개")
                print("-" * 60)
                print(f"{'번호':>3} {'종목':>6} {'수량':>8} {'평균가':>10} {'매수금액':>12}")
                print("-" * 60)
                
                total_invested = 0
                for i, position in enumerate(positions, 1):
                    symbol = position.get("ovrs_pdno", "N/A")  # symbol → ovrs_pdno로 변경
                    try:
                        quantity = self.safe_float(position.get("ovrs_cblc_qty", 0))  # quantity → ovrs_cblc_qty
                        avg_price = self.safe_float(position.get("pchs_avg_pric", 0))  # avg_buy_price → pchs_avg_pric
                    except Exception:
                        self.logger.warning(f"[간단잔고][보유] {symbol} 수량/평균단가 변환 실패 - 스킵")
                        continue
                    if quantity <= 0:
                        self.logger.warning(f"[간단잔고][보유] {symbol} 수량 0 또는 이상치 - 스킵")
                        continue
                    invested = avg_price * quantity
                    total_invested += invested
                    print(f"{i:3} {symbol:>6} {quantity:8.2f}주 ${avg_price:8.2f} ${invested:10.2f}")
                
                print("-" * 60)
                print(f"📊 총 투자금액: ${total_invested:,.2f}")
                print(f"💎 총 계좌가치: ${cash + total_invested:,.2f}")
            else:
                print("📭 보유 종목 없음")
            
            print("="*60)
            
        except Exception as e:
            print(f"❌ 간단 계좌 현황 오류: {e}")
            # 오류가 나도 계속 진행
    
    def execute_buy_strategy(self):
        """매수 전략 실행 (실제 주문)"""
        if not self.is_trading_hours():
            self.logger.debug("[매수][스킵] 운영 시간 외")
            return
        
        if not self.safety_check():
            self.logger.error("[매수][오류] 안전 점검 실패")
            return
        
        try:
            self.logger.debug("[매수][시작] 실전 매수 전략 실행")
            
            # 1. 상승 필터 조건 확인
            filter_passed = self.strategy.check_filter_condition()
            if not filter_passed:
                self.logger.info("[필터][미충족] 매수 신호 없음")
                return
            
            self.logger.info("[필터][충족] 매수 신호 감지")
            
            # 2. 상위 하락 종목 선정
            top_declining = self.strategy.get_top_declining_stocks(3)
            if not top_declining:
                self.logger.info("[필터][미충족] 하락 종목 없음")
                return
            
            self.logger.debug(f"[매수][대상] 상위 하락 종목: {', '.join(top_declining)}")
            
            # 3. 각 종목별 실제 매수 실행
            balance = self.get_balance_with_kis_api()
            if not balance:
                self.logger.error("[매수][오류] 계좌 조회 실패")
                return
            
            if balance.get('available_cash', 0) <= self.safety_checks['min_account_balance']:
                self.logger.warning(f"[매수][오류] 예수금 부족: ${balance.get('available_cash', 0):.2f}")
                return
            
            for symbol in top_declining:
                current_price = self.get_current_price_with_fallback(symbol)
                if current_price is None:
                    self.logger.warning(f"[매수][오류] {symbol} 현재가 조회 실패 - 스킵")
                    continue
                
                # 매수 수량 계산
                quantity = self.strategy.calculate_position_size(symbol, balance.get('available_cash', 0))
                
                if quantity > 0:
                    total_cost = quantity * current_price
                    self.logger.info(f"[매수][시도] {symbol} | 현재가: ${current_price:.2f} | 수량: {quantity} | 총비용: ${total_cost:.2f}")
                    
                    # 🚨 실제 주문 실행!
                    order_id = self.order_manager.place_order_with_tracking(
                        symbol, quantity, current_price, "buy"
                    )
                    print(f"[매수][시도] {symbol} | 현재가: ${current_price:.2f} | 수량: {quantity} | 총비용: ${total_cost:.2f}")
                    if order_id:
                        print(f"[매수][성공] {symbol} | 주문ID: {order_id}")
                        self.logger.info(f"[매수][성공] {symbol} | 주문ID: {order_id}")
                        self.trading_stats['total_orders'] += 1
                        self.trading_stats['successful_orders'] += 1
                        self.trading_stats['buy_orders'] += 1
                    else:
                        print(f"[매수][실패] {symbol}")
                        self.logger.error(f"[매수][실패] {symbol}")
                        self.trading_stats['failed_orders'] += 1
                    
                    # 주문 간 대기 (API 제한 방지)
                    time.sleep(2)
            
            self.logger.debug("[매수][완료] 실전 매수 전략 실행 완료")
            
        except Exception as e:
            self.logger.error(f"[매수][오류] 매수 전략 실행 실패: {e}")
    
    def execute_sell_strategy(self):
        """매도 전략 실행 (실제 주문)"""
        if not self.is_trading_hours():
            self.logger.debug("[매도][스킵] 운영 시간 외")
            return
        
        if not self.safety_check():
            self.logger.error("[매도][오류] 안전 점검 실패")
            return
        
        try:
            self.logger.debug("[매도][시작] 실전 매도 전략 실행")
            
            # 보유종목 조회
            balance = self.get_balance_with_kis_api()
            if not balance or not balance.get("positions"):
                self.logger.debug("[매도][정보] 보유 종목 없음")
                return
            
            high_profit_targets = []
            normal_profit_targets = []
            
            for position in balance["positions"]:
                symbol = position.get("ovrs_pdno", "N/A")
                quantity = float(position.get("ovrs_cblc_qty", 0))
                avg_buy_price = float(position.get("pchs_avg_pric", 0))
                current_price = float(position.get("ovrs_now_pric1", 0))
                
                if quantity <= 0 or avg_buy_price <= 0:
                    continue
                
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) if avg_buy_price > 0 else 0
                
                target_info = {
                    'symbol': symbol,
                    'quantity': quantity,
                    'current_price': current_price,
                    'profit_rate': profit_rate,
                    'avg_buy_price': avg_buy_price
                }
                
                if profit_rate >= PROFIT_THRESHOLD:  # 5% 이상
                    high_profit_targets.append(target_info)
                elif profit_rate > 0:
                    normal_profit_targets.append(target_info)
            
            # 고수익 매도 (5% 이상) - 모두 매도
            for target in high_profit_targets:
                print(f"[매도][시도] {target['symbol']} | 수익률: {target['profit_rate']*100:.2f}% | 현재가: ${target['current_price']:.2f} | 수량: {target['quantity']}")
                order_id = self.order_manager.place_order_with_tracking(
                    target['symbol'], target['quantity'], target['current_price'], "sell"
                )
                if order_id:
                    profit_amount = (target['current_price'] - target['avg_buy_price']) * target['quantity']
                    print(f"[매도][성공] {target['symbol']} | 주문ID: {order_id} | 예상수익: ${profit_amount:.2f}")
                    self.logger.info(f"[매도][성공] {target['symbol']} | 주문ID: {order_id} | 예상수익: ${profit_amount:.2f}")
                    self.trading_stats['total_orders'] += 1
                    self.trading_stats['successful_orders'] += 1
                    self.trading_stats['sell_orders'] += 1
                else:
                    print(f"[매도][실패] {target['symbol']}")
                    self.logger.error(f"[매도][실패] {target['symbol']}")
                    self.trading_stats['failed_orders'] += 1
                time.sleep(2)
            
            # 일반 매도 (최고 수익률 1개)
            if normal_profit_targets and not high_profit_targets:
                best_target = max(normal_profit_targets, key=lambda x: x['profit_rate'])
                print(f"[매도][시도] {best_target['symbol']} | 수익률: {best_target['profit_rate']*100:.2f}% | 현재가: ${best_target['current_price']:.2f} | 수량: {best_target['quantity']}")
                order_id = self.order_manager.place_order_with_tracking(
                    best_target['symbol'], best_target['quantity'], best_target['current_price'], "sell"
                )
                if order_id:
                    profit_amount = (best_target['current_price'] - best_target['avg_buy_price']) * best_target['quantity']
                    print(f"[매도][성공] {best_target['symbol']} | 주문ID: {order_id} | 예상수익: ${profit_amount:.2f}")
                    self.logger.info(f"[매도][성공] {best_target['symbol']} | 주문ID: {order_id} | 예상수익: ${profit_amount:.2f}")
                    self.trading_stats['total_orders'] += 1
                    self.trading_stats['successful_orders'] += 1
                    self.trading_stats['sell_orders'] += 1
                else:
                    print(f"[매도][실패] {best_target['symbol']}")
                    self.logger.error(f"[매도][실패] {best_target['symbol']}")
                    self.trading_stats['failed_orders'] += 1
                time.sleep(2)
            
            if not high_profit_targets and not normal_profit_targets:
                self.logger.info("[매도][정보] 매도 조건 충족 종목 없음")
            
            self.logger.debug("[매도][완료] 실전 매도 전략 실행 완료")
            
        except Exception as e:
            self.logger.error(f"[매도][오류] 매도 전략 실행 실패: {e}")
    
    def cleanup_orders(self):
        """미체결 주문 정리"""
        try:
            self.logger.debug("[정리][시작] 미체결 주문 정리")
            # 미체결 주문 정리 로직 (필요시 구현)
            self.logger.debug("[정리][완료] 미체결 주문 정리 완료")
        except Exception as e:
            self.logger.error(f"[정리][오류] 주문 정리 실패: {e}")
    
    def print_status(self):
        """상태 출력 (5분마다)"""
        try:
            self.logger.debug("[상태][출력] 시스템 상태 점검")
            total_orders = self.trading_stats['total_orders']
            successful_orders = self.trading_stats['successful_orders']
            failed_orders = self.trading_stats['failed_orders']
            if total_orders > 0:
                success_rate = (successful_orders / total_orders) * 100
                self.logger.info(f"[상태][통계] 총주문: {total_orders}건 | 성공: {successful_orders}건 | 실패: {failed_orders}건 | 성공률: {success_rate:.1f}%")
            balance = self.get_balance_with_kis_api()
            if balance and balance.get("positions"):
                total_profit = 0
                profitable_count = 0
                for position in balance["positions"]:
                    symbol = position.get("ovrs_pdno", "N/A")  # symbol → ovrs_pdno로 변경
                    try:
                        quantity = self.safe_float(position.get("ovrs_cblc_qty", 0))  # quantity → ovrs_cblc_qty
                        avg_price = self.safe_float(position.get("pchs_avg_pric", 0))  # avg_buy_price → pchs_avg_pric
                    except Exception:
                        self.logger.warning(f"[상태][보유] {symbol} 수량/평균단가 변환 실패 - 스킵")
                        continue
                    if quantity <= 0 or avg_price <= 0:
                        self.logger.warning(f"[상태][보유] {symbol} 수량 또는 평균단가 0/이상치 - 스킵")
                        continue
                    current_price = self.get_current_price_with_fallback(symbol)
                    if current_price:
                        try:
                            profit = (current_price - avg_price) * quantity
                            profit_rate = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 'N/A'
                            total_profit += profit
                            if profit_rate != 'N/A' and profit_rate > 0:
                                profitable_count += 1
                            status = "🔥" if profit_rate != 'N/A' and profit_rate >= 5 else "💰" if profit_rate != 'N/A' and profit_rate > 0 else "📉"
                            profit_rate_str = f"{profit_rate:+.1f}%" if profit_rate != 'N/A' else 'N/A'
                            profit_str = f"${profit:+.2f}" if profit_rate != 'N/A' else 'N/A'
                            self.logger.info(f"[상태][보유] {symbol}: {profit_rate_str} ({profit_str}) {status}")
                        except Exception as e:
                            self.logger.warning(f"[상태][보유] {symbol} 현재가 조회 실패 - 스킵")
                if total_profit != 0:
                    self.logger.info(f"[상태][요약] 총 평가손익: ${total_profit:+.2f} | 수익종목: {profitable_count}개")
        except Exception as e:
            self.logger.error(f"[상태][오류] 상태 출력 실패: {e}")
    
    def setup_schedule(self):
        """스케줄 설정"""
        # 매도 전략 (30분 주기)
        schedule.every(SELL_INTERVAL_MINUTES).minutes.do(self.execute_sell_strategy)
        
        # 매수 전략 (60분 주기)
        schedule.every(BUY_INTERVAL_MINUTES).minutes.do(self.execute_buy_strategy)
        
        # 주문 정리 (20분 주기)
        schedule.every(20).minutes.do(self.cleanup_orders)
        
        # 상태 출력 (5분 주기)
        schedule.every(5).minutes.do(self.print_status)
        
        # 계좌 현황 출력 (2시간 주기)
        schedule.every(2).hours.do(self.display_account_status)
        
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        self.logger.info(f"[시스템][시작] {trading_mode} 자동매매 스케줄 설정 완료")
        self.logger.info(f"[스케줄][설정] 매도: {SELL_INTERVAL_MINUTES}분 | 매수: {BUY_INTERVAL_MINUTES}분 | 정리: 20분 | 상태: 5분 | 계좌: 2시간")
        self.logger.info(f"[시간][설정] 운영시간: {TRADING_START_TIME} ~ {TRADING_END_TIME} (ET)")
        if not USE_PAPER_TRADING:
            self.logger.warning("[시스템][주의] 실제 돈으로 거래합니다!")
        else:
            self.logger.info("[시스템][안전] 모의투자 모드로 안전하게 실행됩니다!")
    
    def start(self):
        """자동매매 시스템 시작"""
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        
        self.logger.warning("🚨" * 20)
        self.logger.warning(f"[시스템][시작] ⚠️ {trading_mode} 자동매매 시스템 시작!")
        if not USE_PAPER_TRADING:
            self.logger.warning("[시스템][주의] ⚠️ 실제 돈으로 거래가 실행됩니다!")
        self.logger.warning("🚨" * 20)
        
        # 토큰 유효성 점검 및 재발급 시도 (로그/콘솔 출력)
        self.strategy.check_and_refresh_token()
        
        # 최종 확인
        print("\n" + "="*60)
        print(f"⚠️ {trading_mode} 자동매매 시스템을 시작합니다!")
        if not USE_PAPER_TRADING:
            print("⚠️ 실제 돈으로 주식 거래가 실행됩니다!")
        else:
            print("✅ 모의투자 모드로 안전하게 테스트됩니다!")
        print("="*60)
        print("현재 설정:")
        print(f"   - 거래 모드: {trading_mode}")
        print(f"   - 매도 주기: {SELL_INTERVAL_MINUTES}분")
        print(f"   - 매수 주기: {BUY_INTERVAL_MINUTES}분")
        print(f"   - 운영 시간: {TRADING_START_TIME} ~ {TRADING_END_TIME} (ET)")
        print(f"   - 수익 임계값: {PROFIT_THRESHOLD*100}%")
        print("="*60)
        
        if USE_PAPER_TRADING:
            confirm = input("모의투자 모드로 자동매매를 시작하시겠습니까? (y/N): ")
            if confirm.lower() != 'y':
                self.logger.info("[시스템][취소] 자동매매 취소")
                print("자동매매가 취소되었습니다.")
                return
        else:
            confirm = input("정말로 실전 매매를 시작하시겠습니까?\n'START REAL TRADING'을 정확히 입력하세요: ")
            if confirm != "START REAL TRADING":
                self.logger.info("[시스템][취소] 실전 매매 취소")
                print("실전 매매가 취소되었습니다.")
                return
        
        # 🎯 프로그램 시작 시 종합 계좌 현황 출력
        self.logger.info("[시스템][시작] 프로그램 시작 - 종합 계좌 현황 출력")
        self.display_comprehensive_balance()
        
        # 초기 안전 점검
        if not self.safety_check():
            self.logger.error("[시스템][오류] 초기 안전 점검 실패 - 시스템 시작 중단")
            print("초기 안전 점검 실패로 시스템을 시작할 수 없습니다.")
            return
        
        # 초기 상태 확인
        if not self.is_trading_hours():
            time_until = self.get_time_until_trading()
            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)
            self.logger.warning(f"[시간][대기] 현재 운영 시간이 아닙니다. 거래시간까지 {hours}시간 {minutes}분 남음")
            print(f"현재 운영 시간이 아닙니다. 거래시간까지 {hours}시간 {minutes}분 남았습니다.")
            print("대기 모드로 실행됩니다.")
        
        self.setup_schedule()
        self.is_running = True
        
        # 초기 상태 출력
        self.print_status()
        
        print("\n🚀 자동매매 시스템이 시작되었습니다!")
        print("Ctrl+C를 눌러 중단할 수 있습니다.")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 스케줄 체크
                
        except KeyboardInterrupt:
            self.logger.info("[시스템][중단] 사용자에 의한 중단 요청")
            print("\n사용자에 의해 시스템이 중단되었습니다.")
        except Exception as e:
            self.logger.error(f"[시스템][오류] 시스템 실행 오류: {e}")
            print(f"시스템 오류로 중단되었습니다: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """자동매매 시스템 중지"""
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        self.logger.info(f"[시스템][중지] 🛑 {trading_mode} 자동매매 시스템 중지")
        self.is_running = False
        
        # 실행 통계 출력
        runtime = datetime.now() - self.trading_stats['start_time']
        
        print("\n" + "="*60)
        print(f"🛑 {trading_mode} 자동매매 시스템 종료 요약")
        print("="*60)
        print(f"📊 운영 통계:")
        print(f"   - 운영 시간: {runtime}")
        print(f"   - 총 주문: {self.trading_stats['total_orders']}건")
        print(f"   - 매수 주문: {self.trading_stats['buy_orders']}건")
        print(f"   - 매도 주문: {self.trading_stats['sell_orders']}건")
        print(f"   - 성공: {self.trading_stats['successful_orders']}건")
        print(f"   - 실패: {self.trading_stats['failed_orders']}건")
        
        if self.trading_stats['total_orders'] > 0:
            success_rate = (self.trading_stats['successful_orders'] / self.trading_stats['total_orders']) * 100
            print(f"   - 성공률: {success_rate:.1f}%")
        
        print("="*60)

def main():
    """메인 실행 함수"""

    # 1. 로그 파일 이름을 CSV로 변경
    log_filename = f"start_auto_trading_{datetime.now().strftime('%Y%m%d')}.csv"

    # 2. 로깅 설정 (CSV 형식)
    csv_formatter = logging.Formatter('%(asctime)s,%(levelname)s,%(message)s')

    file_handler = RotatingFileHandler(log_filename, maxBytes=5_000_000, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(csv_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(csv_formatter)

    logging.basicConfig(
        level=logging.WARNING,  # 불필요한 로그 최소화
        handlers=[file_handler, stream_handler]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # API 키 미설정 시 경고
        if KIS_APP_KEY == "your_app_key_here":
            logger.error("[시스템][오류] API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            print("❌ API 키가 설정되지 않았습니다.")
            return
        
        if USE_PAPER_TRADING:
            logger.warning("[시스템][모의] 모의투자 모드입니다.")
            print("⚠️ 현재 모의투자 모드로 설정되어 있습니다.")
            print("실전 매매를 위해서는 config.py에서 USE_PAPER_TRADING = False로 설정하세요.")
            
            confirm = input("모의투자 모드로 계속하시겠습니까? (y/N): ")
            if confirm.lower() != 'y':
                return
        
        # 실전 매매 시스템 실행
        trading_system = ProductionTradingSystem()
        trading_system.start()
        
    except Exception as e:
        logger.exception("[시스템][오류] 시스템 시작 오류 발생")
        print(f"시스템 시작 오류: {e}")


if __name__ == "__main__":
    main() 