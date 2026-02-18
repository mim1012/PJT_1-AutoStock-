@echo off
chcp 949 >nul
echo ============================================
echo 한국/미국 주식 잔고 통합 조회
echo ============================================
echo.
echo [1] 전체 조회 (미국 + 한국)
echo [2] 미국 주식만
echo [3] 한국 주식만
echo.
choice /C 123 /M "선택"

if errorlevel 3 (
    set MODE=kr
) else if errorlevel 2 (
    set MODE=us
) else (
    set MODE=all
)

echo.
python check_balance.py %MODE%
echo.
pause
