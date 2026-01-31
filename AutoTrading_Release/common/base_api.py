"""
베이스 API 클라이언트 - 미국/한국 주식 공통 API 기능
"""
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, time as dt_time
from typing import Optional, Dict, Any, List
import pytz


class BaseAPIClient(ABC):
    """
    API 클라이언트 베이스 클래스

    서브클래스에서 구현해야 할 메서드:
    - get_timezone(): 시장 타임존 반환
    - get_market_hours(): (시작시간, 종료시간) 튜플 반환
    - get_account_balance(): 계좌 잔고 조회
    - get_current_price(symbol): 현재가 조회
    - place_order(symbol, side, quantity, price): 주문 실행
    """

    def __init__(self, log_level: str = 'INFO'):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level, 'INFO'))

        # 캐시 시스템
        self.price_cache: Dict[str, tuple] = {}  # {symbol: (price, timestamp)}
        self.cache_timeout: int = 60  # 기본 60초

        # 타임존 설정 (서브클래스에서 오버라이드)
        self._timezone = None
        self._start_time = None
        self._end_time = None

    @abstractmethod
    def get_timezone(self) -> str:
        """시장 타임존 반환 (예: 'US/Eastern', 'Asia/Seoul')"""
        pass

    @abstractmethod
    def get_market_hours(self) -> tuple:
        """(시작시간 문자열, 종료시간 문자열) 반환 (예: ('09:30', '16:00'))"""
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, Any]:
        """
        계좌 잔고 조회

        Returns:
            dict: {
                'total_eval': float,  # 총 평가금액
                'total_profit': float,  # 총 손익
                'available_cash': float,  # 주문 가능 현금
                'positions': [  # 보유 종목 리스트
                    {
                        'symbol': str,
                        'quantity': int,
                        'avg_price': float,
                        'current_price': float,
                        'eval_amount': float,
                        'profit_loss': float,
                        'profit_rate': float,
                        'sellable_qty': int
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        종목 현재가 조회

        Args:
            symbol: 종목 코드

        Returns:
            현재가 (실패 시 None)
        """
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, quantity: int,
                    price: Optional[float] = None) -> Dict[str, Any]:
        """
        주문 실행

        Args:
            symbol: 종목 코드
            side: 'buy' 또는 'sell'
            quantity: 수량
            price: 지정가 (None이면 시장가)

        Returns:
            dict: {
                'success': bool,
                'order_id': str (성공 시),
                'message': str,
                'filled_qty': int,
                'filled_price': float
            }
        """
        pass

    def _init_market_time(self):
        """시장 시간 초기화"""
        self._timezone = pytz.timezone(self.get_timezone())
        start_str, end_str = self.get_market_hours()
        self._start_time = dt_time.fromisoformat(start_str)
        self._end_time = dt_time.fromisoformat(end_str)

    def is_market_open(self) -> bool:
        """현재 시장이 열려있는지 확인"""
        try:
            if self._timezone is None:
                self._init_market_time()

            now = datetime.now(self._timezone)
            current_time = now.time()

            # 주말 체크 (토요일=5, 일요일=6)
            if now.weekday() >= 5:
                return False

            # 시장 시간 체크
            return self._start_time <= current_time <= self._end_time

        except Exception as e:
            self.logger.error(f"시장 시간 확인 오류: {e}")
            return False

    def get_market_status(self) -> Dict[str, Any]:
        """시장 상태 정보 반환"""
        try:
            if self._timezone is None:
                self._init_market_time()

            now = datetime.now(self._timezone)
            is_open = self.is_market_open()

            return {
                'is_open': is_open,
                'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone': self.get_timezone(),
                'market_hours': f"{self._start_time.isoformat()} - {self._end_time.isoformat()}",
                'weekday': now.strftime('%A')
            }
        except Exception as e:
            self.logger.error(f"시장 상태 조회 오류: {e}")
            return {'is_open': False, 'error': str(e)}

    def get_cached_price(self, symbol: str) -> Optional[float]:
        """캐시된 가격 조회 (타임아웃 내인 경우)"""
        if symbol in self.price_cache:
            price, timestamp = self.price_cache[symbol]
            if time.time() - timestamp < self.cache_timeout:
                return price
        return None

    def set_cached_price(self, symbol: str, price: float):
        """가격 캐시 저장"""
        self.price_cache[symbol] = (price, time.time())

    def clear_cache(self):
        """캐시 전체 삭제"""
        self.price_cache.clear()

    def get_price_with_cache(self, symbol: str) -> Optional[float]:
        """
        캐시를 활용한 현재가 조회
        캐시 타임아웃 내면 캐시 반환, 아니면 API 호출
        """
        cached = self.get_cached_price(symbol)
        if cached is not None:
            return cached

        price = self.get_current_price(symbol)
        if price is not None:
            self.set_cached_price(symbol, price)
        return price

    def calculate_position_size(self, available_cash: float, price: float,
                                 max_positions: int = 3,
                                 max_shares: int = 100) -> int:
        """
        포지션 크기 계산

        Args:
            available_cash: 사용 가능 현금
            price: 주당 가격
            max_positions: 최대 포지션 수 (현금을 이 수로 나눔)
            max_shares: 종목당 최대 주식 수

        Returns:
            주문 수량
        """
        if price <= 0:
            return 0

        budget_per_position = available_cash / max_positions
        quantity = int(budget_per_position / price)

        return min(quantity, max_shares)

    def format_order_result(self, success: bool, order_id: str = None,
                           message: str = '', filled_qty: int = 0,
                           filled_price: float = 0.0) -> Dict[str, Any]:
        """주문 결과 표준 포맷"""
        return {
            'success': success,
            'order_id': order_id or '',
            'message': message,
            'filled_qty': filled_qty,
            'filled_price': filled_price,
            'timestamp': datetime.now().isoformat()
        }
