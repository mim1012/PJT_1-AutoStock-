"""
베이스 전략 클래스 - 미국/한국 주식 공통 전략 기능
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime


class BaseStrategy(ABC):
    """
    트레이딩 전략 베이스 클래스

    서브클래스에서 구현해야 할 메서드:
    - execute_buy_strategy(): 매수 전략 실행
    - execute_sell_strategy(): 매도 전략 실행
    - should_buy(symbol): 매수 조건 확인
    - should_sell(symbol, profit_rate): 매도 조건 확인
    - get_watch_list(): 감시 종목 리스트 반환
    - get_filter_stocks(): 필터 종목 딕셔너리 반환
    """

    def __init__(self, api_client, profit_threshold: float = 0.05,
                 stop_loss_threshold: float = -0.10,
                 stop_loss_cooldown_days: int = 50,
                 enable_filter_check: bool = True,
                 check_previous_sell_price: bool = True):
        """
        Args:
            api_client: API 클라이언트 인스턴스 (BaseAPIClient 서브클래스)
            profit_threshold: 목표 수익률 (기본 5%)
            stop_loss_threshold: 손절 기준 (기본 -10%)
            stop_loss_cooldown_days: 손절 후 재매수 금지 기간 (기본 50일)
            enable_filter_check: 필터 체크 활성화 여부
            check_previous_sell_price: 이전 매도가 체크 여부
        """
        self.api_client = api_client
        self.profit_threshold = profit_threshold
        self.stop_loss_threshold = stop_loss_threshold
        self.stop_loss_cooldown_days = stop_loss_cooldown_days
        self.enable_filter_check = enable_filter_check
        self.check_previous_sell_price = check_previous_sell_price

        self.logger = logging.getLogger(self.__class__.__name__)

        # 매도 가격 기록 (재매수 방지용)
        self.last_sell_prices: Dict[str, float] = {}

        # 손절 추적 (서브클래스에서 초기화)
        self.stop_loss_tracker = None

        # 전략 실행 통계
        self.stats = {
            'buy_attempts': 0,
            'buy_successes': 0,
            'sell_attempts': 0,
            'sell_successes': 0,
            'filter_blocks': 0
        }

    @abstractmethod
    def execute_buy_strategy(self) -> Dict[str, Any]:
        """
        매수 전략 실행

        Returns:
            dict: {
                'executed': bool,  # 실행 여부
                'orders': list,    # 실행된 주문 리스트
                'message': str     # 상태 메시지
            }
        """
        pass

    @abstractmethod
    def execute_sell_strategy(self) -> Dict[str, Any]:
        """
        매도 전략 실행

        Returns:
            dict: {
                'executed': bool,
                'orders': list,
                'message': str
            }
        """
        pass

    @abstractmethod
    def should_buy(self, symbol: str) -> bool:
        """
        특정 종목 매수 여부 결정

        Args:
            symbol: 종목 코드

        Returns:
            매수 가능 여부
        """
        pass

    @abstractmethod
    def should_sell(self, symbol: str, profit_rate: float) -> bool:
        """
        특정 종목 매도 여부 결정

        Args:
            symbol: 종목 코드
            profit_rate: 현재 수익률

        Returns:
            매도 가능 여부
        """
        pass

    @abstractmethod
    def get_watch_list(self) -> List[str]:
        """감시 종목 리스트 반환"""
        pass

    @abstractmethod
    def get_filter_stocks(self) -> Dict[str, bool]:
        """필터 종목 딕셔너리 반환"""
        pass

    def get_sectors(self) -> Optional[Dict[str, Any]]:
        """
        섹터 구조 반환 (섹터별 필터링 사용 시)

        Returns:
            dict: 섹터 정보 또는 None (섹터 구조 미사용 시)
        """
        return None

    def check_filter_condition(self) -> bool:
        """
        필터 조건 확인
        - 섹터 구조가 있으면: 섹터별 OR 로직 (어느 섹터든 하나 통과하면 OK)
        - 섹터 구조가 없으면: 기존 AND 로직 (모든 필터 종목 상승 필요)

        Returns:
            True: 필터 조건 충족 (매수 가능)
            False: 필터 조건 미충족 (매수 불가)
        """
        if not self.enable_filter_check:
            self.logger.debug("필터 체크 비활성화됨")
            return True

        # 섹터 구조가 있으면 섹터별 OR 필터 로직 사용
        sectors = self.get_sectors()
        if sectors:
            return self._check_sector_filter_condition(sectors)

        # 기존 방식 (AND 로직)
        filter_stocks = self.get_filter_stocks()

        if not filter_stocks:
            self.logger.debug("필터 종목 없음 - 필터 조건 통과")
            return True

        for symbol in filter_stocks.keys():
            try:
                current_price = self.api_client.get_current_price(symbol)
                previous_close = self._get_previous_close(symbol)

                if current_price is None or previous_close is None:
                    self.logger.warning(f"필터 종목 {symbol} 가격 조회 실패")
                    continue

                if current_price <= previous_close:
                    self.logger.info(f"필터 조건 미충족: {symbol} 하락 중 "
                                   f"(현재: {current_price}, 전일: {previous_close})")
                    self.stats['filter_blocks'] += 1
                    return False

            except Exception as e:
                self.logger.error(f"필터 종목 {symbol} 확인 오류: {e}")
                continue

        self.logger.info("필터 조건 충족 - 모든 필터 종목 상승 중")
        return True

    def _check_sector_filter_condition(self, sectors: Dict[str, Any]) -> bool:
        """
        섹터별 OR 필터 조건 확인
        - 각 섹터 내부: OR 로직 (어느 필터 종목이든 하나 상승하면 해당 섹터 통과)
        - 섹터 간: OR 로직 (어느 섹터든 하나 통과하면 매수 허용)

        Args:
            sectors: 섹터 구조 딕셔너리

        Returns:
            True: 하나 이상의 섹터가 필터 조건 통과
            False: 모든 섹터가 필터 조건 미충족
        """
        passing_sectors = []

        for sector_key, sector_info in sectors.items():
            sector_name = sector_info.get('name', sector_key)
            filter_stocks = sector_info.get('filter_stocks', {})

            if not filter_stocks:
                self.logger.debug(f"섹터 {sector_name}: 필터 종목 없음 - 스킵")
                continue

            # 섹터 내부 OR 로직: 하나라도 상승하면 해당 섹터 통과
            sector_passed = False
            rising_stocks = []

            for symbol in filter_stocks.keys():
                try:
                    current_price = self.api_client.get_current_price(symbol)
                    previous_close = self._get_previous_close(symbol)

                    if current_price is None or previous_close is None:
                        self.logger.warning(f"섹터 {sector_name} 필터 종목 {symbol} 가격 조회 실패")
                        continue

                    if current_price > previous_close:
                        rising_stocks.append(symbol)
                        sector_passed = True
                        self.logger.debug(f"섹터 {sector_name}: {symbol} 상승 중 "
                                        f"(현재: {current_price}, 전일: {previous_close})")

                except Exception as e:
                    self.logger.error(f"섹터 {sector_name} 필터 종목 {symbol} 확인 오류: {e}")
                    continue

            if sector_passed:
                passing_sectors.append({
                    'sector_key': sector_key,
                    'sector_name': sector_name,
                    'rising_stocks': rising_stocks
                })
                self.logger.info(f"✓ 섹터 {sector_name} 통과: {len(rising_stocks)}개 종목 상승 중")
            else:
                self.logger.debug(f"✗ 섹터 {sector_name} 미통과: 모든 필터 종목 하락/보합")

        # 섹터 간 OR 로직: 하나 이상의 섹터가 통과하면 OK
        if passing_sectors:
            self.logger.info(f"필터 조건 충족 - {len(passing_sectors)}개 섹터 통과")
            # 통과한 섹터 정보 저장 (매수 전략에서 활용)
            self._passing_sectors = passing_sectors
            return True
        else:
            self.logger.info("필터 조건 미충족 - 모든 섹터 미통과")
            self.stats['filter_blocks'] += 1
            self._passing_sectors = []
            return False

    def get_passing_sectors(self) -> List[Dict[str, Any]]:
        """
        필터 조건을 통과한 섹터 리스트 반환

        Returns:
            list: [{'sector_key': str, 'sector_name': str, 'rising_stocks': list}, ...]
        """
        if not hasattr(self, '_passing_sectors'):
            return []
        return self._passing_sectors

    def _get_previous_close(self, symbol: str) -> Optional[float]:
        """
        전일 종가 조회 (서브클래스에서 오버라이드 가능)

        기본 구현은 API 클라이언트에 위임
        """
        if hasattr(self.api_client, 'get_previous_close'):
            return self.api_client.get_previous_close(symbol)
        return None

    def record_sell_price(self, symbol: str, price: float):
        """매도 가격 기록"""
        self.last_sell_prices[symbol] = price
        self.logger.debug(f"매도 가격 기록: {symbol} @ {price}")

    def get_last_sell_price(self, symbol: str) -> Optional[float]:
        """마지막 매도 가격 조회"""
        return self.last_sell_prices.get(symbol)

    def clear_sell_price(self, symbol: str):
        """매도 가격 기록 삭제"""
        if symbol in self.last_sell_prices:
            del self.last_sell_prices[symbol]

    def is_price_above_last_sell(self, symbol: str, current_price: float) -> bool:
        """
        현재가가 마지막 매도가보다 높은지 확인

        Args:
            symbol: 종목 코드
            current_price: 현재가

        Returns:
            True: 현재가 > 마지막 매도가 (매수 비추천)
            False: 현재가 <= 마지막 매도가 또는 기록 없음 (매수 가능)
        """
        if not self.check_previous_sell_price:
            return False

        last_sell = self.get_last_sell_price(symbol)
        if last_sell is None:
            return False

        return current_price > last_sell

    def get_top_declining_stocks(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        하락률 상위 종목 조회

        Args:
            count: 조회할 종목 수

        Returns:
            list: [{'symbol': str, 'decline_rate': float, 'current_price': float}, ...]
        """
        watch_list = self.get_watch_list()
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

    def get_strategy_stats(self) -> Dict[str, Any]:
        """전략 실행 통계 반환"""
        total_buys = self.stats['buy_attempts']
        total_sells = self.stats['sell_attempts']

        return {
            **self.stats,
            'buy_success_rate': (self.stats['buy_successes'] / total_buys * 100
                                 if total_buys > 0 else 0),
            'sell_success_rate': (self.stats['sell_successes'] / total_sells * 100
                                  if total_sells > 0 else 0),
            'timestamp': datetime.now().isoformat()
        }

    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'buy_attempts': 0,
            'buy_successes': 0,
            'sell_attempts': 0,
            'sell_successes': 0,
            'filter_blocks': 0
        }
