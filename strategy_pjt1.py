"""
PJT #1 매매 전략 구현
"""
import logging
import json
from datetime import datetime, timedelta
from kis_api import KISAPIClient
from token_manager import TokenManager
from transaction_logger import TransactionLogger
from config import STOCKS_CONFIG_FILE, PROFIT_THRESHOLD

class TradingStrategy:
    def __init__(self):
        # 토큰 매니저 클라이언트 사용 (403 에러 방지)
        self.api_client = KISAPIClient()
        self.token_manager = TokenManager()
        self.transaction_logger = TransactionLogger()
        self.logger = logging.getLogger(__name__)
        self.last_sell_prices = {}
        self.last_buy_prices = {}
        self.filter_stocks, self.watch_list = self.load_stock_config()

    def load_stock_config(self):
        try:
            with open(STOCKS_CONFIG_FILE, 'r') as f:
                config = json.load(f)

            filter_section = config.get("filter_stocks", {})
            if isinstance(filter_section, dict):
                filter_stocks = [symbol for symbol, enabled in filter_section.items() if enabled]
            elif isinstance(filter_section, list):
                filter_stocks = filter_section
            else:
                filter_stocks = []

            watch_list = config.get("watch_list", [])

            self.logger.info(f"설정 파일 로드 완료: filter={len(filter_stocks)}종목, watch={len(watch_list)}종목")
            print("\n필터 종목:", ", ".join(filter_stocks))
            print("관심 종목:", ", ".join(watch_list), "\n")

            # 종목 유효성 검증 건너뛰기 (API 제한 방지)
            self.logger.info("종목 유효성 검증 생략 - 설정된 모든 종목을 사용합니다.")

            return filter_stocks, watch_list

        except Exception as e:
            self.logger.error(f"stocks_config.json 로드 실패: {e}")
            return [], []


    def check_filter_condition(self):
        """필터 조건 확인 (오류 처리 강화)"""
        try:
            # 시장이 닫혀있으면 즉시 종료
            if not self.api_client.is_market_open():
                self.logger.critical("=== 필터 조건 확인 중단: 시장이 닫혀있습니다 ===")
                return False

            self.logger.info("=== 필터 조건 확인 시작 ===")

            if not self.filter_stocks:
                self.logger.warning("필터 종목이 없습니다.")
                return True  # 필터 종목이 없으면 통과로 처리

            self.logger.info(f"필터 종목: {self.filter_stocks}")
            rising_count = 0
            total_count = len(self.filter_stocks)
            failed_symbols = []
            
            for symbol in self.filter_stocks:
                try:
                    current_price = self.api_client.get_current_price(symbol)
                    prev_close = self.api_client.get_previous_close(symbol)

                    if current_price is None or prev_close is None:
                        self.logger.warning(f"{symbol}: 가격 조회 실패 - 스킵")
                        failed_symbols.append(symbol)
                        continue

                    price_change = current_price - prev_close
                    price_change_pct = (price_change / prev_close) * 100
                    
                    if current_price > prev_close:
                        rising_count += 1
                        self.logger.debug(f"필터 통과: {symbol} ↑ (현재: ${current_price:.2f}, 전일: ${prev_close:.2f}, 변동: +${price_change:.2f} (+{price_change_pct:.2f}%))")
                    else:
                        self.logger.debug(f"필터 미충족: {symbol} ↓ (현재: ${current_price:.2f}, 전일: ${prev_close:.2f}, 변동: ${price_change:.2f} ({price_change_pct:.2f}%))")
                        
                except Exception as e:
                    self.logger.error(f"{symbol} 필터 확인 중 오류: {e}")
                    failed_symbols.append(symbol)
                    continue

            # 성공한 종목들만으로 판단
            successful_count = total_count - len(failed_symbols)
            if successful_count == 0:
                self.logger.error("모든 필터 종목 조회 실패")
                return False
            
            # 성공한 종목 중 모두 상승해야 조건 충족
            all_rising = (rising_count == successful_count)
            
            if failed_symbols:
                self.logger.warning(f"실패한 필터 종목들: {', '.join(failed_symbols)}")
            
            self.logger.info(f"필터 결과: {rising_count}/{successful_count} 종목 상승")
            
            if all_rising:
                self.logger.info("모든 필터 종목 상승 → 매수 조건 충족")
            else:
                self.logger.info("일부 필터 종목 하락 → 매수 조건 미충족")
            
            return all_rising
            
        except Exception as e:
            self.logger.error(f"필터 조건 확인 중 오류: {e}")
            return False

    def calculate_decline_rate(self, symbol):
        """종목별 하락률 계산"""
        try:
            current_price = self.api_client.get_current_price(symbol)
            prev_close = self.api_client.get_previous_close(symbol)
            
            if current_price is None or prev_close is None:
                self.logger.warning(f"{symbol}: 가격 데이터 없음 → 하락률 계산 불가")
                return None
            
            if prev_close == 0:
                self.logger.warning(f"{symbol}: 전일 종가가 0 → 하락률 계산 불가")
                return None
            
            decline_rate = (prev_close - current_price) / prev_close
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            self.logger.debug(f"{symbol} 하락률: {decline_rate:.4f} ({price_change_pct:.2f}%) [현재: ${current_price:.2f}, 전일: ${prev_close:.2f}]")
            return decline_rate
            
        except Exception as e:
            self.logger.error(f"{symbol} 하락률 계산 중 오류: {e}")
            return None

    def get_top_declining_stocks(self, count=3):
        """하락률 상위 종목 조회"""
        try:
            # 시장이 닫혀있으면 즉시 종료
            if not self.api_client.is_market_open():
                self.logger.critical("=== 하락률 조회 중단: 시장이 닫혀있습니다 ===")
                return []

            self.logger.info(f"=== 하락률 상위 {count}종목 조회 시작 ===")

            decline_rates = {}
            failed_symbols = []
            
            for symbol in self.watch_list:
                decline_rate = self.calculate_decline_rate(symbol)
                if decline_rate is not None:
                    decline_rates[symbol] = decline_rate
                else:
                    failed_symbols.append(symbol)
            
            if failed_symbols:
                self.logger.warning(f"하락률 계산 실패 종목: {', '.join(failed_symbols)}")
            
            if not decline_rates:
                self.logger.warning("하락률 계산 가능한 종목이 없습니다.")
                return []
            
            # 하락률 기준으로 정렬 (내림차순)
            sorted_stocks = sorted(decline_rates.items(), key=lambda x: x[1], reverse=True)
            top_stocks = [symbol for symbol, rate in sorted_stocks[:count]]
            
            self.logger.info("=== 하락률 상위 종목 순위 ===")
            for i, (symbol, rate) in enumerate(sorted_stocks[:count], 1):
                self.logger.info(f"{i}위: {symbol} (하락률: {rate:.4f})")
            
            self.logger.info(f"선정된 하락률 상위 종목: {top_stocks}")
            return top_stocks
            
        except Exception as e:
            self.logger.error(f"하락률 상위 종목 조회 중 오류: {e}")
            return []

    def monitor_watch_list_trend(self):
        try:
            trend_data = []
            rising_count = 0
            falling_count = 0
            failed_count = 0
            
            for symbol in self.watch_list:
                current = self.api_client.get_current_price(symbol)
                prev = self.api_client.get_previous_close(symbol)
                
                if current is None or prev is None:
                    failed_count += 1
                    continue
                    
                diff = current - prev
                percent = (diff / prev) * 100
                
                if diff > 0:
                    rising_count += 1
                elif diff < 0:
                    falling_count += 1
                    
                trend_data.append({'symbol': symbol, 'percent': percent})

            # 요약 로그
            total = len(self.watch_list)
            self.logger.info(f"관심종목 추세: 상승 {rising_count}개, 하락 {falling_count}개, 실패 {failed_count}개 (총 {total}개)")

            # 하락률 상위 3종목만 상세 표시
            if trend_data:
                falling = sorted(trend_data, key=lambda x: x['percent'])[:3]
                self.logger.info("하락률 상위 3종목:")
                for item in falling:
                    self.logger.info(f"- {item['symbol']}: {item['percent']:.2f}%")
        except Exception as e:
            self.logger.error(f"모니터링 실패: {e}")

    def calculate_position_size(self, symbol, available_cash):
        """매수 수량 계산"""
        try:
            current_price = self.api_client.get_current_price(symbol)
            if current_price is None or current_price <= 0:
                self.logger.warning(f"{symbol}: 현재가 조회 실패 또는 0 이하 → 매수 수량 계산 불가")
                return 0
            
            # 예수금의 1/3을 한 종목당 최대 투자
            max_investment = available_cash / 3
            max_quantity = int(max_investment / current_price)
            
            # 최소 1주, 최대 100주로 제한
            quantity = max(1, min(max_quantity, 100))
            
            total_cost = quantity * current_price
            investment_ratio = (total_cost / available_cash) * 100
            
            self.logger.info(f"{symbol} 매수 수량 계산:")
            self.logger.info(f"  - 현재가: ${current_price:.2f}")
            self.logger.info(f"  - 예수금: ${available_cash:.2f}")
            self.logger.info(f"  - 최대 투자금: ${max_investment:.2f} (33.3%)")
            self.logger.info(f"  - 계산된 수량: {max_quantity}주")
            self.logger.info(f"  - 최종 수량: {quantity}주 (1~100주 제한)")
            self.logger.info(f"  - 총 투자금: ${total_cost:.2f} ({investment_ratio:.1f}%)")
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"{symbol} 매수 수량 계산 중 오류: {e}")
            return 0

    def should_buy(self, symbol, current_price):
        """매수 조건 확인"""
        from config import CHECK_PREVIOUS_SELL_PRICE

        # 이전 매도가격 체크 옵션이 OFF인 경우
        if not CHECK_PREVIOUS_SELL_PRICE:
            self.logger.info(f"{symbol}: 매수 조건 충족 (이전 매도가격 체크 OFF)")
            return True

        # 이전 매도가격 체크 옵션이 ON인 경우
        if symbol not in self.last_sell_prices:
            self.logger.info(f"{symbol}: 첫 매수 대상 (이전 매도 기록 없음)")
            return True

        last_sell_price = self.last_sell_prices[symbol]
        if current_price < last_sell_price:
            self.logger.info(f"{symbol}: 매수 조건 충족 (현재가: ${current_price:.2f} < 이전매도가: ${last_sell_price:.2f})")
            return True
        else:
            self.logger.info(f"{symbol}: 매수 조건 불충족 (현재가: ${current_price:.2f} >= 이전매도가: ${last_sell_price:.2f})")
            return False

    def execute_buy_strategy(self):
        try:
            # 시장이 닫혀있으면 즉시 종료
            if not self.api_client.is_market_open():
                self.logger.critical("=== 매수 전략 중단: 시장이 닫혀있습니다 (미국 장 시간 외) ===")
                self.transaction_logger.log_strategy_execution("buy", "skipped", "시장 닫힘 - 미국 장 시간 외")
                return

            # 실전거래 모드 확인
            from config import USE_PAPER_TRADING
            if USE_PAPER_TRADING:
                self.logger.info("=== 매수 전략 실행 시작 (모의투자 모드) ===")
            else:
                self.logger.critical("=== 매수 전략 실행 시작 (실전거래 모드) ===")
                print("🔴 실전 매수 전략 실행 중...")

            self.transaction_logger.log_strategy_execution("buy", "started", "매수 전략 실행 시작")
            
            self.monitor_watch_list_trend()
            if not self.check_filter_condition():
                self.logger.info("필터 미충족 → 매수 중단")
                self.transaction_logger.log_strategy_execution("buy", "skipped", "필터 조건 미충족")
                return

            balance = self.api_client.get_account_balance()
            if balance is None:
                self.logger.error("잔고 조회 실패")
                self.transaction_logger.log_strategy_execution("buy", "error", "잔고 조회 실패")
                return
            
            # 잔고 기록 저장
            self.transaction_logger.log_balance_check(balance)
            
            available_cash = balance["cash"]
            if available_cash < 100:
                self.logger.info(f"예수금 부족 (${available_cash:.2f}) → 매수 생략")
                self.transaction_logger.log_strategy_execution("buy", "skipped", f"예수금 부족: ${available_cash:.2f}")
                return

            self.logger.info(f"예수금: ${available_cash:.2f}")
            top_declining = self.get_top_declining_stocks()
            self.logger.info(f"하락률 상위 종목: {top_declining}")

            buy_orders_placed = 0
            import time  # 딜레이를 위한 time 모듈

            for symbol in top_declining:
                price = self.api_client.get_current_price(symbol)
                if price is None:
                    self.logger.warning(f"{symbol}: 현재가 조회 실패 → 스킵")
                    continue

                if not self.should_buy(symbol, price):
                    self.logger.info(f"{symbol}: 매수 조건 불충족 (현재가: ${price:.2f}) → 스킵")
                    continue

                quantity = self.calculate_position_size(symbol, available_cash)
                if quantity <= 0:
                    self.logger.info(f"{symbol}: 매수 수량 계산 실패 → 스킵")
                    continue

                # 가격을 소수점 2자리로 반올림 (API 요구사항)
                rounded_price = round(price, 2)
                self.logger.info(f"매수 주문 시도: {symbol} {quantity}주 @ ${rounded_price:.2f}")
                if not USE_PAPER_TRADING:
                    print(f"🔴 실전 매수 주문: {symbol} {quantity}주 @ ${rounded_price:.2f}")

                order_id = self.api_client.place_order(symbol, quantity, rounded_price, "buy")
                if order_id:
                    self.last_buy_prices[symbol] = rounded_price
                    buy_orders_placed += 1
                    if not USE_PAPER_TRADING:
                        print(f"✅ 실전 매수 완료: {symbol} {quantity}주 @ ${price:.2f}")
                    self.logger.info(f"매수 완료: {symbol} {quantity}주 @ ${price:.2f}")

                    # 매수 주문 기록 저장
                    self.transaction_logger.log_buy_order(
                        symbol=symbol,
                        quantity=quantity,
                        price=price,
                        order_type="market",
                        status="filled",
                        balance_cash=available_cash,
                        notes=f"매수 전략 - 하락률 상위 종목 (순위: {top_declining.index(symbol)+1})"
                    )

                    # 매수 성공 후 잔액 재조회 및 업데이트
                    time.sleep(2)  # API 처리를 위한 2초 대기
                    self.logger.info(f"{symbol} 매수 후 잔액 재조회 중...")

                    balance = self.api_client.get_account_balance()
                    if balance:
                        available_cash = balance["cash"]
                        self.logger.info(f"잔액 업데이트 완료: ${available_cash:.2f}")
                    else:
                        # 잔액 조회 실패시 예상 잔액으로 계산
                        estimated_cost = quantity * rounded_price
                        available_cash = max(0, available_cash - estimated_cost)
                        self.logger.warning(f"잔액 조회 실패 - 예상 잔액 사용: ${available_cash:.2f}")
                else:
                    self.logger.error(f"{symbol}: 매수 주문 실패")
            
            if buy_orders_placed > 0:
                self.logger.info(f"매수 전략 완료: {buy_orders_placed}건 주문 성공")
                self.transaction_logger.log_strategy_execution("buy", "completed", f"{buy_orders_placed}건 매수 주문 성공")
            else:
                self.logger.info("매수 전략 완료: 주문할 종목 없음")
                self.transaction_logger.log_strategy_execution("buy", "completed", "주문할 종목 없음")
                
        except Exception as e:
            self.logger.error(f"매수 전략 실패: {e}")
            self.transaction_logger.log_strategy_execution("buy", "error", f"오류: {e}")

    def calculate_profit_rate(self, symbol, current, avg_buy):
        try:
            current = float(current)
            avg_buy = float(avg_buy)
            if avg_buy == 0:
                return 'N/A'
            return (current - avg_buy) / avg_buy
        except Exception:
            return 'N/A'

    def should_sell(self, symbol, current_price):
        """
        매도 조건 확인 (API에서 실시간 평균단가 조회)
        - 메모리에만 의존하지 않고 API에서 실제 평균단가 확인
        - 프로그램 재시작 후에도 정확한 판단 가능
        """
        # 먼저 API에서 현재 보유 종목의 평균단가 조회
        balance = self.api_client.get_account_balance()
        if balance and balance.get('positions'):
            for position in balance['positions']:
                if position['symbol'] == symbol:
                    avg_price = float(position.get('avg_price', 0))
                    if avg_price > 0:
                        # API에서 조회한 평균단가 기준으로 판단
                        # 매도 조건: 현재가 >= 평균단가 * 1.015 (1.5% 수익)
                        target_price = avg_price * 1.015
                        profit_rate = (current_price - avg_price) / avg_price

                        if current_price >= target_price:
                            self.logger.info(f"{symbol}: 매도 조건 충족 (현재가: ${current_price:.2f} >= 목표가: ${target_price:.2f}, 수익률: {profit_rate:.2%})")
                            return True
                        else:
                            self.logger.info(f"{symbol}: 매도 조건 불충족 (현재가: ${current_price:.2f} < 목표가: ${target_price:.2f}, 수익률: {profit_rate:.2%})")
                            return False

        # API에서 못 찾으면 메모리 기준으로 폴백
        if symbol not in self.last_buy_prices:
            self.logger.info(f"{symbol}: 매도 조건 충족 (이전 매수 기록 없음, API 조회 실패)")
            return True

        # 메모리의 매수가 기준 1.5% 수익 확인
        buy_price = self.last_buy_prices[symbol]
        target_price = buy_price * 1.015
        profit_rate = (current_price - buy_price) / buy_price

        if current_price >= target_price:
            self.logger.info(f"{symbol}: 매도 조건 충족 (현재가: ${current_price:.2f} >= 목표가: ${target_price:.2f}, 수익률: {profit_rate:.2%})")
            return True
        else:
            self.logger.info(f"{symbol}: 매도 조건 불충족 (현재가: ${current_price:.2f} < 목표가: ${target_price:.2f}, 수익률: {profit_rate:.2%})")
            return False

    def execute_sell_strategy(self):
        try:
            # 시장이 닫혀있으면 즉시 종료
            if not self.api_client.is_market_open():
                self.logger.critical("=== 매도 전략 중단: 시장이 닫혀있습니다 (미국 장 시간 외) ===")
                self.transaction_logger.log_strategy_execution("sell", "skipped", "시장 닫힘 - 미국 장 시간 외")
                return

            # 실전거래 모드 확인
            from config import USE_PAPER_TRADING
            if USE_PAPER_TRADING:
                self.logger.info("=== 매도 전략 실행 시작 (모의투자 모드) ===")
            else:
                self.logger.critical("=== 매도 전략 실행 시작 (실전거래 모드) ===")
                print("🔴 실전 매도 전략 실행 중...")

            self.transaction_logger.log_strategy_execution("sell", "started", "매도 전략 실행 시작")
            
            balance = self.api_client.get_account_balance()
            if balance is None:
                self.logger.error("잔고 조회 실패")
                self.transaction_logger.log_strategy_execution("sell", "error", "잔고 조회 실패")
                return
            
            # 잔고 기록 저장
            self.transaction_logger.log_balance_check(balance)
            
            positions = balance.get("positions", [])
            if not positions:
                self.logger.info("보유 종목 없음")
                self.transaction_logger.log_strategy_execution("sell", "completed", "보유 종목 없음")
                return

            self.logger.info(f"보유 종목 수: {len(positions)}개")
            high_profit = []
            other = []

            for p in positions:
                symbol = p["symbol"]
                quantity = int(p["quantity"])
                avg_buy = float(p["avg_price"])
                if quantity <= 0:
                    continue
                current = self.api_client.get_current_price(symbol)
                if current is None:
                    self.logger.warning(f"{symbol}: 현재가 조회 실패 → 스킵")
                    continue
                profit = self.calculate_profit_rate(symbol, current, avg_buy)
                self.logger.info(f"{symbol}: 수익률 {profit:.2%} (평균단가: ${avg_buy:.2f}, 현재가: ${current:.2f})")

                if profit >= PROFIT_THRESHOLD:
                    high_profit.append((symbol, quantity, current, profit, avg_buy))
                    self.logger.info(f"{symbol}: 고수익 매도 대상 (수익률: {profit:.2%})")
                else:
                    other.append((symbol, quantity, current, profit, avg_buy))
                    self.logger.info(f"{symbol}: 일반 매도 대상 (수익률: {profit:.2%})")

            sell_orders_placed = 0
            
            # 고수익 매도 처리 (가장 수익률이 높은 종목 1개만)
            if high_profit:
                high_profit.sort(key=lambda x: x[3], reverse=True)
                symbol, qty, price, rate, avg_buy = high_profit[0]
                if self.should_sell(symbol, price):
                    # 가격을 소수점 2자리로 반올림 (API 요구사항)
                    rounded_price = round(price, 2)
                    self.logger.info(f"고수익 매도 시도: {symbol} {qty}주 @ ${rounded_price:.2f} (수익률: {rate:.2%})")
                    if not USE_PAPER_TRADING:
                        print(f"🔴 실전 고수익 매도: {symbol} {qty}주 @ ${rounded_price:.2f} (수익률: {rate:.2%})")
                    
                    order_id = self.api_client.place_order(symbol, qty, rounded_price, "sell")
                    if order_id:
                        self.last_sell_prices[symbol] = rounded_price
                        sell_orders_placed += 1
                        if not USE_PAPER_TRADING:
                            print(f"✅ 실전 고수익 매도 완료: {symbol} {qty}주 @ ${price:.2f} (수익률: {rate:.2%})")
                        self.logger.info(f"고수익 매도 완료: {symbol} {qty}주 @ ${price:.2f} (수익률: {rate:.2%})")
                        
                        # 매도 주문 기록 저장
                        profit_loss = (price - avg_buy) * qty
                        self.transaction_logger.log_sell_order(
                            symbol=symbol,
                            quantity=qty,
                            price=price,
                            profit_loss=profit_loss,
                            profit_rate=rate,
                            order_type="market",
                            status="filled",
                            notes=f"고수익 매도 - 수익률 {rate:.2%} (임계값: {PROFIT_THRESHOLD:.1%})"
                        )
                    else:
                        self.logger.error(f"{symbol}: 고수익 매도 주문 실패")
                else:
                    self.logger.info(f"{symbol}: 매도 조건 불충족 → 스킵")
            else:
                self.logger.info("고수익 매도 대상 종목 없음")

            # 일반 매도 처리 (고수익 매도가 없을 때만, 가장 수익률이 높은 종목 1개)
            if sell_orders_placed == 0 and other:
                other.sort(key=lambda x: x[3], reverse=True)
                symbol, qty, price, rate, avg_buy = other[0]
                if rate > 0 and self.should_sell(symbol, price):
                    # 가격을 소수점 2자리로 반올림 (API 요구사항)
                    rounded_price = round(price, 2)
                    self.logger.info(f"일반 매도 시도: {symbol} {qty}주 @ ${rounded_price:.2f} (수익률: {rate:.2%})")
                    if not USE_PAPER_TRADING:
                        print(f"🔴 실전 일반 매도: {symbol} {qty}주 @ ${rounded_price:.2f} (수익률: {rate:.2%})")
                    
                    order_id = self.api_client.place_order(symbol, qty, rounded_price, "sell")
                    if order_id:
                        self.last_sell_prices[symbol] = rounded_price
                        sell_orders_placed += 1
                        if not USE_PAPER_TRADING:
                            print(f"✅ 실전 일반 매도 완료: {symbol} {qty}주 @ ${price:.2f} (수익률: {rate:.2%})")
                        self.logger.info(f"일반 매도 완료: {symbol} {qty}주 @ ${price:.2f} (수익률: {rate:.2%})")
                        
                        # 소폭 수익 매도 기록 저장
                        profit_loss = (price - avg_buy) * qty
                        self.transaction_logger.log_sell_order(
                            symbol=symbol,
                            quantity=qty,
                            price=price,
                            profit_loss=profit_loss,
                            profit_rate=rate,
                            order_type="market",
                            status="filled",
                            notes=f"일반 매도 - 수익률 {rate:.2%} (임계값 미달)"
                        )
                    else:
                        self.logger.error(f"{symbol}: 일반 매도 주문 실패")
                else:
                    self.logger.info(f"{symbol}: 매도 조건 불충족 (수익률: {rate:.2%}) → 스킵")
            elif sell_orders_placed > 0:
                self.logger.info("고수익 매도 실행됨 → 일반 매도 생략")
            else:
                self.logger.info("일반 매도 대상 종목 없음")

            if sell_orders_placed > 0:
                self.logger.info(f"매도 전략 완료: {sell_orders_placed}건 주문 성공")
                self.transaction_logger.log_strategy_execution("sell", "completed", f"{sell_orders_placed}건 매도 주문 성공")
            else:
                self.logger.info("매도 전략 완료: 주문할 종목 없음")
                self.transaction_logger.log_strategy_execution("sell", "completed", "주문할 종목 없음")
                
        except Exception as e:
            self.logger.error(f"매도 전략 실패: {e}")
            self.transaction_logger.log_strategy_execution("sell", "error", f"오류: {e}")

    def check_and_refresh_token(self):
        """토큰 유효성 점검 및 필요시 재발급, 결과를 로그와 콘솔에 출력"""
        try:
            print("[토큰] 유효성 점검 중...")
            self.logger.info("[토큰] 유효성 점검 시작")
            if not self.token_manager.is_token_valid():
                print("[토큰] 만료됨 → 재발급 시도")
                self.logger.warning("[토큰] 만료됨 → 재발급 시도")
                self.token_manager.force_token_refresh()
                if self.token_manager.is_token_valid():
                    print("[토큰] 재발급 성공")
                    self.logger.info("[토큰] 재발급 성공")
                else:
                    print("[토큰] 재발급 실패")
                    self.logger.error("[토큰] 재발급 실패")
            else:
                print("[토큰] 유효함")
                self.logger.info("[토큰] 유효함")
        except Exception as e:
            print(f"[토큰] 점검 중 오류: {e}")
            self.logger.error(f"[토큰] 점검 중 오류: {e}")
