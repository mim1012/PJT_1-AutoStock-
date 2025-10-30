@echo off
chcp 65001 >nul
title KIS Auto Trading System v2.0 - Main Scheduler

echo ========================================
echo KIS Auto Trading System v2.0 - MAIN
echo ========================================
echo Current Time: %date% %time%
echo Execution Mode: Main Scheduler (main.py)
echo.
echo REAL TRADING MODE ACTIVE
echo WARNING: Real money trading will be executed!
echo.

cd /d "%~dp0"

echo Current Directory: %CD%
echo.

echo Activating Python Virtual Environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate >nul
    echo Virtual Environment Activated (venv)
) else if exist "new_venv\Scripts\activate.bat" (
    call new_venv\Scripts\activate >nul
    echo Virtual Environment Activated (new_venv)
) else (
    echo Using system Python (no virtual environment found)
)
echo.

echo Checking API Connection...
python -c "from kis_api import KISAPIClient; client = KISAPIClient(); print('API Client OK' if client.broker else 'API Client Failed')" 2>nul
echo.

echo Checking Account Balance...
python simple_balance_check.py 2>nul
echo.

echo Checking Stock Configuration...
python -c "import json; config=json.load(open('stocks_config.json')); print('Filter Stocks: ' + str(list(config['filter_stocks'].keys()))); print('Watch List: ' + str(len(config['watch_list'])) + ' stocks')"
echo.

echo ========================================
echo Starting Auto Trading System...
python -c "from config import TRADING_START_TIME, TRADING_END_TIME, SELL_INTERVAL_MINUTES, BUY_INTERVAL_MINUTES; print(f'Operating Hours: {TRADING_START_TIME} ~ {TRADING_END_TIME} (US Eastern Time)'); print(f'Sell Check: Every {SELL_INTERVAL_MINUTES} minutes'); print(f'Buy Check: Every {BUY_INTERVAL_MINUTES} minutes')"
echo ========================================
echo.

echo IMPORTANT NOTES:
echo - Press Ctrl+C to stop anytime
echo - Logs saved to trading.log
echo - Trade records saved to transaction_logs folder
echo.

set /p confirm=Do you really want to start REAL auto trading? (y/N): 
if /i "%confirm%" neq "y" (
    echo User cancelled.
    pause
    exit /b
)

echo.
echo Starting Auto Trading System...
python main.py

echo.
echo ========================================
echo Auto Trading System Stopped.
echo ========================================
pause