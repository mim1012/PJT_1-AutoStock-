@echo off
chcp 65001
title 한국투자증권 예수금 조회 테스트

echo.
echo ======================================================
echo           한국투자증권 예수금 조회 전용 테스트
echo ======================================================
echo.
echo 💰 예수금 조회 기능만 집중적으로 테스트합니다
echo 📊 API 응답 구조와 필드를 상세 분석합니다
echo 🔍 실전/모의투자 모드별로 비교 테스트합니다
echo.

if exist "venv\Scripts\activate.bat" (
    echo 🔄 가상환경 활성화 중...
    call venv\Scripts\activate.bat
    echo ✅ 가상환경 활성화 완료
) else (
    echo ⚠️  가상환경이 없습니다. 시스템 Python을 사용합니다.
)

echo.
echo 🚀 예수금 조회 테스트 시작...
echo.

python test_balance_only.py

echo.
echo ======================================================
echo.
echo 📋 테스트 결과가 balance_test.log 파일에도 저장되었습니다.
echo 🔍 로그 파일을 확인하여 상세한 분석 결과를 볼 수 있습니다.
echo.

pause 