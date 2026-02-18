# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KIS (한국투자증권) 24-hour automated stock trading system v4.7. Trades both Korean stocks (KOSPI/KOSDAQ, 09:00-15:30 KST) and US stocks (NASDAQ/NYSE, 09:30-16:00 ET) via the KIS OpenAPI. The main source code lives in `PJT v4.7 1023 new/`.

**Language**: Python 3 (no type checker, no linter configured)
**Primary library**: `mojito2` (KIS OpenAPI wrapper), `schedule`, `pytz`, `pandas`, `python-dotenv`
**Platform**: Windows (batch files for startup), also runs on Linux

## Development Commands

All commands run from the `PJT v4.7 1023 new/` directory with the venv activated.

```bash
# Activate virtual environment
# Windows: venv\Scripts\activate
# Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# --- Entry Points ---
# US-only trading (legacy single-market)
python main.py

# 24-hour dual-market trading (KR + US)
python dual_market_scheduler.py

# 24-hour via overseas_stock module
cd overseas_stock && python main_24h_trading.py

# Windows batch (recommended for production)
start_24h_trading.bat

# --- Token Management ---
# US tokens
python -m us.token_manager check|delete|refresh|get

# KR tokens
python -m kr.token_manager check|delete|refresh|get

# Legacy root token manager
python token_manager.py check|refresh|delete|get

# --- Tests ---
# Dual-token separation tests
python -m pytest tests/test_dual_token.py -v

# Integration tests (module imports, config, market)
python -m pytest tests/test_integration.py -v

# KR API tests
python -m pytest tests/test_kr_api.py -v

# Run a single test function
python -m pytest tests/test_dual_token.py::test_token_file_paths -v

# Sector filter tests (standalone, not pytest)
python test_sector_filter.py

# Excel logging tests
python test_excel_logging.py

# API connection quick check
python simple_balance_check.py
```

Note: Tests under `tests/` use plain functions (no pytest fixtures or markers), but are discoverable by pytest. Root-level `test_*.py` files are standalone scripts run directly with `python`.

## Architecture

### Three Entry Points

1. **`main.py`** - US-only scheduler. Uses `TradingScheduler` with `schedule` library. Tries to import from `us/` module first, falls back to `strategy_pjt1.py`.
2. **`dual_market_scheduler.py`** - Full dual-market scheduler (`MarketScheduler`). Imports both `us.strategy.USStrategy` and `kr.strategy.KRStrategy`, switches between markets based on timezone.
3. **`overseas_stock/main_24h_trading.py`** - Alternate 24H system using `Market24hScheduler`. Imports `KRStrategy` and `TradingStrategy` (from root `strategy_pjt1.py`).

### Module Hierarchy (Inheritance Pattern)

```
common/                         # Abstract base classes (ABC)
  base_api.py       → BaseAPIClient    (get_account_balance, get_current_price, place_order)
  base_strategy.py  → BaseStrategy     (execute_buy_strategy, execute_sell_strategy, should_buy, should_sell)
  base_token_manager.py → BaseTokenManager (get_api_url, get_app_credentials, get_token_file_prefix)

us/                             # US stock implementation
  config.py         → USConfig         (NASDAQ/NYSE exchange codes, stop-loss: -15%, 100-day cooldown)
  api_client.py     → USAPIClient      (extends BaseAPIClient)
  strategy.py       → USStrategy       (extends BaseStrategy)
  token_manager.py  → USTokenManager   (extends BaseTokenManager, prefix="us")

kr/                             # Korean stock implementation
  config.py         → KRConfig         (KOSPI/KOSDAQ codes, tick sizes, stop-loss: -10%, 50-day cooldown)
  api_client.py     → KRAPIClient      (extends BaseAPIClient)
  strategy.py       → KRStrategy       (extends BaseStrategy)
  token_manager.py  → KRTokenManager   (extends BaseTokenManager, prefix="kr")
```

### Root-Level Legacy Modules (US-only, pre-refactor)

These are the original US-focused modules still used by `main.py` and `strategy_pjt1.py`:
- **`kis_api.py`** - KIS API client with dual NASDAQ/NYSE detection. Uses `mojito2` with direct HTTP fallback.
- **`token_manager.py`** - Token lifecycle with 24h policy, 5h refresh threshold, unified sync between `api_token.json` and `token.dat`.
- **`strategy_pjt1.py`** - PJT #1 US trading strategy. Loads `stocks_config.json`, uses `StopLossTracker`.
- **`order_manager.py`** - Order tracking with 20-minute timeout and auto-cleanup.
- **`transaction_logger.py`** - CSV logger to `transaction_logs/`. Prefix-aware (`kr_trading_log_*` vs `trading_log_*`).
- **`stop_loss_tracker.py`** - JSON cache + CSV hybrid blacklist. Atomic writes with `.bak` backup.

### Token Architecture

US and KR tokens are managed independently with prefix-based file separation:
- US: `us_api_token.json`, `us_token_issued_at.dat`, `us_krs_token.dat`
- KR: `kr_api_token.json`, `kr_token_issued_at.dat`, `kr_krs_token.dat`
- Legacy (root): `api_token.json`, `token_issued_at.dat`, `token.dat`

Tokens expire after 24h (KIS API policy). Auto-renewal triggers when <5h remaining. Emergency re-issue bypasses the 24h limit.

### Trading Strategy Logic

**Buy**: Filter stocks must all be rising (if `ENABLE_FILTER_CHECK=True`) → select top 3 declining from watch_list → check previous sell price → position size = cash / 3 (max 100 shares).

**Sell**: Exit at `PROFIT_THRESHOLD` (default 5%). Highest-profit position sold first. Uses API-sourced average price (not in-memory).

**Stop Loss**: US market at -15% with 100-day cooldown. KR market at -10% with 50-day cooldown. Managed by `StopLossTracker`.

### KIS API Field Mapping

The API uses different field names across real/paper modes and endpoints. The system uses fallback chains:
- Sellable quantity: `ord_psbl_qty` → `ord_psbl_qty1` → `ovrs_cblc_qty` → `ccld_qty_smtl1`
- Evaluation amount: `ovrs_stck_evlu_amt` → `frcr_evlu_amt2` → `frcr_evlu_amt`
- Purchase amount: `frcr_pchs_amt1` → `frcr_pchs_amt` → `pchs_amt`

Debug with `python debug_raw_balance.py` → saves full response to `debug_balance_raw.json`.

## Configuration

### Credentials

Priority: environment variables (.env) > `config.py` fallback. Copy `.env.example` to `.env` and fill in `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER`.

### Key Config Flags (`config.py`)

- `USE_PAPER_TRADING`: `True` = paper trading (safe), `False` = REAL MONEY
- `PROFIT_THRESHOLD`: Target sell profit rate (default 0.05 = 5%)
- `CHECK_PREVIOUS_SELL_PRICE`: Prevent buying above last sell price
- `SELL_INTERVAL_MINUTES` / `BUY_INTERVAL_MINUTES`: Strategy check frequency

### Stock Lists (`stocks_config.json` for US, `kr_stocks_config.json` for KR)

```json
{
  "filter_stocks": {"NVDA": true, "AMZN": true},  // All must be rising for buy trigger; {} = no filter
  "watch_list": ["SOUN", "RGTI", "SMCI"]           // Eligible trading symbols
}
```

## Important Conventions

- All time comparisons use `pytz` timezone-aware datetimes. US market uses `US/Eastern`, KR uses `Asia/Seoul`.
- T+1 settlement rule for US stocks (changed from T+2 on May 28, 2024). Only `ord_psbl_qty` (settled shares) used for sell orders.
- CSV logs use UTF-8 BOM encoding for Excel compatibility with Korean text.
- `sys.path.insert(0, project_root)` is used throughout submodules to resolve imports from the project root.
- The `open-trading-api/` directory contains KIS reference SDK samples and is not part of the runtime system.
