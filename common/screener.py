"""종목 선정 스크리너 (StockDante 이식 + PJT 특화).

봉 데이터를 받아 단테식 검색기 조건(세력봉 + 거래량 급증 + 이평 배열 + 이격도)을
평가하고, 통과 여부와 근거를 반환한다. 백테스트/실시간 공통 사용.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from common import indicators as ind
from common.candle import Candle


@dataclass
class StrategyParams:
    rise_pct: float = 5.0
    body_ratio: float = 0.6
    vol_high_lookback: int = 20
    vol_mult: float = 3.0
    vol_avg_period: int = 20
    ma_periods: list = field(default_factory=lambda: [5, 20, 60, 120, 240])
    disparity_max: float = 120.0
    disparity_base_ma: int = 20
    # PJT 특화 추가
    min_decline_pct: float = 0.5   # 매수 대상 최소 전일대비 하락률(%)
    max_decline_pct: float = 8.0   # 매수 대상 최대 하락률(%)
    rsi_max: float = 45.0          # 매수 시 RSI 상한

    @classmethod
    def from_config(cls) -> StrategyParams:
        try:
            from config import (SCREEN_RISE_PCT, SCREEN_BODY_RATIO, SCREEN_VOL_MULT,
                                SCREEN_VOL_AVG_PERIOD, SCREEN_VOL_HIGH_LOOKBACK,
                                SCREEN_MA_PERIODS, SCREEN_DISPARITY_MAX, SCREEN_DISPARITY_BASE_MA)
            return cls(rise_pct=SCREEN_RISE_PCT, body_ratio=SCREEN_BODY_RATIO,
                       vol_mult=SCREEN_VOL_MULT, vol_avg_period=SCREEN_VOL_AVG_PERIOD,
                       vol_high_lookback=SCREEN_VOL_HIGH_LOOKBACK, ma_periods=SCREEN_MA_PERIODS,
                       disparity_max=SCREEN_DISPARITY_MAX, disparity_base_ma=SCREEN_DISPARITY_BASE_MA)
        except ImportError:
            return cls()


@dataclass
class ScreenResult:
    passed: bool
    reasons: list           # 탈락/통과 근거 메시지 리스트
    metrics: dict           # 계산된 지표값(디버깅/로깅용)


def is_power_candle(candle: Candle, params: StrategyParams) -> bool:
    """세력봉/기준봉: 양봉 + 상승률 충족 + 몸통비율 충족."""
    return (
        candle.is_bull
        and candle.change_pct >= params.rise_pct
        and candle.body_ratio >= params.body_ratio
    )


def screen(candles: list[Candle], params: StrategyParams | None = None) -> ScreenResult:
    """마지막 봉을 기준으로 검색기 조건 평가 (4개 조건 AND).

    candles는 오래된→최신 순으로 정렬되어 있어야 한다.
    """
    params = params or StrategyParams()
    reasons: list[str] = []
    metrics: dict = {}

    if not candles:
        return ScreenResult(False, ["데이터 없음"], {})

    last = candles[-1]

    # 1) 세력봉
    power_ok = is_power_candle(last, params)
    metrics["change_pct"] = round(last.change_pct, 2)
    metrics["body_ratio"] = round(last.body_ratio, 3)
    if not power_ok:
        reasons.append(
            f"세력봉 미충족(change={metrics['change_pct']}%, body={metrics['body_ratio']})"
        )

    # 2) 거래량 급증 (둘 중 하나 이상이면 통과)
    vr = ind.volume_ratio(candles, params.vol_avg_period)
    vol_mult_ok = vr is not None and vr >= params.vol_mult
    vol_high_ok = ind.is_volume_high(candles, params.vol_high_lookback)
    volume_ok = bool(vol_mult_ok or vol_high_ok)
    if vr is not None:
        metrics["volume_ratio"] = round(vr, 2)
    if not volume_ok:
        reasons.append(f"거래량 급증 미충족(ratio={metrics.get('volume_ratio')})")

    # 3) 이평 배열 (정배열 또는 초기 혼조 진입 허용)
    align = ind.ma_alignment(candles, params.ma_periods)
    align_ok = align in ("bullish", "mixed")
    metrics["ma_alignment_code"] = {"bullish": 2, "mixed": 1, "bearish": 0,
                                    "insufficient": -1}[align]
    if not align_ok:
        reasons.append(f"이평 배열 미충족({align})")

    # 4) 이격도 과열 차단 (상한 천장만 검사)
    disp = ind.disparity(candles, params.disparity_base_ma)
    disp_ok = disp is not None and disp <= params.disparity_max
    if disp is not None:
        metrics["disparity"] = round(disp, 2)
    if not disp_ok:
        reasons.append(f"이격도 과열/부족(disparity={metrics.get('disparity')})")

    passed = power_ok and volume_ok and align_ok and disp_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)
