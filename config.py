# 한국투자증권 API 설정 (blance02.py와 동일한 키 사용)
# ⚠️ 403 Forbidden 오류 해결을 위해 새 API 키를 발급받아 입력하세요
# https://securities.koreainvestme.com/main/index.jsp 에서 Open API 신청

KIS_APP_KEY = "PS9Yr8VDczEhRt6kbhrAExgLO9mno70zMJvp"
KIS_APP_SECRET = "2mfGKemkM4CTyvkQ1oquImEb+uUKwrflzTn23wjWJ5/PoFu5dwIW1OoyKYCoY2lPxl7L7ukzQqZD8PylBkYA1/SLFQ4r110XH6YCajAcMCzQnQekj1xBNGAaZo8zltZgX7YkomUzoBKV+8kopKGm3c9+juaQU+NJfM4vwMuyk8wkGFiK4v8="
KIS_ACCOUNT_NUMBER = "64721801-01"

# API 엔드포인트 (해외주식 실거래용)
KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"  # 해외주식 실거래
KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 해외주식 모의투자

# 거래 설정
USE_PAPER_TRADING = False  # 실거래 모드
MAX_RETRY_COUNT = 3  # API 재시도 횟수
ORDER_TIMEOUT_MINUTES = 20  # 미체결 주문 취소 시간 (분)

# 전략 설정
STOCKS_CONFIG_FILE = "stocks_config.json"
PROFIT_THRESHOLD = 0.05  # 매도 수익률 임계값 (5%)

# 운영 시간 설정 (미국 동부시간 EST/EDT 기준)
TRADING_START_TIME = "11:30"
TRADING_END_TIME = "17:00"

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