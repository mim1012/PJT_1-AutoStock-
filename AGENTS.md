# Repository Guidelines

## Project Structure & Module Organization
This repository is a Korean Investment Securities (KIS) automated trading system. Root Python modules such as `main.py`, `api_server.py`, `strategy_pjt1.py`, `token_manager.py`, and `config.py` drive scheduling, API access, strategy execution, and configuration. Shared trading primitives live in `common/`; market-specific implementations live in `kr/` and `us/`; 24-hour overseas trading scripts live in `overseas_stock/`. Tests are in `tests/`, with a few legacy smoke scripts named `_test_*.py` at the root. Documentation is in `docs/`, research artifacts in `RESEARCH/`, logs in `log/` and `transaction_logs/`, and the Flutter client in `mobile_app/`.

## Build, Test, and Development Commands
```bash
python -m venv venv && source venv/bin/activate  # create/activate local env on Unix
pip install -r requirements.txt                  # install Python dependencies
python main.py                                   # run the trading scheduler
python api_server.py                             # run the backend API if needed
pytest tests                                     # run the Python test suite
```
On Windows, activate with `venv\Scripts\activate` and use `start_24h_trading.bat` for the 24-hour trading workflow. For the Flutter app, run `cd mobile_app && flutter pub get && flutter test`; use `flutter analyze` before UI changes are submitted.

## Coding Style & Naming Conventions
Use Python 3 with 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes, and clear constant names such as `USE_PAPER_TRADING`. Keep trading logic deterministic and prefer small helpers in `common/` over duplicating logic across `kr/`, `us/`, and `overseas_stock/`. Dart code follows `mobile_app/analysis_options.yaml` and `flutter_lints`.

## Testing Guidelines
Add or update `pytest` tests in `tests/test_*.py` for Python behavior. Prefer mocks or paper-trading paths for KIS API flows; never require real account credentials in automated tests. Before live trading changes, run targeted tests, then perform the smoke checks documented in `docs/TESTING_GUIDE.md` such as `python simple_balance_check.py` and `python token_manager.py check`.

## Commit & Pull Request Guidelines
Git history uses concise conventional prefixes, often with Korean descriptions, for example `feat: ...`, `fix: ...`, and `docs: ...`. Keep commits focused on one behavior. Pull requests should describe the trading impact, list test/smoke results, link relevant issues or docs, and include screenshots for `mobile_app/` UI changes.

## Security & Configuration Tips
Do not commit `.env`, token files, account numbers, generated logs, CSV/XLSX outputs, or secrets. Use `.env.example` as the template and keep `USE_PAPER_TRADING = True` for validation before any real-market run.
