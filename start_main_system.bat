@echo off
chcp 65001 >nul
title 한국투자증권 자동매매 시스템 v2.0 - 메인 스케줄러

echo ========================================
echo 🚀 한국투자증권 자동매매 시스템 v2.0
echo ========================================
echo 현재 시간: %date% %time%
echo 실행 모드: 메인 스케줄러 (main.py)
echo.
echo 🔴 실전투자 모드 활성화됨
echo ⚠️  실제 돈으로 거래가 실행됩니다!
echo.

cd /d "%~dp0"

echo 📂 현재 디렉토리: %CD%
echo.

echo 🐍 Python 가상환경 활성화 중...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
    echo ✅ 가상환경 활성화 완료
) else if exist "new_venv\Scripts\activate.bat" (
    call new_venv\Scripts\activate
    echo ✅ 가상환경 활성화 완료 (new_venv)
) else (
    echo ⚠️  가상환경을 찾을 수 없습니다. 시스템 Python 사용
)
echo.

echo 🔑 API 연결 상태 확인 중...
python -c "from kis_api import KISAPIClient; client = KISAPIClient(); print('✅ API 클라이언트 초기화 성공' if client.broker else '❌ API 클라이언트 초기화 실패')"
echo.

echo 💰 계좌 잔고 간단 확인 중...
python simple_balance_check.py
echo.

echo 📊 종목 설정 확인 중...
python -c "import json; config=json.load(open('stocks_config.json')); print(f'필터 종목: {list(config[\"filter_stocks\"].keys())}'); print(f'관심 종목: {len(config[\"watch_list\"])}개')"
echo.

echo ========================================
echo 🎯 자동매매 시스템 시작 중...
echo 운영시간: 09:30 ~ 16:00 (미국 동부시간)
echo 매도 체크: 30분마다
echo 매수 체크: 60분마다
echo ========================================
echo.

echo 🚨 CAUTION:
echo - Press Ctrl+C to stop anytime
echo - Logs saved to trading.log file
echo - Trading records in transaction_logs folder
echo.

set /p confirm=정말로 실전 자동매매를 시작하시겠습니까? (y/N): 
if /i "%confirm%" neq "y" (
    echo 사용자가 취소했습니다.
    pause
    exit /b
)

echo.
echo 🟢 자동매매 시스템 실행 시작...
python main.py

echo.
echo ========================================
echo 자동매매 시스템이 종료되었습니다.
echo ========================================
pause