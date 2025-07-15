@echo off
chcp 65001 > nul
echo =====================================
echo 🚀 모의투자 매수/매도 메서드 테스트
echo =====================================
echo.
echo 💡 현재 설정: 모의투자 모드 (실제 돈 사용 안함)
echo.
echo 🎯 테스트 메뉴:
echo    1. 전략 시뮬레이터 (가상 포트폴리오)
echo    2. 통합 테스트 가이드
echo    3. 실제 모의투자 API 테스트
echo    4. 계좌 잔고 확인 (빠른 테스트)
echo    5. 기존 전략 테스트
echo    0. 종료
echo.
set /p choice=선택하세요 (0-5): 

if "%choice%"=="1" (
    echo.
    echo 🎯 전략 시뮬레이터 실행 중...
    python strategy_test_simulator.py
    pause
) else if "%choice%"=="2" (
    echo.
    echo 🎯 통합 테스트 가이드 실행 중...
    python quick_test_guide.py
    pause
) else if "%choice%"=="3" (
    echo.
    echo 🎯 실제 모의투자 API 테스트 실행 중...
    python real_paper_trading_test.py
    pause
) else if "%choice%"=="4" (
    echo.
    echo 🎯 계좌 잔고 확인 중...
    python quick_balance_test.py
    pause
) else if "%choice%"=="5" (
    echo.
    echo 🎯 기존 전략 테스트 실행 중...
    python final_strategy_test.py
    pause
) else if "%choice%"=="0" (
    echo.
    echo 👋 테스트 종료
    exit /b 0
) else (
    echo.
    echo ❌ 잘못된 선택입니다.
    pause
)

echo.
echo =====================================
echo 🔄 다른 테스트를 실행하려면 다시 실행하세요
echo =====================================
pause 