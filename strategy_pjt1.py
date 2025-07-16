"""
PJT #1 매매 전략 구현
"""
import logging
import json
from datetime import datetime, timedelta
from kis_api import KISAPIClient
from token_manager import TokenManager
from config import STOCKS_CONFIG_FILE, PROFIT_THRESHOLD

class TradingStrategy:
    def __init__(self):
        # 토큰 매니저 클라이언트 사용 (403 에러 방지)
        self.api_client = KISAPIClient()
        self.token_manager = TokenManager()
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

            self.logger.info(f"⚙️ 설정 파일 로드 완료: filter={len(filter_stocks)}종목, watch={len(watch_list)}종목")
            print("\n🧾 필터 종목:", ", ".join(filter_stocks))
            print("📋 관심 종목:", ", ".join(watch_list), "\n")

            # 종목 유효성 검증 건너뛰기 (API 제한 방지)
            self.logger.info("⚡ 종목 유효성 검증 생략 - 설정된 모든 종목을 사용합니다.")

            return filter_stocks, watch_list

        except Exception as e:
            self.logger.error(f"📂 stocks_config.json 로드 실패: {e}")
            return [], []


    def check_filter_condition(self):
        """필터 조건 확인 (오류 처리 강화)"""
        try:
            if not self.filter_stocks:
                self.logger.warning("⚠️ 필터 종목이 없습니다.")
                return True  # 필터 종목이 없으면 통과로 처리
            
            rising_count = 0
            total_count = len(self.filter_stocks)
            failed_symbols = []
            
            for symbol in self.filter_stocks:
                try:
                    current_price = self.api_client.get_current_price(symbol)
                    prev_close = self.api_client.get_previous_close(symbol)

                    if current_price is None or prev_close is None:
                        self.logger.warning(f"⚠️ {symbol}: 가격 조회 실패 - 스킵")
                        failed_symbols.append(symbol)
                        continue

                    if current_price > prev_close:
                        rising_count += 1
                        self.logger.info(f"📈 필터 통과: {symbol} ↑ (현재: ${current_price:.2f}, 전일: ${prev_close:.2f})")
                    else:
                        self.logger.info(f"📉 필터 미충족: {symbol} ↓ (현재: ${current_price:.2f}, 전일: ${prev_close:.2f})")
                        
                except Exception as e:
                    self.logger.error(f"❌ {symbol} 필터 확인 중 오류: {e}")
                    failed_symbols.append(symbol)
                    continue

            # 성공한 종목들만으로 판단
            successful_count = total_count - len(failed_symbols)
            if successful_count == 0:
                self.logger.error("❌ 모든 필터 종목 조회 실패")
                return False
            
            # 성공한 종목 중 모두 상승해야 조건 충족
            all_rising = (rising_count == successful_count)
            
            if failed_symbols:
                self.logger.warning(f"⚠️ 실패한 필터 종목들: {', '.join(failed_symbols)}")
            
            self.logger.info(f"📊 필터 결과: {rising_count}/{successful_count} 종목 상승")
            
            if all_rising:
                self.logger.info("✅ 모든 필터 종목 상승 → 매수 조건 충족")
            else:
                self.logger.info("❌ 필터 조건 미충족 → 매수 중단")
                
            return all_rising
            
        except Exception as e:
            self.logger.error(f"❌ 필터 조건 확인 실패: {e}")
            return False

    def calculate_decline_rate(self, symbol):
        try:
            current = self.api_client.get_current_price(symbol)
            prev = self.api_client.get_previous_close(symbol)
            if current is None or prev is None:
                return None
            return max(0, (prev - current) / prev)
        except Exception as e:
            self.logger.error(f"{symbol} 하락률 계산 실패: {e}")
            return None

    def get_top_declining_stocks(self, count=3):
        """하락률 상위 종목 선정 (오류 처리 강화)"""
        declining = []
        failed_symbols = []
        
        for symbol in self.watch_list:
            try:
                rate = self.calculate_decline_rate(symbol)
                if rate is not None:
                    declining.append((symbol, rate))
                    self.logger.debug(f"📊 {symbol} 하락률: {rate:.2%}")
                else:
                    failed_symbols.append(symbol)
            except Exception as e:
                self.logger.error(f"❌ {symbol} 하락률 계산 중 오류: {e}")
                failed_symbols.append(symbol)
        
        if failed_symbols:
            self.logger.warning(f"⚠️ 하락률 계산 실패 종목들: {', '.join(failed_symbols)}")
        
        if not declining:
            self.logger.warning("⚠️ 유효한 하락률 데이터가 없습니다.")
            return []
        
        # 하락률 기준으로 정렬 (높은 하락률 우선)
        top = sorted(declining, key=lambda x: x[1], reverse=True)[:count]
        
        self.logger.info(f"📉 하락률 TOP{count}:")
        for i, (symbol, rate) in enumerate(top, 1):
            self.logger.info(f"  {i}. {symbol}: {rate:.2%}")
        
        return [s[0] for s in top]

    def monitor_watch_list_trend(self):
        try:
            trend_data = []
            self.logger.info("📊 관심 종목 추세 모니터링:")
            for symbol in self.watch_list:
                current = self.api_client.get_current_price(symbol)
                prev = self.api_client.get_previous_close(symbol)
                if current is None or prev is None:
                    continue
                diff = current - prev
                percent = (diff / prev) * 100
                trend = "📈 상승" if diff > 0 else ("📉 하락" if diff < 0 else "➖ 보합")
                self.logger.info(f"{symbol}: {trend} ({percent:.2f}%)")
                trend_data.append({'symbol': symbol, 'percent': percent})

            # 하락률 상위 3종목
            falling = sorted(trend_data, key=lambda x: x['percent'])[:3]
            self.logger.info("🔻 하락률 상위 3종목:")
            for item in falling:
                self.logger.info(f"- {item['symbol']}: {item['percent']:.2f}%")
        except Exception as e:
            self.logger.error(f"모니터링 실패: {e}")

    def calculate_position_size(self, symbol, available_cash):
        try:
            price = self.api_client.get_current_price(symbol)
            if price is None:
                return 0
            alloc = available_cash / 3
            quantity = int(alloc / price)
            self.logger.info(f"{symbol}: 할당금 ${alloc:.2f} → {quantity}주")
            return quantity
        except Exception as e:
            self.logger.error(f"{symbol} 수량 계산 실패: {e}")
            return 0

    def should_buy(self, symbol, current_price):
        if symbol in self.last_sell_prices:
            if current_price >= self.last_sell_prices[symbol]:
                self.logger.info(f"{symbol} 매수 스킵: 현재가 >= 직전 매도가")
                return False
        return True

    def execute_buy_strategy(self):
        try:
            self.monitor_watch_list_trend()
            if not self.check_filter_condition():
                self.logger.info("❌ 필터 미충족 → 매수 중단")
                return

            balance = self.api_client.get_account_balance()
            if balance is None:
                self.logger.error("❌ 잔고 조회 실패")
                return
            available_cash = balance["cash"]
            if available_cash < 100:
                self.logger.info("❌ 예수금 부족 → 매수 생략")
                return

            self.logger.info(f"💰 예수금: ${available_cash:.2f}")
            top_declining = self.get_top_declining_stocks()

            for symbol in top_declining:
                price = self.api_client.get_current_price(symbol)
                if price is None or not self.should_buy(symbol, price):
                    continue
                quantity = self.calculate_position_size(symbol, available_cash)
                if quantity > 0:
                    order_id = self.api_client.place_order(symbol, quantity, price, "buy")
                    if order_id:
                        self.last_buy_prices[symbol] = price
                        self.logger.info(f"🟢 매수 완료: {symbol} {quantity}주 @ ${price}")
        except Exception as e:
            self.logger.error(f"매수 전략 실패: {e}")

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
        if symbol not in self.last_buy_prices:
            return True
        if current_price < self.last_buy_prices[symbol]:
            self.logger.info(f"{symbol}: 매도 스킵 - 현재가 < 매수가")
            return False
        return True

    def execute_sell_strategy(self):
        try:
            balance = self.api_client.get_account_balance()
            if balance is None:
                self.logger.error("❌ 잔고 조회 실패")
                return
            positions = balance.get("positions", [])
            if not positions:
                self.logger.info("📭 보유 종목 없음")
                return

            high_profit = []
            other = []

            for p in positions:
                symbol = p["ovrs_pdno"]
                quantity = int(p["ovrs_cblc_qty"])
                avg_buy = float(p["pchs_avg_pric"])
                if quantity <= 0:
                    continue
                current = self.api_client.get_current_price(symbol)
                if current is None:
                    continue
                profit = self.calculate_profit_rate(symbol, current, avg_buy)
                self.logger.info(f"{symbol}: 수익률 {profit:.2%}")

                if profit >= PROFIT_THRESHOLD:
                    high_profit.append((symbol, quantity, current, profit))
                else:
                    other.append((symbol, quantity, current, profit))

            for symbol, qty, price, rate in high_profit:
                if self.should_sell(symbol, price):
                    order_id = self.api_client.place_order(symbol, qty, price, "sell")
                    if order_id:
                        self.last_sell_prices[symbol] = price
                        self.logger.info(f"🔴 매도 완료: {symbol} {qty}주 @ ${price} ({rate:.2%})")

            if other:
                other.sort(key=lambda x: x[3], reverse=True)
                symbol, qty, price, rate = other[0]
                if rate > 0 and self.should_sell(symbol, price):
                    order_id = self.api_client.place_order(symbol, qty, price, "sell")
                    if order_id:
                        self.last_sell_prices[symbol] = price
                        self.logger.info(f"🟠 소폭 수익 매도: {symbol} {qty}주 @ ${price} ({rate:.2%})")
        except Exception as e:
            self.logger.error(f"매도 전략 실패: {e}")

    def check_and_refresh_token(self):
        """토큰 유효성 점검 및 필요시 재발급, 결과를 로그와 콘솔에 출력"""
        try:
            print("🔑 [토큰] 유효성 점검 중...")
            self.logger.info("[토큰] 유효성 점검 시작")
            if not self.token_manager.is_token_valid():
                print("🔄 [토큰] 만료됨 → 재발급 시도")
                self.logger.warning("[토큰] 만료됨 → 재발급 시도")
                self.token_manager.force_token_refresh()
                if self.token_manager.is_token_valid():
                    print("✅ [토큰] 재발급 성공")
                    self.logger.info("[토큰] 재발급 성공")
                else:
                    print("❌ [토큰] 재발급 실패")
                    self.logger.error("[토큰] 재발급 실패")
            else:
                print("✅ [토큰] 유효함")
                self.logger.info("[토큰] 유효함")
        except Exception as e:
            print(f"❌ [토큰] 점검 중 오류: {e}")
            self.logger.error(f"[토큰] 점검 중 오류: {e}")
