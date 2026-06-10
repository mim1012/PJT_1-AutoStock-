"""단테 'E. 단타 3종 세트' 검색기 — 5분봉 + 호가 기반 (장중 타점/단타).

근거: RESEARCH/dante_youtube_screener_conditions.md
  · "검색기 E — 단타 3종 세트 (16)" / "E. 단타 3종 세트 (16) — 5분봉 기준"
    ①돌파: 당일 ≥10% + 거래량 ≥7만 + 224일선 위(5분봉) + 전일거래량 80~100%+
    ②눌림: 일목 기준선 1.5~2% 근접 + 매도/매수 잔량비 ≥150%
    ③복합: 고가 ≥10% + 고점대비 -4~5% 하락 + 기준선 2% 이내 + 체결강도 ≥120%
  · "D-1. 5분봉 눌림목 (14)" (이격 확장 후 복귀 / 급등 후 눌림 개념 참고)

설계 원칙 (기존 common/screener.py 와 동일):
  · 순수 함수 — KIS API/스케줄러/매매 로직과 분리. 검색 판정만 수행.
  · 반환은 common.screener.ScreenResult(passed, reasons, metrics) 재사용.
  · common.indicators 의 sma / ichimoku / highest_high 재사용. 부족분만 local 헬퍼.
  · 데이터 부족(분봉/호가 None·빈값) 시 graceful → ScreenResult(False, [사유], {}).

입력 규약:
  · minute_candles: list[Candle] 5분봉, 오래된→최신 (kr.api_client.get_minute_candles 출력).
  · orderbook: dict {'ask_total','bid_total','ratio'} 또는 None
               (ratio = 매도총잔량/매수총잔량*100; kr.api_client.get_orderbook 출력).
  · daily_candles: list[Candle] 일봉(옵션) — 5분봉이 224봉 미만일 때 224일선 대용.
"""
from __future__ import annotations

from dataclasses import dataclass

from common import indicators as ind
from common.candle import Candle
from common.screener import ScreenResult


# ============================================================================
# 공용 파라미터
# ============================================================================

@dataclass
class DanteIntradayParams:
    """단타 3종 공용 파라미터.

    수치 근거는 RESEARCH/dante_youtube_screener_conditions.md "E. 단타 3종 세트".
    """
    # ① 돌파 (breakout)
    day_change_min_pct: float = 10.0    # 당일 등락률 ≥10%
    min_volume: float = 70_000          # 당일 누적 거래량 ≥7만주
    ma_anchor: int = 224                # 224(분봉)선 위 — 부족 시 daily 224 대용
    # ② 눌림 (pullback)
    kijun_near_pct: float = 2.0         # 일목 기준선 1.5~2% 근접 → 2% 이내로 판정
    min_orderbook_ratio: float = 150.0  # 매도/매수 총잔량비 ≥150%
    # ③ 복합 (combo)
    high_change_min_pct: float = 10.0   # 당일 고가 등락률 ≥10%
    pullback_min_pct: float = 4.0       # 고점 대비 -4% 이상
    pullback_max_pct: float = 5.0       # 고점 대비 -5% 이내 (4~5% 눌림 구간)
    combo_kijun_near_pct: float = 2.0   # 일목 기준선 2% 이내
    min_exec_strength: float = 120.0    # 체결강도 ≥120% (없으면 호가비로 대용)


# ============================================================================
# local 헬퍼 (indicators 에 없는 분봉 전용 계산)
# ============================================================================

def _day_change_pct(minute_candles: list[Candle],
                    prev_close: float | None = None) -> float | None:
    """당일 등락률(%).

    prev_close(전일 종가)가 주어지면 (현재가 - 전일종가)/전일종가*100.
    없으면 당일 첫 분봉 시가 대비 현재가 등락으로 대용(분봉만으로 추정).
    """
    if not minute_candles:
        return None
    cur = minute_candles[-1].close
    base = prev_close if (prev_close and prev_close > 0) else minute_candles[0].open
    if not base or base <= 0:
        return None
    return (cur - base) / base * 100


def _day_high_change_pct(minute_candles: list[Candle],
                         prev_close: float | None = None) -> float | None:
    """당일 고가 등락률(%) — 당일 최고가가 기준대비 얼마나 올랐는지."""
    if not minute_candles:
        return None
    day_high = max(c.high for c in minute_candles)
    base = prev_close if (prev_close and prev_close > 0) else minute_candles[0].open
    if not base or base <= 0:
        return None
    return (day_high - base) / base * 100


def _day_volume(minute_candles: list[Candle],
                day_volume: float | None = None) -> float:
    """당일 누적 거래량 — 인자로 주어지면 우선, 없으면 분봉 거래량 합."""
    if day_volume is not None and day_volume > 0:
        return float(day_volume)
    return float(sum(c.volume for c in minute_candles))


def _anchor_ma(minute_candles: list[Candle], period: int,
               daily_candles: list[Candle] | None) -> tuple[float | None, str]:
    """기준 이평(224선). 5분봉이 period봉 이상이면 5분봉 기준,
    부족하면 daily_candles 의 동일 period 일봉선으로 대용.

    반환: (ma값|None, 출처태그). 둘 다 부족하면 (None, 'insufficient').
    """
    ma = ind.sma(ind.closes(minute_candles), period)
    if ma is not None:
        return ma, "5min"
    # 분봉 부족 → 일봉 224선 대용 (장중에는 당일 일봉 미확정이라 근사치임)
    if daily_candles:
        ma_d = ind.sma(ind.closes(daily_candles), period)
        if ma_d is not None:
            return ma_d, "daily"
    return None, "insufficient"


# ============================================================================
# ① 돌파 (breakout)
# ============================================================================

def screen_dante_intraday_breakout(minute_candles: list[Candle],
                                   orderbook: dict | None = None,
                                   daily_candles: list[Candle] | None = None,
                                   prev_close: float | None = None,
                                   day_volume: float | None = None,
                                   params: DanteIntradayParams | None = None
                                   ) -> ScreenResult:
    """E① 돌파: 당일 등락률 ≥10% + 당일 거래량 ≥7만 + 현재가 > 224선(5분봉).

    224선은 5분봉이 224봉 미만이면 daily_candles 의 224일선으로 대용(메트릭에 출처 표기).
    orderbook 은 이 검색기에서 직접 쓰지 않으나 시그니처 일관성을 위해 받는다.
    """
    params = params or DanteIntradayParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not minute_candles:
        return ScreenResult(False, ["분봉 데이터 없음"], {})

    cur = minute_candles[-1].close

    # 1) 당일 등락률 ≥10%
    chg = _day_change_pct(minute_candles, prev_close)
    metrics["day_change_pct"] = round(chg, 2) if chg is not None else None
    metrics["day_change_basis"] = "prev_close" if (prev_close and prev_close > 0) else "first_open"
    change_ok = chg is not None and chg >= params.day_change_min_pct
    if not change_ok:
        reasons.append(f"당일 등락률 미충족({metrics['day_change_pct']}% < {params.day_change_min_pct}%)")

    # 2) 당일 거래량 ≥7만
    vol = _day_volume(minute_candles, day_volume)
    metrics["day_volume"] = int(vol)
    vol_ok = vol >= params.min_volume
    if not vol_ok:
        reasons.append(f"당일 거래량 부족({metrics['day_volume']} < {int(params.min_volume)})")

    # 3) 현재가 > 224선 (5분봉 기준, 부족 시 daily 대용)
    anchor, src = _anchor_ma(minute_candles, params.ma_anchor, daily_candles)
    metrics[f"ma{params.ma_anchor}"] = round(anchor, 2) if anchor is not None else None
    metrics["ma_anchor_src"] = src
    anchor_ok = anchor is not None and cur > anchor
    if anchor is None:
        reasons.append(f"{params.ma_anchor}선 계산 불가(5분봉/일봉 모두 부족)")
    elif not anchor_ok:
        reasons.append(f"{params.ma_anchor}선 위 아님(현재가 {cur} ≤ {metrics[f'ma{params.ma_anchor}']}, src={src})")

    passed = change_ok and vol_ok and anchor_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


# ============================================================================
# ② 눌림 (pullback)
# ============================================================================

def screen_dante_intraday_pullback(minute_candles: list[Candle],
                                   orderbook: dict | None = None,
                                   daily_candles: list[Candle] | None = None,
                                   params: DanteIntradayParams | None = None
                                   ) -> ScreenResult:
    """E② 눌림: 5분봉 일목 기준선 근접(≤kijun_near_pct%) + 호가 잔량비 ≥150%.

    호가(orderbook) None 이면 graceful 탈락 처리.
    """
    params = params or DanteIntradayParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not minute_candles:
        return ScreenResult(False, ["분봉 데이터 없음"], {})

    cur = minute_candles[-1].close

    # 1) 일목 기준선 근접
    ichi = ind.ichimoku(minute_candles)
    kijun = ichi.get("kijun")
    metrics["kijun"] = round(kijun, 2) if kijun else None
    if kijun and kijun > 0:
        dist = abs(cur - kijun) / kijun * 100
        metrics["kijun_dist_pct"] = round(dist, 2)
        kijun_ok = dist <= params.kijun_near_pct
        if not kijun_ok:
            reasons.append(f"기준선 미근접(이격 {metrics['kijun_dist_pct']}% > {params.kijun_near_pct}%)")
    else:
        kijun_ok = False
        metrics["kijun_dist_pct"] = None
        reasons.append("일목 기준선 계산 불가(분봉 부족)")

    # 2) 호가 잔량비 ≥150%
    if orderbook and orderbook.get("ratio", 0) > 0:
        ratio = orderbook["ratio"]
        metrics["orderbook_ratio"] = ratio
        ob_ok = ratio >= params.min_orderbook_ratio
        if not ob_ok:
            reasons.append(f"호가잔량비 부족({ratio}% < {params.min_orderbook_ratio}%)")
    else:
        ob_ok = False
        metrics["orderbook_ratio"] = None
        reasons.append("호가 데이터 없음")

    passed = kijun_ok and ob_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


# ============================================================================
# ③ 복합 (combo = 돌파 + 눌림)
# ============================================================================

def screen_dante_intraday_combo(minute_candles: list[Candle],
                                orderbook: dict | None = None,
                                daily_candles: list[Candle] | None = None,
                                prev_close: float | None = None,
                                exec_strength: float | None = None,
                                params: DanteIntradayParams | None = None
                                ) -> ScreenResult:
    """E③ 복합: 당일 고가 등락률 ≥10% + 현재가 고점대비 -4~5% 눌림
              + 일목 기준선 2% 이내 + 체결강도 ≥120%.

    exec_strength(체결강도) 인자가 없으면 호가 잔량비(orderbook['ratio'])로 대용.
    """
    params = params or DanteIntradayParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not minute_candles:
        return ScreenResult(False, ["분봉 데이터 없음"], {})

    cur = minute_candles[-1].close
    day_high = max(c.high for c in minute_candles)
    metrics["day_high"] = day_high

    # 1) 당일 고가 등락률 ≥10%
    hchg = _day_high_change_pct(minute_candles, prev_close)
    metrics["high_change_pct"] = round(hchg, 2) if hchg is not None else None
    metrics["high_change_basis"] = "prev_close" if (prev_close and prev_close > 0) else "first_open"
    high_ok = hchg is not None and hchg >= params.high_change_min_pct
    if not high_ok:
        reasons.append(f"당일 고가 등락률 미충족({metrics['high_change_pct']}% < {params.high_change_min_pct}%)")

    # 2) 고점 대비 -4~5% 눌림
    if day_high > 0:
        drop = (day_high - cur) / day_high * 100
        metrics["drop_from_high_pct"] = round(drop, 2)
        pull_ok = params.pullback_min_pct <= drop <= params.pullback_max_pct
        if not pull_ok:
            reasons.append(f"고점대비 눌림 구간 밖({metrics['drop_from_high_pct']}% ∉ "
                           f"[{params.pullback_min_pct},{params.pullback_max_pct}]%)")
    else:
        pull_ok = False
        metrics["drop_from_high_pct"] = None
        reasons.append("당일 고가 계산 불가")

    # 3) 일목 기준선 2% 이내
    ichi = ind.ichimoku(minute_candles)
    kijun = ichi.get("kijun")
    metrics["kijun"] = round(kijun, 2) if kijun else None
    if kijun and kijun > 0:
        dist = abs(cur - kijun) / kijun * 100
        metrics["kijun_dist_pct"] = round(dist, 2)
        kijun_ok = dist <= params.combo_kijun_near_pct
        if not kijun_ok:
            reasons.append(f"기준선 미근접(이격 {metrics['kijun_dist_pct']}% > {params.combo_kijun_near_pct}%)")
    else:
        kijun_ok = False
        metrics["kijun_dist_pct"] = None
        reasons.append("일목 기준선 계산 불가(분봉 부족)")

    # 4) 체결강도 ≥120% (없으면 호가 잔량비로 대용)
    if exec_strength is not None and exec_strength > 0:
        strength = exec_strength
        metrics["exec_strength_src"] = "exec_strength"
    elif orderbook and orderbook.get("ratio", 0) > 0:
        strength = orderbook["ratio"]
        metrics["exec_strength_src"] = "orderbook_ratio"
    else:
        strength = None
        metrics["exec_strength_src"] = "none"
    metrics["exec_strength"] = strength
    if strength is None:
        strength_ok = False
        reasons.append("체결강도/호가 데이터 없음")
    else:
        strength_ok = strength >= params.min_exec_strength
        if not strength_ok:
            reasons.append(f"체결강도 부족({strength} < {params.min_exec_strength})")

    passed = high_ok and pull_ok and kijun_ok and strength_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)
