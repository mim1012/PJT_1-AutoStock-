@echo off
chcp 65001 >nul
title KIS Auto Trading System v4.0 - Auto Setup and Run

echo ========================================
echo KIS Auto Trading System v4.0
echo Auto Environment Setup and Run
echo ========================================
echo Current Time: %date% %time%
echo.

cd /d "%~dp0"
echo Current Directory: %CD%
echo.

echo Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

echo Checking virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo Existing virtual environment found (venv)
    goto activate_env
) else if exist "new_venv\Scripts\activate.bat" (
    echo Existing virtual environment found (new_venv)
    set VENV_NAME=new_venv
    goto activate_env
) else (
    echo No virtual environment found. Creating new one...
    goto create_env
)

:create_env
echo.
echo Creating Python virtual environment...
python -m venv venv
if %ERRORLEVEL% neq 0 (
    echo Virtual environment creation failed.
    pause
    exit /b 1
)
echo Virtual environment created successfully
set VENV_NAME=venv
goto activate_env

:activate_env
echo.
echo Activating virtual environment...
if not defined VENV_NAME set VENV_NAME=venv
call %VENV_NAME%\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo Virtual environment activation failed.
    pause
    exit /b 1
)
echo Virtual environment activated successfully (%VENV_NAME%)
echo.

echo Checking dependencies installation...
pip list | findstr "requests" >nul
if %ERRORLEVEL% neq 0 (
    echo Installing dependency packages...
    echo This process may take a few minutes...
    pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo Dependency installation failed.
        pause
        exit /b 1
    )
    echo Dependencies installed successfully
) else (
    echo Dependencies already installed
)
echo.

echo 🔑 API 연결 상태 확인 중...
python -c "from kis_api import KISAPIClient; client = KISAPIClient(); print('✅ API 클라이언트 초기화 성공' if client.broker else '❌ API 클라이언트 초기화 실패')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ API 연결에 문제가 있습니다. config.py를 확인해주세요.
    pause
    exit /b 1
)
echo.

echo 💰 계좌 잔고 간단 확인 중...
python simple_balance_check.py
if %ERRORLEVEL% neq 0 (
    echo ❌ 계좌 정보 확인에 실패했습니다.
    pause
    exit /b 1
)
echo.

echo Checking stock configuration...
if not exist "stocks_config.json" (
    echo stocks_config.json file not found.
    echo Please create the stock configuration file.
    pause
    exit /b 1
)
python -c "import json; config=json.load(open('stocks_config.json')); print(f'Filter Stocks: {list(config[\"filter_stocks\"].keys())}'); print(f'Watch List: {len(config[\"watch_list\"])} stocks')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error in stock configuration file.
    pause
    exit /b 1
)
echo.

echo ========================================
echo Auto Trading System setup completed!
python -c "from config import TRADING_START_TIME, TRADING_END_TIME, SELL_INTERVAL_MINUTES, BUY_INTERVAL_MINUTES; print(f'Operating Hours: {TRADING_START_TIME} ~ {TRADING_END_TIME} (US Eastern Time)'); print(f'Sell Check: Every {SELL_INTERVAL_MINUTES} minutes'); print(f'Buy Check: Every {BUY_INTERVAL_MINUTES} minutes')"
echo ========================================
echo.

echo IMPORTANT NOTES:
echo - Press Ctrl+C to stop anytime
echo - Logs are saved to trading.log file
echo - Trade records are saved to transaction_logs folder
echo - Real money trading will be executed!
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
echo Auto Trading System has been terminated.
echo ========================================
pause