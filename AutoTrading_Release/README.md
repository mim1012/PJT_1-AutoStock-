# 한국투자증권 자동매매 시스템 v4.7

한국투자증권 OpenAPI를 사용한 미국/한국 주식 자동매매 시스템입니다.

## 주요 기능

- **자동 시장 전환** ⭐NEW: 현재 시간 기준으로 활성 시장만 모니터링
  - 한국 장 시간 (09:00-15:30 KST) → 한국 시장만
  - 미국 장 시간 (09:30-16:00 ET) → 미국 시장만
  - 폐장 시간 → 대기 모드
- **듀얼 마켓 지원**: 미국 주식(NASDAQ, NYSE)과 한국 주식(KOSPI, KOSDAQ) 동시 거래
- **24시간 자동매매**: 시장 시간 자동 감지 및 스케줄링
- **토큰 자동 관리**: OAuth2 토큰 자동 발급/갱신 (24시간 제한 준수)
- **손절매 자동화**: 설정된 손실률 도달 시 자동 매도
- **모의투자 지원**: 실전 투자 전 안전한 테스트 가능

## 시스템 요구사항

- **OS**: Windows 10 이상
- **Python**: 3.8 이상 (3.11 권장)
- **인터넷**: 안정적인 인터넷 연결 필수
- **API 키**: 한국투자증권 OpenAPI 인증 정보 필요

## 설치 방법

### 1단계: Python 설치

[Python 공식 사이트](https://www.python.org/downloads/)에서 Python 3.11을 다운로드하여 설치합니다.

**중요**: 설치 시 "Add Python to PATH" 옵션을 반드시 체크하세요!

### 2단계: 패키지 설치

프로그램 폴더에서 명령 프롬프트(cmd)를 열고 다음 명령어를 실행하세요:

```bash
pip install -r requirements.txt
pip install mojito2
```

### 3단계: API 인증 정보 설정

#### 3-1. 한국투자증권 API 키 발급

1. [한국투자증권 API 포털](https://apiportal.koreainvestment.com) 접속
2. 회원가입 및 로그인
3. API 신청 → APP KEY, APP SECRET 발급
4. 계좌번호 확인

#### 3-2. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env` 파일 생성:

```bash
copy .env.example .env
```

`.env` 파일을 메모장으로 열고 다음 정보를 입력:

```env
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCOUNT_NUMBER=계좌번호
USE_PAPER_TRADING=True
```

**보안 주의**: `.env` 파일은 절대 다른 사람과 공유하지 마세요!

### 4단계: 종목 설정

#### 미국 주식 설정 (`us_stocks_config.json`)

```json
{
  "NVDA": {"exchange": "NASDAQ"},
  "AMZN": {"exchange": "NASDAQ"},
  "MSFT": {"exchange": "NASDAQ"}
}
```

#### 한국 주식 설정 (`kr_stocks_config.json`)

```json
{
  "005930": {"name": "삼성전자"},
  "000660": {"name": "SK하이닉스"}
}
```

## 실행 방법

### ⭐ 권장: 자동 시장 전환 모드 (NEW!)

```bash
start_auto.bat
```

**기능**:
- 현재 시간에 따라 활성 시장만 자동 모니터링
- 한국 장 시간 → 한국 시장만
- 미국 장 시간 → 미국 시장만
- CPU 효율적, 불필요한 API 호출 없음

### 방법 1: 미국 주식 단독 실행

```bash
start.bat
```

또는

```bash
python main.py
```

### 방법 2: 듀얼 마켓 (미국 + 한국 동시)

```bash
python main.py --market both
```

### 방법 3: 한국 주식 단독 실행

```bash
python main.py --market kr
```

## 주요 설정 (config.py)

```python
# 거래 모드
USE_PAPER_TRADING = True  # True: 모의투자, False: 실전투자

# 매매 스케줄
SELL_INTERVAL_MINUTES = 30  # 매도 체크 주기 (분)
BUY_INTERVAL_MINUTES = 60   # 매수 체크 주기 (분)

# 손절 설정
STOP_LOSS_THRESHOLD = -0.15  # 손절 기준 (-15%)
```

## 파일 구조

```
AutoTrading_Release/
├── common/                      # 공통 모듈
│   ├── base_token_manager.py   # 토큰 관리 (시간 버그 수정 완료)
│   ├── base_strategy.py        # 매매 전략 기반
│   └── base_api.py             # API 클라이언트 기반
├── us/                          # 미국 주식 모듈
│   ├── config.py               # 미국 시장 설정
│   ├── token_manager.py        # US 토큰 관리
│   └── strategy.py             # US 매매 전략
├── kr/                          # 한국 주식 모듈
│   ├── config.py               # 한국 시장 설정
│   ├── token_manager.py        # KR 토큰 관리
│   └── strategy.py             # KR 매매 전략
├── main.py                      # 메인 실행 (미국 단독)
├── dual_market_scheduler.py    # 듀얼 마켓 스케줄러
├── auto_market_scheduler.py    # ⭐ 자동 시장 전환 (권장)
├── config.py                    # 전역 설정
├── requirements.txt             # Python 패키지 목록
├── .env.example                 # 환경 변수 템플릿
├── start.bat                    # 미국 주식 실행
├── start_auto.bat               # ⭐ 자동 시장 전환 실행
├── us_stocks_config.json        # 미국 주식 종목 설정
└── kr_stocks_config.json        # 한국 주식 종목 설정
```

## 토큰 관리

### 토큰 파일 (자동 생성됨)

- `us_api_token.json` - 미국 주식 API 토큰
- `kr_api_token.json` - 한국 주식 API 토큰
- `us_krs_token.dat` - mojito2 US 토큰
- `kr_krs_token.dat` - mojito2 KR 토큰

### 24시간 제한

한국투자증권 API는 **하루에 1번만 토큰을 발급**할 수 있습니다. 토큰 파일을 삭제하거나 손상시키지 마세요!

### 토큰 문제 해결

토큰 오류 발생 시:

1. 프로그램 재시작 (자동으로 토큰 검증 및 갱신)
2. 24시간 이내 재발급 시도 시 다음날까지 대기
3. 토큰 파일이 손상되었을 경우에만 수동 삭제 후 재발급

## 로그 확인

모든 거래 내역과 오류는 `trading.log` 파일에 기록됩니다.

```bash
# 실시간 로그 확인 (PowerShell)
Get-Content trading.log -Wait -Tail 50
```

## 주의사항

### 1. 모의투자로 먼저 테스트
실전 투자 전에 반드시 `USE_PAPER_TRADING=True`로 설정하여 충분히 테스트하세요.

### 2. 24시간 제한
토큰 재발급은 하루에 1번만 가능합니다. 토큰 파일을 함부로 삭제하지 마세요.

### 3. 거래 시간
- 미국 시장: 23:30 ~ 06:00 (한국시간, 서머타임 고려)
- 한국 시장: 09:00 ~ 15:30 (한국시간)

### 4. 보안
- `.env` 파일은 절대 공유 금지
- API 키가 노출되면 즉시 재발급
- GitHub 등에 업로드 금지 (.gitignore 설정됨)

### 5. 책임
- 모든 투자 손실에 대한 책임은 사용자에게 있습니다
- 충분한 테스트 후 신중하게 사용하세요

## 문제 해결

### 토큰 발급 실패
- API 키 확인 (.env 파일)
- 24시간 제한 확인 (다음날 재시도)
- 인터넷 연결 확인

### 주문 실패
- 잔고 확인
- 거래 시간 확인
- 종목 코드 확인
- trading.log 파일 확인

### 프로그램 종료
- Python 버전 확인 (3.8 이상)
- 패키지 재설치: `pip install -r requirements.txt --force-reinstall`
- 로그 파일 확인

## 📚 상세 문서

| 문서 | 설명 |
|------|------|
| **[국장 매매 설정 가이드](국장_매매_설정_가이드.md)** ⭐NEW | 한국 주식 종목 설정, 손절, 매수/매도 조건 완벽 가이드 |
| **[운영 메뉴얼](운영_메뉴얼.md)** | 전체 시스템 운영 가이드 (완전판) |
| **[빠른 시작 가이드](빠른_시작_가이드.md)** | 5분 안에 시작하기 |
| **[설정 빠른 참조](설정_빠른_참조.md)** | 주요 설정 한눈에 보기 |
| **[배포 체크리스트](배포_체크리스트.md)** | 배포 담당자용 TODO 리스트 |

### 📍 중요 설정 위치

| 설정 항목 | 파일 | 줄 번호 |
|----------|------|---------|
| 목표 수익률 | `config.py` | 33 |
| 한국 손절률 | `kr/config.py` | 78 |
| 미국 손절률 | `us/config.py` | 90 |
| 한국 재매수 금지 | `kr/config.py` | 79 |
| 미국 재매수 금지 | `us/config.py` | 91 |
| 한국 종목 | `kr_stocks_config.json` | - |
| 미국 종목 | `us_stocks_config.json` | - |

자세한 내용은 **[설정 빠른 참조](설정_빠른_참조.md)** 참조

## 🆕 v4.7 업데이트 (2026-01-27)

- ✅ **로그 메시지 명확화**: 조건 검사 vs 실제 주문 구분
- ✅ **계좌번호 검증 강화**: 하이픈 형식 체크
- ✅ **잔고 조회 오류 수정**: not enough values to unpack 해결
- ✅ **완전한 문서화**: 운영 메뉴얼, 빠른 참조 가이드 추가
- ✅ **배포 자동화**: 체크리스트 및 가이드 완성

## 기술 지원

**문서 확인**:
1. [국장 매매 설정 가이드](국장_매매_설정_가이드.md) ⭐ - 한국 주식 설정 완벽 가이드
2. [운영 메뉴얼](운영_메뉴얼.md) - 전체 가이드
3. [빠른 시작 가이드](빠른_시작_가이드.md) - 초보자용
4. [설정 빠른 참조](설정_빠른_참조.md) - 설정 변경

**긴급 문제**:
- GitHub Issues
- 로그 파일 확인: `trading.log`

---

**버전**: v4.7
**최종 업데이트**: 2026-01-27
**개발**: Claude Code with AI Agent
**상태**: Production Ready ✅
