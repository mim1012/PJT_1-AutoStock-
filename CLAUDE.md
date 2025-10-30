# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Korean Investment Securities (한국투자증권) automated trading system for US stocks using their OpenAPI with the `mojito2` library. The system implements a scheduled filter-based trading strategy that operates during US market hours (09:30-16:00 ET).

**Version**: v4.6 (실전거래 대응)
**Primary Trading Target**: US stocks (NASDAQ/NYSE)
**Execution Mode**: Scheduled automated trading with filter-based stock selection

## Critical Architecture Components

### System Flow Overview
```
main.py (Scheduler)
  └─> TradingScheduler
       ├─> execute_sell_strategy() [every 30 min]
       │    └─> strategy_pjt1.TradingStrategy.execute_sell_strategy()
       │         ├─> get_account_balance() via kis_api
       │         ├─> Calculate profit rates
       │         └─> place_order("sell") if threshold met
       │
       ├─> execute_buy_strategy() [every 60 min]
       │    └─> strategy_pjt1.TradingStrategy.execute_buy_strategy()
       │         ├─> check_filter_condition() [if ENABLE_FILTER_CHECK=True]
       │         ├─> get_top_declining_stocks(count=3)
       │         ├─> should_buy() [check previous sell price]
       │         └─> place_order("buy") with position sizing
       │
       └─> cleanup_orders() [every 10 min]
```

### Trading Strategy Flow
The system follows a conditional buy/sell pattern:
1. **Buy Trigger**:
   - If `ENABLE_FILTER_CHECK=True`: All `filter_stocks` in `stocks_config.json` must be rising (vs previous close)
   - Selects top 3 declining stocks from `watch_list` (sorted by decline rate)
   - Checks `CHECK_PREVIOUS_SELL_PRICE` flag to prevent buying above last sell price
   - Position sizing: divides available cash by 3 (max 100 shares per stock)
2. **Sell Trigger**:
   - Positions are exited when they reach `PROFIT_THRESHOLD` (default: 5% gain)
   - Sells highest profit position first (priority: high-profit > general-profit)
   - Uses **API-sourced average price** (not memory) to ensure accuracy after restarts
3. **Scheduling**:
   - Sell checks: every 30 minutes during market hours (configurable via `SELL_INTERVAL_MINUTES`)
   - Buy checks: every 60 minutes during market hours (configurable via `BUY_INTERVAL_MINUTES`)
   - Order cleanup: every 10 minutes
   - Status report: every 5 minutes
   - Token refresh check: every 30 minutes

### API Integration Architecture
- **Primary Client**: `kis_api.py` uses `mojito2` library for all KIS OpenAPI interactions
  - **Dual Exchange Support**: Automatically detects NASDAQ vs NYSE for each symbol
  - **Direct API Calls**: Fallback to direct HTTP requests if mojito2 fails
  - **Balance Query**: Uses TTTS3012R (real) / VTTS3012R (paper) with empty `OVRS_EXCG_CD` to query all exchanges
- **Token Management**: `token_manager.py` handles automatic token refresh with unified synchronization
  - Tokens expire every 24 hours (KIS API policy enforced)
  - Auto-renewal when remaining time drops below 5 hours (18000 seconds)
  - Emergency re-issue bypasses 24-hour limit if token expiring soon
  - Token files: `api_token.json` (token data) + `token_issued_at.dat` (issue timestamp)
  - **Unified Token Architecture**: TokenManager serves as master token source
    - `api_token.json`: Master token for balance queries and order placement
    - `token.dat`: mojito2 token automatically synced from TokenManager
    - Synchronization occurs during client initialization and broker reinitialization
    - Prevents dual-token desync issues that caused API failures
- **Rate Limiting**: Built-in retry logic with exponential backoff (up to 20 retries via `MAX_RETRY_COUNT`)
- **Mode Switching**: `USE_PAPER_TRADING` flag switches between paper/real trading endpoints
  - Real: `https://openapi.koreainvestment.com:9443`
  - Paper: `https://openapivts.koreainvestment.com:29443`

### Order State Management
The `OrderManager` (order_manager.py) tracks order lifecycle:
- Pending orders timeout after 20 minutes
- Filled orders are logged to daily CSV files
- Order cleanup runs automatically every 10 minutes

### Module Architecture
```
Main Components:
├── main.py                    # Scheduler and entry point
├── config.py                  # Configuration (API keys, trading params)
├── stocks_config.json         # Stock lists (filter_stocks, watch_list)
├── kis_api.py                 # KIS API client with dual exchange support
├── token_manager.py           # Token lifecycle management (24h policy)
├── strategy_pjt1.py           # PJT #1 trading strategy implementation
├── order_manager.py           # Order tracking and cleanup
├── transaction_logger.py      # CSV transaction logging
└── currency_utils.py          # USD/KRW formatting utilities

Supporting Files:
├── api_token.json             # Current access token + expiry
├── token_issued_at.dat        # Token issue timestamp (24h enforcement)
├── trading.log                # Detailed execution logs
└── transaction_logs/          # Daily CSV files
    └── trading_log_YYYYMMDD.csv
```

## Development Commands

### Quick Start
```bash
# Automated setup and run (Windows) - handles venv, dependencies, and checks
start_main_system_cmd.bat

# Alternative: setup and run
setup_and_run.bat

# Direct execution (requires activated venv)
python main.py
```

### Token Management
```bash
# Check token status
python token_manager.py check

# Force token refresh (respects 24-hour limit)
python token_manager.py refresh

# Delete token file
python token_manager.py delete

# Get valid token
python token_manager.py get
```

### Testing Components
```bash
# Test API connection and balance
python simple_balance_check.py

# Debug raw API responses (saves to debug_balance_raw.json)
python debug_raw_balance.py

# Test real trading logic flow
python test_trading_logic.py

# Test transaction logger
python test_transaction_logger.py

# Test mojito2 API directly
python test_mojito_api.py

# Test pykis alternative library
python test_pykis_api.py

# Test token synchronization (TokenManager ↔ mojito2)
python test_token_sync.py
```

### Environment Management
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration Architecture

### Mode Control (`config.py`)
```python
USE_PAPER_TRADING = False  # False = REAL money trading, True = Paper trading
SIMULATION_MODE = False    # True = dry run without API calls
ENABLE_FILTER_CHECK = True # True = require filter stocks to be up before buying
CHECK_PREVIOUS_SELL_PRICE = True # True = prevent buying above last sell price
```

**Critical Safety Note**: When `USE_PAPER_TRADING = False`, the system trades with REAL MONEY. Always verify this setting before running.

### Stock Configuration (`stocks_config.json`)
```json
{
    "filter_stocks": {},  // Empty {} = no filter requirement (buy anytime)
                          // {"NVDA": true, "AMZN": true} = all must be rising
    "watch_list": ["SOUN", "RGTI", "SMCI", ...]  // Stocks eligible for trading
}
```

**Filter Logic**:
- If `filter_stocks` is empty `{}`: Buy strategy ignores filter check
- If `filter_stocks` has entries: ALL listed stocks must be rising (current > previous close) for buy trigger
- Filter is ignored if `ENABLE_FILTER_CHECK = False` in config.py

### Schedule Parameters
- `SELL_INTERVAL_MINUTES`: Sell strategy frequency (default: 30)
- `BUY_INTERVAL_MINUTES`: Buy strategy frequency (default: 60)
- `ORDER_TIMEOUT_MINUTES`: Cancel unfilled orders after (default: 20)
- `PROFIT_THRESHOLD`: Target profit for sells (default: 0.05 = 5%)

## Key Implementation Details

### Dual Exchange Support (NASDAQ/NYSE)
The system automatically detects whether a stock trades on NASDAQ or NYSE:
- **Method**: `_get_broker_for_symbol()` in `kis_api.py`
- **Logic**: Try NASDAQ first, fallback to NYSE if no data
- **API Codes**: `NASD` (NASDAQ) vs `NYSE` (NYSE)
- **Impact**: Order placement uses correct exchange code (`OVRS_EXCG_CD` field)

### Balance Query Strategy
- **Query Mode**: Empty `OVRS_EXCG_CD = ""` queries ALL exchanges (NASDAQ + NYSE + others)
- **Sellable Quantity**: Uses `ord_psbl_qty` / `ord_psbl_qty1` (T+1 settlement completed shares only, changed from T+2 on May 28, 2024)
- **Field Fallback**: Multiple field attempts for robustness:
  - Quantity: `ord_psbl_qty` → `ord_psbl_qty1` → `ovrs_cblc_qty` → `ccld_qty_smtl1` → `cblc_qty13`
  - Eval Amount: `ovrs_stck_evlu_amt` → `frcr_evlu_amt2` → `frcr_evlu_amt` → `evlu_amt`
  - Purchase Amount: `frcr_pchs_amt1` → `frcr_pchs_amt` → `pchs_amt` → `tot_evlu_amt`

### Time Zone Handling
- All scheduling uses `pytz.timezone('US/Eastern')` for market hours
- Trading hours: 09:30-16:00 ET (weekdays only)
- Weekend/holiday detection prevents unnecessary API calls
- **Important**: System must run on a machine with correct local time or use NTP sync

### Error Recovery Patterns
```python
# Token refresh on 403/401
if response.status_code in [403, 401]:
    self.refresh_token()
    return self.retry_request()

# Order timeout cleanup
if order.age_minutes > ORDER_TIMEOUT_MINUTES:
    self.cancel_order(order.id)
```

### Transaction Logging
Daily CSV files in `transaction_logs/` with format:
- `trading_log_YYYYMMDD.csv`: All trades and strategy events
- **Event Types**:
  - `BALANCE_CHECK`: Account balance snapshots
  - `BUY_ORDER`: Buy order execution details
  - `SELL_ORDER`: Sell order execution with profit/loss
  - `STRATEGY_EXECUTION`: Strategy start/stop/error events
- Columns: timestamp, event_type, symbol, quantity, price, total, profit_loss, notes

## Common Troubleshooting

### API Connection Issues
```bash
# Force token refresh (Windows) - deletes both token files
del token_issued_at.dat
del api_token.json

# Check API credentials
python -c "from config import *; print(f'Key: {KIS_APP_KEY[:10]}...')"

# Test balance query
python simple_balance_check.py

# Debug raw API responses
python debug_raw_balance.py
```

### Exchange Detection Issues
If a stock fails to trade, check exchange detection:
```python
# In kis_api.py, the _get_broker_for_symbol() method tries:
# 1. NASDAQ (nasd_broker) first
# 2. NYSE (nyse_broker) if NASDAQ fails
#
# Check logs for: "{symbol} 현재가: ${price} (나스닥)" or "(뉴욕)"
```

### Token Management Issues
If you see "토큰 남은시간 5시간 이하" warnings:
- System automatically triggers re-issue when token has less than 5 hours remaining
- Emergency re-issue bypasses the 24-hour limit
- Both `token_issued_at.dat` and `api_token.json` are deleted to force renewal
- Check `token_manager.py` lines 49-71 (`can_issue_token`) and 147-157 (`load_token`)

**Token Synchronization Issues**:
If you see mismatched tokens between TokenManager and mojito2:
- Run `python test_token_sync.py` to verify synchronization
- TokenManager (`api_token.json`) is the master token source
- mojito2 (`token.dat`) is automatically synced during broker initialization
- Check logs for `[TOKEN_SYNC]` messages confirming sync operations
- If sync fails, delete both `api_token.json` and `token.dat` to force fresh issue

### mojito2 Library Problems
```bash
# Reinstall specific version
pip uninstall mojito2 -y
pip install mojito2==0.1.6
```

### Order Execution Issues
- Check `trading.log` for detailed error messages
- Verify market hours in ET timezone (09:30-16:00, weekdays only)
- Confirm sufficient account balance
- Check if stock is tradeable (not halted/delisted)
- **Sellable Quantity Error**: "요청수량 > 매도가능수량" means T+1 settlement not complete
  - System uses `ord_psbl_qty` (settled shares only) for sell orders
  - Recently bought shares need 1 business day to settle before selling (T+1 rule, changed May 28, 2024)

### Balance Shows $0 Despite Having Positions
This indicates API field mapping issues:
1. Run `python debug_raw_balance.py` to save raw API response to `debug_balance_raw.json`
2. Check which fields contain the actual amounts in the response
3. Update field priority in `kis_api.py` line 278-311 (eval_fields / purchase_fields)
4. Common fields: `ovrs_stck_evlu_amt`, `frcr_evlu_amt2`, `frcr_pchs_amt1`

## Testing Workflow

### Pre-Production Testing
1. **Set paper trading mode**: `USE_PAPER_TRADING = True` in config.py
2. **Verify API connection**: Run `python simple_balance_check.py`
3. **Test token management**: Run `python token_manager.py check`
4. **Configure stocks**: Edit `stocks_config.json` with test symbols
5. **Test strategy logic**: Set `SIMULATION_MODE = True` and run `python main.py` briefly
6. **Paper trade test**: Run with paper account for 1-2 days (monitor `trading.log`)
7. **Review transaction logs**: Check `transaction_logs/trading_log_YYYYMMDD.csv` for correctness
8. **Production deployment**:
   - Set `USE_PAPER_TRADING = False` in config.py
   - **CRITICAL**: Double-check this setting before running
   - Start with small position sizes
   - Monitor actively for first few hours

## API Response Field Mapping

The KIS API uses different field names for production vs paper trading and has inconsistent field naming across endpoints.

### Critical Balance Fields (kis_api.py:278-427)
The system uses fallback field priority for robustness:

**Sellable Quantity** (settled shares only):
- `ord_psbl_qty` → `ord_psbl_qty1` → `ovrs_cblc_qty` → `ccld_qty_smtl1` → `cblc_qty13`

**Evaluation Amount** (current portfolio value):
- `ovrs_stck_evlu_amt` → `frcr_evlu_amt2` → `frcr_evlu_amt` → `evlu_amt`

**Purchase Amount** (cost basis):
- `frcr_pchs_amt1` → `frcr_pchs_amt` → `pchs_amt` → `tot_evlu_amt`

**Average Price**:
- `pchs_avg_pric` (primary)
- Calculated from `frcr_pchs_amt1 / quantity` if missing

**Current Price**:
- `now_pric2` → `ovrs_now_pric1` → multiple fallbacks

**Profit/Loss**:
- `ovrs_ernr_amt` → `evlu_pfls_amt2` → calculated from `evlu_amt - pchs_amt`

**Profit Rate**:
- `ovrs_ernr_rt` → `evlu_pfls_rt1` → calculated from `profit_loss / pchs_amt * 100`

### Debugging Field Issues
If total amounts show $0.00 despite having positions:
1. Run `python debug_raw_balance.py` to save full API response
2. Open `debug_balance_raw.json` and find `output1` array
3. Check which fields contain non-zero values for your positions
4. Update field priority in `kis_api.py` around lines 278-427

## Critical Safety Checks

### Security
- **Never commit** files containing API keys or account numbers
- Files to protect: `config.py`, `api_token.json`, `token_issued_at.dat`, `.env`
- Ensure `.gitignore` includes: `*.json`, `*.dat`, `*.log`, `*.csv`, `.env`

### Trading Safety
- **Always test** in paper trading mode (`USE_PAPER_TRADING = True`) before production
- **Monitor logs** during first production runs: `tail -f trading.log` (or `Get-Content trading.log -Wait` on Windows)
- **Set appropriate** position sizes to limit risk (system divides cash by 3, max 100 shares)
- **Verify timezone** settings match your deployment environment
- **Check settlement**: T+1 rule means recently bought shares can't be sold for 1 business day (changed May 28, 2024)

### Production Checklist
Before running in production mode:
- [ ] Verified `USE_PAPER_TRADING = False` in config.py
- [ ] Tested in paper trading for at least 1-2 days
- [ ] Reviewed `stocks_config.json` watch_list and filter_stocks
- [ ] Confirmed `PROFIT_THRESHOLD` setting (default 5%)
- [ ] Checked account balance is sufficient
- [ ] Verified token is valid: `python token_manager.py check`
- [ ] Monitored logs for first 30 minutes after start
- [ ] Set up log monitoring: `Get-Content trading.log -Wait -Tail 50`

### Emergency Stop
To stop trading immediately:
1. Press `Ctrl+C` in the terminal running main.py
2. Verify no pending orders: check `trading.log` or run balance check
3. Manually cancel any stuck orders via KIS web interface if needed