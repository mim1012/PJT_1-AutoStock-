@echo off
chcp 65001 >nul
echo ========================================
echo 한국투자증권 자동매매 시스템 시작
echo ========================================
echo 현재 시간: %date% %time%
echo.

cd /d "%~dp0"

echo 가상환경 활성화 중...
call venv\Scripts\activate

echo.
echo 토큰 상태 확인 및 자동 재발급...
python token_manager.py renew

echo.
echo ========================================
echo 자동매매 시스템 시작 중...
echo ⚠️ 실제 돈으로 거래가 실행됩니다!
echo ========================================
echo.

python start_auto_trading.py

pause 