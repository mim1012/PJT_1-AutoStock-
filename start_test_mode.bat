@echo off
chcp 65001 >nul
echo ========================================
echo 자동매매 테스트 모드 시작
echo ========================================
echo 현재 시간: %date% %time%
echo 📝 테스트 모드: 실제 주문 실행 안함
echo.

cd /d "C:\Users\PC_1M\Downloads\프로젝트 요구사항 기반 작업 진행 요청"

echo 가상환경 활성화 중...
call venv\Scripts\activate

echo.
echo 토큰 상태 확인 중...
python token_manager.py check

echo.
echo ========================================
echo 테스트 모드 실행 중...
echo ========================================
echo.

python final_strategy_test.py

pause 