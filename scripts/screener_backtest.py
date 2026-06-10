# -*- coding: utf-8 -*-
"""검색기 파라미터 실측 튜닝 — 포워드 리턴 백테스트.

과거 여러 as-of 시점에서 각 검색기를 (그 시점까지의 봉으로) 평가하고,
통과 종목의 +N일 포워드 수익률·승률을 시장 기준선과 비교한다.
주요 파라미터를 스윕해 "신호 수 적정 + 포워드 엣지"가 좋은 값을 찾는다.

데이터: FinanceDataReader 일봉 (전 종목 1회 로드 후 슬라이스 재사용).
실행: python scripts/screener_backtest.py [종목수] [as_of_샘플간격]
"""
from __future__ import annotations
import os, sys, logging
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
logging.basicConfig(level=logging.CRITICAL)

from common.candle import Candle
from common import indicators as ind
from common.screener import (
    screen_dante_reversal, DanteReversalParams,
    screen_dante_convergence, DanteConvergenceParams,
    screen_dante_newhigh, DanteNewHighParams,
    screen_dante_closebet, DanteCloseBetParams,
    screen_dante_basecandle, DanteBaseCandleParams,
)
from common.screener_dante_extra import (
    screen_dante_bottom, DanteBottomParams,
    screen_dante_morning, DanteMorningParams,
)

FWD_WINDOWS = [5, 10, 20]
MIN_HISTORY = 460   # 448MA + 여유


def load_universe(n: int):
    import FinanceDataReader as fdr
    df = fdr.StockListing("KRX")
    df = df[(df["Marcap"] >= 1e10) & (df["Code"].astype(str).str[-1] == "0")]
    df = df.sort_values("Marcap", ascending=False)
    step = max(1, len(df) // n)
    sample = df.iloc[::step][:n]
    data = {}
    for _, r in sample.iterrows():
        code, name = r["Code"], r["Name"]
        try:
            h = fdr.DataReader(code, "2021-06-01")
        except Exception:
            continue
        if h is None or len(h) < MIN_HISTORY + max(FWD_WINDOWS) + 30:
            continue
        cs = [Candle(str(i.date()), float(x.Open), float(x.High), float(x.Low),
                     float(x.Close), int(x.Volume))
              for i, x in h.iterrows() if x.Volume == x.Volume and x.Open > 0]
        if len(cs) >= MIN_HISTORY + max(FWD_WINDOWS) + 30:
            data[code] = (name, cs)
    return data


def asof_indices(length: int, sample_step: int):
    """평가 가능한 as-of 인덱스들 (충분한 과거 + 포워드 여유)."""
    lo = MIN_HISTORY
    hi = length - max(FWD_WINDOWS) - 1
    return list(range(lo, hi, sample_step))


def fwd_returns(cs, idx):
    base = cs[idx].close
    out = {}
    for w in FWD_WINDOWS:
        if idx + w < len(cs) and base > 0:
            out[w] = (cs[idx + w].close - base) / base * 100
        else:
            out[w] = None
    return out


def backtest(data, screen_fn, params, sample_step=20):
    """반환: {'signals':n, 'baseline_n':m, per-window {'avg','win','base_avg'}}."""
    sig_rets = {w: [] for w in FWD_WINDOWS}
    base_rets = {w: [] for w in FWD_WINDOWS}
    n_sig = 0
    n_base = 0
    for code, (name, cs) in data.items():
        for idx in asof_indices(len(cs), sample_step):
            window = cs[: idx + 1]
            fr = fwd_returns(cs, idx)
            for w in FWD_WINDOWS:
                if fr[w] is not None:
                    base_rets[w].append(fr[w])
            n_base += 1
            try:
                res = screen_fn(window, params) if params else screen_fn(window)
            except Exception:
                continue
            if res.passed:
                n_sig += 1
                for w in FWD_WINDOWS:
                    if fr[w] is not None:
                        sig_rets[w].append(fr[w])
    out = {"signals": n_sig, "baseline_n": n_base}
    for w in FWD_WINDOWS:
        s = sig_rets[w]; b = base_rets[w]
        out[w] = {
            "avg": round(sum(s) / len(s), 2) if s else None,
            "win": round(sum(1 for x in s if x > 0) / len(s) * 100, 1) if s else None,
            "base_avg": round(sum(b) / len(b), 2) if b else None,
            "n": len(s),
        }
    return out


def _fmt(label, r):
    e10 = ""
    if r[10]["avg"] is not None and r[10]["base_avg"] is not None:
        e10 = f"엣지{round(r[10]['avg'] - r[10]['base_avg'], 2):+}%p"
    print(f"  {label:<22} 신호 {r['signals']:>4} | "
          f"+5d {r[5]['avg']}% / +10d {r[10]['avg']}%(승{r[10]['win']}%) / +20d {r[20]['avg']}% | {e10}")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    print(f"유니버스 로딩 (시총100억+ ~{n}종목)...")
    data = load_universe(n)
    sample = next(iter(data.values()))[1] if data else []
    n_asof = len(asof_indices(len(sample), step)) if sample else 0
    print(f"로드 {len(data)}종목 × as-of {n_asof}개 시점 (간격 {step}봉)\n")

    base = data[next(iter(data))][1] if data else None
    if base:
        br = fwd_returns  # noqa
    # 기본 파라미터 백테스트
    print("=== 기본 파라미터 포워드 리턴 (시장 기준선 대비 엣지) ===")
    specs = [
        ("B-1 역배열", screen_dante_reversal, DanteReversalParams()),
        ("B-2 이격수렴", screen_dante_convergence, DanteConvergenceParams()),
        ("C 신고가", screen_dante_newhigh, DanteNewHighParams()),
        ("D-3 종가베팅", screen_dante_closebet, DanteCloseBetParams()),
        ("F 기준봉", screen_dante_basecandle, DanteBaseCandleParams()),
        ("G 바닥", screen_dante_bottom, DanteBottomParams()),
        ("A 오전장", screen_dante_morning, DanteMorningParams()),
    ]
    base_r = None
    for label, fn, p in specs:
        r = backtest(data, fn, p, step)
        if base_r is None:
            base_r = r
        _fmt(label, r)
    print(f"\n  [시장 기준선] +5d {base_r[5]['base_avg']}% / +10d {base_r[10]['base_avg']}% / +20d {base_r[20]['base_avg']}%")

    # 파라미터 스윕
    print("\n=== 파라미터 스윕 ===")
    print("[B-2 이격수렴] converge_pct:")
    for pct in (8, 10, 12, 15):
        r = backtest(data, screen_dante_convergence,
                     DanteConvergenceParams(converge_pct=pct, loose_pct=pct + 5), step)
        _fmt(f"  converge_pct={pct}", r)
    print("[F 기준봉] move_min_pct (기준봉 급등 임계):")
    for mv in (8, 10, 15, 20):
        r = backtest(data, screen_dante_basecandle,
                     DanteBaseCandleParams(move_min_pct=mv), step)
        _fmt(f"  move_min_pct={mv}", r)
    print("[C 신고가] near_high_pct (신고가 근접):")
    for nh in (1, 3, 5, 8):
        r = backtest(data, screen_dante_newhigh,
                     DanteNewHighParams(near_high_pct=nh), step)
        _fmt(f"  near_high_pct={nh}", r)


if __name__ == "__main__":
    main()
