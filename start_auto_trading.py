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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from strategy_pjt1 import TradingStrategy
from order_manager import OrderManager
from config import *
from logging.handlers import RotatingFileHandler



class ProductionTradingSystem:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        self.strategy = TradingStrategy()
        self.order_manager = OrderManager()
        
        # 전략은 이미 토큰 매니저 클라이언트를 사용하므로 별도 할당 불필요
        
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
    
    def print_time_status(self):
        """시간 상태 출력 (1시간마다)"""
        try:
            et_now = datetime.now(self.et_tz)
            
            # 1시간마다만 출력
            if (self.last_time_check and 
                et_now - self.last_time_check < timedelta(hours=1)):
                return
            
            self.last_time_check = et_now
            
            if self.is_trading_hours():
                self.logger.info(f"🟢 거래시간 중 - {et_now.strftime('%Y-%m-%d %H:%M:%S ET')}")
                return
            
            time_until = self.get_time_until_trading()
            
            if time_until.total_seconds() > 0:
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                if et_now.weekday() >= 5:
                    self.logger.info(f"🔴 주말 - 다음 거래시간까지 {hours}시간 {minutes}분 남음")
                else:
                    self.logger.info(f"🟡 거래시간 외 - 다음 거래시간까지 {hours}시간 {minutes}분 남음")
                    self.logger.info(f"   현재: {et_now.strftime('%H:%M:%S ET')}, "
                                   f"거래시간: {TRADING_START_TIME}~{TRADING_END_TIME} ET")
            
        except Exception as e:
            self.logger.error(f"시간 상태 출력 오류: {e}")
    
    def safety_check(self):
        """안전 점검"""
        try:
            # 1. 토큰 강제 재발급 (동기화 문제 해결)
            self.logger.info("🔄 토큰 강제 재발급 중...")
            self.api_client.token_expires_at = 0  # 토큰 강제 만료
            if not self.api_client.ensure_token_valid():
                self.logger.error("❌ API 토큰 문제")
                return False
            
            # 2. 일일 주문 수 체크
            if self.trading_stats['total_orders'] >= self.safety_checks['max_daily_orders']:
                self.logger.error(f"❌ 일일 최대 주문 수 초과: {self.trading_stats['total_orders']}")
                return False
            
            # 3. 계좌 잔고 체크
            balance = self.api_client.get_account_balance()
            if not balance:
                self.logger.error("❌ 계좌 조회 실패")
                return False
            
            self.logger.info(f"✅ 안전 점검 통과 (예수금: ${balance['cash']:.2f}, 주문수: {self.trading_stats['total_orders']})")
            return True
            
        except Exception as e:
            self.logger.error(f"안전 점검 오류: {e}")
            return False

    def display_account_status(self):
        """계좌 현황을 콘솔에 상세 표시"""
        try:
            print("\n" + "="*60)
            print("📊 계좌 현황")
            print("="*60)
            
            # 계좌 잔고 조회
            balance = self.api_client.get_account_balance()
            if not balance:
                print("❌ 계좌 조회 실패")
                self.logger.error("❌ 계좌 조회 실패")
                return
            
            # 예수금 표시
            print(f"💰 예수금: ${balance['cash']:,.2f}")
            self.logger.info(f"💰 예수금: ${balance['cash']:,.2f}")
            
            # 보유 종목 표시
            positions = balance.get('positions', [])
            if positions:
                print(f"📈 보유 종목: {len(positions)}개")
                print("-" * 60)
                
                total_market_value = 0
                total_profit_loss = 0
                
                for i, position in enumerate(positions, 1):
                    symbol = position.get("ovrs_pdno", "N/A")
                    quantity = int(position.get("ovrs_cblc_qty", 0))
                    avg_price = float(position.get("pchs_avg_pric", 0))
                    
                    if quantity <= 0:
                        continue
                    
                    # 현재가 조회 (실패해도 계속 진행)
                    try:
                        current_price = self.api_client.get_current_price(symbol)
                        if current_price and current_price > 0:
                            market_value = current_price * quantity
                            purchase_value = avg_price * quantity
                            profit_loss = market_value - purchase_value
                            profit_rate = (profit_loss / purchase_value) * 100 if purchase_value > 0 else 0
                            
                            total_market_value += market_value
                            total_profit_loss += profit_loss
                            
                            # 수익률에 따른 아이콘
                            if profit_rate >= 5:
                                icon = "🔥"
                            elif profit_rate > 0:
                                icon = "💰"
                            else:
                                icon = "📉"
                            
                            print(f"{i:2d}. {symbol:>6s}: {quantity:>4d}주 @ ${avg_price:>6.2f} "
                                  f"→ ${current_price:>6.2f} ({profit_rate:+6.1f}%) ${profit_loss:+8.2f} {icon}")
                            
                            self.logger.info(f"보유종목: {symbol} {quantity}주, 평균가: ${avg_price:.2f}, "
                                           f"현재가: ${current_price:.2f}, 수익률: {profit_rate:+.1f}%")
                        else:
                            # 현재가 조회 실패 시 기본 정보만 표시
                            purchase_value = avg_price * quantity
                            print(f"{i:2d}. {symbol:>6s}: {quantity:>4d}주 @ ${avg_price:>6.2f} → 현재가 조회 실패 (매수금액: ${purchase_value:.2f})")
                            self.logger.warning(f"보유종목 {symbol} 현재가 조회 실패")
                    except Exception as e:
                        # 현재가 조회 오류 시 기본 정보만 표시
                        purchase_value = avg_price * quantity
                        print(f"{i:2d}. {symbol:>6s}: {quantity:>4d}주 @ ${avg_price:>6.2f} → 조회 오류 (매수금액: ${purchase_value:.2f})")
                        self.logger.warning(f"보유종목 {symbol} 현재가 조회 오류: {e}")
                
                print("-" * 60)
                if total_market_value > 0:
                    total_profit_rate = (total_profit_loss / (total_market_value - total_profit_loss)) * 100
                    print(f"📊 총 평가금액: ${total_market_value:,.2f}")
                    print(f"📈 총 평가손익: ${total_profit_loss:+,.2f} ({total_profit_rate:+.1f}%)")
                    
                    # 전체 계좌 가치
                    total_account_value = balance['cash'] + total_market_value
                    print(f"💎 총 계좌 가치: ${total_account_value:,.2f}")
                    
                    self.logger.info(f"총 평가손익: ${total_profit_loss:+,.2f} ({total_profit_rate:+.1f}%)")
                    self.logger.info(f"총 계좌 가치: ${total_account_value:,.2f}")
            else:
                print("📭 보유 종목 없음")
                self.logger.info("보유 종목 없음")
            
            print("="*60)
            
        except Exception as e:
            print(f"❌ 계좌 현황 표시 오류: {e}")
            self.logger.error(f"계좌 현황 표시 오류: {e}")

    def simple_balance_display(self):
        """간단한 예수금과 보유종목만 표시 (현재가 조회 없음)"""
        try:
            print("\n" + "="*60)
            print("💰 간단 계좌 현황")
            print("="*60)
            
            # 계좌 잔고 조회
            balance = self.api_client.get_account_balance()
            if not balance:
                print("❌ 계좌 조회 실패")
                return
            
            # 예수금 표시
            cash = balance.get('cash', 0)
            print(f"💵 예수금: ${cash:,.2f}")
            
            # 보유 종목 기본 정보만 표시 (현재가 조회 없음)
            positions = balance.get('positions', [])
            if positions:
                print(f"📈 보유 종목: {len(positions)}개")
                print("-" * 60)
                print(f"{'번호':>3} {'종목':>6} {'수량':>8} {'평균가':>10} {'매수금액':>12}")
                print("-" * 60)
                
                total_invested = 0
                for i, position in enumerate(positions, 1):
                    symbol = position.get("ovrs_pdno", "N/A")
                    quantity = int(position.get("ovrs_cblc_qty", 0))
                    avg_price = float(position.get("pchs_avg_pric", 0))
                    
                    if quantity > 0:
                        invested = avg_price * quantity
                        total_invested += invested
                        print(f"{i:3d} {symbol:>6} {quantity:8d}주 ${avg_price:8.2f} ${invested:10.2f}")
                
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
            self.logger.info("🔴 운영 시간 외 - 매수 전략 스킵")
            return
        
        if not self.safety_check():
            self.logger.error("❌ 안전 점검 실패 - 매수 중단")
            return
        
        try:
            self.logger.info("=== 🚀 실전 매수 전략 실행 시작 ===")
            
            # 1. 상승 필터 조건 확인
            filter_passed = self.strategy.check_filter_condition()
            if not filter_passed:
                self.logger.info("❌ 상승 필터 조건 미충족 - 매수 신호 없음")
                return
            
            self.logger.info("✅ 상승 필터 조건 충족")
            
            # 2. 상위 하락 종목 선정
            top_declining = self.strategy.get_top_declining_stocks(3)
            if not top_declining:
                self.logger.info("❌ 하락 종목 없음 - 매수 신호 없음")
                return
            
            self.logger.info(f"📉 상위 하락 종목: {', '.join(top_declining)}")
            
            # 3. 각 종목별 실제 매수 실행
            balance = self.api_client.get_account_balance()
            if not balance:
                self.logger.error("❌ 계좌 조회 실패")
                return
            
            if balance['cash'] <= self.safety_checks['min_account_balance']:
                self.logger.warning(f"⚠️ 예수금 부족: ${balance['cash']:.2f}")
                return
            
            for symbol in top_declining:
                current_price = self.api_client.get_current_price(symbol)
                if current_price is None:
                    self.logger.warning(f"⚠️ {symbol} 현재가 조회 실패 - 스킵")
                    continue
                
                # 매수 수량 계산
                quantity = self.strategy.calculate_position_size(symbol, balance['cash'])
                
                if quantity > 0:
                    total_cost = quantity * current_price
                    self.logger.info(f"💰 매수 주문 실행: {symbol}")
                    self.logger.info(f"   - 현재가: ${current_price:.2f}")
                    self.logger.info(f"   - 수량: {quantity}주")
                    self.logger.info(f"   - 총 비용: ${total_cost:.2f}")
                    
                    # 🚨 실제 주문 실행!
                    order_id = self.order_manager.place_order_with_tracking(
                        symbol, quantity, current_price, "buy"
                    )
                    
                    if order_id:
                        self.logger.info(f"✅ 매수 주문 성공: {order_id}")
                        self.trading_stats['total_orders'] += 1
                        self.trading_stats['successful_orders'] += 1
                        self.trading_stats['buy_orders'] += 1
                    else:
                        self.logger.error(f"❌ 매수 주문 실패: {symbol}")
                        self.trading_stats['failed_orders'] += 1
                    
                    # 주문 간 대기 (API 제한 방지)
                    time.sleep(2)
            
            self.logger.info("=== ✅ 실전 매수 전략 실행 완료 ===")
            
        except Exception as e:
            self.logger.error(f"❌ 매수 전략 실행 오류: {e}")
    
    def execute_sell_strategy(self):
        """매도 전략 실행 (실제 주문)"""
        if not self.is_trading_hours():
            self.logger.info("🔴 운영 시간 외 - 매도 전략 스킵")
            return
        
        if not self.safety_check():
            self.logger.error("❌ 안전 점검 실패 - 매도 중단")
            return
        
        try:
            self.logger.info("=== 🚀 실전 매도 전략 실행 시작 ===")
            
            # 보유종목 조회
            balance = self.api_client.get_account_balance()
            if not balance or not balance.get("positions"):
                self.logger.info("ℹ️ 보유 종목 없음")
                return
            
            high_profit_targets = []
            normal_profit_targets = []
            
            for position in balance["positions"]:
                symbol = position["ovrs_pdno"]
                quantity = int(position["ovrs_cblc_qty"])
                avg_buy_price = float(position["pchs_avg_pric"])
                
                if quantity <= 0:
                    continue
                
                current_price = self.api_client.get_current_price(symbol)
                if current_price is None:
                    self.logger.warning(f"⚠️ {symbol} 현재가 조회 실패 - 스킵")
                    continue
                
                profit_rate = self.strategy.calculate_profit_rate(symbol, current_price, avg_buy_price)
                
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
                self.logger.info(f"🔥 고수익 매도 실행: {target['symbol']}")
                self.logger.info(f"   - 수익률: {target['profit_rate']:.2%}")
                self.logger.info(f"   - 현재가: ${target['current_price']:.2f}")
                
                # 🚨 실제 매도 주문 실행!
                order_id = self.order_manager.place_order_with_tracking(
                    target['symbol'], target['quantity'], target['current_price'], "sell"
                )
                
                if order_id:
                    profit_amount = (target['current_price'] - target['avg_buy_price']) * target['quantity']
                    self.logger.info(f"✅ 고수익 매도 성공: {order_id} (예상수익: ${profit_amount:.2f})")
                    self.trading_stats['total_orders'] += 1
                    self.trading_stats['successful_orders'] += 1
                    self.trading_stats['sell_orders'] += 1
                else:
                    self.logger.error(f"❌ 고수익 매도 실패: {target['symbol']}")
                    self.trading_stats['failed_orders'] += 1
                
                time.sleep(2)  # 주문 간 대기
            
            # 일반 매도 (최고 수익률 1개)
            if normal_profit_targets and not high_profit_targets:
                best_target = max(normal_profit_targets, key=lambda x: x['profit_rate'])
                
                self.logger.info(f"📈 일반 매도 실행: {best_target['symbol']}")
                self.logger.info(f"   - 수익률: {best_target['profit_rate']:.2%}")
                self.logger.info(f"   - 현재가: ${best_target['current_price']:.2f}")
                
                # 🚨 실제 매도 주문 실행!
                order_id = self.order_manager.place_order_with_tracking(
                    best_target['symbol'], best_target['quantity'], best_target['current_price'], "sell"
                )
                
                if order_id:
                    profit_amount = (best_target['current_price'] - best_target['avg_buy_price']) * best_target['quantity']
                    self.logger.info(f"✅ 일반 매도 성공: {order_id} (예상수익: ${profit_amount:.2f})")
                    self.trading_stats['total_orders'] += 1
                    self.trading_stats['successful_orders'] += 1
                    self.trading_stats['sell_orders'] += 1
                else:
                    self.logger.error(f"❌ 일반 매도 실패: {best_target['symbol']}")
                    self.trading_stats['failed_orders'] += 1
            
            if not high_profit_targets and not normal_profit_targets:
                self.logger.info("ℹ️ 매도 대상 없음 (모든 종목 손실 중)")
            
            self.logger.info("=== ✅ 실전 매도 전략 실행 완료 ===")
            
        except Exception as e:
            self.logger.error(f"❌ 매도 전략 실행 오류: {e}")
    
    def cleanup_orders(self):
        """주문 정리 작업"""
        try:
            self.logger.info("🧹 주문 정리 작업 시작")
            self.order_manager.cleanup_old_orders()
            
        except Exception as e:
            self.logger.error(f"❌ 주문 정리 오류: {e}")
    
    def print_status(self):
        """현재 상태 출력"""
        try:
            et_now = datetime.now(self.et_tz)
            
            # 시간 상태 출력
            self.print_time_status()
            
            if not self.is_trading_hours():
                return
            
            self.logger.info(f"=== 🚀 실전 매매 시스템 상태 ({et_now.strftime('%Y-%m-%d %H:%M:%S ET')}) ===")
            
            # 주문 통계
            if self.trading_stats['total_orders'] > 0:
                success_rate = (self.trading_stats['successful_orders'] / self.trading_stats['total_orders']) * 100
                self.logger.info(f"📊 주문 통계: 총 {self.trading_stats['total_orders']}건 "
                               f"(성공: {self.trading_stats['successful_orders']}, "
                               f"실패: {self.trading_stats['failed_orders']}, "
                               f"성공률: {success_rate:.1f}%)")
            
            # 계좌 상태
            balance = self.api_client.get_account_balance()
            if balance:
                self.logger.info(f"💰 계좌 현황: 예수금 ${balance['cash']:.2f}, 보유종목 {len(balance['positions'])}개")
                
                # 보유종목 수익률 요약
                total_profit = 0
                for position in balance['positions']:
                    symbol = position["ovrs_pdno"]
                    quantity = int(position["ovrs_cblc_qty"])
                    avg_price = float(position["pchs_avg_pric"])
                    
                    if quantity <= 0:
                        continue
                    
                    current_price = self.api_client.get_current_price(symbol)
                    if current_price:
                        profit = (current_price - avg_price) * quantity
                        profit_rate = ((current_price - avg_price) / avg_price) * 100
                        total_profit += profit
                        
                        status = "🔥" if profit_rate >= 5 else "💰" if profit_rate > 0 else "📉"
                        self.logger.info(f"   {symbol}: {profit_rate:+.1f}% (${profit:+.2f}) {status}")
                
                if total_profit != 0:
                    self.logger.info(f"📈 총 평가손익: ${total_profit:+.2f}")
            
        except Exception as e:
            self.logger.error(f"❌ 상태 출력 오류: {e}")
    
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
        
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        self.logger.info(f"🚀 {trading_mode} 자동매매 스케줄 설정 완료")
        self.logger.info(f"   - 매도 전략: {SELL_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"   - 매수 전략: {BUY_INTERVAL_MINUTES}분 주기")
        self.logger.info(f"   - 주문 정리: 20분 주기")
        self.logger.info(f"   - 상태 출력: 5분 주기")
        self.logger.info(f"   - 운영 시간: {TRADING_START_TIME} ~ {TRADING_END_TIME} (ET)")
        if not USE_PAPER_TRADING:
            self.logger.warning("⚠️ 주의: 실제 돈으로 거래합니다!")
        else:
            self.logger.info("✅ 모의투자 모드로 안전하게 실행됩니다!")
    
    def start(self):
        """자동매매 시스템 시작"""
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        
        self.logger.warning("🚨" * 20)
        self.logger.warning(f"⚠️ {trading_mode} 자동매매 시스템 시작!")
        if not USE_PAPER_TRADING:
            self.logger.warning("⚠️ 실제 돈으로 거래가 실행됩니다!")
        self.logger.warning("🚨" * 20)
        
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
                self.logger.info("❌ 자동매매 취소")
                print("자동매매가 취소되었습니다.")
                return
        else:
            confirm = input("정말로 실전 매매를 시작하시겠습니까?\n'START REAL TRADING'을 정확히 입력하세요: ")
            if confirm != "START REAL TRADING":
                self.logger.info("❌ 실전 매매 취소")
                print("실전 매매가 취소되었습니다.")
                return
        
        # 계좌 현황 먼저 표시 (안전 점검 전에)
        self.simple_balance_display()
        
        # 초기 안전 점검
        if not self.safety_check():
            self.logger.error("❌ 초기 안전 점검 실패 - 시스템 시작 중단")
            print("초기 안전 점검 실패로 시스템을 시작할 수 없습니다.")
            return
        
        # 초기 상태 확인
        if not self.is_trading_hours():
            time_until = self.get_time_until_trading()
            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)
            self.logger.warning(f"🔴 현재 운영 시간이 아닙니다. 거래시간까지 {hours}시간 {minutes}분 남음")
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
            self.logger.info("🛑 사용자에 의한 중단 요청")
            print("\n사용자에 의해 시스템이 중단되었습니다.")
        except Exception as e:
            self.logger.error(f"❌ 시스템 실행 오류: {e}")
            print(f"시스템 오류로 중단되었습니다: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """자동매매 시스템 중지"""
        trading_mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        self.logger.info(f"=== 🛑 {trading_mode} 자동매매 시스템 중지 ===")
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
        level=getattr(logging, LOG_LEVEL),
        handlers=[file_handler, stream_handler]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # API 키 미설정 시 경고
        if KIS_APP_KEY == "your_app_key_here":
            logger.error("❌ API 키가 설정되지 않았습니다. config.py를 확인해주세요.")
            print("❌ API 키가 설정되지 않았습니다.")
            return
        
        if USE_PAPER_TRADING:
            logger.warning("⚠️ 모의투자 모드입니다.")
            print("⚠️ 현재 모의투자 모드로 설정되어 있습니다.")
            print("실전 매매를 위해서는 config.py에서 USE_PAPER_TRADING = False로 설정하세요.")
            
            confirm = input("모의투자 모드로 계속하시겠습니까? (y/N): ")
            if confirm.lower() != 'y':
                return
        
        # 실전 매매 시스템 실행
        trading_system = ProductionTradingSystem()
        trading_system.start()
        
    except Exception as e:
        logger.exception("❌ 시스템 시작 오류 발생")
        print(f"시스템 시작 오류: {e}")


if __name__ == "__main__":
    main() 