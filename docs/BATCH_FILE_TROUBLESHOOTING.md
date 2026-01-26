# 배치 파일 문제 해결 가이드

**파일**: `start_24h_trading.bat`
**날짜**: 2026-01-25

---

## 🚨 잠재적 문제점 및 해결 방법

### 1. 한글 깨짐 문제

#### 증상
```
��� �ѱ����ڱ��� 24�ð� �ڵ����ż�����
```

#### 원인
- Windows 콘솔 코드페이지가 UTF-8(65001)이 아님
- 배치 파일 인코딩이 UTF-8 BOM이 아님
- 레지스트리 설정 문제

#### 해결 방법

**방법 1: 배치 파일 자동 해결 (권장)**
```batch
배치 파일 첫 줄에 이미 포함되어 있음:
chcp 65001 >nul
```

**방법 2: 수동 해결**
```batch
# 실행 전 명령 프롬프트에서 실행
chcp 65001
start_24h_trading.bat
```

**방법 3: 콘솔 폰트 변경**
1. 명령 프롬프트 제목 표시줄 우클릭
2. 속성 → 글꼴
3. "Consolas" 또는 "맑은 고딕" 선택

**방법 4: Windows Terminal 사용 (최고의 해결책)**
```powershell
# Windows Terminal 설치 (Windows 11에는 기본 설치됨)
winget install Microsoft.WindowsTerminal

# Windows Terminal에서 실행
wt -d . cmd /k start_24h_trading.bat
```

#### 테스트
```batch
# 한글이 제대로 표시되는지 확인
echo 한국투자증권 24시간 자동매매 시스템

# 정상 출력: 한국투자증권 24시간 자동매매 시스템
# 깨진 출력: �ѱ����ڱ��� 24�ð� �ڵ����ż�����
```

---

### 2. 갑자기 꺼지는 문제

#### 증상
- 배치 파일이 실행 중 갑자기 종료됨
- 오류 메시지 없이 사라짐

#### 원인 및 해결

**원인 1: Python 오류로 프로그램 종료**
```
해결: 배치 파일에 이미 오류 처리 추가됨
- pushd/popd로 디렉토리 복귀 보장
- 오류 코드 저장 및 표시
- pause로 창 유지
```

**원인 2: overseas_stock 폴더 없음**
```batch
# 배치 파일에 이미 체크 로직 포함됨
if not exist "overseas_stock" (
    echo ❌ overseas_stock 폴더를 찾을 수 없습니다!
    pause
    exit /b 1
)
```

**원인 3: .env 파일 없음**
```batch
# 배치 파일에 이미 체크 로직 포함됨
if not exist ".env" (
    echo ❌ .env 파일이 없습니다!
    pause
    exit /b 1
)
```

**원인 4: Python 설치 안 됨**
```batch
# 확인 방법
python --version

# 없으면 Python 설치
# https://www.python.org/downloads/
```

---

### 3. 배치 파일 개선 사항 (이미 적용됨)

#### ✅ 적용된 개선사항

1. **디렉토리 복귀 보장**
   ```batch
   pushd overseas_stock
   python main_24h_trading.py
   popd  # 항상 원래 디렉토리로 복귀
   ```

2. **오류 코드 저장**
   ```batch
   set ERRORCODE=%ERRORLEVEL%

   if %ERRORCODE% NEQ 0 (
       echo 오류 해결 방법:
       echo   1. overseas_stock\trading_24h_*.log 파일 확인
       echo   2. README_24H.md 문제 해결 섹션 참조
   )
   ```

3. **모든 단계에 pause 추가**
   - 오류 발생 시 창이 닫히지 않음
   - 사용자가 메시지를 읽을 수 있음

4. **자동 재시도 로직**
   ```batch
   # API 모듈 로드 실패 시 재시도
   python -c "..." 2>nul
   if errorlevel 1 (
       timeout /t 2 /nobreak >nul
       python -c "..." 2>nul  # 재시도
   )
   ```

5. **python-dotenv 자동 설치**
   ```batch
   python -c "import dotenv" 2>nul
   if errorlevel 1 (
       pip install python-dotenv
   )
   ```

---

### 4. 실행 전 체크리스트

#### 필수 확인 사항

- [ ] `.env` 파일 생성됨
- [ ] `.env`에 API 키 입력됨
- [ ] `overseas_stock` 폴더 존재
- [ ] Python 3.8 이상 설치됨
- [ ] `requirements.txt` 패키지 설치됨

#### 확인 명령어

```batch
# 1. .env 파일 확인
dir .env

# 2. overseas_stock 폴더 확인
dir overseas_stock

# 3. Python 버전 확인
python --version

# 4. 필수 패키지 확인
python -c "import dotenv, pytz, requests, schedule; print('모든 패키지 설치됨')"
```

---

### 5. 로그 파일 확인 방법

#### 실행 로그 위치
```
overseas_stock\trading_24h_YYYYMMDD.log
```

#### 오류 발생 시 확인할 내용
```bash
# 최근 오류 확인
findstr /i "error" overseas_stock\trading_24h_*.log

# 최근 경고 확인
findstr /i "warning" overseas_stock\trading_24h_*.log

# 특정 시간대 로그 확인
findstr "09:00" overseas_stock\trading_24h_*.log
```

---

### 6. 배치 파일 실행 옵션

#### 옵션 1: 더블클릭 (권장)
```
start_24h_trading.bat 파일을 더블클릭
```

#### 옵션 2: 명령 프롬프트에서 실행
```batch
cd "D:\Project\PJT v4.7 1023 new"
start_24h_trading.bat
```

#### 옵션 3: Windows Terminal에서 실행 (최고)
```powershell
wt -d "D:\Project\PJT v4.7 1023 new" cmd /k start_24h_trading.bat
```

#### 옵션 4: 관리자 권한으로 실행
```
start_24h_trading.bat 우클릭 → 관리자 권한으로 실행
```

---

### 7. 자주 발생하는 오류

#### 오류 1: "python은(는) 내부 또는 외부 명령이 아닙니다"
```
원인: Python이 설치되지 않았거나 PATH에 없음

해결:
1. Python 설치: https://www.python.org/downloads/
2. 설치 시 "Add Python to PATH" 체크
3. 또는 수동으로 PATH 추가
```

#### 오류 2: "ModuleNotFoundError: No module named 'dotenv'"
```
원인: python-dotenv 패키지 미설치

해결: 배치 파일이 자동으로 설치 시도
또는 수동 설치:
pip install python-dotenv
```

#### 오류 3: "❌ .env 파일이 없습니다"
```
원인: .env 파일 미생성

해결:
1. copy .env.example .env
2. notepad .env (API 키 입력)
```

#### 오류 4: "⚠️ API 키가 설정되지 않았습니다"
```
원인: .env 파일에 API 키 미입력

해결:
1. notepad .env
2. KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER 입력
```

---

### 8. 한글 깨짐 최종 해결책

만약 위 모든 방법으로 한글이 깨진다면, **한글 없는 버전**을 사용하세요:

```batch
@echo off
chcp 65001 >nul
title KIS 24H Auto Trading System v4.7

echo ================================================
echo   KIS 24H Auto Trading System v4.7
echo ================================================
echo Start Time: %date% %time%
echo.

cd /d "%~dp0"

REM Check .env file
if not exist ".env" (
    echo ERROR: .env file not found
    echo.
    echo Please:
    echo   1. copy .env.example .env
    echo   2. Edit .env and input API keys
    echo.
    pause
    exit /b 1
)

echo [OK] .env file exists
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
    echo [OK] Virtual environment activated
) else (
    echo [WARN] Virtual environment not found
)

echo.
echo Starting 24H Trading System...
echo.

pushd overseas_stock
python main_24h_trading.py

set ERRORCODE=%ERRORLEVEL%
popd

echo.
if %ERRORCODE% EQU 0 (
    echo [OK] System stopped normally
) else (
    echo [ERROR] System stopped with error: %ERRORCODE%
    echo.
    echo Please check:
    echo   1. overseas_stock\trading_24h_*.log
    echo   2. README_24H.md
)
echo.
pause
```

---

## 🎯 정리

### 배치 파일은 이미 다음 문제를 해결했습니다:

✅ 한글 깨짐 방지 (`chcp 65001`)
✅ 갑자기 꺼지는 문제 방지 (`pause`, 오류 처리)
✅ 디렉토리 복귀 보장 (`pushd`/`popd`)
✅ 오류 메시지 표시
✅ 자동 재시도 로직
✅ 필수 패키지 자동 설치

### 추가 조치가 필요한 경우:

1. **한글이 여전히 깨진다면**: Windows Terminal 사용
2. **Python 없다는 오류**: Python 설치
3. **.env 파일 없다는 오류**: `.env` 파일 생성

---

**작성자**: Claude Code
**최종 업데이트**: 2026-01-25
