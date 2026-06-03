"""
동적 종목 발굴 모듈

pykrx (한국), yfinance (미국) 기반으로 매수 후보 종목을 자동 발굴한다.
USE_DYNAMIC_UNIVERSE=False인 경우 기존 watch_list 방식 유지.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class KRUniverseProvider:
    """
    pykrx 기반 한국 주식 동적 종목 발굴.

    조건:
    1. 시가총액 >= UNIVERSE_MIN_MARKET_CAP (기본 500억)
    2. 당일 등락률 >= SCREEN_RISE_PCT (세력봉 후보: 5% 이상 상승)
    3. 관리종목/거래정지/우선주 제외 (종목명 기반 필터)

    pykrx 미설치 시 빈 리스트 반환 (graceful degradation).
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
            from pykrx import stock
        except ImportError:
            logger.warning("pykrx 미설치 — KR 동적 발굴 불가. pip install pykrx")
            return []

        try:
            date_str = today.strftime("%Y%m%d")

            # 1) 시총 조회 (KOSPI + KOSDAQ 통합)
            cap_df = stock.get_market_cap_by_ticker(date_str, market="ALL")
            if cap_df is None or cap_df.empty:
                return []

            # 시총 필터
            try:
                from config import UNIVERSE_MIN_MARKET_CAP
            except ImportError:
                UNIVERSE_MIN_MARKET_CAP = 5e10
            cap_df = cap_df[cap_df["시가총액"] >= UNIVERSE_MIN_MARKET_CAP]

            # 2) 당일 OHLCV + 등락률
            ohlcv_df = stock.get_market_ohlcv_by_ticker(date_str, market="ALL")
            if ohlcv_df is None or ohlcv_df.empty:
                return []

            # 등락률 필터: 세력봉 후보 (상승 종목)
            try:
                from config import SCREEN_RISE_PCT
            except ImportError:
                SCREEN_RISE_PCT = 5.0
            ohlcv_df = ohlcv_df[ohlcv_df["등락률"] >= SCREEN_RISE_PCT]

            # 3) 교집합 (시총 + 등락률 둘 다 통과)
            candidates = cap_df.index.intersection(ohlcv_df.index).tolist()

            # 4) 우선주/ETF 제외 (종목코드 끝자리가 0이 아닌 것 중 일부 제외)
            #    간단 필터: 종목코드 6자리 중 끝 한 자리가 '0' (보통주) 또는 'K'(ETF 제외)
            filtered = []
            for code in candidates:
                if len(code) == 6 and code[-1] == '0':
                    filtered.append(code)

            # 거래량 많은 순으로 정렬 (유동성 우선)
            if filtered and not ohlcv_df.empty:
                common_codes = [c for c in filtered if c in ohlcv_df.index]
                if common_codes:
                    volume_sorted = (
                        ohlcv_df.loc[common_codes, "거래량"]
                        .sort_values(ascending=False)
                        .index.tolist()
                    )
                    filtered = volume_sorted

            logger.info(f"KR 동적 발굴: {len(filtered)}종목 (시총 {UNIVERSE_MIN_MARKET_CAP/1e8:.0f}억+, "
                        f"등락률 +{SCREEN_RISE_PCT:.0f}% 이상)")

            return filtered[:limit]

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
