# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

한국투자증권(KIS) OpenAPI 기반 미국/한국 주식 자동매매 시스템 v4.7. Python으로 작성되었으며 Windows 10+, Python 3.8+ (3.11 권장) 환경에서 동작합니다.

## Build & Run Commands

```bash
# Install dependencies
pip install -r AutoTrading_Release/requirements.txt
pip install mojito2

# Entry points (from AutoTrading_Release/)
python auto_market_scheduler.py    # Recommended: auto-switches US/KR based on time
python dual_market_scheduler.py    # Concurrent US + KR trading
python main.py --market us         # US only
python main.py --market kr         # KR only
python main.py --market both       # Dual market

# Token management
python -m us.token_manager get     # Issue/refresh US token
python -m kr.token_manager get     # Issue/refresh KR token

# Windows batch files
start_auto.bat                     # Auto market switching (recommended)
start.bat                          # US only
```

## Architecture

### Entry Points (choose one)
- `auto_market_scheduler.py` - Detects active market by current time, runs single market
- `dual_market_scheduler.py` - Runs both markets simultaneously with independent schedulers
- `main.py` - Single-market scheduler with `--market` flag

### Module Structure
```
AutoTrading_Release/
├── common/                  # Abstract base classes
│   ├── base_strategy.py     # Template method pattern for strategies
│   ├── base_api.py          # Abstract API client interface
│   └── base_token_manager.py # Token lifecycle management (24h limit)
├── us/                      # US market implementation
│   ├── strategy.py          # Buy: top declining stocks, Sell: 5% profit target
│   ├── api_client.py        # Uses mojito2 library (NASDAQ + NYSE)
│   └── token_manager.py     # Prefix: "us"
├── kr/                      # Korean market implementation
│   ├── strategy.py          # Adds stop-loss at -15%, 50-day blacklist
│   ├── api_client.py        # Direct KIS REST API (KRX tick sizes)
│   └── token_manager.py     # Prefix: "kr"
```

### Key Components
- **Strategies** inherit from `BaseStrategy`: override `execute_buy_strategy()`, `execute_sell_strategy()`
- **API Clients** inherit from `BaseAPIClient`: implement `get_account_balance()`, `get_current_price()`, `place_order()`
- **Token Managers** inherit from `BaseTokenManager`: handle OAuth2 tokens with 24-hour API limit
- **TransactionLogger** - CSV logging per market (`{prefix}_trading_log_YYYYMMDD.csv`)
- **StopLossTracker** (KR only) - JSON-based blacklist with 50-day cooldown

### Trading Flow
1. Scheduler checks market hours (US: 09:30-16:00 ET, KR: 09:00-15:30 KST)
2. Token manager ensures valid OAuth2 token (auto-refresh if < 5h remaining)
3. Sell strategy runs every 30 minutes: check profit target (5%) or stop-loss (-15%)
4. Buy strategy runs every 60 minutes: find top declining stocks, apply filters, place orders

### Configuration Files
- `config.py` - Global settings (loads from `.env`)
- `us/config.py`, `kr/config.py` - Market-specific settings
- `us_stocks_config.json`, `kr_stocks_config.json` - Watchlists and filter stocks

## Critical Constraints

### Token Limitations
- KIS API allows **only 1 token issue per 24 hours**
- Token files (`{us,kr}_api_token.json`) must not be deleted
- `{us,kr}_token_issued_at.dat` tracks last issue time

### Trading Mode
- `USE_PAPER_TRADING=True` in `.env` for sandbox (모의투자)
- `USE_PAPER_TRADING=False` for live trading (실전투자)

### Credentials
- All API credentials in `.env` file (never commit)
- Required: `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER` (format: `12345678-01`)

## Code Patterns

### Adding a New Market
1. Create `{market}/config.py` with timezone and market hours
2. Implement `{market}/api_client.py` extending `BaseAPIClient`
3. Implement `{market}/strategy.py` extending `BaseStrategy`
4. Create `{market}/token_manager.py` extending `BaseTokenManager`

### Strategy Filters
- `filter_stocks` in config JSON: reference stocks for market direction
- `watch_list`: tradeable symbols
- AND filter: all filter stocks must be positive
- OR filter: any sector condition met (KR supports sectors)

## Logging

- Main log: `trading.log` (10MB rotation, 5 backups)
- Transaction logs: `transaction_logs/{prefix}_trading_log_YYYYMMDD.csv`
- Real-time monitoring: `Get-Content trading.log -Wait -Tail 50` (PowerShell)
