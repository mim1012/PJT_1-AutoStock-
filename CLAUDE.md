# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KIS (한국투자증권) 24-hour automated stock trading system v4.7. Trades Korean stocks (KOSPI/KOSDAQ, 09:00–15:30 KST) and US stocks (NASDAQ/NYSE, 09:30–16:00 ET) via the KIS OpenAPI. Includes a FastAPI mobile/web dashboard and a Flutter Android app.

**Language**: Python 3.11 (no type checker, no linter configured), Dart/Flutter for mobile  
**Primary libs**: `mojito2`, `schedule`, `pytz`, `pandas`, `fastapi`, `uvicorn`, `python-dotenv`

---

## Development Commands

All commands run from `PJT v4.7 1023 new/` with venv activated.

```bash
# Activate venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux

# Install deps
pip install -r requirements.txt

# ── Entry Points ──────────────────────────────────────────────
# Production (auto-detects active market, starts API server too)
python _test_scheduler_run.py          # dev: skips startup_validator, starts API server on :8000
python auto_market_scheduler.py        # prod: calls startup_validator first, then scheduler only

# API server only (no scheduler)
python api_server.py                   # NOT standalone — use _test_scheduler_run.py instead
                                       # (api_server.py has no uvicorn __main__ block)

# ── Token Management ──────────────────────────────────────────
python -m us.token_manager check|delete|refresh|get
python -m kr.token_manager check|delete|refresh|get

# ── Tests ─────────────────────────────────────────────────────
python -m pytest tests/test_dual_token.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_kr_api.py -v
python -m pytest tests/test_dual_token.py::test_token_file_paths -v

# ── Mobile API (requires running server) ─────────────────────
# ADB wireless port forward (run once per session):
adb reverse tcp:8000 tcp:8000
# Dashboard: http://localhost:8000  (API key: value of MOBILE_API_SECRET in .env)

# ── Flutter App ───────────────────────────────────────────────
cd mobile_app
# Requires Flutter SDK at D:\flutter\flutter and JAVA_HOME set
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
$env:ANDROID_HOME = "C:\Users\PC_1M\AppData\Local\Android\Sdk"
$env:GRADLE_USER_HOME = "D:\.gradle"         # C: drive too small; keep Gradle on D:
$env:PATH = "D:\flutter\flutter\bin;" + $env:PATH
flutter pub get
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk

# ── TradingAgents AI pre-analysis (manual) ───────────────────
python -c "
from dotenv import load_dotenv; load_dotenv()
from common.ta_filter import run_daily_analysis
run_daily_analysis(us_symbols=['AAPL','NVDA'], force=True)
"

# ── EOD discovery scan (Stage-0 발굴, manual) ─────────────────
# Runs all daily screeners on confirmed closes; writes RESEARCH/eod/eod_{market}_{YYYYMMDD}.md
python scripts/eod_scan.py kr|us|all
# (Also auto-run by AutoMarketScheduler: KR 15:40 KST, US 16:10 ET, once/weekday)

# ── Screener parameter tuning (forward-return backtest) ──────
# Sweeps screener params over historical as-of points; writes RESEARCH/backtest_outputs/
python scripts/screener_backtest.py [n_symbols] [as_of_sample_step]
```

---

## Architecture

### Entry-Point Flow

```
_test_scheduler_run.py          ← dev/test entry point
  ├── Thread: uvicorn(api_server.app, :8000)   ← REST API + web dashboard
  └── AutoMarketScheduler.start()              ← 10-sec poll loop

auto_market_scheduler.py        ← prod entry point
  └── startup_validator → AutoMarketScheduler.start()   (no API server)
```

`AutoMarketScheduler` detects active market every minute and delegates to `MarketScheduler(market)` from `dual_market_scheduler.py`. Runs sell every 30 min, buy every 60 min.

### Module Hierarchy

```
common/                      # Abstract base classes + shared utilities
  base_api.py     → BaseAPIClient        (get_account_balance, get_current_price, place_order)
  base_strategy.py→ BaseStrategy         (should_buy, should_sell, passes_screen, execute_*)
  base_token_manager.py → BaseTokenManager
  candle.py       → Candle               (frozen OHLCV bar; is_bull/body_ratio/change_pct props)
  indicators.py   → SMA/MA helpers used by screen() and backtests
  screener.py     → screen() (breakout 세력봉) + screen_dante_* (reversal/convergence/newhigh/
                    closebet/basecandle) + screen_entry_timing() — all take list[Candle]
  screener_dante_extra.py    → screen_dante_bottom (G 바닥) / screen_dante_morning (A 오전급등)
  screener_dante_intraday.py → screen_dante_intraday_breakout/pullback/combo (5-min bars, 타점 단계)
  dante_indicators.py / dante_faithful_daily.py / dante_candidates.py → faithful StockDante port
                    (EMA-stack reversal, candidate dataclasses + JSON artifact writer)
  universe.py     → discover_kr_universe() / discover_us_universe()
  shared_state.py → SharedState singleton (trading_enabled, active_market, API client cache)
  settings_store.py → read_settings() / patch_settings()  ← runtime override via settings.json
  ta_filter.py    → is_bullish(symbol, market) / run_daily_analysis(...)  ← TradingAgents

kr/                          # Korean market implementation
  config.py    → KRConfig    (KOSPI/KOSDAQ, stop-loss -10%, cooldown 50d, tick sizes)
  api_client.py→ KRAPIClient
  strategy.py  → KRStrategy  (extends BaseStrategy)
  token_manager.py → KRTokenManager

us/                          # US market implementation
  config.py    → USConfig    (NASDAQ/NYSE/AMEX, stop-loss -15%, cooldown 100d)
  api_client.py→ USAPIClient (yfinance fallback for price)
  strategy.py  → USStrategy
  token_manager.py → USTokenManager
```

### Config Layering (applied in order, later wins)

1. `config.py` — code defaults
2. `.env` — secrets + `USE_PAPER_TRADING`
3. `settings.json` — runtime overrides written by mobile API (`PATCH /api/v1/settings`)

`config.py` reads `settings.json` at the bottom of the file; every consumer imports from `config`, so mobile-app changes take effect on the next strategy cycle without restart.

### Trading Strategy Logic

**Buy pipeline** (`KRStrategy.should_buy` / `USStrategy.should_buy`):
1. Blacklist check (`stop_loss_tracker.is_blocked`)
2. Price above last-sell check
3. Kill-switch check (`DAILY_LOSS_LIMIT_PCT`)
4. Time-window check (KR: 09:30–15:00, US: 09:30–15:30)
5. Change-rate filter (`PULLBACK_MIN/MAX_PCT` or `BREAKOUT_MIN/MAX_PCT`)
6. Screener (`USE_SCREENER` → `passes_screen()` via `common/screener.py`)
7. JSON strategy engine (`USE_STRATEGY_ENGINE`)
8. **TradingAgents AI filter** (`USE_TA_FILTER` → `common/ta_filter.is_bullish()`, cache-based)

`passes_screen()` in `BaseStrategy` is strategy-aware:
- `pullback`: searches last 10 historical candles with relaxed params (`rise_pct=2%, ma=[5,20,60]`)
- `breakout`: checks today's candle with strict params from `StrategyParams.from_config()`

**Sell pipeline**: stop-loss → trailing stop (`ENABLE_TRAILING_STOP`, `TRAIL_PCT=2%`) → take-profit (`PROFIT_THRESHOLD`).

### Dante Screener / Discovery Layer (`kr/phase1-refactor` focus)

The "단테" (Dante) work models trading as a **two-stage funnel** — discovery and entry-timing are deliberately separated (see `RESEARCH/dante_strategy_pipeline.md` for the canonical spec; `RESEARCH/dante_youtube_screener_conditions.md` for the full condition set; `RESEARCH/dante_screener_tuning.md` for measured params).

| Stage | Purpose | Bar | When | Status |
|-------|---------|-----|------|--------|
| **0 — 발굴 (discovery)** | narrow universe → watch candidates | daily | after close (confirmed) | ✅ `scripts/eod_scan.py` |
| **1 — pre-open triage** | gap/news filter on watchlist | daily | morning | partial |
| **2 — 타점 (entry timing)** | "when to buy now" | 5-min | intraday realtime | ⚠️ TODO (`screener_dante_intraday.py` exists, not wired) |
| **3 — entry gate** | final 8-gate filter | — | per cycle | ✅ `should_buy` |
| **4 — exit** | stop/trail/take-profit | — | per cycle | ✅ `should_sell` |

Key idea: **discovery needs no realtime data** (runs on confirmed daily closes after market close), so only the much smaller Stage-2 watchlist needs intraday/realtime feeds. This is why `eod_scan.py` is decoupled from the live trading loop.

- **All screeners operate on `list[Candle]`** (`common/candle.py`), oldest→newest; the caller guarantees ordering. They are pure functions returning a result dataclass — no API/IO inside.
- **`scripts/eod_scan.py`** runs every daily screener (`screen` + all `screen_dante_*`) over the full universe using **FinanceDataReader (KR) / yfinance (US)** — deliberately *not* KIS, to avoid rate limits on a whole-universe batch. Output: `RESEARCH/eod/eod_{market}_{YYYYMMDD}.md` plus a `*_candidates.json` artifact (`common/dante_candidates.py`). It's wired into `AutoMarketScheduler._run_eod_scan()` (KR 15:40 KST / US 16:10 ET, once per weekday, on a daemon thread).
- **`scripts/screener_backtest.py`** is the tuning harness: for many historical as-of points it evaluates each screener on bars-up-to-that-point, then measures forward returns (`FWD_WINDOWS = [5,10,20,40,60]` days) vs. a market baseline, sweeping params. Use it (and the `offset` sampling for robustness/CV) before committing screener-param changes — avoid overfitting to one symbol sample.
- **TODO / not yet wired**: EOD watchlist → live `watch_list`/universe auto-injection, and the intraday 타점 screeners (`screener_dante_intraday.py`) into `should_buy`. The daily `passes_screen()` path is the only screener currently in the live loop.

### REST API (`api_server.py`)

FastAPI app — **no `__main__` block**, always launched via `uvicorn` in a thread from `_test_scheduler_run.py`.

Key endpoints:
| Method | Path | Notes |
|--------|------|-------|
| GET | `/` or `/dashboard` | Web dashboard HTML (no auth) |
| GET | `/api/v1/system/status` | SharedState snapshot |
| POST | `/api/v1/system/start\|stop` | Toggle trading |
| GET/PATCH | `/api/v1/settings` | Read/write settings.json |
| GET | `/api/v1/account/balance?market=kr\|us\|all` | Live balance |
| GET | `/api/v1/account/positions?market=all` | Positions |
| POST | `/api/v1/orders` | Manual order (requires `confirm_live=true` in live mode) |
| GET/POST | `/api/v1/stocks/config` | Edit watch_list / filter_stocks |

Auth: `X-API-Key: <MOBILE_API_SECRET>` header on all `/api/v1/*` routes.

`SettingsPatch` model controls which keys are patchable: `TRADING_STRATEGY`, `USE_SCREENER`, `USE_TA_FILTER`, `ENABLE_FILTER_CHECK`, `USE_PAPER_TRADING`, `PROFIT_THRESHOLD`, `TRAIL_PCT`, `MAX_POSITIONS`, etc.

### TradingAgents AI Filter (`common/ta_filter.py`)

Daily pre-analysis that saves `ta_signals.json` (14h cache). `is_bullish()` reads cache only — zero latency in the trading loop.

- Signals: `Buy` / `Overweight` → allow; `Sell` / `Underweight` → block; `Hold` / cache-miss → allow
- Pre-analysis triggered by `AutoMarketScheduler` at **08:45 KST** (KR) and **09:15 ET** (US)
- Requires `ANTHROPIC_API_KEY` in `.env` and `USE_TA_FILTER=True` in `config.py` or `settings.json`
- KR tickers: `{symbol}.KS` (KOSPI default); KOSDAQ overrides in `_KR_SUFFIX_OVERRIDE` dict

### Token Architecture

Prefix-based separation — US and KR tokens never share files:
- US: `us_api_token.json`, `us_token_issued_at.dat`, `us_krs_token.dat`
- KR: `kr_api_token.json`, `kr_token_issued_at.dat`, `kr_krs_token.dat`

Tokens expire after 24h. Auto-renewal at <5h remaining.

### Stock Config Files

| File | Used by | Format |
|------|---------|--------|
| `stocks_config.json` | `strategy_pjt1.py` / `main.py` (legacy US) | `{filter_stocks:{}, watch_list:[]}` |
| `us_stocks_config.json` | `USConfig` / `us/strategy.py` | `{"AAPL":{"exchange":"NASD"}}` |
| `kr_stocks_config.json` | `KRConfig` / `kr/strategy.py` | `{filter_stocks:{}, watch_list:[]}` |

`filter_stocks`: all must be rising before any buy fires (disabled when `ENABLE_FILTER_CHECK=False` or `{}`).  
`watch_list`: buy candidates; top 3 by decline rate selected (`pullback`) or top risers (`breakout`).

### Flutter Mobile App (`mobile_app/`)

Single-file Flutter app (`lib/main.dart`, ~1100 lines). Uses plain `dart:io` HTTP (no http package).

5 tabs: Dashboard (balance + start/stop), Transactions, Strategy (strategy/amount/filter toggles), Stocks (watch_list editor), Settings (server URL, API key, credentials).

Build env requirements (Windows):
- Flutter SDK: `D:\flutter\flutter`
- `GRADLE_USER_HOME=D:\.gradle` — C: drive is too small (~6GB free); Gradle cache is 8+ GB
- JDK 17: `C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot`

---

## Key Conventions

- All time comparisons use `pytz` timezone-aware datetimes (`Asia/Seoul` for KR, `US/Eastern` for US).
- KR tick sizes enforced via `KRConfig.round_to_tick(price)` before every order.
- CSV logs use UTF-8 BOM encoding (`transaction_logger.py`) for Excel Korean-text compatibility.
- `sys.path.insert(0, project_root)` appears in submodules to resolve root imports.
- KIS API field names differ between real/paper modes; use fallback chains (see `CLAUDE.md` field mapping section in original docs or `common/base_api.py`).
- `open-trading-api/` is KIS reference SDK — not part of the runtime.
- T+1 settlement for US stocks (since 2024-05-28): use `ord_psbl_qty` (settled shares) for sells.
