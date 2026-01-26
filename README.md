# 한국투자증권 자동매매 시스템 v4.7

## 개요

US/KR 듀얼 마켓 자동매매 시스템 - 24시간 무인 운영

## 주요 기능

- ✅ US/KR 토큰 분리 관리
- ✅ 자동 토큰 갱신 (24시간 제한 준수)
- ✅ 섹터 기반 필터 전략
- ✅ 듀얼 마켓 스케줄러

## 환경 설정

### 1. 환경 변수 설정 (프로덕션 권장)

```bash
# Linux/Mac
export KIS_APP_KEY="your_app_key_here"
export KIS_APP_SECRET="your_app_secret_here"
export KIS_ACCOUNT_NUMBER="12345678-01"
export USE_PAPER_TRADING="true"  # false for real trading

# Windows PowerShell
$env:KIS_APP_KEY="your_app_key_here"
$env:KIS_APP_SECRET="your_app_secret_here"
$env:KIS_ACCOUNT_NUMBER="12345678-01"
$env:USE_PAPER_TRADING="true"
```

### 2. config.py 설정 (개발 전용)

환경 변수가 없으면 자동으로 `config.py`에서 로드합니다.

**⚠️ 보안 경고**: `config.py`는 절대 git에 커밋하지 마세요!

## 토큰 관리

### 토큰 파일

시스템은 US/KR 토큰을 분리하여 관리합니다:

**US 토큰:**
- `us_api_token.json` - 액세스 토큰
- `us_token_issued_at.dat` - 발급 시각
- `us_krs_token.dat` - Mojito2 라이브러리 토큰

**KR 토큰:**
- `kr_api_token.json` - 액세스 토큰
- `kr_token_issued_at.dat` - 발급 시각
- `kr_krs_token.dat` - Mojito2 라이브러리 토큰

### CLI 명령어

#### US 토큰 관리
```bash
# 토큰 상태 확인
python -m us.token_manager check

# 토큰 삭제
python -m us.token_manager delete

# 토큰 강제 재발급
python -m us.token_manager refresh

# 유효한 토큰 획득
python -m us.token_manager get
```

#### KR 토큰 관리
```bash
# 토큰 상태 확인
python -m kr.token_manager check

# 토큰 삭제
python -m kr.token_manager delete

# 유효한 토큰 획득
python -m kr.token_manager get
```

## 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 토큰 초기 발급
python -m us.token_manager get
python -m kr.token_manager get
```

## 실행

```bash
# 듀얼 마켓 스케줄러 시작
python dual_market_scheduler.py
```

## 테스트

```bash
# 토큰 분리 테스트
python -m pytest tests/test_dual_token.py

# 토큰 갱신 테스트
python test_token_refresh.py

# 통합 테스트
python -m pytest tests/test_integration.py
```

## 보안 주의사항

1. **환경 변수 사용**: 프로덕션에서는 반드시 환경 변수 사용
2. **토큰 파일 보호**: `.gitignore`에 포함됨 (커밋 금지)
3. **파일 권한**: 토큰 파일은 600 권한 설정 권장
   ```bash
   chmod 600 *_api_token.json *_token_issued_at.dat *_krs_token.dat
   ```

## 문제 해결

### 토큰 갱신 실패

**증상**: "24시간 제한" 오류
**원인**: API는 24시간당 1회만 토큰 발급 허용
**해결**: 기존 토큰이 완전히 만료될 때까지 대기

### 환경 변수 인식 안 됨

**증상**: `ValueError: Missing required credentials`
**해결**:
1. 환경 변수 설정 확인: `echo $KIS_APP_KEY`
2. 또는 `config.py` 생성

### 동시 토큰 갱신 충돌

**증상**: 여러 프로세스 실행 시 토큰 파일 손상
**해결**: 단일 프로세스만 실행 또는 file locking 구현

## 아키텍처

```
common/
  base_token_manager.py  # 토큰 관리 베이스 클래스
us/
  config.py             # US 설정
  token_manager.py      # US 토큰 매니저
  api_client.py         # US API 클라이언트
kr/
  config.py             # KR 설정
  token_manager.py      # KR 토큰 매니저
  api_client.py         # KR API 클라이언트
tests/
  test_dual_token.py    # 토큰 분리 테스트
  test_integration.py   # 통합 테스트
```

## 라이센스

MIT License

## 기여

Pull Request 환영합니다!

## 지원

이슈: https://github.com/mim1012/PJT_1-AutoStock-/issues
