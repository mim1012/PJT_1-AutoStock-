# 24시간 자동매매 시스템 - ADVERSARIAL 코드 리뷰 리포트

**리뷰 날짜**: 2026-01-25
**리뷰어**: Claude Code (Adversarial Senior Developer)
**시스템**: 한국투자증권 24시간 자동매매 시스템 v4.7
**거래 모드**: 🔴 **실전투자 모드** (USE_PAPER_TRADING = False)

---

## 🚨 CRITICAL ISSUES (즉시 수정 필수)

### 1. **보안 취약점: API 키/시크릿 코드에 하드코딩**
**위치**: `config.py:5-7`

```python
KIS_APP_KEY = "PS9Yr8VDczEhRt6kbhrAExgLO9mno70zMJvp"
KIS_APP_SECRET = "2mfGKemkM4CTyvkQ1oquImEb+uUKwrflzTn23wjWJ5/PoFu5dwIW1OoyKYCoY2lPxl7L7ukzQqZD8PylBkYA1/SLFQ4r110XH6YCajAcMCzQnQekj1xBNGAaZo8zltZgX7YkomUzoBKV+8kopKGm3c9+juaQU+NJfM4vwMuyk8wkGFiK4v8="
KIS_ACCOUNT_NUMBER = "64721801-01"
```

**문제점**:
- ❌ API 키와 시크릿이 소스코드에 **평문**으로 노출
- ❌ Git 저장소에 커밋될 경우 **영구적으로 유출**
- ❌ 실전투자 계좌번호까지 노출
- ❌ 누군가가 이 키를 획득하면 **계좌의 모든 자금을 탈취** 가능

**즉시 조치 사항**:
1. ⚠️ **지금 즉시** 한국투자증권에서 API 키를 **재발급** 받으세요
2. `.env` 파일로 이동:
   ```bash
   # .env 파일 생성
   KIS_APP_KEY=your_new_key_here
   KIS_APP_SECRET=your_new_secret_here
   KIS_ACCOUNT_NUMBER=your_account_here
   ```
3. `.gitignore`에 추가:
   ```gitignore
   .env
   *.env
   config.py  # 또는 config.py에서 키 제거
   ```
4. `config.py` 수정:
   ```python
   import os
   from dotenv import load_dotenv

   load_dotenv()

   KIS_APP_KEY = os.getenv("KIS_APP_KEY")
   KIS_APP_SECRET = os.getenv("KIS_APP_SECRET")
   KIS_ACCOUNT_NUMBER = os.getenv("KIS_ACCOUNT_NUMBER")
   ```

**심각도**: 🔴 CRITICAL
**영향도**: 전체 계좌 자금 탈취 위험
**수정 우선순위**: P0 (최우선)

---

### 2. **24시간 로직 버그: 동계시간/하계시간 자동 전환 미지원**
**위치**: `main_24h_trading.py:55-58`, `main.py:44-46`

**문제점**:
```python
# main.py:44-46
self.start_time = dt_time.fromisoformat(TRADING_START_TIME)  # "09:30"
self.end_time = dt_time.fromisoformat(TRADING_END_TIME)      # "16:00"
```

- ❌ 미국 시장은 **매년 3월/11월에 서머타임 전환**
  - 동계: 09:30 ET = 23:30 KST
  - 하계: 09:30 ET = 22:30 KST (1시간 차이)
- ❌ 현재 코드는 고정 시간만 체크 → **시즌 전환 시 1시간 오차** 발생
- ❌ `pytz.timezone('US/Eastern')`는 서머타임을 **자동으로 처리**하지만, 고정된 시간과 비교하므로 무의미

**실제 영향**:
- 3월 두 번째 일요일 ~ 11월 첫 번째 일요일: 22:30 KST에 개장하는데 23:30까지 대기
- **1시간 동안 거래 기회 상실**

**수정 방안**:
```python
# main.py의 is_trading_hours() 수정
def is_trading_hours(self):
    """현재 시간이 운영 시간인지 확인 (서머타임 대응)"""
    try:
        # ET 기준으로 비교 (서머타임 자동 처리)
        et_now = datetime.now(self.et_tz)
        current_time_et = et_now.time()

        # ET 기준 고정 시간 (09:30-16:00)
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)

        # 주말 체크
        if et_now.weekday() >= 5:
            return False

        # ET 기준으로 비교
        return market_open <= current_time_et <= market_close

    except Exception as e:
        self.logger.error(f"운영 시간 확인 오류: {e}")
        return False
```

**심각도**: 🔴 CRITICAL
**영향도**: 연간 약 8개월 동안 1시간 거래 기회 손실
**수정 우선순위**: P0

---

### 3. **한국 주식 TR_ID 정합성 검증 필요**
**위치**: `kr/api_client.py:299-303`

```python
# TR ID 설정 (2024년 신규 TR_ID)
if KRConfig.is_paper_trading():
    tr_id = "VTTC0012U" if side.lower() == 'buy' else "VTTC0011U"
else:
    tr_id = "TTTC0012U" if side.lower() == 'buy' else "TTTC0011U"
```

**주석 vs 실제**:
- ✅ 주석에 "2024년 신규 TR_ID"라고 명시
- ✅ 신규 TR_ID 사용 (TTTC0012U/0011U)
- ✅ 구 TR_ID (TTTC0802U/0801U)는 사용하지 않음

**그러나**:
- ⚠️ **한국투자증권 API 명세서 2025년 최신 버전 확인 필요**
- ⚠️ 2026년 1월 현재, TR_ID가 또 변경되었을 가능성
- ⚠️ 실제 운영 중 "EQw00356" 같은 오류 발생 시 TR_ID 재검증 필요

**검증 방법**:
```bash
# 실제 API 호출 테스트
python check_kr_config.py
```

**권장 사항**:
1. 한국투자증권 Open API 문서 최신 버전 확인
2. 테스트 주문으로 TR_ID 검증
3. 오류 발생 시 즉시 롤백할 수 있도록 fallback TR_ID 준비

**심각도**: 🟡 HIGH
**영향도**: API 호출 실패 시 전체 한국 주식 거래 중단
**수정 우선순위**: P1

---

### 4. **잔고 조회 페이징 처리 누락 위험**
**위치**: `kr/api_client.py:82-155`

**현재 코드**:
```python
# 페이징 처리를 위한 변수
all_positions = []
ctx_area_fk100 = ""
ctx_area_nk100 = ""
page_count = 0
max_pages = 20  # 안전장치: 최대 20페이지

# 페이징 루프
while page_count < max_pages:
    # ... API 호출 ...

    # 다음 페이지 체크
    tr_cont = balance.get('tr_cont', '')
    if tr_cont in ['F', 'M']:  # F: 다음 데이터 있음, M: 중간
        ctx_area_fk100 = balance.get('ctx_area_fk100', '')
        ctx_area_nk100 = balance.get('ctx_area_nk100', '')
        page_count += 1
        # ...
```

**문제점**:
- ⚠️ 보유 종목이 20페이지(약 200종목)를 초과하면 **일부 종목이 누락**될 수 있음
- ⚠️ `max_pages` 안전장치가 오히려 **데이터 손실** 유발 가능

**실제 영향**:
- 보유 종목 200개 초과 시 → 201번째부터 매도 전략 실행 안 됨
- **수익 실현 기회 상실**

**수정 방안**:
```python
max_pages = 100  # 또는 무제한 (while True)

# 무제한 페이징 (안전하게)
safety_counter = 0
while safety_counter < 1000:  # 최대 1000페이지 (충분히 큼)
    # ...
    if tr_cont not in ['F', 'M']:
        break
    safety_counter += 1

if safety_counter >= 1000:
    self.logger.critical("페이징 한계 도달 - 일부 종목 누락 가능성!")
```

**심각도**: 🟡 HIGH
**영향도**: 대량 보유 시 일부 종목 매도 불가
**수정 우선순위**: P1

---

## ⚠️ HIGH PRIORITY ISSUES

### 5. **토큰 갱신 실패 시 복구 로직 부재**
**위치**: `main.py:108-184`

**문제점**:
```python
def check_and_refresh_token(self):
    # ...
    new_token = token_manager.get_valid_token()

    # 토큰 변경 감지
    token_changed = (old_token != new_token)

    if token_changed or not hasattr(self, '_last_broker_reinit_time'):
        # 브로커 재초기화
        if self.strategy.api_client.reinitialize_brokers():
            self.logger.info("✅ 브로커 재초기화 성공")
        else:
            self.logger.error("❌ 브로커 재초기화 실패")  # ← 실패 후 조치 없음!
```

- ❌ 브로커 재초기화 실패 시 **거래 중단**되지만 시스템은 계속 실행
- ❌ **오류 알림**이나 **재시도 로직** 없음
- ❌ 사용자는 로그를 확인하기 전까지 거래 중단 사실을 **모름**

**수정 방안**:
```python
# 재시도 로직 추가
max_retries = 3
for attempt in range(max_retries):
    if self.strategy.api_client.reinitialize_brokers():
        self.logger.info(f"✅ 브로커 재초기화 성공 (시도 {attempt+1}/{max_retries})")
        self._last_broker_reinit_time = time.time()
        break
    else:
        self.logger.error(f"❌ 브로커 재초기화 실패 (시도 {attempt+1}/{max_retries})")
        if attempt < max_retries - 1:
            time.sleep(60)  # 1분 대기 후 재시도
        else:
            # 최종 실패 시 알림
            self.logger.critical("🚨 브로커 재초기화 최종 실패! 거래 중단!")
            # TODO: 이메일/SMS 알림 추가
            self.stop()  # 시스템 중지
```

**심각도**: 🟠 MEDIUM-HIGH
**수정 우선순위**: P2

---

### 6. **배치 파일: 오류 발생 시 자동 종료**
**위치**: `start_24h_trading.bat:35-40`

```batch
echo 🔑 API 연결 상태 확인 중...
python -c "import sys; sys.path.insert(0, 'overseas_stock'); import kis_auth as ka; print('✅ API 모듈 로드 성공')"
if errorlevel 1 (
    echo ❌ API 모듈 로드 실패
    pause
    exit /b 1
)
```

**문제점**:
- ⚠️ API 모듈 로드 실패 시 **즉시 종료**
- ⚠️ `overseas_stock` 디렉토리 구조 변경 시 **항상 실패**
- ⚠️ 일시적 네트워크 오류로도 **시스템 시작 불가**

**개선 방안**:
```batch
echo 🔑 API 연결 상태 확인 중...
python -c "import sys; sys.path.insert(0, 'overseas_stock'); import kis_auth as ka; print('✅ API 모듈 로드 성공')" 2>nul
if errorlevel 1 (
    echo ⚠️  API 모듈 로드 실패 - 재시도 중...
    timeout /t 3 /nobreak >nul
    python -c "import sys; sys.path.insert(0, 'overseas_stock'); import kis_auth as ka; print('✅ API 모듈 로드 성공 (재시도)')" 2>nul
    if errorlevel 1 (
        echo ❌ API 모듈 로드 최종 실패
        echo.
        echo 다음을 확인하세요:
        echo   1. overseas_stock 폴더가 존재하는지
        echo   2. kis_auth.py 파일이 있는지
        echo   3. 가상환경이 올바르게 활성화되었는지
        echo.
        set /p continue=그래도 계속하시겠습니까? (y/N):
        if /i "%continue%" neq "y" (
            pause
            exit /b 1
        )
    )
)
```

**심각도**: 🟡 MEDIUM
**수정 우선순위**: P2

---

### 7. **한국 주식 페이징 Rate Limiting 미흡**
**위치**: `kr/api_client.py:151-152`

```python
import time
time.sleep(0.1)  # Rate limiting ← 너무 짧음!
```

**문제점**:
- ⚠️ 한국투자증권 API는 **초당 요청 제한**(예: 20건/초)
- ⚠️ 0.1초 = 초당 10건이지만, 다른 API 호출과 **합산**되면 제한 초과 가능
- ⚠️ Rate limit 초과 시 **일시적 차단** (몇 분~몇 시간)

**권장 설정**:
```python
time.sleep(0.2)  # 200ms = 초당 5건 (안전 마진)
```

**심각도**: 🟡 MEDIUM
**수정 우선순위**: P2

---

## 📋 MEDIUM PRIORITY ISSUES

### 8. **로그 파일 무한 증가 위험**
**위치**: `main_24h_trading.py:179-210`

```python
file_handler = RotatingFileHandler(
    log_filename,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
```

**문제점**:
- ⚠️ 24시간 운영 시 **하루 로그 파일 크기 예상**: 50MB ~ 500MB
- ⚠️ 5개 백업 = 최대 60MB (10MB × 6개)
- ⚠️ **수개월 운영 시 디스크 공간 고갈** 가능

**개선 방안**:
```python
# 더 큰 백업 카운트 또는 일별 로테이션
from logging.handlers import TimedRotatingFileHandler

file_handler = TimedRotatingFileHandler(
    log_filename,
    when='midnight',  # 매일 자정에 로테이션
    interval=1,
    backupCount=30,  # 30일치 보관
    encoding='utf-8'
)
```

**심각도**: 🟢 MEDIUM-LOW
**수정 우선순위**: P3

---

### 9. **Exception 처리 너무 광범위**
**위치**: 전체 코드

**예시** (`kr/strategy.py:332-334`):
```python
except Exception as e:
    self.logger.error(f"매수 전략 실행 오류: {e}")
    return {'executed': False, 'orders': [], 'message': str(e)}
```

**문제점**:
- ⚠️ 모든 예외를 `Exception`으로 잡음
- ⚠️ **네트워크 오류**와 **로직 오류**를 구분 불가
- ⚠️ **재시도 가능한 오류**인지 판단 불가

**개선 방안**:
```python
except requests.exceptions.RequestException as e:
    # 네트워크 오류 - 재시도 가능
    self.logger.warning(f"네트워크 오류 (재시도 가능): {e}")
    return {'executed': False, 'orders': [], 'message': 'network_error', 'retryable': True}
except ValueError as e:
    # 데이터 파싱 오류 - 재시도 불가
    self.logger.error(f"데이터 오류: {e}")
    return {'executed': False, 'orders': [], 'message': str(e), 'retryable': False}
except Exception as e:
    # 예상치 못한 오류
    self.logger.critical(f"예상치 못한 오류: {e}", exc_info=True)
    return {'executed': False, 'orders': [], 'message': 'unexpected_error', 'retryable': False}
```

**심각도**: 🟢 MEDIUM-LOW
**수정 우선순위**: P3

---

### 10. **미국 주식 전일 종가 필드명 하드코딩**
**위치**: `config.py:38`

```python
possible_fields = ["clos", "last", "prvs_clpr", "stck_clpr", "base_pric"]
```

**문제점**:
- ⚠️ API 응답 구조 변경 시 **전일 종가 조회 실패**
- ⚠️ 실제 사용하는 코드에서 이 리스트를 **활용하지 않는** 곳도 있음

**확인 필요**:
- `us/api_client.py`에서 이 리스트를 사용하는지 검증
- 실제 API 응답 구조와 일치하는지 테스트

**심각도**: 🟢 LOW
**수정 우선순위**: P4

---

## ✅ POSITIVE FINDINGS (잘한 점)

### 1. **토큰 자동 갱신 로직 우수**
**위치**: `main.py:108-184`

- ✅ 30분마다 토큰 상태 확인
- ✅ 토큰 변경 감지 시 브로커 자동 재초기화
- ✅ 6시간마다 주기적 재초기화 (24시간 토큰 만료 대비)
- ✅ 상세한 로깅

### 2. **시장 개장/폐장 구분 명확**
**위치**: `main.py:50-66`, `main_24h_trading.py:33-73`

- ✅ 한국장/미국장 개장 시간 정확히 구분
- ✅ 주말 체크 로직 포함
- ✅ 폐장 중에는 불필요한 API 호출 방지

### 3. **트랜잭션 로그 체계적**
**위치**: `kr/strategy.py:316-324`, `406-416`

- ✅ CSV 파일로 모든 거래 기록
- ✅ 손절/익절 구분 명확
- ✅ 주문번호, 수량, 가격 등 상세 정보 저장

### 4. **손절 블랙리스트 관리**
**위치**: `kr/strategy.py:64-71`, `382-391`

- ✅ 손절 종목 50일간 재매수 금지
- ✅ StopLossTracker로 체계적 관리
- ✅ 감정적 재매수 방지

### 5. **섹터 필터 구조 지원**
**위치**: `kr/strategy.py:88-110`

- ✅ 신규 섹터 기반 구조와 레거시 flat 구조 모두 지원
- ✅ 하위 호환성 유지
- ✅ 유연한 설정 구조

---

## 📊 코드 품질 메트릭

| 항목 | 평가 | 점수 |
|------|------|------|
| **보안** | 🔴 CRITICAL | 2/10 |
| **24시간 로직** | 🟡 NEEDS FIX | 6/10 |
| **API 정합성** | 🟢 GOOD | 8/10 |
| **에러 핸들링** | 🟡 AVERAGE | 6/10 |
| **로깅** | 🟢 GOOD | 8/10 |
| **코드 구조** | 🟢 GOOD | 8/10 |
| **테스트 가능성** | 🟡 AVERAGE | 6/10 |
| **문서화** | 🟡 AVERAGE | 7/10 |

**전체 평가**: 🟡 **6.4/10 (개선 필요)**

---

## 🔧 즉시 수정 체크리스트

### P0 (즉시 수정 - 오늘 안에)
- [ ] **보안**: API 키를 `.env`로 이동 + 키 재발급
- [ ] **보안**: `.gitignore`에 `.env` 추가
- [ ] **로직**: 서머타임 자동 전환 로직 수정

### P1 (1주일 이내)
- [ ] **API**: 한국 주식 TR_ID 2025/2026 최신 명세 확인
- [ ] **로직**: 잔고 조회 페이징 한계 확대
- [ ] **에러**: 토큰 갱신 실패 시 재시도 로직 추가

### P2 (1개월 이내)
- [ ] **배치**: start_24h_trading.bat 오류 처리 강화
- [ ] **API**: Rate limiting 간격 조정 (0.1초 → 0.2초)
- [ ] **로그**: 로그 파일 로테이션 정책 개선

### P3 (여유 있을 때)
- [ ] **코드**: Exception 세분화 (네트워크 vs 로직 오류)
- [ ] **테스트**: 단위 테스트 추가
- [ ] **문서**: API 명세 버전 추적 문서 작성

---

## 💡 배치 파일 납품 전 최종 점검

### 배치 파일 개선 사항

현재 `start_24h_trading.bat`은 기본적으로 **잘 작성되어 있습니다**. 다음 개선 사항을 반영하면 완벽합니다:

#### 1. **오류 처리 강화** (상기 #6 참조)
#### 2. **로그 경로 명시**
```batch
echo.
echo 📝 로그 파일 위치:
echo   - %CD%\overseas_stock\trading_24h_%date:~0,4%%date:~5,2%%date:~8,2%.log
echo   - %CD%\transaction_logs\kr_trading_log_%date:~0,4%%date:~5,2%%date:~8,2%.csv
echo   - %CD%\transaction_logs\trading_log_%date:~0,4%%date:~5,2%%date:~8,2%.csv
```

#### 3. **실전투자 경고 강화**
```batch
echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  🚨🚨🚨  실전투자 모드 - 최종 확인  🚨🚨🚨        ║
echo ╚═══════════════════════════════════════════════════════╝
echo.
echo   ⚠️  실제 돈으로 거래가 실행됩니다
echo   ⚠️  손실 가능성이 있습니다
echo   ⚠️  24시간 자동으로 거래합니다
echo.
set /p final_confirm=정말로 시작하시겠습니까? "YES"를 입력하세요:
if /i "%final_confirm%" neq "YES" (
    echo 취소되었습니다.
    pause
    exit /b
)
```

#### 4. **시작 시각 기록**
```batch
echo.
echo ========================================
echo 시작 시각: %date% %time%
echo ========================================
```

---

## 📦 납품 전 최종 파일 리스트

### 필수 파일
```
PJT v4.7 1023 new/
├── start_24h_trading.bat         ← 메인 실행 파일 (개선 버전)
├── .env                            ← API 키 (고객에게 직접 입력 요청)
├── .env.example                    ← 설정 템플릿
├── README_24H.md                   ← 사용 설명서
├── config.py                       ← API 키 제거된 버전
├── main.py
├── overseas_stock/
│   └── main_24h_trading.py
├── kr/
│   ├── strategy.py
│   ├── api_client.py
│   └── config.py
└── us/
    ├── strategy.py
    ├── api_client.py
    └── config.py
```

### 추가 권장 파일
```
├── INSTALL.md                      ← 설치 가이드
├── TROUBLESHOOTING.md              ← 문제 해결 가이드
└── docs/
    └── CODE_REVIEW_REPORT_ADVERSARIAL.md  ← 본 리포트
```

---

## 🎯 결론

### 현재 상태
이 24시간 자동매매 시스템은 **기능적으로는 잘 작동**하며, 전반적인 코드 품질도 **양호**합니다.

### 치명적 결함
그러나 **보안 취약점(API 키 노출)**과 **서머타임 미대응**은 즉시 수정이 필요한 **CRITICAL 이슈**입니다.

### 납품 가능 여부
**조건부 납품 가능**:
1. ✅ **P0 이슈를 오늘 안에 수정**하면 납품 가능
2. ⚠️ 수정 없이 납품 시 **고객 계좌 보안 위험** + **3~11월 거래 기회 손실**

### 최종 권장사항
1. 본 리포트의 **P0 이슈 3개**를 즉시 수정
2. P1 이슈는 **1주일 이내** 패치로 제공
3. 배치 파일에 **상세한 오류 안내** 추가
4. 고객에게 **사용 설명서(README_24H.md)** 제공
5. **1개월 기술 지원** 약속

---

**리포트 작성**: Claude Code (Adversarial Senior Developer)
**최종 업데이트**: 2026-01-25
