"""기술적 지표 계산 (순수 함수, StockDante 이식 + RSI 추가)."""
from __future__ import annotations

from common.candle import Candle


def sma(values: list[float], period: int) -> float | None:
    """단순이동평균. 데이터가 period 미만이면 None."""
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def volumes(candles: list[Candle]) -> list[int]:
    return [c.volume for c in candles]


def volume_ratio(candles: list[Candle], period: int) -> float | None:
    """당일(마지막 봉) 거래량 / 직전 period봉 평균 거래량.

    직전 period봉을 기준으로 하므로 당일 봉은 평균에서 제외한다.
    """
    if len(candles) < period + 1:
        return None
    prev = volumes(candles[-(period + 1):-1])
    avg = sum(prev) / period
    if avg == 0:
        return None
    return candles[-1].volume / avg


def is_volume_high(candles: list[Candle], lookback: int) -> bool:
    """마지막 봉 거래량이 직전 lookback봉 내 최고치인지."""
    if len(candles) < lookback + 1:
        return False
    prev_max = max(volumes(candles[-(lookback + 1):-1]))
    return candles[-1].volume >= prev_max


def disparity(candles: list[Candle], period: int) -> float | None:
    """이격도(%) = 현재가 / 이평 * 100."""
    ma = sma(closes(candles), period)
    if ma is None or ma == 0:
        return None
    return candles[-1].close / ma * 100


def ma_alignment(candles: list[Candle], periods: list[int]) -> str:
    """이동평균선 배열 상태.

    반환: 'bullish'(정배열, 단기>장기), 'bearish'(역배열), 'mixed'(혼조), 'insufficient'.
    """
    mas: list[float] = []
    cl = closes(candles)
    for p in sorted(periods):
        m = sma(cl, p)
        if m is None:
            return "insufficient"
        mas.append(m)
    # mas는 짧은기간→긴기간 순. 정배열이면 단조 감소.
    if all(mas[i] > mas[i + 1] for i in range(len(mas) - 1)):
        return "bullish"
    if all(mas[i] < mas[i + 1] for i in range(len(mas) - 1)):
        return "bearish"
    return "mixed"


def golden_cross_within(candles: list[Candle], fast: int, slow: int,
                        lookback: int) -> bool:
    """최근 lookback봉 내 fast이평이 slow이평을 상향돌파(골든크로스)한 적이 있는지."""
    cl = closes(candles)
    n = len(cl)
    if n < slow + 1:
        return False
    start = max(slow, n - lookback)
    for i in range(start, n):
        f_prev, s_prev = sma(cl[:i], fast), sma(cl[:i], slow)
        f_cur, s_cur = sma(cl[:i + 1], fast), sma(cl[:i + 1], slow)
        if None in (f_prev, s_prev, f_cur, s_cur):
            continue
        if f_prev <= s_prev and f_cur > s_cur:
            return True
    return False


def price_range_pct(candles: list[Candle], lookback: int) -> float | None:
    """최근 lookback봉의 (최고가-최저가)/최저가 * 100 (변동폭 %)."""
    if len(candles) < lookback:
        return None
    window = candles[-lookback:]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    return (hi - lo) / lo * 100 if lo > 0 else None


def highest_high(candles: list[Candle], lookback: int) -> float | None:
    """최근 lookback봉의 최고 고가 (신고가 판정용). 데이터 부족 시 전체 사용."""
    if not candles:
        return None
    window = candles[-lookback:] if len(candles) >= lookback else candles
    return max(c.high for c in window)


def max_change_pct(candles: list[Candle], lookback: int) -> float | None:
    """최근 lookback봉 내 봉별 전일대비 종가 상승률(%)의 최댓값."""
    if len(candles) < 2:
        return None
    window = candles[-(lookback + 1):] if len(candles) > lookback + 1 else candles
    best = None
    for i in range(1, len(window)):
        prev = window[i - 1].close
        if prev > 0:
            chg = (window[i].close - prev) / prev * 100
            best = chg if best is None else max(best, chg)
    return best


def bollinger(values: list[float], period: int = 20, mult: float = 2.0):
    """볼린저밴드 (중심=SMA, 상/하단=중심±mult*표준편차).

    반환: (lower, mid, upper) 또는 데이터 부족 시 None. (순수 파이썬, 모표준편차)
    """
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    sd = var ** 0.5
    return (mid - mult * sd, mid, mid + mult * sd)


def _hl_mid(candles: list[Candle], period: int) -> float | None:
    """최근 period봉의 (최고가+최저가)/2. 데이터 부족 시 None."""
    if len(candles) < period:
        return None
    window = candles[-period:]
    return (max(c.high for c in window) + min(c.low for c in window)) / 2


def ichimoku(candles: list[Candle], conv: int = 9, base: int = 26,
             span_b: int = 52) -> dict:
    """일목균형표 — 현재(마지막) 봉에 걸리는 값.

    전환선/기준선은 현재 기준, 선행스팬1·2는 base봉 전 데이터로 계산된 값이
    현재에 표시된다(앞당김 표시 보정). 계산 불가 항목은 None.
    """
    tenkan = _hl_mid(candles, conv)
    kijun = _hl_mid(candles, base)
    # 선행스팬: base봉 전 데이터 기준 (현재 봉에 표시되는 구름)
    past = candles[:-base] if len(candles) > base else []
    if len(past) >= span_b:
        t_p = _hl_mid(past, conv)
        k_p = _hl_mid(past, base)
        senkou_a = (t_p + k_p) / 2 if (t_p is not None and k_p is not None) else None
        senkou_b = _hl_mid(past, span_b)
    else:
        senkou_a = senkou_b = None
    return {"tenkan": tenkan, "kijun": kijun,
            "senkou_a": senkou_a, "senkou_b": senkou_b}


def rsi(values: list[float], period: int = 14) -> float | None:
    """RSI (Wilder 방식, 순수 파이썬 구현).

    gain/loss EMA(Wilder smoothing) → RS → RSI = 100 - (100/(1+RS)).
    데이터 부족(len < period+1) 시 None 반환.
    """
    if period <= 0 or len(values) < period + 1:
        return None

    # 가격 변화량 (delta)
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # 최초 period 구간 단순평균으로 시드
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # 이후 Wilder smoothing (EMA)
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        # 손실이 없으면 RSI 100 (완전 상승)
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
