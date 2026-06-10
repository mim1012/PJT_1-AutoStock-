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


@dataclass
class DanteReversalParams:
    """주식단테 'B-1 저평가 역배열 스윙' 검색기 파라미터 (유튜브 조건식 이식).

    핵심: 장기 이평 역배열(저평가 바닥)인데 종가가 가장 짧은 장기선(112일)을
    막 회복한 첫 단추 + 거래량/일목 구름 확인. 단테 표준 이평 5/20/60/112/224/448 사용.
    근거: RESEARCH/dante_youtube_screener_conditions.md (영상 06·10·13·04·20).
    """
    ma_periods: list = field(default_factory=lambda: [112, 224, 448])  # 역배열 체크용 장기선
    recover_ma: int = 112              # 종가가 이 선 위로 회복해야 함
    vol_avg_period: int = 5            # 평균 거래량/대금 기간(일)
    min_avg_volume: float = 50_000     # 평균 거래량 ≥ 5만주
    min_avg_value: float = 5e8         # 평균 거래대금 ≥ 5억 (종가*거래량 근사)
    vol_value_and: bool = False        # True=거래량 AND 대금, False=둘 중 하나(OR)
    require_ichimoku: bool = True      # 종가 > 일목 선행스팬2 (구름 위)
    require_kijun: bool = False        # 종가 > 일목 기준선


def screen_dante_reversal(candles: list[Candle],
                          params: DanteReversalParams | None = None) -> ScreenResult:
    """단테 B-1 저평가 역배열 스윙 검색기.

    조건(AND):
      1) 역배열: 112일선 < 224일선 < 448일선 (장기선이 위 = 바닥권 저평가)
      2) 회복확인: 종가 > 112일선 (가장 짧은 장기선 회복)
      3) 유동성: 평균거래량 ≥ 5만주 OR(기본)/AND 평균거래대금 ≥ 5억
      4) (옵션) 종가 > 일목 선행스팬2 (구름 위), 종가 > 기준선

    candles는 오래된→최신. 448일선 때문에 최소 ~448봉 필요(부족 시 insufficient).
    """
    params = params or DanteReversalParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not candles:
        return ScreenResult(False, ["데이터 없음"], {})

    last = candles[-1]
    cl = ind.closes(candles)

    # 1) 역배열 (단기<장기 = 단테식 '역배열' = ma_alignment 'bearish')
    align = ind.ma_alignment(candles, params.ma_periods)
    align_ok = align == "bearish"
    metrics["ma_alignment"] = align
    if not align_ok:
        reasons.append(f"역배열 아님({align}) — 저평가 바닥 조건 미충족")

    # 2) 종가 > 112일선 (회복 첫 단추)
    recover_ma = ind.sma(cl, params.recover_ma)
    recover_ok = recover_ma is not None and last.close > recover_ma
    if recover_ma is not None:
        metrics[f"ma{params.recover_ma}"] = round(recover_ma, 1)
    if not recover_ok:
        reasons.append(f"종가 {last.close} ≤ {params.recover_ma}일선 — 회복 미확인")

    # 3) 유동성: 평균거래량 / 평균거래대금
    n = params.vol_avg_period
    if len(candles) >= n:
        vols = ind.volumes(candles[-n:])
        avg_vol = sum(vols) / n
        avg_value = sum(c.close * c.volume for c in candles[-n:]) / n
        metrics["avg_volume"] = int(avg_vol)
        metrics["avg_value"] = int(avg_value)
        vol_ok = avg_vol >= params.min_avg_volume
        value_ok = avg_value >= params.min_avg_value
        liquidity_ok = (vol_ok and value_ok) if params.vol_value_and else (vol_ok or value_ok)
    else:
        liquidity_ok = False
        reasons.append("유동성 계산 봉 부족")
    if len(candles) >= n and not liquidity_ok:
        reasons.append(f"유동성 미충족(거래량 {metrics.get('avg_volume')}, 대금 {metrics.get('avg_value')})")

    # 4) 일목균형표 (옵션)
    ichi_ok = True
    if params.require_ichimoku or params.require_kijun:
        ichi = ind.ichimoku(candles)
        metrics["senkou_b"] = round(ichi["senkou_b"], 1) if ichi["senkou_b"] else None
        metrics["kijun"] = round(ichi["kijun"], 1) if ichi["kijun"] else None
        if params.require_ichimoku:
            if ichi["senkou_b"] is None or last.close <= ichi["senkou_b"]:
                ichi_ok = False
                reasons.append(f"종가 ≤ 선행스팬2({metrics.get('senkou_b')}) — 구름 아래")
        if params.require_kijun and ichi_ok:
            if ichi["kijun"] is None or last.close <= ichi["kijun"]:
                ichi_ok = False
                reasons.append(f"종가 ≤ 기준선({metrics.get('kijun')})")

    passed = align_ok and recover_ok and liquidity_ok and ichi_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)
