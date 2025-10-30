# 토큰 재발급 문제 해결 가이드

## 🔴 문제 상황

**증상:**
- 첫 실행 시에는 현재가 조회/매수/매도가 정상 작동
- 5시간 경과 후 토큰 재발급 시점부터 API 호출이 모두 실패
- 24시간 동안 테스트할 수 없어 재현이 어려움

**원인:**
토큰 재발급 과정에서 `mojito2` 라이브러리의 내부 토큰과 `TokenManager`의 토큰이 동기화되지 않는 문제

## 🔍 근본 원인 분석

### 1. 이중 토큰 관리 시스템 충돌

```python
# kis_api.py - mojito2 자체 토큰 관리
self.nasdaq_broker = mojito.KoreaInvestment(
    api_key=KIS_APP_KEY,
    api_secret=KIS_APP_SECRET,
    acc_no=acc_no,
    exchange="나스닥",
    mock=USE_PAPER_TRADING
)
# ↑ mojito2가 내부적으로 토큰 생성 및 관리

# kis_api.py - 별도 TokenManager
self.token_manager = TokenManager()
# ↑ 별도로 토큰을 관리하지만 mojito2와 동기화 안됨
```

### 2. 문제 발생 시나리오

```
시간 0시간 → mojito2가 자체 토큰 발급 → 정상 작동 ✓
     ↓
시간 5시간 → TokenManager가 "5시간 이하" 감지
     ↓
     → TokenManager만 토큰 재발급 (api_token.json 업데이트)
     ↓
     → mojito2는 구 토큰 유지 (내부 캐시)
     ↓
시간 5시간+ → API 호출 시도
     ↓
     → mojito2가 만료된 토큰으로 요청
     ↓
     → 403/401 에러 발생 ✗
```

## ✅ 해결 방안

### 1. `kis_api.py`에 브로커 재초기화 메서드 추가

```python
def reinitialize_brokers(self):
    """
    브로커를 재초기화하여 새 토큰 적용
    토큰 재발급 후 호출해야 함
    """
    self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 시작...")

    try:
        # 기존 브로커 정리
        if hasattr(self, 'nasdaq_broker'):
            del self.nasdaq_broker
        if hasattr(self, 'nyse_broker'):
            del self.nyse_broker
        if hasattr(self, 'broker'):
            del self.broker

        # 브로커 재생성
        self._init_mojito_client()

        self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 완료")
        return True

    except Exception as e:
        self.logger.error(f"[TOKEN_REFRESH] 브로커 재초기화 실패: {e}")
        return False
```

### 2. `main.py`에 토큰 체크 및 재초기화 로직 추가

```python
def check_and_refresh_token(self):
    """
    토큰 상태 확인 및 필요시 재발급
    재발급 시 KISAPIClient의 브로커도 재초기화
    """
    try:
        # TokenManager를 통해 토큰 상태 확인
        if not hasattr(self.strategy.api, 'token_manager') or self.strategy.api.token_manager is None:
            return

        token_manager = self.strategy.api.token_manager

        # 현재 토큰 유효성 확인
        current_token = token_manager.load_token()

        if current_token is None:
            self.logger.warning("[TOKEN_CHECK] 토큰이 만료되었거나 없음 - 재발급 시도")

            # 새 토큰 발급 시도
            new_token = token_manager.get_valid_token(force_refresh=True)

            if new_token:
                self.logger.info("[TOKEN_CHECK] 새 토큰 발급 성공 - 브로커 재초기화")

                # KISAPIClient의 브로커 재초기화
                if hasattr(self.strategy.api, 'reinitialize_brokers'):
                    if self.strategy.api.reinitialize_brokers():
                        self.logger.info("[TOKEN_CHECK] 브로커 재초기화 성공")
                    else:
                        self.logger.error("[TOKEN_CHECK] 브로커 재초기화 실패")
                else:
                    self.logger.warning("[TOKEN_CHECK] reinitialize_brokers 메서드 없음")
            else:
                self.logger.error("[TOKEN_CHECK] 토큰 재발급 실패 (24시간 제한 가능)")

    except Exception as e:
        self.logger.error(f"토큰 체크 오류: {e}")
```

### 3. 스케줄에 토큰 체크 작업 추가

```python
def setup_schedule(self):
    """스케줄 설정"""
    # 매도 전략 (30분 주기)
    schedule.every(SELL_INTERVAL_MINUTES).minutes.do(self.execute_sell_strategy)

    # 매수 전략 (1시간 주기)
    schedule.every(BUY_INTERVAL_MINUTES).minutes.do(self.execute_buy_strategy)

    # 주문 정리 (10분 주기)
    schedule.every(10).minutes.do(self.cleanup_orders)

    # 상태 출력 (5분 주기)
    schedule.every(5).minutes.do(self.print_status)

    # 토큰 상태 체크 (30분 주기) - 만료 감지 및 브로커 재초기화
    schedule.every(30).minutes.do(self.check_and_refresh_token)
```

### 4. 시작 시 토큰 체크 추가

```python
def start(self):
    """스케줄러 시작"""
    self.logger.info("=== 자동매매 시스템 시작 ===")

    # 시작 시 토큰 상태 확인 및 필요시 재발급
    self.logger.info("시작 전 토큰 상태 확인 중...")
    self.check_and_refresh_token()

    # ... (기존 코드)
```

## 🧪 테스트 방법

### 방법 1: 토큰 재발급 테스트 스크립트 실행

```bash
python test_token_refresh.py
```

**테스트 시나리오:**
1. 현재 토큰 상태 확인
2. 토큰 강제 만료 (5시간 이상 이전으로 설정)
3. API 클라이언트 초기화 (만료된 토큰)
4. 현재가 조회 시도 (실패 예상)
5. 토큰 재발급
6. 브로커 재초기화
7. 현재가 재조회 (성공 예상)
8. 결과 요약

### 방법 2: 실제 운영 시나리오 테스트

```bash
# 1. 토큰을 강제로 5시간 이전으로 설정
python -c "import json, time; data=json.load(open('api_token.json')); data['expires_at']=time.time()-19000; json.dump(data, open('api_token.json','w'), indent=2)"

# 2. main.py 실행
python main.py

# 3. 로그 확인 (trading.log)
# - "[TOKEN_CHECK] 토큰이 만료되었거나 없음" 로그 확인
# - "[TOKEN_CHECK] 새 토큰 발급 성공" 로그 확인
# - "[TOKEN_REFRESH] 브로커 재초기화 완료" 로그 확인
```

## 📊 기대 효과

### Before (수정 전)
```
시간 0h   → 정상 작동 ✓
시간 5h   → 토큰 재발급 시도 (TokenManager만)
시간 5h+  → API 호출 실패 ✗ (mojito2가 구 토큰 사용)
시간 24h  → 시스템 재시작 필요
```

### After (수정 후)
```
시간 0h   → 정상 작동 ✓
시간 5h   → 토큰 재발급 + 브로커 재초기화
시간 5h+  → 정상 작동 ✓ (새 토큰 적용)
시간 24h+ → 계속 정상 작동 ✓
```

## 🔧 추가 개선 사항

### 1. 토큰 갱신 타이밍 최적화

현재: 5시간 이하 남으면 재발급
개선: 3-4시간 남았을 때 미리 재발급 (여유 확보)

```python
# token_manager.py line 164
if remaining <= 14400:  # 4시간 = 4 * 3600
    self.logger.warning(f"[WARNING] 토큰 남은시간 4시간 이하 - 재발급 필요")
    return None
```

### 2. 재발급 실패 시 재시도 로직

```python
def check_and_refresh_token(self):
    max_retries = 3
    retry_delay = 60  # 1분

    for attempt in range(max_retries):
        try:
            # ... (기존 코드)
            if new_token:
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                self.logger.warning(f"재발급 실패 ({attempt+1}/{max_retries}), {retry_delay}초 후 재시도")
                time.sleep(retry_delay)
            else:
                self.logger.error("최대 재시도 횟수 초과")
                return False
```

### 3. 토큰 만료 알림

```python
def check_token_expiry_warning(self):
    """토큰 만료 2시간 전 경고"""
    if remaining <= 7200 and remaining > 7100:  # 2시간 전후
        self.logger.warning(f"⚠️ 토큰 만료 2시간 전! (남은시간: {remaining//3600}시간)")
        # 알림 전송 (이메일/슬랙 등)
```

## 📝 요약

**변경된 파일:**
1. `kis_api.py` - `reinitialize_brokers()` 메서드 추가
2. `main.py` - `check_and_refresh_token()` 메서드 및 스케줄 추가
3. `test_token_refresh.py` - 테스트 스크립트 생성 (신규)

**핵심 해결책:**
- 토큰 재발급 감지 시 mojito2 브로커를 재초기화하여 새 토큰 적용
- 30분마다 토큰 상태를 자동 체크
- 시스템 시작 시에도 토큰 상태 확인

**장점:**
- 24시간 연속 운영 가능 (재시작 불필요)
- 토큰 만료로 인한 거래 중단 방지
- 자동 복구 기능으로 안정성 향상
