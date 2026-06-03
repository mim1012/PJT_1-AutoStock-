"""
미국 주식 전용 매매 전략
"""
import os
import sys
import json
import logging
from typing import Optional, Dict, Any, List

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.base_strategy import BaseStrategy
from us.config import USConfig
from us.api_client import USAPIClient
from transaction_logger import TransactionLogger
from stop_loss_tracker import StopLossTracker
from config import PROFIT_THRESHOLD


class USStrategy(BaseStrategy):
    """
    미국 주식 전용 매매 전략

    BaseStrategy를 상속하여 미국 주식 거래에 맞게 구현
    - 필터 종목 기반 매수 조건
    - 하락률 상위 종목 매수
    - 목표 수익률 달성 시 매도
    """

    def __init__(self, api_client: USAPIClient = None,
                 profit_threshold: float = None,
                 enable_filter_check: bool = True,
                 check_previous_sell_price: bool = True):
        """
        Args:
            api_client: 미국 주식 API 클라이언트 (없으면 자동 생성)
            profit_threshold: 목표 수익률 (없으면 config에서 로드)
            enable_filter_check: 필터 체크 활성화 여부
            check_previous_sell_price: 이전 매도가 체크 여부
        """
        if api_client is None:
            api_client = USAPIClient()

        if profit_threshold is None:
            profit_threshold = PROFIT_THRESHOLD

        super().__init__(
            api_client,
            profit_threshold=profit_threshold,
            stop_loss_threshold=USConfig.STOP_LOSS_THRESHOLD,
            stop_loss_cooldown_days=USConfig.STOP_LOSS_COOLDOWN_DAYS,
            enable_filter_check=enable_filter_check,
            check_previous_sell_price=check_previous_sell_price
        )

        self.transaction_logger = TransactionLogger()
        self._filter_stocks = {}
        self._watch_list = []

        # StopLossTracker 초기화
        self.stop_loss_tracker = StopLossTracker(
            blacklist_file="us_stop_loss_blacklist.json",
            cooldown_days=USConfig.STOP_LOSS_COOLDOWN_DAYS,
            timezone=USConfig.TIMEZONE,
            transaction_logger=self.transaction_logger
        )

        # 설정 파일 로드
        self._load_stock_config()

    def _load_stock_config(self):
        """종목 설정 파일 로드"""
        try:
            config_file = USConfig.STOCKS_CONFIG_FILE

            # us_stocks_config.json이 없으면 기존 stocks_config.json 사용
            if not os.path.exists(config_file):
                config_file = "stocks_config.json"

            if not os.path.exists(config_file):
                self.logger.warning(f"설정 파일 없음: {config_file}")
                return

            with open(config_file, 'r') as f:
                config = json.load(f)

            filter_section = config.get("filter_stocks", {})
            if isinstance(filter_section, dict):
                self._filter_stocks = {k: v for k, v in filter_section.items() if v}
            elif isinstance(filter_section, list):
                self._filter_stocks = {s: True for s in filter_section}

            self._watch_list = config.get("watch_list", [])

            self.logger.info(f"US 설정 로드: filter={len(self._filter_stocks)}종목, watch={len(self._watch_list)}종목")

        except Exception as e:
            self.logger.error(f"설정 파일 로드 실패: {e}")

    def get_watch_list(self) -> List[str]:
        try:
            from config import USE_DYNAMIC_UNIVERSE
        except ImportError:
            USE_DYNAMIC_UNIVERSE = False

        if USE_DYNAMIC_UNIVERSE:
            try:
                from common.universe import get_us_provider
                discovered = get_us_provider().discover()
                if discovered:
                    self.logger.info(f"US 동적 유니버스 사용: {len(discovered)}종목")
                    return discovered
            except Exception as e:
                self.logger.warning(f"US 동적 발굴 실패, watch_list 폴백: {e}")

        return self._watch_list

    def get_filter_stocks(self) -> Dict[str, bool]:
        return self._filter_stocks

    def _get_previous_close(self, symbol: str) -> Optional[float]:
        """전일 종가 조회"""
        return self.api_client.get_previous_close(symbol)

    def should_buy(self, symbol: str) -> bool:
        """매수 조건 확인"""
        try:
            # 손절 블랙리스트 체크 (최우선)
            if self.stop_loss_tracker.is_blocked(symbol):
                remaining = self.stop_loss_tracker.get_remaining_days(symbol)
                self.logger.info(f"{symbol}: 손절 후 재매수 금지 중 (남은 기간: {remaining}일)")
                return False

            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                return False

            # 이전 매도가격 체크
            if self.is_price_above_last_sell(symbol, current_price):
                self.logger.info(f"{symbol}: 현재가 ${current_price:.2f}가 이전 매도가보다 높음 → 매수 불가")
                return False

            # === 신규 추가 ===

            # 킬스위치 체크
            if self.is_trading_halted():
                self.logger.info(f"{symbol}: 킬스위치 활성 → 매수 불가")
                return False

            # 매수 시간대 제한 (09:30~15:30 ET, 마감 30분 전까지)
            import pytz
            from datetime import datetime, time as dt_time
            now_et = datetime.now(pytz.timezone('US/Eastern'))
            buy_start = dt_time(9, 30)
            buy_end = dt_time(15, 30)
            if not (buy_start <= now_et.time() <= buy_end):
                self.logger.debug(f"{symbol}: 매수 허용 시간 외 ({now_et.strftime('%H:%M')} ET)")
                return False

            # 하락률 범위 필터 (너무 조금 또는 너무 많이 떨어진 종목 제외)
            previous_close = self.api_client.get_previous_close(symbol)
            if previous_close and previous_close > 0:
                decline_pct = (previous_close - current_price) / previous_close * 100
                min_d = getattr(self.strategy_params, 'min_decline_pct', 0.5) if self.strategy_params else 0.5
                max_d = getattr(self.strategy_params, 'max_decline_pct', 8.0) if self.strategy_params else 8.0
                if decline_pct < min_d:
                    self.logger.debug(f"{symbol}: 하락률 {decline_pct:.2f}% < 최소 {min_d}% → 스킵")
                    return False
                if decline_pct > max_d:
                    self.logger.info(f"{symbol}: 하락률 {decline_pct:.2f}% > 최대 {max_d}% (과도 하락) → 스킵")
                    return False

            # 세력봉 스크리너 통과 여부 (USE_SCREENER=True일 때)
            try:
                from config import USE_SCREENER
            except ImportError:
                USE_SCREENER = True
            if USE_SCREENER and not self.passes_screen(symbol):
                self.logger.info(f"{symbol}: 스크리너 탈락 → 매수 불가")
                return False

            return True

        except Exception as e:
            self.logger.error(f"{symbol} 매수 조건 확인 오류: {e}")
            return False

    def should_sell(self, symbol: str, profit_rate: float) -> bool:
        """
        매도 조건 (우선순위: 손절 > 익절 > 트레일링)
        profit_rate: 소수 단위 (0.05 = 5%)
        """
        # 1. 손절 (최우선)
        if profit_rate <= self.stop_loss_threshold:
            self.logger.warning(f"{symbol}: 손절 ({profit_rate*100:.2f}%)")
            return True

        # 2. 익절
        if profit_rate >= self.profit_threshold:
            return True

        # 3. 트레일링 스탑 (수익 중일 때만)
        try:
            from config import ENABLE_TRAILING_STOP, TRAIL_PCT
        except ImportError:
            ENABLE_TRAILING_STOP, TRAIL_PCT = True, 0.02

        if ENABLE_TRAILING_STOP and profit_rate > 0:
            peak = self.get_peak(symbol)
            if peak and peak > 0:
                current_price = self.api_client.get_current_price(symbol)
                if current_price and current_price > 0:
                    drop_from_peak = (peak - current_price) / peak
                    if drop_from_peak >= TRAIL_PCT:
                        self.logger.info(
                            f"{symbol}: 트레일링 스탑 (고점 대비 -{drop_from_peak*100:.2f}%, "
                            f"수익률 {profit_rate*100:.2f}%)"
                        )
                        return True

        return False

    def execute_buy_strategy(self) -> Dict[str, Any]:
        """매수 전략 실행"""
        try:
            # 시장 확인
            if not self.api_client.is_market_open():
                self.logger.info("=== 매수 전략 중단: 시장이 닫혀있습니다 ===")
                return {'executed': False, 'orders': [], 'message': '시장 닫힘'}

            self.logger.info("=== 미국 주식 매수 전략 실행 ===")
            self.stats['buy_attempts'] += 1

            # 필터 조건 확인
            if not self.check_filter_condition():
                self.logger.info("필터 조건 미충족 → 매수 건너뜀")
                return {'executed': False, 'orders': [], 'message': '필터 조건 미충족'}

            # 잔고 조회
            balance = self.api_client.get_account_balance()
            if not balance:
                return {'executed': False, 'orders': [], 'message': '잔고 조회 실패'}

            available_cash = balance.get('available_cash', 0)
            if available_cash <= 0:
                return {'executed': False, 'orders': [], 'message': '예수금 부족'}

            # 하락률 상위 종목 조회
            top_declining = self.get_top_declining_stocks(count=3)
            if not top_declining:
                return {'executed': False, 'orders': [], 'message': '하락률 상위 종목 없음'}

            executed_orders = []

            for stock in top_declining:
                symbol = stock['symbol']
                current_price = stock['current_price']

                # 매수 조건 확인
                if not self.should_buy(symbol):
                    continue

                # 수량 계산
                quantity = self.api_client.calculate_position_size(
                    available_cash, current_price, max_positions=3, max_shares=100
                )

                if quantity <= 0:
                    continue

                # 주문 실행
                result = self.api_client.place_order(symbol, 'buy', quantity, price=round(current_price, 2))

                if result['success']:
                    self.stats['buy_successes'] += 1
                    executed_orders.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': current_price,
                        'order_id': result['order_id']
                    })

                    # 사용 가능 금액 업데이트
                    available_cash -= (quantity * current_price)

                    # 트레일링 스탑용 고점 초기화
                    self.update_peak(symbol, current_price)

                    # 트랜잭션 로그
                    self.transaction_logger.log_buy_order(
                        symbol, quantity, current_price,
                        result['order_id'], "하락률 상위 매수"
                    )

            return {
                'executed': len(executed_orders) > 0,
                'orders': executed_orders,
                'message': f'{len(executed_orders)}건 매수 실행'
            }

        except Exception as e:
            self.logger.error(f"매수 전략 실행 오류: {e}")
            return {'executed': False, 'orders': [], 'message': str(e)}

    def execute_sell_strategy(self) -> Dict[str, Any]:
        """매도 전략 실행"""
        try:
            # 시장 확인
            if not self.api_client.is_market_open():
                self.logger.info("=== 매도 전략 중단: 시장이 닫혀있습니다 ===")
                return {'executed': False, 'orders': [], 'message': '시장 닫힘'}

            self.logger.info("=== 미국 주식 매도 전략 실행 ===")
            self.stats['sell_attempts'] += 1

            # 잔고 조회
            balance = self.api_client.get_account_balance()
            if not balance:
                return {'executed': False, 'orders': [], 'message': '잔고 조회 실패'}

            positions = balance.get('positions', [])
            if not positions:
                return {'executed': False, 'orders': [], 'message': '보유 종목 없음'}

            # 수익률 순으로 정렬 (높은 것부터)
            positions.sort(key=lambda x: x.get('profit_rate', 0), reverse=True)

            executed_orders = []

            for pos in positions:
                symbol = pos['symbol']
                profit_rate = pos.get('profit_rate', 0) / 100  # 퍼센트 → 소수

                # 고점 갱신 (트레일링 스탑용)
                current_price_for_peak = pos.get('current_price', 0)
                if current_price_for_peak > 0:
                    self.update_peak(symbol, current_price_for_peak)

                # 매도 조건 확인
                if not self.should_sell(symbol, profit_rate):
                    continue

                quantity = pos.get('sellable_qty', 0)
                if quantity <= 0:
                    continue

                current_price = pos.get('current_price', 0)

                # 주문 실행 (해외주식은 시장가 미지원 → 현재가 지정가 매도)
                result = self.api_client.place_order(
                    symbol, 'sell', quantity,
                    price=round(current_price, 2) if current_price > 0 else None
                )

                if result['success']:
                    self.stats['sell_successes'] += 1

                    # 트레일링 스탑용 고점 기록 삭제
                    self.clear_peak(symbol)

                    # 손절 여부 확인
                    is_stop_loss = profit_rate <= self.stop_loss_threshold

                    if is_stop_loss:
                        # 손절 블랙리스트 추가
                        avg_price = pos.get('avg_price', 0)
                        self.stop_loss_tracker.add_stop_loss(
                            symbol=symbol,
                            avg_price=avg_price,
                            loss_price=current_price,
                            loss_rate=profit_rate
                        )
                        reason = f"손절 실행 ({profit_rate*100:.2f}%)"
                    else:
                        # 익절 시 매도 가격 기록
                        self.record_sell_price(symbol, current_price)
                        reason = f"목표 수익률 달성 ({profit_rate*100:.2f}%)"

                    executed_orders.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': current_price,
                        'profit_rate': profit_rate,
                        'order_id': result['order_id']
                    })

                    # 트랜잭션 로그
                    self.transaction_logger.log_sell_order(
                        symbol, quantity, current_price,
                        pos.get('profit_loss', 0),
                        result['order_id'],
                        reason
                    )

            return {
                'executed': len(executed_orders) > 0,
                'orders': executed_orders,
                'message': f'{len(executed_orders)}건 매도 실행'
            }

        except Exception as e:
            self.logger.error(f"매도 전략 실행 오류: {e}")
            return {'executed': False, 'orders': [], 'message': str(e)}


# 하위 호환성을 위한 TradingStrategy 별칭
TradingStrategy = USStrategy
