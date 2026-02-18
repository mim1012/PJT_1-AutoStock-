# Team Development Guide - KIS 24-Hour Automated Trading System v4.7

## Table of Contents

1. [AGENTS.md Structure & Navigation](#1-agentsmd-structure--navigation)
2. [Module Dependency Map](#2-module-dependency-map)
3. [Development Patterns](#3-development-patterns)
4. [Testing Checklist](#4-testing-checklist)
5. [Pre-Deployment Validation](#5-pre-deployment-validation)
6. [Code Examples (Good/Bad Patterns)](#6-code-examples-goodbad-patterns)

---

## 1. AGENTS.md Structure & Navigation

### Hierarchical Layout

The project uses a hierarchical `AGENTS.md` system where each module directory has its own file with a parent reference:

```
PJT v4.7 1023 new/
  AGENTS.md                  <-- Root: project overview, all entry points, architecture
  common/AGENTS.md           <-- ABC definitions, class contracts
  us/AGENTS.md               <-- US market implementation details
  kr/AGENTS.md               <-- Korean market implementation details
  overseas_stock/AGENTS.md   <-- Alternative 24h system (independent subsystem)
  tests/AGENTS.md            <-- Test suite organization and conventions
```

### Parent References

Each child `AGENTS.md` starts with an HTML comment pointing to its parent:

```html
<!-- Parent: ../AGENTS.md -->
```

This enables navigation up the hierarchy when exploring an unfamiliar module.

### How to Use AGENTS.md for Development

| Task | Start Here |
|------|-----------|
| Understanding the full system | Root `AGENTS.md` - Architecture Overview section |
| Modifying base class contracts | `common/AGENTS.md` - Class Reference section |
| Working on US trading logic | `us/AGENTS.md` - Class Details section |
| Working on KR trading logic | `kr/AGENTS.md` - Class Details section |
| Modifying the 24h scheduler | `overseas_stock/AGENTS.md` - note it's an independent subsystem |
| Adding or modifying tests | `tests/AGENTS.md` - Adding New Tests section |
| Understanding token management | `common/AGENTS.md` (BaseTokenManager) then `us/` or `kr/` for specifics |
| Understanding API field mappings | `us/AGENTS.md` (balance field fallback chains) |

### Key Information in Each AGENTS.md

- **Purpose**: What the module does
- **Key Files**: Table of files with descriptions
- **Class Details**: Method signatures, parameters, return types
- **For AI Agents**: Working conventions, import paths, testing commands
- **Dependencies**: External packages and internal module dependencies

---

## 2. Module Dependency Map

### Inheritance Hierarchy

```
common/ (Abstract Base Classes - Dependency Root)
  |
  |-- base_api.py (BaseAPIClient)
  |     |-- us/api_client.py (USAPIClient)
  |     +-- kr/api_client.py (KRAPIClient)
  |
  |-- base_strategy.py (BaseStrategy)
  |     |-- us/strategy.py (USStrategy)
  |     +-- kr/strategy.py (KRStrategy)
  |
  +-- base_token_manager.py (BaseTokenManager)
        |-- us/token_manager.py (USTokenManager)
        +-- kr/token_manager.py (KRTokenManager)
```

### Full Dependency Graph

```
config.py (root)
  ^--- us/config.py (imports credentials, trading params)
  ^--- kr/config.py (imports credentials, trading params)
  ^--- dual_market_scheduler.py (imports intervals, log settings)

common/
  ^--- us/ (all 4 files inherit from common/)
  ^--- kr/ (all 4 files inherit from common/)

stop_loss_tracker.py (root)
  ^--- us/strategy.py (US blacklist: us_stop_loss_blacklist.json)
  ^--- kr/strategy.py (KR blacklist: kr_stop_loss_blacklist.json)

transaction_logger.py (root)
  ^--- us/strategy.py (prefix: none, files: trading_log_*.csv)
  ^--- kr/strategy.py (prefix: "kr", files: kr_trading_log_*.csv)

currency_utils.py (root)
  ^--- us/api_client.py (USD/KRW formatting)

order_manager.py (root)
  ^--- dual_market_scheduler.py

overseas_stock/ (INDEPENDENT subsystem)
  |-- kis_auth.py (local, NOT common/base_token_manager)
  |-- imports kr/strategy.py (KRStrategy)
  +-- imports strategy_pjt1.py (legacy US strategy, NOT us/strategy.py)
```

### Impact Analysis Quick Reference

| If you change... | Test these modules... |
|-------------------|----------------------|
| `common/base_api.py` | `us/api_client.py`, `kr/api_client.py`, all tests |
| `common/base_strategy.py` | `us/strategy.py`, `kr/strategy.py`, all tests |
| `common/base_token_manager.py` | `us/token_manager.py`, `kr/token_manager.py`, token tests |
| `config.py` (root) | Everything (all modules depend on this) |
| `us/config.py` | `us/api_client.py`, `us/strategy.py`, `us/token_manager.py` |
| `kr/config.py` | `kr/api_client.py`, `kr/strategy.py`, `kr/token_manager.py` |
| `stop_loss_tracker.py` | `us/strategy.py`, `kr/strategy.py` |
| `transaction_logger.py` | `us/strategy.py`, `kr/strategy.py`, CSV output format |
| `dual_market_scheduler.py` | Integration tests, both US and KR strategies |
| `overseas_stock/*` | Only `overseas_stock/` (independent subsystem) |

---

## 3. Development Patterns

### 3.1 Modifying Base Classes

Base classes in `common/` define the contract for all market implementations. Changes here have the widest blast radius.

**Process:**

1. Read the current abstract method signatures in `common/base_*.py`
2. Check both `us/` and `kr/` implementations for how they implement the contract
3. Make the change in `common/`
4. Update BOTH `us/` and `kr/` implementations if the contract changed
5. Run all tests: `python -m pytest tests/ -v`

**Example - Adding a new abstract method to BaseStrategy:**

```python
# 1. Add to common/base_strategy.py
@abstractmethod
def get_max_position_count(self) -> int:
    """Maximum number of concurrent positions"""
    pass

# 2. Implement in us/strategy.py
def get_max_position_count(self) -> int:
    return 3  # US: max 3 positions

# 3. Implement in kr/strategy.py
def get_max_position_count(self) -> int:
    return 3  # KR: max 3 positions

# 4. Run tests
# python -m pytest tests/test_integration.py -v
```

### 3.2 Adding Trading Strategies

New strategies must extend `BaseStrategy` and implement all 6 abstract methods.

**Required abstract method implementations:**

| Method | Purpose |
|--------|---------|
| `execute_buy_strategy()` | Full buy logic, return `{'executed': bool, 'orders': list, 'message': str}` |
| `execute_sell_strategy()` | Full sell logic, same return format |
| `should_buy(symbol)` | Per-symbol buy decision |
| `should_sell(symbol, profit_rate)` | Per-symbol sell decision |
| `get_watch_list()` | Return list of monitored symbols |
| `get_filter_stocks()` | Return dict of filter stocks |

**Testing requirements for new strategies:**
- Unit test for `should_buy()` with blacklisted, above-sell-price, and normal cases
- Unit test for `should_sell()` with profit-take, stop-loss, and hold cases
- Integration test verifying the strategy can be imported and instantiated
- Verify `StopLossTracker` integration (blacklist file naming)
- Verify `TransactionLogger` prefix (CSV file naming)

### 3.3 Token Management Changes

Token management uses prefix-based file separation. US and KR tokens are fully independent.

**Token file mapping:**

| Market | Token File | Issued-At File | mojito2 File |
|--------|-----------|----------------|-------------|
| US | `us_api_token.json` | `us_token_issued_at.dat` | `us_krs_token.dat` |
| KR | `kr_api_token.json` | `kr_token_issued_at.dat` | `kr_krs_token.dat` |
| Legacy | `api_token.json` | `token_issued_at.dat` | `token.dat` |

**Sync between US/KR tokens:**
- US and KR tokens are completely independent - different files, different refresh cycles
- `USAPIClient.__init__()` syncs `USTokenManager` token into `mojito2`'s pickle file (`us_krs_token.dat`)
- The `overseas_stock/` subsystem uses `kis_auth` directly - completely separate token management

**When modifying token logic:**
1. Change in `common/base_token_manager.py` if the change applies to all markets
2. Change in `us/token_manager.py` or `kr/token_manager.py` if market-specific
3. Run `python -m pytest tests/test_dual_token.py -v` to verify independence
4. Verify 24-hour expiry policy is maintained (KIS API enforced)
5. Verify 5-hour refresh threshold is maintained

### 3.4 Adding a New Market

To add a new market (e.g., Japanese stocks):

1. Create `jp/` directory with:
   - `__init__.py`
   - `config.py` (JPConfig with timezone, hours, exchange codes)
   - `api_client.py` (JPAPIClient extending BaseAPIClient)
   - `strategy.py` (JPStrategy extending BaseStrategy)
   - `token_manager.py` (JPTokenManager extending BaseTokenManager)
   - `AGENTS.md`
2. Create `jp_stocks_config.json` in the project root
3. Register in `dual_market_scheduler.py`:
   - Import `JPStrategy` and `JPConfig`
   - Add `'jp'` market option to `MarketScheduler`
4. Add tests in `tests/test_jp_api.py`
5. Run full integration test suite

---

## 4. Testing Checklist

### 4.1 Test Organization

| Location | Type | Runner | Description |
|----------|------|--------|-------------|
| `tests/test_dual_token.py` | Unit | pytest | Token separation (6 scenarios) |
| `tests/test_integration.py` | Integration | pytest | Module imports, config, market hours (7 scenarios) |
| `tests/test_kr_api.py` | API | pytest | KR balance, price, order structure |
| `test_sector_filter.py` (root) | Standalone | `python` | Sector filter logic |
| `test_excel_logging.py` (root) | Standalone | `python` | CSV/Excel encoding |

### 4.2 Running Tests

```bash
# Activate virtual environment first
# Windows: venv\Scripts\activate
# Linux: source venv/bin/activate

# --- Full Suite ---
python -m pytest tests/ -v

# --- Individual Test Files ---
python -m pytest tests/test_dual_token.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_kr_api.py -v

# --- Single Test Function ---
python -m pytest tests/test_dual_token.py::test_token_file_paths -v

# --- Standalone Scripts (root directory) ---
python test_sector_filter.py
python test_excel_logging.py

# --- Token CLI Tests ---
python -m us.token_manager check
python -m kr.token_manager check

# --- API Connection Test ---
python simple_balance_check.py
```

### 4.3 Test Conventions

- Tests use plain `def test_*()` functions (no fixtures, no markers)
- All test files add project root to `sys.path` via `sys.path.insert(0, project_root)`
- Tests make real API calls (no mocking) - handle API unavailability gracefully
- Use `print()` for progress output (pytest captures on failure)
- Assert with descriptive messages: `assert us_file != kr_file, "US/KR token files are the same!"`

### 4.4 Testing Checklist by Change Type

**After modifying `common/` base classes:**
- [ ] `python -m pytest tests/test_integration.py -v` (module imports still work)
- [ ] `python -m pytest tests/test_dual_token.py -v` (token separation intact)
- [ ] Verify both US and KR strategy instantiation works

**After modifying `us/` or `kr/` modules:**
- [ ] `python -m pytest tests/test_integration.py -v`
- [ ] `python -m pytest tests/test_kr_api.py -v` (if KR changes)
- [ ] `python -m pytest tests/test_dual_token.py -v` (if token changes)

**After modifying `config.py`:**
- [ ] `python -m pytest tests/ -v` (all tests)
- [ ] `python simple_balance_check.py` (API connection)

**After modifying stock config files:**
- [ ] `python test_sector_filter.py` (if sector structure changed)
- [ ] Verify filter_stocks and watch_list load correctly

**After modifying `stop_loss_tracker.py`:**
- [ ] Verify US blacklist (`us_stop_loss_blacklist.json`)
- [ ] Verify KR blacklist (`kr_stop_loss_blacklist.json`)
- [ ] Test cooldown expiry logic

**After modifying `transaction_logger.py`:**
- [ ] `python test_excel_logging.py`
- [ ] Verify UTF-8 BOM encoding in output CSV
- [ ] Verify prefix separation (`kr_trading_log_*` vs `trading_log_*`)

---

## 5. Pre-Deployment Validation

### 5.1 Configuration Validation

- [ ] `.env` file exists with valid credentials (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER`)
- [ ] `USE_PAPER_TRADING` in `config.py` is set correctly (`True` for paper, `False` for REAL MONEY)
- [ ] `stocks_config.json` (US) has valid `filter_stocks` and `watch_list`
- [ ] `kr_stocks_config.json` (KR) has valid structure (flat or sector-based)
- [ ] `PROFIT_THRESHOLD` is set appropriately (default: 0.05 = 5%)

### 5.2 API Connectivity

```bash
# Check API connection
python simple_balance_check.py

# Verify US token
python -m us.token_manager check

# Verify KR token
python -m kr.token_manager check
```

### 5.3 Module Integrity

```bash
# Full integration test
python -m pytest tests/test_integration.py -v

# Token independence
python -m pytest tests/test_dual_token.py -v
```

### 5.4 Safety Checks

- [ ] `USE_PAPER_TRADING` verified (CRITICAL - False = real money)
- [ ] Stop-loss thresholds confirmed (US: -15%, KR: -10%)
- [ ] Stop-loss cooldown periods confirmed (US: 100 days, KR: 50 days)
- [ ] Position sizing limits confirmed (US: max 100 shares, KR: max 1000 shares)
- [ ] Token files exist and are valid (not expired)
- [ ] Log rotation configured (`LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`)

### 5.5 Runtime Validation

- [ ] Start in paper trading mode for at least 1 day
- [ ] Verify sell strategy triggers at `PROFIT_THRESHOLD`
- [ ] Verify buy strategy respects filter conditions
- [ ] Verify stop-loss triggers correctly
- [ ] Check CSV logs in `transaction_logs/` are being written
- [ ] Check `trading.log` for errors
- [ ] Verify token auto-refresh (run for >5 hours to test threshold)

---

## 6. Code Examples (Good/Bad Patterns)

### 6.1 Timezone Handling

**GOOD - Always use pytz timezone-aware datetimes:**
```python
import pytz
from datetime import datetime

tz = pytz.timezone('US/Eastern')
now = datetime.now(tz)
```

**BAD - Never use naive datetimes for market time:**
```python
from datetime import datetime

# WRONG: This uses local system time, not market time
now = datetime.now()
```

### 6.2 API Field Access

**GOOD - Use fallback chains for KIS API fields:**
```python
# Multiple field attempts for robustness (real vs paper mode differences)
quantity = 0
for qty_field in ['ord_psbl_qty', 'ord_psbl_qty1', 'ovrs_cblc_qty']:
    qty_val = self._safe_float(item.get(qty_field))
    if qty_val > 0:
        quantity = int(qty_val)
        break
```

**BAD - Assuming a single field name:**
```python
# WRONG: This field may not exist in paper trading mode
quantity = int(item['ord_psbl_qty'])
```

### 6.3 Token Management

**GOOD - Use the token manager hierarchy:**
```python
from us.token_manager import USTokenManager

tm = USTokenManager()
token = tm.get_valid_token()  # Auto-refreshes if needed
```

**BAD - Directly reading token files:**
```python
# WRONG: Bypasses expiry checks and refresh logic
import json
with open('us_api_token.json') as f:
    token = json.load(f)['access_token']
```

### 6.4 Configuration Access

**GOOD - Use environment variables with fallback:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('KIS_APP_KEY')
```

**BAD - Hardcoding credentials:**
```python
# WRONG: Security risk, will be committed to git
api_key = "PSxxxxxxxxxx"
```

### 6.5 Strategy Implementation

**GOOD - Follow the BaseStrategy contract:**
```python
class NewStrategy(BaseStrategy):
    def execute_buy_strategy(self) -> Dict[str, Any]:
        if not self.api_client.is_market_open():
            return {'executed': False, 'orders': [], 'message': 'Market closed'}

        # Check filter condition first
        if not self.check_filter_condition():
            return {'executed': False, 'orders': [], 'message': 'Filter failed'}

        # ... buy logic ...
        return {'executed': True, 'orders': orders, 'message': f'{len(orders)} orders'}
```

**BAD - Ignoring market hours and filter checks:**
```python
class NewStrategy(BaseStrategy):
    def execute_buy_strategy(self) -> Dict[str, Any]:
        # WRONG: No market hours check, no filter check
        balance = self.api_client.get_account_balance()
        # ... directly placing orders ...
```

### 6.6 Korean Stock Tick Sizes

**GOOD - Use KRConfig.round_to_tick() for limit orders:**
```python
from kr.config import KRConfig

price = 45_320  # raw price
adjusted_price = KRConfig.round_to_tick(price)  # rounds to 45_300 (tick=100)
```

**BAD - Using raw prices for KR limit orders:**
```python
# WRONG: KIS API will reject orders with invalid tick sizes
order_price = 45_320  # Not a valid tick for this price range
```

### 6.7 Stop-Loss Tracking

**GOOD - Check blacklist before buying:**
```python
def should_buy(self, symbol: str) -> bool:
    # Blacklist check FIRST (highest priority)
    if self.stop_loss_tracker.is_blocked(symbol):
        remaining = self.stop_loss_tracker.get_remaining_days(symbol)
        self.logger.info(f"{symbol}: blocked for {remaining} more days")
        return False

    # Then check other conditions...
    return True
```

**BAD - Forgetting to check stop-loss blacklist:**
```python
def should_buy(self, symbol: str) -> bool:
    # WRONG: Missing blacklist check - could buy a stock that was just stop-lossed
    price = self.api_client.get_current_price(symbol)
    return price is not None
```

### 6.8 Import Path Setup

**GOOD - Standard project root path setup:**
```python
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
```

**BAD - Relative imports or hardcoded paths:**
```python
# WRONG: Breaks when run from different directories
sys.path.insert(0, '../../')

# WRONG: Hardcoded path
sys.path.insert(0, 'C:/Users/admin/project/')
```

### 6.9 CSV Logging with Korean Text

**GOOD - UTF-8 BOM encoding for Excel compatibility:**
```python
with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'symbol', 'action', 'notes'])
```

**BAD - Plain UTF-8 (Korean text garbled in Excel):**
```python
# WRONG: Excel will show garbled Korean characters
with open(filename, 'w', encoding='utf-8') as f:
    writer = csv.writer(f)
```

---

## Appendix: Quick Reference

### Entry Points

| Command | Description |
|---------|-------------|
| `python main.py` | US-only trading |
| `python dual_market_scheduler.py` | Dual-market (US + KR) |
| `python dual_market_scheduler.py --market us` | US market only |
| `python dual_market_scheduler.py --market kr` | KR market only |
| `cd overseas_stock && python main_24h_trading.py` | Alternative 24h system |
| `start_24h_trading.bat` | Windows production startup |

### Token CLI

| Command | Description |
|---------|-------------|
| `python -m us.token_manager check` | Check US token status |
| `python -m us.token_manager refresh` | Force US token refresh |
| `python -m us.token_manager delete` | Delete US token |
| `python -m kr.token_manager check` | Check KR token status |
| `python -m kr.token_manager delete` | Delete KR token |

### Key Configuration Values

| Setting | Location | Default | Description |
|---------|----------|---------|-------------|
| `USE_PAPER_TRADING` | `config.py` | `False` | Paper vs real trading |
| `PROFIT_THRESHOLD` | `config.py` | `0.05` | Sell at 5% profit |
| `SELL_INTERVAL_MINUTES` | `config.py` | `30` | Sell check frequency |
| `BUY_INTERVAL_MINUTES` | `config.py` | `60` | Buy check frequency |
| `STOP_LOSS_THRESHOLD` (US) | `us/config.py` | `-0.15` | US stop-loss at -15% |
| `STOP_LOSS_COOLDOWN_DAYS` (US) | `us/config.py` | `100` | US 100-day cooldown |
| `STOP_LOSS_THRESHOLD` (KR) | `kr/config.py` | `-0.10` | KR stop-loss at -10% |
| `STOP_LOSS_COOLDOWN_DAYS` (KR) | `kr/config.py` | `50` | KR 50-day cooldown |
