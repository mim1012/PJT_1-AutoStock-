# 한국투자증권 API 설정
# ⚠️ 보안을 위해 .env 파일에서 API 키를 로드합니다
# .env.example을 .env로 복사하고 실제 값을 입력하세요

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 API 키 로드
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "your_app_key_here")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "your_app_secret_here")
KIS_ACCOUNT_NUMBER = os.getenv("KIS_ACCOUNT_NUMBER", "your_account_number_here")

# API 키 검증
if KIS_APP_KEY == "your_app_key_here" or not KIS_APP_KEY:
    print("⚠️ WARNING: API 키가 설정되지 않았습니다!")
    print("   .env 파일을 생성하고 KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER를 설정하세요.")
    print("   자세한 내용은 .env.example 파일을 참조하세요.")

# API 엔드포인트 (해외주식 실거래용)
KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"  # 해외주식 실거래
KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 해외주식 모의투자

# 거래 설정
USE_PAPER_TRADING = os.getenv("USE_PAPER_TRADING", "False").lower() in ("true", "1", "yes")
MAX_RETRY_COUNT = 3  # API 재시도 횟수
ORDER_TIMEOUT_MINUTES = 20  # 미체결 주문 취소 시간 (분)

# 전략 설정
STOCKS_CONFIG_FILE = "stocks_config.json"
PROFIT_THRESHOLD = 0.05  # 매도 수익률 임계값 (5%)
CHECK_PREVIOUS_SELL_PRICE = True  # True = 이전 매도가보다 높으면 재매수 금지

# 운영 시간 설정 (미국 동부시간 EST/EDT 기준)
TRADING_START_TIME = "09:30"  # 미국 주식 시장 개장 시간 (ET)
TRADING_END_TIME = "16:00"    # 미국 주식 시장 폐장 시간 (ET)

# 스케줄 설정
SELL_INTERVAL_MINUTES = 30  # 매도 체크 주기 (분)
BUY_INTERVAL_MINUTES = 60   # 매수 체크 주기 (분)

# 로그 설정
LOG_LEVEL = "INFO"
LOG_FILE = "trading.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5  # 최대 5개 백업

# 전일 종가 조회 시 시도할 필드명들 (KIS API 응답 구조 대응)
possible_fields = ["clos", "last", "prvs_clpr", "stck_clpr", "base_pric"]

# ============================================================
# 단테 전략 통합 파라미터 (2026-06 업그레이드)
# ============================================================
USE_SCREENER = True                          # 세력봉 스크리너 사용 여부
ENABLE_TRAILING_STOP = True                  # 트레일링 스탑 사용 여부
TRAIL_PCT = 0.02                             # 트레일링 스탑: 고점 대비 하락 허용폭 (2%)
ACCOUNT_RISK_PCT = 0.02                      # 종목당 최대 손실 허용 (총자금 2%)
DAILY_LOSS_LIMIT_PCT = 0.05                  # 일일 손실 한도 (5%) → 킬스위치
PER_TRADE_PCT = 0.15                         # 종목당 투입 비중 (15%)
MAX_POSITIONS = 4                            # 동시 보유 최대 종목 수

# 스크리너 임계값
SCREEN_RISE_PCT = 5.0                        # 세력봉 최소 상승률(%)
SCREEN_BODY_RATIO = 0.6                      # 몸통/전체 최소 비율
SCREEN_VOL_MULT = 3.0                        # 거래량 급증 배수 (평균 대비)
SCREEN_VOL_AVG_PERIOD = 20                   # 거래량 평균 기간(일)
SCREEN_VOL_HIGH_LOOKBACK = 20                # 최고 거래량 판정 기간(일)
SCREEN_MA_PERIODS = [5, 20, 60, 120, 240]    # 이평선 기간 리스트
SCREEN_DISPARITY_MAX = 120.0                 # 이격도 과열 차단 상한(%)
SCREEN_DISPARITY_BASE_MA = 20               # 이격도 기준 이평선

# 종목 발굴
USE_DYNAMIC_UNIVERSE = True                 # True면 pykrx/yfinance 동적 발굴 사용
UNIVERSE_LIMIT = 50                          # 발굴 종목 최대 수
UNIVERSE_MIN_MARKET_CAP = 5e10               # 최소 시총 500억
CANDLE_COUNT = 120                           # get_candles() 기본 조회 봉 수