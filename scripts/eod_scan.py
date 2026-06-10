# -*- coding: utf-8 -*-
"""장 마감 후(End-of-Day) 검색기 스캔.

확정 종가 기준으로 두 검색기를 돌려 결과를 마크다운 리포트로 저장한다.
장중에 돌리면 봉이 미확정이라 통과/탈락이 뒤집히므로, 마감 후 1회 실행이 정석.

  ① breakout 세력봉 검색기 (common.screener.screen)
  ② 단테 역배열 스윙 B-1 (common.screener.screen_dante_reversal)

데이터: KR=FinanceDataReader, US=yfinance (유니버스 전체 배치라 KIS 레이트리밋 회피).
저장: RESEARCH/eod/eod_{market}_{YYYYMMDD}.md  (+ 콘솔 출력)

수동 실행:
    python scripts/eod_scan.py kr
    python scripts/eod_scan.py us
    python scripts/eod_scan.py all

자동 실행:
    AutoMarketScheduler가 KR 15:40 KST / US 16:10 ET 에 run_eod_scan() 호출.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date

# 프로젝트 루트 import 경로
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.candle import Candle
from common.screener import (
    screen, screen_dante_reversal, StrategyParams, DanteReversalParams,
    screen_dante_convergence, screen_dante_newhigh,
    screen_dante_closebet, screen_dante_basecandle,
)

# 추가 단테 검색기 (코드, 라벨, 실행함수) — 모두 일봉 ≥448 필요
_DANTE_SCREENS = [
    ("convergence", "B-2 이격수렴", screen_dante_convergence),
    ("newhigh", "C 역사적신고가", screen_dante_newhigh),
    ("closebet", "D-3 종가베팅", screen_dante_closebet),
    ("basecandle", "F 기준봉", screen_dante_basecandle),
]
from common import indicators as ind

logger = logging.getLogger(__name__)

# 유니버스 규모 기본값 (마감 후 배치라 넉넉히)
DEFAULT_BREAKOUT_LIMIT = 60      # breakout 후보(당일 급등) 평가 상한
DEFAULT_REVERSAL_LIMIT = 500     # 역배열/단테 검색기 평가 대상(시총 100억+ 상위)
WATCHLIST_TOP = 12               # 역배열 워치리스트 출력 수


# ----------------------------------------------------------------------------
# 캔들 공급 (마감 후 배치 — KR=FDR, US=yfinance)
# ----------------------------------------------------------------------------
def _rows_to_candles(rows) -> list[Candle]:
    out = []
    for idx, r in rows.iterrows():
        try:
            o, h, l, c, v = (float(r["Open"]), float(r["High"]), float(r["Low"]),
                             float(r["Close"]), int(r["Volume"]))
        except (ValueError, TypeError):
            continue
        if o <= 0 or c != c:  # NaN/0 제외
            continue
        out.append(Candle(str(getattr(idx, "date", lambda: idx)()), o, h, l, c, v))
    return out


def _kr_candles(code: str, start: str = "2023-06-01") -> list[Candle] | None:
    try:
        import FinanceDataReader as fdr
        h = fdr.DataReader(code, start)
        if h is None or len(h) < 60:
            return None
        return _rows_to_candles(h)
    except Exception:
        return None


def _us_candles(ticker: str) -> list[Candle] | None:
    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(period="3y", auto_adjust=False)
        if h is None or len(h) < 60:
            return None
        return _rows_to_candles(h)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 유니버스
# ----------------------------------------------------------------------------
def _kr_universe(breakout_limit: int, reversal_limit: int):
    """KRX 전종목에서 (breakout 후보, reversal 후보) 코드·이름 리스트 반환."""
    import FinanceDataReader as fdr
    try:
        from config import SCREEN_RISE_PCT, UNIVERSE_MIN_MARKET_CAP
    except ImportError:
        SCREEN_RISE_PCT, UNIVERSE_MIN_MARKET_CAP = 5.0, 5e10

    df = fdr.StockListing("KRX")
    df = df[df["Code"].astype(str).str[-1] == "0"]  # 보통주만

    # breakout: 당일 급등 + 시총 필터 + 거래량순
    bdf = df[(df["Marcap"] >= UNIVERSE_MIN_MARKET_CAP)
             & (df["ChagesRatio"] >= SCREEN_RISE_PCT)]
    bdf = bdf.sort_values("Volume", ascending=False).head(breakout_limit)
    breakout = list(zip(bdf["Code"], bdf["Name"]))

    # reversal/단테 검색기: 시총 100억+ 보통주, 시총순 상위 reversal_limit (넓은 유니버스)
    # (검색기 자체에 거래량/대금 유동성 필터가 있어 잡주는 걸러짐)
    rdf = df[df["Marcap"] >= 1e10]
    rdf = rdf.sort_values("Marcap", ascending=False).head(reversal_limit)
    reversal = list(zip(rdf["Code"], rdf["Name"]))
    return breakout, reversal


def _us_universe():
    """US 정적 베이스 유니버스 (breakout/reversal 공통)."""
    from common.universe import _US_BASE_UNIVERSE
    return [(s, s) for s in _US_BASE_UNIVERSE]


# ----------------------------------------------------------------------------
# 스캔 본체
# ----------------------------------------------------------------------------
def _scan(candidates_breakout, candidates_reversal, fetch):
    """주어진 후보·캔들공급자로 두 검색기를 실행. 결과 dict 반환."""
    bp = StrategyParams.from_config()
    rp = DanteReversalParams()

    breakout_pass = []
    for code, name in candidates_breakout:
        cs = fetch(code)
        if not cs:
            continue
        res = screen(cs, bp)
        if res.passed:
            breakout_pass.append((code, name, dict(res.metrics)))

    reversal_pass, watch = [], []
    dante = {key: [] for key, _, _ in _DANTE_SCREENS}  # 추가 검색기 통과 결과
    for code, name in candidates_reversal:
        cs = fetch(code)
        if not cs or len(cs) < 448:
            continue
        res = screen_dante_reversal(cs, rp)
        if res.passed:
            reversal_pass.append((code, name, dict(res.metrics)))
        elif res.metrics.get("ma_alignment") == "bearish":
            ma112 = ind.sma(ind.closes(cs), 112)
            if ma112:
                watch.append((code, name, round(cs[-1].close / ma112 * 100, 1)))
        # 추가 단테 검색기 (같은 일봉 재사용)
        for key, _, fn in _DANTE_SCREENS:
            r = fn(cs)
            if r.passed:
                dante[key].append((code, name, dict(r.metrics)))
    watch.sort(key=lambda x: -x[2])
    return {"breakout": breakout_pass, "reversal": reversal_pass,
            "watch": watch, "dante": dante}


def _render_report(market: str, scan_date: str, result: dict) -> str:
    lines = [f"# EOD 검색기 스캔 — {market.upper()} {scan_date}", ""]
    lines.append(f"_확정 종가 기준 / breakout {len(result['breakout'])}종목, "
                 f"역배열 통과 {len(result['reversal'])}종목_\n")

    lines.append("## ① breakout 세력봉 검색기")
    if result["breakout"]:
        for code, name, m in result["breakout"]:
            lines.append(f"- ✅ `{code}` {name} — chg {m.get('change_pct')}% / "
                         f"body {m.get('body_ratio')} / volx {m.get('volume_ratio')} / "
                         f"이격 {m.get('disparity')}")
    else:
        lines.append("- (통과 종목 없음)")

    lines.append("\n## ② 단테 역배열 스윙 (B-1)")
    if result["reversal"]:
        for code, name, m in result["reversal"]:
            lines.append(f"- ✅ `{code}` {name} — 거래량 {m.get('avg_volume')} / "
                         f"선행스팬2 {m.get('senkou_b')}")
    else:
        lines.append("- (통과 0 — 역배열 종목이 아직 112일선 회복 전)")

    lines.append(f"\n### 🔻 역배열 워치리스트 (112일선 회복 시 발동, top {WATCHLIST_TOP})")
    if result["watch"]:
        for code, name, ratio in result["watch"][:WATCHLIST_TOP]:
            lines.append(f"- `{code}` {name} — 종가/112일선 {ratio}% "
                         f"(발동까지 +{round(100 - ratio, 1)}%p)")
    else:
        lines.append("- (역배열 종목 없음)")

    # ③ 추가 단테 검색기
    dante = result.get("dante", {})
    lines.append("\n## ③ 추가 단테 검색기")
    for key, label, _ in _DANTE_SCREENS:
        hits = dante.get(key, [])
        lines.append(f"\n### {label} ({len(hits)}종목)")
        if hits:
            for code, name, _m in hits[:WATCHLIST_TOP]:
                lines.append(f"- ✅ `{code}` {name}")
        else:
            lines.append("- (통과 종목 없음)")
    lines.append("")
    return "\n".join(lines)


def run_eod_scan(market: str = "kr",
                 breakout_limit: int = DEFAULT_BREAKOUT_LIMIT,
                 reversal_limit: int = DEFAULT_REVERSAL_LIMIT,
                 out_dir: str | None = None,
                 scan_date: str | None = None) -> list[str]:
    """EOD 스캔 실행 → 마켓별 리포트 파일 경로 리스트 반환.

    market: 'kr' | 'us' | 'all'
    """
    markets = ["kr", "us"] if market == "all" else [market]
    out_dir = out_dir or os.path.join(_ROOT, "RESEARCH", "eod")
    os.makedirs(out_dir, exist_ok=True)
    scan_date = scan_date or date.today().strftime("%Y%m%d")
    saved = []

    for mk in markets:
        logger.info(f"[EOD] {mk.upper()} 검색기 스캔 시작...")
        if mk == "kr":
            cand_b, cand_r = _kr_universe(breakout_limit, reversal_limit)
            fetch = _kr_candles
        else:
            uni = _us_universe()
            cand_b = cand_r = uni
            fetch = _us_candles

        result = _scan(cand_b, cand_r, fetch)
        report = _render_report(mk, scan_date, result)
        path = os.path.join(out_dir, f"eod_{mk}_{scan_date}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        saved.append(path)
        logger.info(f"[EOD] {mk.upper()} 완료 → {path} "
                    f"(breakout {len(result['breakout'])}, "
                    f"역배열통과 {len(result['reversal'])}, "
                    f"워치 {len(result['watch'])})")
        print(report)
    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    mk = sys.argv[1] if len(sys.argv) > 1 else "kr"
    run_eod_scan(market=mk)
