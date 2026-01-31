@echo off
chcp 65001 >nul
echo ============================================
echo 자동 시장 전환 시스템 시작
echo ============================================
echo.
echo [기능]
echo - 한국 장 시간 (09:00-15:30 KST) → 한국 시장만 모니터링
echo - 미국 장 시간 (09:30-16:00 ET) → 미국 시장만 모니터링
echo - 자동 시장 감지 및 전환
echo.
echo ============================================
echo.

REM Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo setup.bat를 먼저 실행하세요.
    pause
    exit /b 1
)

REM .env 파일 확인
if not exist .env (
    echo [ERROR] .env 파일이 없습니다!
    echo.
    echo setup.bat를 먼저 실행하여 환경 설정을 완료하세요.
    pause
    exit /b 1
)

REM 거래 모드 확인
findstr /C:"USE_PAPER_TRADING=False" .env >nul
if %errorlevel% equ 0 (
    echo [경고] 실전투자 모드입니다!
    echo.
    echo 실제 돈이 거래됩니다. 계속하시겠습니까?
    echo.
    choice /C YN /M "Y: 실행, N: 취소"
    if errorlevel 2 exit /b 0
) else (
    echo [안전] 모의투자 모드로 실행합니다.
)
echo.

REM 메인 프로그램 실행
echo [자동 시장 전환] 시스템을 시작합니다...
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo 로그는 trading.log 파일에서 확인할 수 있습니다.
echo.
echo ========================================
echo.

python auto_market_scheduler.py

REM 종료 처리
echo.
echo ========================================
echo 프로그램이 종료되었습니다.
echo ========================================
pause
