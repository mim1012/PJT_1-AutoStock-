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


@dataclass
class EntryTimingParams:
    """타점(진입 타이밍) 파라미터 — 발굴 워치리스트 종목의 '지금 살 자리' 판정.

    단테식 눌림목 타점: 일봉 기준선/5일선을 지지선으로 두고, 장중 현재가가
    5일선을 회복한 채 기준선에 눌려 근접 + 호가 매도잔량 우위일 때 진입.
    데이터: 일봉(캐시) + 현재가 + 호가만 사용(분봉 깊은 조회 불필요, 폴링 친화).
    근거: RESEARCH/dante_strategy_pipeline.md / 영상 08·14·16.
    """
    kijun_period: int = 26         # 일목 기준선 (지지 기준선)
    recover_ma: int = 5            # 5일선 (회복 라인, 오도리)
    pullback_pct: float = 3.0      # 현재가가 기준선에 이 % 이내 근접 = 눌림 도달
    chase_max_pct: float = 5.0     # 현재가가 5일선 위로 이 % 초과 = 추격 → 제외
    min_orderbook_ratio: float = 150.0  # 매도총잔량/매수총잔량(%) 하한
    require_orderbook: bool = True  # 호가 없으면(조회실패) 호가 조건 스킵(통과 처리)


def screen_entry_timing(current_price: float,
                        daily_candles: list[Candle],
                        orderbook: dict | None = None,
                        params: EntryTimingParams | None = None) -> ScreenResult:
    """타점 판정 — 워치리스트 종목에 대해 '지금이 진입 자리인가'.

    조건(AND):
      1) 회복: 현재가 ≥ 5일선
      2) 추격방지: 현재가 ≤ 5일선 × (1 + chase_max_pct%)
      3) 눌림 도달: 현재가가 일목 기준선에 pullback_pct% 이내 근접
      4) 호가: 매도/매수 총잔량비 ≥ min_orderbook_ratio (호가 없으면 스킵)

    daily_candles는 오래된→최신(발굴 시 캐시한 일봉 재사용). current_price/orderbook은 장중 실시간.
    """
    params = params or EntryTimingParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not daily_candles or current_price <= 0:
        return ScreenResult(False, ["데이터 없음"], {})

    cl = ind.closes(daily_candles)
    ma5 = ind.sma(cl, params.recover_ma)
    ichi = ind.ichimoku(daily_candles)
    kijun = ichi.get("kijun")
    metrics["price"] = current_price
    metrics["ma5"] = round(ma5, 1) if ma5 else None
    metrics["kijun"] = round(kijun, 1) if kijun else None

    # 1) 5일선 회복
    recover_ok = ma5 is not None and current_price >= ma5
    if not recover_ok:
        reasons.append(f"5일선 미회복(현재가 {current_price} < {metrics['ma5']})")

    # 2) 추격 방지 (5일선 위 과도 이격 제외)
    chase_ok = ma5 is not None and current_price <= ma5 * (1 + params.chase_max_pct / 100)
    if ma5 and not chase_ok:
        over = round((current_price / ma5 - 1) * 100, 2)
        reasons.append(f"추격 구간(5일선 +{over}% > {params.chase_max_pct}%)")

    # 3) 눌림 도달 (일목 기준선 근접)
    if kijun:
        dist = abs(current_price - kijun) / kijun * 100
        metrics["kijun_dist_pct"] = round(dist, 2)
        pullback_ok = dist <= params.pullback_pct
        if not pullback_ok:
            reasons.append(f"기준선 미근접(이격 {metrics['kijun_dist_pct']}% > {params.pullback_pct}%)")
    else:
        pullback_ok = False
        reasons.append("기준선 계산 불가(일봉 부족)")

    # 4) 호가 잔량비
    if orderbook and orderbook.get("ratio", 0) > 0:
        metrics["orderbook_ratio"] = orderbook["ratio"]
        orderbook_ok = orderbook["ratio"] >= params.min_orderbook_ratio
        if not orderbook_ok:
            reasons.append(f"호가잔량비 부족({orderbook['ratio']}% < {params.min_orderbook_ratio}%)")
    else:
        # 호가 조회 실패 시: require_orderbook=True면 스킵(통과), False면 탈락
        orderbook_ok = params.require_orderbook
        metrics["orderbook_ratio"] = None
        if not orderbook_ok:
            reasons.append("호가 조회 실패")

    passed = recover_ok and chase_ok and pullback_ok and orderbook_ok
    if passed:
        reasons.append("ENTRY")
    return ScreenResult(passed, reasons, metrics)


# ============================================================================
# 단테 추가 검색기 (발굴 단계, 일봉 기반). 근거: RESEARCH/dante_*.md
# ============================================================================

@dataclass
class DanteConvergenceParams:
    """B-2 초보 단타(이격수렴) — 영상24. 모든 이평이 한곳에 수렴 + 바닥 골든크로스."""
    converge_mas: list = field(default_factory=lambda: [33, 112, 224, 448])
    # 실측 튜닝(screener_backtest): converge_pct 10→8에서 +10d 엣지 -0.26%p→+0.66%p
    # (8%가 신호수 35로 적지만 엣지·품질 최선. 더 많은 신호 원하면 12~15로 완화)
    converge_pct: float = 8.0      # 위 이평들 이격 ±8% 이내
    loose_ma: int = 7              # 7일선은 더 완화
    loose_pct: float = 13.0
    gc_fast: int = 5               # 5이평 ×
    gc_slow: int = 224             # 224이평 골든크로스
    gc_lookback: int = 50          # 최근 50봉 내
    range_lookback: int = 60       # 변동폭 기간
    range_min_pct: float = 30.0    # 변동폭 ≥30%


def screen_dante_convergence(candles: list[Candle],
                             params: DanteConvergenceParams | None = None) -> ScreenResult:
    """B-2: 모든 이평 이격≤5% 수렴 + 5×224 골든크로스(50봉) + 변동폭≥30%."""
    params = params or DanteConvergenceParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not candles:
        return ScreenResult(False, ["데이터 없음"], {})

    # 1) 이평 수렴 (각 이평 이격도 [100-pct, 100+pct])
    lo, hi = 100 - params.converge_pct, 100 + params.converge_pct
    conv_ok = True
    for p in params.converge_mas:
        d = ind.disparity(candles, p)
        if d is None:
            conv_ok = False
            reasons.append(f"{p}일선 이격 계산불가")
            break
        metrics[f"disp{p}"] = round(d, 1)
        if not (lo <= d <= hi):
            conv_ok = False
    if conv_ok:
        # 7일선 완화 이격
        d7 = ind.disparity(candles, params.loose_ma)
        if d7 is not None:
            metrics[f"disp{params.loose_ma}"] = round(d7, 1)
            if not (100 - params.loose_pct <= d7 <= 100 + params.loose_pct):
                conv_ok = False
    if not conv_ok:
        reasons.append(f"이평 수렴 미충족(이격 ±{params.converge_pct}% 밖)")

    # 2) 골든크로스 5×224 (최근 50봉)
    gc_ok = ind.golden_cross_within(candles, params.gc_fast, params.gc_slow, params.gc_lookback)
    metrics["golden_cross"] = gc_ok
    if not gc_ok:
        reasons.append(f"{params.gc_fast}×{params.gc_slow} 골든크로스 없음(최근{params.gc_lookback}봉)")

    # 3) 변동폭
    rng = ind.price_range_pct(candles, params.range_lookback)
    metrics["range_pct"] = round(rng, 1) if rng else None
    range_ok = rng is not None and rng >= params.range_min_pct
    if not range_ok:
        reasons.append(f"변동폭 부족({metrics.get('range_pct')}% < {params.range_min_pct}%)")

    passed = conv_ok and gc_ok and range_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


@dataclass
class DanteNewHighParams:
    """C 역사적 신고가 대시세 — 영상21. 448 안착 + 신고가 근접 + 구름 위."""
    high_lookback: int = 252       # 52주(약 252거래일) 신고가 기준
    # 실측 튜닝(screener_backtest): near_high_pct 3→5에서 +10d 엣지 -1.4%p→+2.79%p
    near_high_pct: float = 5.0     # 신고가 대비 -5% 이내 = 근접/돌파
    anchor_ma: int = 448           # 현재가 > 448일선 (대시세 안착)
    require_ichimoku: bool = True  # 종가 > 선행스팬2
    vol_avg_period: int = 20
    min_avg_volume: float = 50_000


def screen_dante_newhigh(candles: list[Candle],
                         params: DanteNewHighParams | None = None) -> ScreenResult:
    """C: 448일선 위 + 52주 신고가 근접 + 선행스팬2 위 + 거래량."""
    params = params or DanteNewHighParams()
    reasons: list[str] = []
    metrics: dict = {}
    if not candles:
        return ScreenResult(False, ["데이터 없음"], {})
    last = candles[-1]
    cl = ind.closes(candles)

    # 1) 448일선 위
    anchor = ind.sma(cl, params.anchor_ma)
    anchor_ok = anchor is not None and last.close > anchor
    metrics[f"ma{params.anchor_ma}"] = round(anchor, 1) if anchor else None
    if not anchor_ok:
        reasons.append(f"{params.anchor_ma}일선 위 아님(안착 미확인)")

    # 2) 52주 신고가 근접/돌파
    hh = ind.highest_high(candles, params.high_lookback)
    metrics["high_252"] = round(hh, 1) if hh else None
    near_ok = hh is not None and last.close >= hh * (1 - params.near_high_pct / 100)
    if not near_ok:
        reasons.append(f"신고가 미근접(종가 {last.close} < 고점 {metrics.get('high_252')} -{params.near_high_pct}%)")

    # 3) 선행스팬2 위
    ichi_ok = True
    if params.require_ichimoku:
        ichi = ind.ichimoku(candles)
        metrics["senkou_b"] = round(ichi["senkou_b"], 1) if ichi["senkou_b"] else None
        ichi_ok = ichi["senkou_b"] is not None and last.close > ichi["senkou_b"]
        if not ichi_ok:
            reasons.append(f"종가 ≤ 선행스팬2({metrics.get('senkou_b')})")

    # 4) 거래량
    vr_vol = ind.sma([c.volume for c in candles], params.vol_avg_period) if len(candles) >= params.vol_avg_period else None
    vol_ok = vr_vol is not None and vr_vol >= params.min_avg_volume
    metrics["avg_volume"] = int(vr_vol) if vr_vol else None
    if not vol_ok:
        reasons.append(f"평균거래량 부족({metrics.get('avg_volume')})")

    passed = anchor_ok and near_ok and ichi_ok and vol_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


@dataclass
class DanteCloseBetParams:
    """D-3 종가베팅 3번자리 — 영상18. 거래량 급감(눌림) + 최근 강세 + 60일선 위."""
    vol_drop_ratio: float = 0.5    # 오늘 거래량 / 어제 거래량 ≤ 0.5 (급감)
    move_lookback: int = 20        # 최근 20봉
    move_close_pct: float = 10.0   # 종가 상승률 ≥10% (OR)
    move_high_pct: float = 20.0    # 고가 변동폭 ≥20% (OR)
    support_ma: int = 60           # 현재가 > 60일선
    require_ichimoku: bool = True  # 선행스팬2 위
    min_avg_volume: float = 50_000
    vol_avg_period: int = 20


def screen_dante_closebet(candles: list[Candle],
                          params: DanteCloseBetParams | None = None) -> ScreenResult:
    """D-3: 거래량 전일대비 급감(눌림) + 최근 20봉 강세 + 60일선 위 + 구름 위."""
    params = params or DanteCloseBetParams()
    reasons: list[str] = []
    metrics: dict = {}
    if len(candles) < 2:
        return ScreenResult(False, ["데이터 없음"], {})
    last = candles[-1]
    cl = ind.closes(candles)

    # 1) 거래량 급감
    prev_vol = candles[-2].volume
    vol_ratio = last.volume / prev_vol if prev_vol > 0 else 999
    metrics["vol_ratio"] = round(vol_ratio, 2)
    drop_ok = vol_ratio <= params.vol_drop_ratio
    if not drop_ok:
        reasons.append(f"거래량 급감 아님(전일대비 {round(vol_ratio*100)}% > {round(params.vol_drop_ratio*100)}%)")

    # 2) 최근 강세 (종가 변동 OR 고가 변동)
    win = candles[-params.move_lookback:] if len(candles) >= params.move_lookback else candles
    cmax = max(c.close for c in win); cmin = min(c.close for c in win)
    close_chg = (cmax - cmin) / cmin * 100 if cmin > 0 else 0
    high_chg = ind.price_range_pct(candles, params.move_lookback) or 0
    metrics["close_move"] = round(close_chg, 1)
    metrics["high_move"] = round(high_chg, 1)
    move_ok = close_chg >= params.move_close_pct or high_chg >= params.move_high_pct
    if not move_ok:
        reasons.append(f"최근 강세 부족(종가 {metrics['close_move']}%/고가 {metrics['high_move']}%)")

    # 3) 60일선 위
    sup = ind.sma(cl, params.support_ma)
    sup_ok = sup is not None and last.close > sup
    metrics[f"ma{params.support_ma}"] = round(sup, 1) if sup else None
    if not sup_ok:
        reasons.append(f"{params.support_ma}일선 위 아님")

    # 4) 선행스팬2 위
    ichi_ok = True
    if params.require_ichimoku:
        ichi = ind.ichimoku(candles)
        metrics["senkou_b"] = round(ichi["senkou_b"], 1) if ichi["senkou_b"] else None
        ichi_ok = ichi["senkou_b"] is not None and last.close > ichi["senkou_b"]
        if not ichi_ok:
            reasons.append(f"종가 ≤ 선행스팬2({metrics.get('senkou_b')})")

    passed = drop_ok and move_ok and sup_ok and ichi_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)


@dataclass
class DanteBaseCandleParams:
    """F 기준봉 speed dial — 영상15. 최근 기준봉(급등+거래량) + 224일선 근접."""
    move_lookback: int = 10        # 최근 10봉 내
    # 실측 튜닝: move_min_pct 10→15에서 +10d 엣지 -0.4%p→+2.32%p (신호수 적어짐 주의)
    move_min_pct: float = 15.0     # 종가 전일대비 ≥15% 상승봉(강한 기준봉)
    vol_lookback: int = 10
    vol_mult: float = 2.0          # 거래량 전일대비 ≥200%
    anchor_ma: int = 224           # 224일선 근접
    anchor_band_pct: float = 8.0   # ±8%
    vol_avg_period: int = 5
    min_avg_volume: float = 70_000  # 5일 평균 ≥7만


def screen_dante_basecandle(candles: list[Candle],
                            params: DanteBaseCandleParams | None = None) -> ScreenResult:
    """F: 최근 10봉 내 기준봉(≥10% 급등+거래량 폭증) + 224일선 ±8% + 5일평균 거래량."""
    params = params or DanteBaseCandleParams()
    reasons: list[str] = []
    metrics: dict = {}
    if len(candles) < 2:
        return ScreenResult(False, ["데이터 없음"], {})
    last = candles[-1]
    cl = ind.closes(candles)

    # 1) 최근 기준봉 (전일대비 ≥10% 상승봉)
    mc = ind.max_change_pct(candles, params.move_lookback)
    metrics["max_change"] = round(mc, 1) if mc is not None else None
    move_ok = mc is not None and mc >= params.move_min_pct
    if not move_ok:
        reasons.append(f"기준봉 없음(최근{params.move_lookback}봉 최대 {metrics.get('max_change')}% < {params.move_min_pct}%)")

    # 2) 거래량 폭증 (최근 vol_lookback 내 평균대비 vol_mult)
    vol_ok = False
    win = candles[-params.vol_lookback:] if len(candles) >= params.vol_lookback else candles
    base_avg = ind.sma([c.volume for c in candles[:-1]], 20) if len(candles) > 21 else None
    if base_avg and base_avg > 0:
        peak = max(c.volume for c in win)
        metrics["vol_peak_x"] = round(peak / base_avg, 1)
        vol_ok = peak / base_avg >= params.vol_mult
    if not vol_ok:
        reasons.append(f"거래량 폭증 없음(최근 최대 x{metrics.get('vol_peak_x')} < {params.vol_mult})")

    # 3) 224일선 근접 ±8%
    anchor = ind.sma(cl, params.anchor_ma)
    if anchor and anchor > 0:
        dist = abs(last.close - anchor) / anchor * 100
        metrics[f"ma{params.anchor_ma}_dist"] = round(dist, 1)
        anchor_ok = dist <= params.anchor_band_pct
    else:
        anchor_ok = False
    if not anchor_ok:
        reasons.append(f"{params.anchor_ma}일선 ±{params.anchor_band_pct}% 밖")

    # 4) 5일 평균 거래량
    av = ind.sma([c.volume for c in candles], params.vol_avg_period) if len(candles) >= params.vol_avg_period else None
    avg_ok = av is not None and av >= params.min_avg_volume
    metrics["avg_volume"] = int(av) if av else None
    if not avg_ok:
        reasons.append(f"5일 평균거래량 부족({metrics.get('avg_volume')})")

    passed = move_ok and vol_ok and anchor_ok and avg_ok
    if passed:
        reasons.append("PASS")
    return ScreenResult(passed, reasons, metrics)
