"""
미국 주식 전용 설정
"""
import os
import sys

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# API 인증 정보는 환경 변수에서 로드 (보안 강화)
# Fallback: config.py에서 import (하위 호환성)
try:
    # 우선순위 1: 환경 변수
    KIS_APP_KEY = os.getenv('KIS_APP_KEY')
    KIS_APP_SECRET = os.getenv('KIS_APP_SECRET')
    KIS_ACCOUNT_NUMBER = os.getenv('KIS_ACCOUNT_NUMBER')
    USE_PAPER_TRADING = os.getenv('USE_PAPER_TRADING', 'False').lower() == 'true'

    # 환경 변수 없으면 config.py에서 로드 (개발 환경)
    if not all([KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER]):
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
    else:
        # 환경 변수 사용 시 기타 설정도 로드
        from config import (
            MAX_RETRY_COUNT,
            ORDER_TIMEOUT_MINUTES,
            PROFIT_THRESHOLD,
            LOG_LEVEL,
            LOG_FILE,
            possible_fields
        )
except ImportError:
    # config.py 없으면 환경 변수 필수
    if not all([KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER]):
        raise ValueError("Missing required credentials. Set KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER environment variables")


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

    # mojito2 토큰 파일 (기존 token.dat 대체)
    MOJITO_TOKEN_FILE = "us_krs_token.dat"

    # 손절 설정 (미국 시장 전용)
    STOP_LOSS_THRESHOLD = -0.15      # 손절 기준 (-15%)
    STOP_LOSS_COOLDOWN_DAYS = 100    # 손절 후 재매수 금지 기간 (100일)

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
