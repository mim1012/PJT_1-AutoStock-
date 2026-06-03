"""
동적 종목 발굴 모듈

FinanceDataReader(KR) + yfinance(US) 기반으로 매수 후보 종목을 자동 발굴한다.
USE_DYNAMIC_UNIVERSE=False인 경우 기존 watch_list 방식 유지.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class KRUniverseProvider:
    """
    FinanceDataReader 기반 한국 주식 동적 종목 발굴.

    조건:
    1. 시가총액 >= UNIVERSE_MIN_MARKET_CAP (기본 500억)
    2. 당일 등락률 >= SCREEN_RISE_PCT (세력봉 후보: 5% 이상 상승)
    3. 우선주/ETF 제외 (종목코드 끝자리 '0' 보통주만)

    finance-datareader 미설치 시 빈 리스트 반환 (graceful degradation).
    """

    def __init__(self):
        self._cache: list[str] = []
        self._cache_date: Optional[date] = None

    def discover(self, limit: int = 50) -> list[str]:
        """조건 통과 종목 코드 리스트 반환 (당일 1회 캐시)"""
        today = date.today()

        # 당일 캐시
        if self._cache_date == today and self._cache:
            logger.info(f"KR 유니버스 캐시 사용: {len(self._cache)}종목")
            return self._cache[:limit]

        result = self._fetch(today, limit)
        self._cache = result
        self._cache_date = today
        return result

    def _fetch(self, today: date, limit: int) -> list[str]:
        try:
            import FinanceDataReader as fdr
        except ImportError:
            logger.warning("finance-datareader 미설치 — KR 동적 발굴 불가. pip install finance-datareader")
            return []

        try:
            try:
                from config import UNIVERSE_MIN_MARKET_CAP, SCREEN_RISE_PCT
            except ImportError:
                UNIVERSE_MIN_MARKET_CAP = 5e10
                SCREEN_RISE_PCT = 5.0

            # 1) KRX 전체 종목 리스트 + 당일 시세 (Code, Name, Close, ChagesRatio, Volume, Marcap 포함)
            krx_df = fdr.StockListing('KRX')
            if krx_df is None or krx_df.empty:
                logger.warning("KR 종목 목록 조회 실패")
                return []

            # 2) 시총 필터 (Marcap 컬럼, 단위: 원)
            krx_df = krx_df[krx_df['Marcap'] >= UNIVERSE_MIN_MARKET_CAP]

            # 3) 등락률 필터 (ChagesRatio 컬럼, 단위: %)
            krx_df = krx_df[krx_df['ChagesRatio'] >= SCREEN_RISE_PCT]

            # 4) 보통주만 (Code 끝자리 '0', 우선주/ETF/ETN 제외)
            krx_df = krx_df[krx_df['Code'].str[-1] == '0']

            # 5) 거래량 내림차순 정렬 (유동성 우선)
            krx_df = krx_df.sort_values('Volume', ascending=False)

            result = krx_df['Code'].tolist()[:limit]

            logger.info(
                f"KR 동적 발굴: {len(result)}종목 "
                f"(시총 {UNIVERSE_MIN_MARKET_CAP/1e8:.0f}억+, 등락률 +{SCREEN_RISE_PCT:.0f}% 이상)"
            )
            return result

        except Exception as e:
            logger.error(f"KR 동적 발굴 실패: {e}")
            return []


# S&P500 + NASDAQ100 주요 종목 (정적 유니버스 — yfinance 스크리닝 기반)
_US_BASE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "NFLX",
    "AMD", "INTC", "QCOM", "MU", "AMAT", "KLAC", "LRCX", "MRVL", "ON", "SMCI",
    "PLTR", "SNOW", "CRWD", "PANW", "ZS", "NET", "DDOG", "MDB", "GTLB", "PATH",
    "SOUN", "RGTI", "IONQ", "QBTS", "ARQQ", "BBAI", "ASTS", "RKLB", "LUNR", "ACHR",
    "MSTR", "COIN", "HOOD", "SOFI", "UPST", "LC", "AFRM", "NU", "SQ", "PYPL",
    "RIVN", "LCID", "NIO", "LI", "XPEV", "NKLA", "BLNK", "CHPT", "EVGO", "WKHS",
]


class USUniverseProvider:
    """
    yfinance 기반 미국 주식 동적 종목 발굴.

    사전 정의된 유니버스(_US_BASE_UNIVERSE)에서 조건 필터링:
    1. 당일 등락률 >= SCREEN_RISE_PCT (세력봉 후보)
    2. 평균 거래량 >= 1,000,000주 (유동성 확보)
    3. 시총 >= 10억 달러 (초소형 제외)

    yfinance 미설치 시 빈 리스트 반환.
    """

    def __init__(self, base_universe: Optional[list[str]] = None):
        self._base = base_universe or _US_BASE_UNIVERSE
        self._cache: list[str] = []
        self._cache_date: Optional[date] = None

    def discover(self, limit: int = 30) -> list[str]:
        """조건 통과 종목 리스트 반환 (당일 1회 캐시)"""
        today = date.today()
        if self._cache_date == today and self._cache:
            logger.info(f"US 유니버스 캐시 사용: {len(self._cache)}종목")
            return self._cache[:limit]

        result = self._fetch(limit)
        self._cache = result
        self._cache_date = today
        return result

    def _fetch(self, limit: int) -> list[str]:
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance 미설치 — US 동적 발굴 불가. pip install yfinance")
            return []

        try:
            try:
                from config import SCREEN_RISE_PCT
            except ImportError:
                SCREEN_RISE_PCT = 5.0

            candidates = []
            batch_size = 20  # 레이트리밋 방지

            for i in range(0, len(self._base), batch_size):
                batch = self._base[i:i + batch_size]
                try:
                    tickers = yf.Tickers(" ".join(batch))
                    for sym in batch:
                        try:
                            t = tickers.tickers.get(sym)
                            if t is None:
                                continue
                            fast = t.fast_info
                            # 당일 등락률
                            prev_close = getattr(fast, 'previous_close', None) or 0
                            last_price = getattr(fast, 'last_price', None) or 0
                            if prev_close > 0 and last_price > 0:
                                change_pct = (last_price - prev_close) / prev_close * 100
                                if change_pct < SCREEN_RISE_PCT:
                                    continue
                            # 평균 거래량
                            three_month_avg_vol = getattr(fast, 'three_month_average_volume', 0) or 0
                            if three_month_avg_vol < 1_000_000:
                                continue
                            # 시총
                            market_cap = getattr(fast, 'market_cap', 0) or 0
                            if market_cap < 1e9:
                                continue
                            candidates.append((sym, change_pct))
                        except Exception:
                            continue
                except Exception:
                    continue

            # 등락률 높은 순 정렬
            candidates.sort(key=lambda x: x[1], reverse=True)
            result = [sym for sym, _ in candidates[:limit]]

            logger.info(f"US 동적 발굴: {len(result)}종목 (등락률 +{SCREEN_RISE_PCT:.0f}% 이상)")
            return result

        except Exception as e:
            logger.error(f"US 동적 발굴 실패: {e}")
            return []


def get_kr_provider() -> KRUniverseProvider:
    """KR 종목 발굴 프로바이더 싱글턴 반환"""
    if not hasattr(get_kr_provider, '_instance'):
        get_kr_provider._instance = KRUniverseProvider()
    return get_kr_provider._instance


def get_us_provider() -> USUniverseProvider:
    """US 종목 발굴 프로바이더 싱글턴 반환"""
    if not hasattr(get_us_provider, '_instance'):
        get_us_provider._instance = USUniverseProvider()
    return get_us_provider._instance
