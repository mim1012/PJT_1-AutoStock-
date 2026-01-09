"""
미국 주식 전용 설정
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
    LOG_FILE,
    possible_fields
)


class USConfig:
    """미국 주식 설정 클래스"""

    # API 엔드포인트
    BASE_URL = "https://openapi.koreainvestment.com:9443"
    PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"

    # 시장 시간 (US Eastern Time)
    TIMEZONE = "US/Eastern"
    TRADING_START_TIME = "09:30"
    TRADING_END_TIME = "16:00"

    # 스케줄 설정 (분)
    SELL_INTERVAL_MINUTES = 30
    BUY_INTERVAL_MINUTES = 60

    # 거래소 코드
    EXCHANGE_CODES = {
        'NASDAQ': 'NASD',
        'NYSE': 'NYS',
        'AMEX': 'AMS'
    }

    # mojito2 거래소 이름
    MOJITO_EXCHANGES = {
        'NASDAQ': '나스닥',
        'NYSE': '뉴욕'
    }

    # 종목 설정 파일
    STOCKS_CONFIG_FILE = "us_stocks_config.json"

    # 토큰 파일 접두사
    TOKEN_FILE_PREFIX = "us"

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
