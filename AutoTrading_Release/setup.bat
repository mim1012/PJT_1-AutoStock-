@echo off
chcp 65001 >nul
echo ========================================
echo 한국투자증권 자동매매 시스템 v4.7
echo 자동 설치 프로그램
echo ========================================
echo.

REM Python 설치 확인
echo [1/5] Python 설치 확인 중...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo.
    echo Python 3.8 이상을 먼저 설치하세요:
    echo https://www.python.org/downloads/
    echo.
    echo 설치 시 "Add Python to PATH" 옵션을 체크하세요!
    pause
    exit /b 1
)

python --version
echo [OK] Python이 설치되어 있습니다.
echo.

REM pip 업그레이드
echo [2/5] pip 업그레이드 중...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARN] pip 업그레이드 실패 (무시하고 계속)
)
echo.

REM 필수 패키지 설치
echo [3/5] 필수 패키지 설치 중...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] 패키지 설치 실패
    pause
    exit /b 1
)
echo [OK] 필수 패키지 설치 완료
echo.

REM mojito2 설치
echo [4/5] 한국투자증권 API 라이브러리 설치 중...
pip install mojito2
if errorlevel 1 (
    echo [ERROR] mojito2 설치 실패
    pause
    exit /b 1
)
echo [OK] mojito2 설치 완료
echo.

REM 환경 변수 파일 확인
echo [5/5] 환경 설정 확인 중...
if not exist .env (
    echo [WARN] .env 파일이 없습니다.
    echo.
    echo .env.example 파일을 복사하여 .env 파일을 생성합니다...
    copy .env.example .env >nul
    echo.
    echo [중요] .env 파일을 열어서 다음 정보를 입력하세요:
    echo   - KIS_APP_KEY (한국투자증권 APP KEY)
    echo   - KIS_APP_SECRET (한국투자증권 APP SECRET)
    echo   - KIS_ACCOUNT_NUMBER (계좌번호)
    echo.
    echo API 키 발급: https://apiportal.koreainvestment.com
    echo.
    notepad .env
) else (
    echo [OK] .env 파일이 존재합니다.
)
echo.

REM 설치 완료
echo ========================================
echo 설치가 완료되었습니다!
echo ========================================
echo.
echo 다음 단계:
echo 1. .env 파일에 API 키 입력 (위에서 자동으로 열렸습니다)
echo 2. us_stocks_config.json, kr_stocks_config.json 파일에 거래할 종목 설정
echo 3. 프로그램 실행 (3가지 방법):
echo.
echo    ⭐ [권장] start_auto.bat - 자동 시장 전환 모드
echo       └─ 한국 장 시간 → 한국 시장만
echo       └─ 미국 장 시간 → 미국 시장만
echo.
echo    또는
echo    - start.bat          - 미국 주식만
echo    - python main.py --market kr  - 한국 주식만
echo    - python main.py --market both - 듀얼 마켓
echo.
echo 처음 사용하시는 경우:
echo - USE_PAPER_TRADING=True 로 설정 (모의투자)
echo - 충분히 테스트 후 실전 투자 시작
echo.
pause
