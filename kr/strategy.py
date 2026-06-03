"""
한국 주식 전용 매매 전략 (Phase 2에서 상세 구현)
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
from kr.config import KRConfig
from kr.api_client import KRAPIClient
from transaction_logger import TransactionLogger
from config import PROFIT_THRESHOLD


class KRStrategy(BaseStrategy):
    """
    한국 주식 전용 매매 전략

    BaseStrategy를 상속하여 한국 주식 거래에 맞게 구현
    - 필터 종목 기반 매수 조건
    - 하락률 상위 종목 매수
    - 목표 수익률 달성 시 매도
    - 호가 단위 고려
    """

    def __init__(self, api_client: KRAPIClient = None,
                 profit_threshold: float = None,
                 enable_filter_check: bool = True,
                 check_previous_sell_price: bool = True):
        """
        Args:
            api_client: 한국 주식 API 클라이언트 (없으면 자동 생성)
            profit_threshold: 목표 수익률 (없으면 config에서 로드)
            enable_filter_check: 필터 체크 활성화 여부
            check_previous_sell_price: 이전 매도가 체크 여부
        """
        if api_client is None:
            api_client = KRAPIClient()

        if profit_threshold is None:
            profit_threshold = PROFIT_THRESHOLD

        super().__init__(
            api_client,
            profit_threshold,
            KRConfig.STOP_LOSS_THRESHOLD,
            KRConfig.STOP_LOSS_COOLDOWN_DAYS,
            enable_filter_check,
            check_previous_sell_price
        )

        self.transaction_logger = TransactionLogger(prefix="kr")
        self._filter_stocks = {}
        self._watch_list = []
        self._sectors = None  # 섹터 구조 (있을 경우)

        # StopLossTracker 초기화
        from stop_loss_tracker import StopLossTracker
        self.stop_loss_tracker = StopLossTracker(
            blacklist_file="kr_stop_loss_blacklist.json",
            cooldown_days=KRConfig.STOP_LOSS_COOLDOWN_DAYS,
            timezone=KRConfig.TIMEZONE,
            transaction_logger=self.transaction_logger
        )

        # 설정 파일 로드
        self._load_stock_config()

    def _load_stock_config(self):
        """종목 설정 파일 로드 (섹터 구조 및 기존 구조 모두 지원)"""
        try:
            config_file = KRConfig.STOCKS_CONFIG_FILE

            if not os.path.exists(config_file):
                self.logger.warning(f"설정 파일 없음: {config_file}")
                return

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 섹터 구조가 있는지 확인
            if 'sectors' in config:
                # 새로운 섹터 기반 구조
                self._sectors = config['sectors']
                self.logger.info(f"KR 설정 로드 (섹터 모드): {len(self._sectors)}개 섹터")

                # 섹터 정보 로깅
                for sector_key, sector_info in self._sectors.items():
                    sector_name = sector_info.get('name', sector_key)
                    filter_count = len(sector_info.get('filter_stocks', {}))
                    watch_count = len(sector_info.get('watch_list', []))
                    self.logger.info(f"  - {sector_name}: filter={filter_count}종목, watch={watch_count}종목")
            else:
                # 기존 flat 구조 (하위 호환성)
                filter_section = config.get("filter_stocks", {})
                if isinstance(filter_section, dict):
                    self._filter_stocks = {k: v for k, v in filter_section.items() if v}
                elif isinstance(filter_section, list):
                    self._filter_stocks = {s: True for s in filter_section}

                self._watch_list = config.get("watch_list", [])

                self.logger.info(f"KR 설정 로드 (레거시 모드): filter={len(self._filter_stocks)}종목, watch={len(self._watch_list)}종목")

        except Exception as e:
            self.logger.error(f"설정 파일 로드 실패: {e}")

    def get_watch_list(self) -> List[str]:
        """감시 종목 리스트 반환 (레거시 모드용)"""
        return self._watch_list

    def get_filter_stocks(self) -> Dict[str, bool]:
        """필터 종목 반환 (레거시 모드용)"""
        return self._filter_stocks

    def get_sectors(self) -> Optional[Dict[str, Any]]:
        """섹터 구조 반환 (섹터 모드용)"""
        return self._sectors

    def _get_active_watch_list(self) -> List[str]:
        """
        활성 watch_list 반환
        - 동적 발굴 모드: pykrx 기반 당일 조건 통과 종목 반환
        - 섹터 모드: 필터 조건을 통과한 섹터의 watch_list만 반환
        - 레거시 모드: 전체 watch_list 반환

        Returns:
            list: 매수 가능 종목 리스트
        """
        # 동적 발굴 모드
        try:
            from config import USE_DYNAMIC_UNIVERSE
        except ImportError:
            USE_DYNAMIC_UNIVERSE = False

        if USE_DYNAMIC_UNIVERSE:
            try:
                from common.universe import get_kr_provider
                discovered = get_kr_provider().discover()
                if discovered:
                    self.logger.info(f"동적 유니버스 사용: {len(discovered)}종목")
                    return discovered
            except Exception as e:
                self.logger.warning(f"동적 발굴 실패, watch_list 폴백: {e}")

        # 섹터 모드인 경우
        if self._sectors:
            passing_sectors = self.get_passing_sectors()

            if not passing_sectors:
                self.logger.debug("통과한 섹터 없음 - 빈 watch_list 반환")
                return []

            # 통과한 섹터들의 watch_list 합치기
            active_watch_list = []
            for sector in passing_sectors:
                sector_key = sector['sector_key']
                sector_info = self._sectors.get(sector_key, {})
                sector_watch_list = sector_info.get('watch_list', [])
                active_watch_list.extend(sector_watch_list)

            # 중복 제거
            active_watch_list = list(set(active_watch_list))

            self.logger.info(f"활성 watch_list: {len(active_watch_list)}종목 "
                           f"(통과 섹터 {len(passing_sectors)}개)")
            return active_watch_list
        else:
            # 레거시 모드: 전체 watch_list 반환
            return self._watch_list

    def _get_previous_close(self, symbol: str) -> Optional[float]:
        """전일 종가 조회"""
        return self.api_client.get_previous_close(symbol)

    def get_top_declining_stocks(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        하락률 상위 종목 조회 (섹터 필터 고려)

        섹터 모드인 경우, 통과한 섹터의 watch_list만 대상으로 조회

        Args:
            count: 조회할 종목 수

        Returns:
            list: [{'symbol': str, 'decline_rate': float, 'current_price': float}, ...]
        """
        # 활성 watch_list 사용 (섹터 필터 적용됨)
        watch_list = self._get_active_watch_list()

        if not watch_list:
            self.logger.warning("활성 watch_list가 비어있음")
            return []

        declining_stocks = []

        for symbol in watch_list:
            try:
                current_price = self.api_client.get_current_price(symbol)
                previous_close = self._get_previous_close(symbol)

                if current_price is None or previous_close is None:
                    continue

                if previous_close > 0:
                    decline_rate = (previous_close - current_price) / previous_close
                    declining_stocks.append({
                        'symbol': symbol,
                        'decline_rate': decline_rate,
                        'current_price': current_price,
                        'previous_close': previous_close
                    })
            except Exception as e:
                self.logger.debug(f"종목 {symbol} 하락률 계산 오류: {e}")
                continue

        # 하락률 내림차순 정렬 후 상위 N개 반환
        declining_stocks.sort(key=lambda x: x['decline_rate'], reverse=True)
        return declining_stocks[:count]

    def should_buy(self, symbol: str) -> bool:
        """매수 조건 확인"""
        try:
            # 블랙리스트 체크 (최우선)
            if self.stop_loss_tracker.is_blocked(symbol):
                remaining = self.stop_loss_tracker.get_remaining_days(symbol)
                self.logger.info(f"{symbol}: 손절 후 재매수 금지 중 (남은 기간: {remaining}일)")
                return False

            current_price = self.api_client.get_current_price(symbol)
            if current_price is None:
                return False

            # 이전 매도가격 체크
            if self.is_price_above_last_sell(symbol, current_price):
                self.logger.info(f"{symbol}: 현재가 {current_price:,.0f}원이 이전 매도가보다 높음 → 매수 불가")
                return False

            # === 신규 추가 ===

            # 킬스위치 체크
            if self.is_trading_halted():
                self.logger.info(f"{symbol}: 킬스위치 활성 → 매수 불가")
                return False

            # 매수 시간대 제한 (장 시작 30분, 마감 30분 제외)
            import pytz
            from datetime import datetime, time as dt_time
            now_kr = datetime.now(pytz.timezone('Asia/Seoul'))
            buy_start = dt_time(9, 30)
            buy_end = dt_time(15, 0)
            if not (buy_start <= now_kr.time() <= buy_end):
                self.logger.debug(f"{symbol}: 매수 허용 시간 외 ({now_kr.strftime('%H:%M')} KST)")
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
        if profit_rate <= KRConfig.STOP_LOSS_THRESHOLD:
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

            self.logger.info("=== 한국 주식 매수 전략 실행 ===")
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
                    available_cash, current_price, max_positions=3, max_shares=1000
                )

                if quantity <= 0:
                    continue

                # 주문 실행
                result = self.api_client.place_order(symbol, 'buy', quantity)

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
                        symbol=symbol,
                        quantity=quantity,
                        price=current_price,
                        order_type="market",
                        status="filled",
                        balance_cash=available_cash,
                        notes=f"하락률 상위 매수 (주문번호: {result['order_id']})"
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

            self.logger.info("=== 한국 주식 매도 전략 실행 ===")
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

                # 주문 실행
                result = self.api_client.place_order(symbol, 'sell', quantity)

                if result['success']:
                    self.stats['sell_successes'] += 1

                    # 트레일링 스탑용 고점 기록 삭제
                    self.clear_peak(symbol)

                    # 손절 여부 확인
                    is_stop_loss = profit_rate <= KRConfig.STOP_LOSS_THRESHOLD

                    if is_stop_loss:
                        # 손절 블랙리스트 추가
                        self.stop_loss_tracker.add_stop_loss(
                            symbol=symbol,
                            avg_price=pos.get('avg_price', 0),
                            loss_price=current_price,
                            loss_rate=profit_rate
                        )
                        notes = f"stop_loss_triggered ({profit_rate*100:.2f}%) (주문번호: {result['order_id']})"
                    else:
                        # 익절 기록
                        self.record_sell_price(symbol, current_price)
                        notes = f"profit_target_reached ({profit_rate*100:.2f}%) (주문번호: {result['order_id']})"

                    executed_orders.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': current_price,
                        'profit_rate': profit_rate,
                        'order_id': result['order_id']
                    })

                    # 트랜잭션 로그 (손절/익절 구분)
                    self.transaction_logger.log_sell_order(
                        symbol=symbol,
                        quantity=quantity,
                        price=current_price,
                        profit_loss=pos.get('profit_loss', 0),
                        profit_rate=profit_rate,
                        order_type="market",
                        status="filled",
                        notes=notes
                    )

            return {
                'executed': len(executed_orders) > 0,
                'orders': executed_orders,
                'message': f'{len(executed_orders)}건 매도 실행'
            }

        except Exception as e:
            self.logger.error(f"매도 전략 실행 오류: {e}")
            return {'executed': False, 'orders': [], 'message': str(e)}
