"""
한국 주식 전용 설정 (Phase 2에서 상세 구현)
"""
import os
import sys

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 전역 설정에서 API 키 가져오기
from config import (
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_ACCOUNT_NUMBER,
    USE_PAPER_TRADING,
    MAX_RETRY_COUNT,
    ORDER_TIMEOUT_MINUTES,
    PROFIT_THRESHOLD,
    LOG_LEVEL,
    LOG_FILE
)


class KRConfig:
    """한국 주식 설정 클래스"""

    # API 엔드포인트
    BASE_URL = "https://openapi.koreainvestment.com:9443"
    PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"

    # 시장 시간 (Asia/Seoul)
    TIMEZONE = "Asia/Seoul"
    TRADING_START_TIME = "09:00"
    TRADING_END_TIME = "15:30"

    # 스케줄 설정 (분)
    SELL_INTERVAL_MINUTES = 30
    BUY_INTERVAL_MINUTES = 60

    # 거래소 코드
    EXCHANGE_CODES = {
        'KOSPI': 'KRX',
        'KOSDAQ': 'KRX'
    }

    # 종목 설정 파일
    STOCKS_CONFIG_FILE = "kr_stocks_config.json"

    # 토큰 파일 접두사
    TOKEN_FILE_PREFIX = "kr"

    # mojito2 토큰 파일 (한국 주식용 - Phase 3에서 사용)
    MOJITO_TOKEN_FILE = "kr_krs_token.dat"

    # 한국 주식 특수 설정
    # 호가 단위 (가격대별)
    TICK_SIZES = {
        # 가격대: 호가단위
        2000: 1,
        5000: 5,
        20000: 10,
        50000: 50,
        200000: 100,
        500000: 500,
        float('inf'): 1000
    }

    # 세금/수수료
    SELLING_TAX_RATE = 0.0023  # 0.23% 증권거래세
    COMMISSION_RATE = 0.00015  # 0.015% 거래 수수료 (예시)

    # 가격 제한 (전일 종가 대비)
    PRICE_LIMIT_RATE = 0.30  # ±30%

    # 손절 설정 (한국 시장 전용)
    STOP_LOSS_THRESHOLD = -0.10      # 손절 기준 (-10%)
    STOP_LOSS_COOLDOWN_DAYS = 50     # 손절 후 재매수 금지 기간 (50일)

    @classmethod
    def get_api_url(cls) -> str:
        """현재 모드에 맞는 API URL 반환"""
        return cls.PAPER_BASE_URL if USE_PAPER_TRADING else cls.BASE_URL

    @classmethod
    def get_credentials(cls) -> tuple:
        """API 인증 정보 반환"""
        return (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER)

    @classmethod
    def is_paper_trading(cls) -> bool:
        """모의투자 모드 여부"""
        return USE_PAPER_TRADING

    @classmethod
    def get_tick_size(cls, price: float) -> int:
        """가격에 맞는 호가 단위 반환"""
        for threshold, tick in cls.TICK_SIZES.items():
            if price < threshold:
                return tick
        return 1000

    @classmethod
    def round_to_tick(cls, price: float) -> int:
        """가격을 호가 단위에 맞게 반올림"""
        tick = cls.get_tick_size(price)
        return int(round(price / tick) * tick)
