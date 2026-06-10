"""단테 추가 검색기 (G 바닥 / A 오전장 급등 단타) — 일봉 기반 순수 함수.

기존 `common/screener.py`의 패턴(ScreenResult 반환, dataclass 파라미터)을 그대로 따른다.
근거: RESEARCH/dante_youtube_screener_conditions.md
  - 검색기 G — 바닥 (영상 12): 이평 3개 데드크로스 + 최근 3일 + 당일 음봉 + 스펙 제외
  - 검색기 A — 오전장 급등 단타 (영상 01·02·19): 전일대비 거래량 2배, 등락률 2~15%,
    금일거래량 7만주+, 5일선 위, 볼린저 상단 4% 근접, 시가 상향돌파

지표 헬퍼는 `common/indicators.py`를 재사용하고, 그곳에 없는 데드크로스 탐지는
이 파일에 로컬 헬퍼로 정의한다(indicators.py는 수정하지 않음).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from common import indicators as ind
from common.candle import Candle
from common.screener import ScreenResult


# ============================================================================
# 로컬 헬퍼 — 데드크로스 탐지 (indicators.golden_cross_within의 역(逆))
# ============================================================================
def dead_cross_within(candles: list[Candle], fast: int, slow: int,
                      lookback: int) -> bool:
    """최근 lookback봉 내 fast이평이 slow이평을 하향돌파(데드크로스)한 적이 있는지.

    indicators.golden_cross_within의 부호 반대 버전. indicators.py를 건드리지 않기 위해
    이 파일에 로컬로 둔다.
    """
    cl = ind.closes(candles)
    n = len(cl)
    if n < slow + 1:
        return False
    start = max(slow, n - lookback)
    for i in range(start, n):
        f_prev, s_prev = ind.sma(cl[:i], fast), ind.sma(cl[:i], slow)
        f_cur, s_cur = ind.sma(cl[:i + 1], fast), ind.sma(cl[:i + 1], slow)
        if None in (f_prev, s_prev, f_cur, s_cur):
            continue
        if f_prev >= s_prev and f_cur < s_cur:
            return True
    return False


def _adjacent_pairs(periods: list[int]) -> list[tuple[int, int]]:
    """정렬된 이평 기간 리스트에서 인접쌍 [(짧은,긴), ...] 반환."""
    sp = sorted(periods)
    return [(sp[i], sp[i + 1]) for i in range(len(sp) - 1)]


# ============================================================================
# 검색기 G — 바닥 (영상 12)
# ============================================================================
@dataclass
class DanteBottomParams:
    """G 바닥 검색기 — 영상 12. 이평 3개 데드크로스 + 최근 3일 + 당일 음봉.

    개념: 단기 이평들이 막 데드크로스(하락 전환)를 낸 직후, 당일 음봉으로 추가 하락한
    '바닥권' 자리를 포착해 스윙(2주~1달)으로 반등을 노린다. 스펙/관리종목 제외는
    유니버스(스캐너) 단계 필터이므로 여기서는 다루지 않는다.
    """
    mas: list = field(default_factory=lambda: [5, 20, 60])  # 이평 3개
    dead_lookback: int = 3              # '최근 3일' 내 데드크로스
    min_dead_crosses: int = 1           # 인접쌍 중 데드크로스가 난 개수 하한
    require_bear_candle: bool = True     # 당일 음봉(종가<시가)
    require_bear_align: bool = False     # (옵션) 현재 역배열(단기<장기) 추가 요구


def screen_dante_bottom(candles: list[Candle],
                        params: DanteBottomParams | None = None) -> ScreenResult:
    """G 바닥 검색기.

    조건(AND):
      1) 데드크로스: 이평 인접쌍(예 5×20, 20×60) 중 최근 dead_lookback봉 내
         데드크로스가 min_dead_crosses개 이상 발생
      2) 당일 음봉: 마지막 봉 종가 < 시가
      3) (옵션) 역배열: 현재 단기<장기 (require_bear_align=True일 때만)

    candles는 오래된→최신. 가장 긴 이평+1봉 이상 필요(부족 시 데드크로스 미탐지).
    """
    params = params or DanteBottomParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not candles:
        return ScreenResult(False, ["데이터 없음"], {})

    last = candles[-1]

    # 1) 데드크로스 개수 (인접 이평쌍별)
    pairs = _adjacent_pairs(params.mas)
    dc_count = 0
    dc_detail = []
    for fast, slow in pairs:
        hit = dead_cross_within(candles, fast, slow, params.dead_lookback)
        if hit:
            dc_count += 1
            dc_detail.append(f"{fast}×{slow}")
    metrics["dead_cross_count"] = dc_count
    metrics["dead_cross_pairs"] = ",".join(dc_detail) if dc_detail else None
    dc_ok = dc_count >= params.min_dead_crosses
    if not dc_ok:
        reasons.append(
            f"데드크로스 부족(최근{params.dead_lookback}봉 {dc_count}개 "
            f"< {params.min_dead_crosses})"
        )

    # 2) 당일 음봉
    bear_ok = True
    if params.require_bear_candle:
        bear_ok = last.close < last.open
        metrics["is_bear"] = bear_ok
        if not bear_ok:
            reasons.append(f"당일 음봉 아님(종가 {last.close} ≥ 시가 {last.open})")

    # 3) (옵션) 역배열
    align_ok = True
    align = ind.ma_alignment(candles, params.mas)
    metrics["ma_alignment"] = align
    if params.require_bear_align:
        align_ok = align == "bearish"
        if not align_ok:
            reasons.append(f"역배열 아님({align})")

    passed = dc_ok and bear_ok and align_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


# ============================================================================
# 검색기 A — 오전장 급등 단타 (영상 01·02·19), 일봉판
# ============================================================================
@dataclass
class DanteMorningParams:
    """A 오전장 급등 단타 — 영상 01·02·19. 일봉 확정 종가 기준 이식.

    원 검색기는 5분봉 타점·체결강도·호가잔량·거래량순위 같은 장중 데이터를 쓰지만,
    여기서는 일봉만으로 판정 가능한 핵심 조건만 구현한다(장중 전용 조건은 제외).
    """
    vol_prev_mult: float = 2.0      # 전일대비 거래량 ≥ 100%(=2배)
    min_volume: float = 70_000      # 금일 거래량 ≥ 7만주
    change_min_pct: float = 2.0     # 등락률(전일종가대비) 하한
    change_max_pct: float = 15.0    # 등락률 상한
    recover_ma: int = 5             # 현재가 > 5일선
    require_open_break: bool = True  # 현재가(종가)가 시가 상향돌파(양봉)
    bb_period: int = 20             # 볼린저 기간
    bb_mult: float = 2.0            # 볼린저 표준편차 배수
    bb_near_pct: float = 4.0        # 볼린저 상단 4% 이내 근접
    trend_ma: int = 60              # (옵션) 60일선 추세
    require_trend_ma: bool = False   # 60일선 위 추가 요구(기본 off)
    avoid_ma: int = 448             # (옵션) 448일선 역배열 고점회피
    require_avoid_high: bool = False  # 448일선 아래(역배열) 추가 요구(기본 off)


def screen_dante_morning(candles: list[Candle],
                         params: DanteMorningParams | None = None) -> ScreenResult:
    """A 오전장 급등 단타 검색기 (일봉판).

    조건(AND):
      1) 전일대비 거래량 ≥ vol_prev_mult배
      2) 금일 거래량 ≥ min_volume
      3) 등락률(전일종가대비) change_min~change_max%
      4) 시가 상향돌파: 종가 > 시가 (require_open_break)
      5) 5일선 위: 종가 > 5일선
      6) 볼린저 상단 bb_near_pct% 이내 근접
      7) (옵션) 60일선 위 / 448일선 아래(역배열)

    candles는 오래된→최신. 볼린저/5일선 계산을 위해 최소 bb_period+1봉 권장.
    """
    params = params or DanteMorningParams()
    reasons: list[str] = []
    metrics: dict = {}
    if len(candles) < 2:
        return ScreenResult(False, ["데이터 없음"], {})

    last = candles[-1]
    prev = candles[-2]
    cl = ind.closes(candles)

    # 1) 전일대비 거래량 ≥ vol_prev_mult배
    if prev.volume > 0:
        vol_mult = last.volume / prev.volume
    else:
        vol_mult = 999.0
    metrics["vol_prev_mult"] = round(vol_mult, 2)
    vol_mult_ok = vol_mult >= params.vol_prev_mult
    if not vol_mult_ok:
        reasons.append(f"전일대비 거래량 부족(x{metrics['vol_prev_mult']} < x{params.vol_prev_mult})")

    # 2) 금일 거래량 ≥ min_volume
    metrics["volume"] = last.volume
    vol_min_ok = last.volume >= params.min_volume
    if not vol_min_ok:
        reasons.append(f"금일 거래량 부족({last.volume} < {int(params.min_volume)})")

    # 3) 등락률 (전일 종가 대비)
    if prev.close > 0:
        chg = (last.close - prev.close) / prev.close * 100
    else:
        chg = 0.0
    metrics["change_pct"] = round(chg, 2)
    change_ok = params.change_min_pct <= chg <= params.change_max_pct
    if not change_ok:
        reasons.append(
            f"등락률 범위밖({metrics['change_pct']}% ∉ "
            f"[{params.change_min_pct},{params.change_max_pct}])"
        )

    # 4) 시가 상향돌파 (양봉)
    open_ok = True
    if params.require_open_break:
        open_ok = last.close > last.open
        if not open_ok:
            reasons.append(f"시가 미돌파(종가 {last.close} ≤ 시가 {last.open})")

    # 5) 5일선 위
    ma5 = ind.sma(cl, params.recover_ma)
    metrics[f"ma{params.recover_ma}"] = round(ma5, 1) if ma5 else None
    ma5_ok = ma5 is not None and last.close > ma5
    if not ma5_ok:
        reasons.append(f"{params.recover_ma}일선 미회복(종가 {last.close} ≤ {metrics[f'ma{params.recover_ma}']})")

    # 6) 볼린저 상단 bb_near_pct% 이내 근접
    bb = ind.bollinger(cl, params.bb_period, params.bb_mult)
    if bb is not None:
        _lower, _mid, upper = bb
        metrics["bb_upper"] = round(upper, 1)
        # 상단 대비 종가 이격(%): 음수면 상단 아래, 0이면 상단, 양수면 상단 돌파
        upper_gap = (last.close - upper) / upper * 100 if upper > 0 else None
        metrics["bb_upper_gap_pct"] = round(upper_gap, 2) if upper_gap is not None else None
        # 상단 'bb_near_pct% 이내 근접': 종가가 상단의 (1-near%) 이상 (돌파 포함)
        bb_ok = upper > 0 and last.close >= upper * (1 - params.bb_near_pct / 100)
    else:
        bb_ok = False
        metrics["bb_upper"] = None
    if not bb_ok:
        reasons.append(f"볼린저 상단 미근접(상단 {metrics.get('bb_upper')}, 종가 {last.close})")

    # 7) (옵션) 60일선 위
    trend_ok = True
    if params.require_trend_ma:
        ma_t = ind.sma(cl, params.trend_ma)
        metrics[f"ma{params.trend_ma}"] = round(ma_t, 1) if ma_t else None
        trend_ok = ma_t is not None and last.close > ma_t
        if not trend_ok:
            reasons.append(f"{params.trend_ma}일선 위 아님")

    # 7') (옵션) 448일선 아래(역배열 고점회피)
    avoid_ok = True
    if params.require_avoid_high:
        ma_a = ind.sma(cl, params.avoid_ma)
        metrics[f"ma{params.avoid_ma}"] = round(ma_a, 1) if ma_a else None
        avoid_ok = ma_a is not None and last.close < ma_a
        if not avoid_ok:
            reasons.append(f"{params.avoid_ma}일선 역배열 아님(고점회피 실패)")

    passed = (vol_mult_ok and vol_min_ok and change_ok and open_ok
              and ma5_ok and bb_ok and trend_ok and avoid_ok)
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)
