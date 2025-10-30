# 한국투자증권 미국주식 자동매매 시스템 v2.0

## 📋 목차
- [프로젝트 개요](#프로젝트-개요)
- [주요 기능](#주요-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [설치 가이드](#설치-가이드)
- [설정 방법](#설정-방법)
- [실행 방법](#실행-방법)
- [매매 전략](#매매-전략)
- [API 문서](#api-문서)
- [문제 해결](#문제-해결)
- [주의사항](#주의사항)

## 프로젝트 개요

한국투자증권 OpenAPI를 활용한 미국 주식(나스닥) 자동매매 시스템입니다. 필터 기반 매수/매도 전략을 구현하여 24시간 자동으로 거래를 수행합니다.

### 핵심 특징
- 🤖 **완전 자동화**: 스케줄 기반 자동 매매
- 📊 **필터 전략**: 다중 종목 모니터링 및 조건부 매매
- 📝 **거래 기록**: 모든 거래를 CSV로 자동 기록
- 🔒 **안전 모드**: 모의투자/실전투자 모드 전환 가능
- ⏰ **시장 시간 준수**: 미국 주식시장 운영시간 자동 체크

## 주요 기능

### 1. 자동 매매
- 설정된 주기에 따라 자동으로 매수/매도 실행
- 미국 동부시간 기준 09:30 ~ 16:00 운영
- 주말 및 휴장일 자동 감지

### 2. 포트폴리오 관리
- 실시간 잔고 조회
- 보유 종목 수익률 모니터링
- 자동 포지션 사이징

### 3. 리스크 관리
- 수익 목표 달성 시 자동 매도 (기본 5%)
- 분산 투자 (최대 3종목 동시 매수)
- 주문 타임아웃 관리 (20분)

### 4. 로깅 및 모니터링
- 실시간 거래 로그
- CSV 형식 거래 기록
- 5분 단위 상태 리포트

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│                  main.py                        │
│            (스케줄러 및 메인 로직)                │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┴────────────┬─────────────┐
        ▼                         ▼             ▼
┌──────────────┐        ┌──────────────┐  ┌──────────────┐
│strategy_pjt1 │        │order_manager │  │transaction   │
│   (전략)     │        │  (주문관리)   │  │  logger      │
└──────┬───────┘        └──────────────┘  └──────────────┘
       │
       ▼
┌──────────────┐        ┌──────────────┐
│   kis_api    │◄───────│token_manager │
│ (API 연동)   │        │ (토큰 관리)   │
└──────────────┘        └──────────────┘
```

### 주요 모듈 설명

| 모듈 | 파일명 | 역할 |
|------|--------|------|
| 메인 스케줄러 | `main.py` | 전체 시스템 제어 및 스케줄 관리 |
| API 클라이언트 | `kis_api.py` | 한국투자증권 API 통신 (mojito2) |
| 매매 전략 | `strategy_pjt1.py` | PJT #1 필터 기반 매매 전략 |
| 주문 관리 | `order_manager.py` | 주문 생성, 추적, 정리 |
| 거래 기록 | `transaction_logger.py` | CSV 거래 로그 생성 |
| 토큰 관리 | `token_manager.py` | API 인증 토큰 관리 |
| 설정 | `config.py` | 시스템 설정 및 파라미터 |

## 설치 가이드

### 시스템 요구사항
- Python 3.8 이상
- Windows/Linux/macOS
- 인터넷 연결 (API 통신)

### 1. 저장소 클론
```bash
git clone [repository-url]
cd "PJT v2.0"
```

### 2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 필수 패키지
- `mojito2==0.1.6` - 한국투자증권 API 라이브러리
- `requests==2.31.0` - HTTP 통신
- `pytz==2023.3` - 시간대 처리
- `pandas==2.0.3` - 데이터 처리
- `schedule==1.2.2` - 작업 스케줄링
- `python-dotenv==1.0.0` - 환경변수 관리

## 설정 방법

### 1. API 키 발급
1. [한국투자증권](https://securities.koreainvestment.com) 접속
2. OpenAPI 서비스 신청
3. APP KEY와 APP SECRET 발급

### 2. 환경 설정 (.env 파일 생성)
```bash
# .env 파일 생성 (권장)
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NUMBER=12345678-01
```

### 3. config.py 수정
```python
# 거래 모드 설정
USE_PAPER_TRADING = True  # True: 모의투자, False: 실전투자

# 매매 주기 설정 (분)
SELL_INTERVAL_MINUTES = 30  # 매도 체크 주기
BUY_INTERVAL_MINUTES = 60   # 매수 체크 주기

# 수익률 임계값
PROFIT_THRESHOLD = 0.05  # 5% 수익 시 매도
```

### 4. 종목 설정 (stocks_config.json)
```json
{
  "filter_stocks": {
    "AAPL": true,
    "MSFT": true,
    "GOOGL": true
  },
  "watch_list": [
    "NVDA", "TSLA", "META", "AMZN", "AMD"
  ]
}
```

- **filter_stocks**: 모든 종목이 상승해야 매수 신호 발생
- **watch_list**: 매수 대상 종목 풀 (하락률 상위 3종목 선정)

## 실행 방법

### 1. 기본 실행
```bash
python main.py
```

### 2. 백그라운드 실행 (Linux/macOS)
```bash
nohup python main.py > output.log 2>&1 &
```

### 3. 테스트 실행
```bash
# API 연결 테스트
python test_api_connection_fixed.py

# 잔고 조회 테스트
python simple_balance_check.py

# 전략 시뮬레이션
python strategy_test_simulator.py
```

## 매매 전략

### PJT #1 전략 상세

#### 매수 조건 (AND 조건)
1. **필터 통과**: filter_stocks의 모든 종목이 전일 대비 상승
2. **타겟 선정**: watch_list 중 하락률 상위 3종목
3. **자금 관리**: 가용 현금을 3등분하여 분산 매수

#### 매도 조건 (OR 조건)
1. **수익 실현**: 보유 종목이 5% 이상 수익 달성
2. **시간 기반**: 30분마다 수익률 체크

#### 실행 주기
- **매수 전략**: 60분마다 실행
- **매도 전략**: 30분마다 실행
- **주문 정리**: 10분마다 미체결 주문 확인
- **상태 출력**: 5분마다 시스템 상태 로깅

## API 문서

### KISAPIClient 주요 메서드

#### 잔고 조회
```python
balance = api_client.get_account_balance()
# 반환값: {
#   "cash": 10000.0,
#   "positions": [...],
#   "total_positions": 3
# }
```

#### 현재가 조회
```python
price = api_client.get_current_price("AAPL")
# 반환값: 150.25
```

#### 매수 주문
```python
result = api_client.place_buy_order(
    symbol="AAPL",
    quantity=10,
    price=150.00,
    order_type="limit"
)
```

#### 매도 주문
```python
result = api_client.place_sell_order(
    symbol="AAPL",
    quantity=10,
    price=155.00,
    order_type="limit"
)
```

## 문제 해결

### 자주 발생하는 오류

#### 1. API 인증 오류 (403 Forbidden)
```
원인: 토큰 만료 또는 잘못된 API 키
해결: 
- config.py의 API 키 확인
- token.dat 파일 삭제 후 재실행
```

#### 2. ModuleNotFoundError: mojito2
```
원인: mojito2 패키지 미설치
해결: pip install mojito2
```

#### 3. 주문 실패
```
원인: 잔고 부족 또는 시장 마감
해결:
- 계좌 잔고 확인
- 미국 시장 운영시간 확인 (09:30-16:00 ET)
```

#### 4. CSV 파일 오류
```
원인: 파일 권한 또는 경로 문제
해결:
- transaction_logs 폴더 생성 확인
- 파일 쓰기 권한 확인
```

### 로그 확인
```bash
# 실시간 로그 확인
tail -f trading.log

# 오늘 거래 기록 확인
cat transaction_logs/trading_log_$(date +%Y%m%d).csv
```

## 주의사항

### ⚠️ 보안 주의사항
1. **API 키 보호**
   - config.py를 절대 공개 저장소에 업로드하지 마세요
   - .env 파일 사용을 권장합니다
   - .gitignore에 민감한 파일 추가 필수

2. **계좌 정보 보호**
   - 계좌번호와 비밀번호를 코드에 하드코딩하지 마세요
   - 환경변수 또는 별도 설정 파일 사용

### ⚠️ 거래 주의사항
1. **실전 거래 전 충분한 테스트**
   - 모의투자 모드에서 최소 1주일 이상 테스트
   - 모든 시나리오 검증 완료 후 실전 전환

2. **자금 관리**
   - 초기에는 소액으로 시작
   - 손실 한도 설정 권장

3. **모니터링**
   - 자동매매 중에도 주기적인 모니터링 필요
   - 비정상 거래 발생 시 즉시 중단

### ⚠️ 법적 책임
- 이 시스템 사용으로 인한 모든 거래 손실은 사용자 본인의 책임입니다
- 투자 결정은 본인의 판단 하에 신중히 하시기 바랍니다

## 라이선스

이 프로젝트는 개인 사용 목적으로 제작되었습니다. 상업적 사용 시 별도 문의 바랍니다.

## 기여 방법

버그 리포트, 기능 제안, 풀 리퀘스트는 언제나 환영합니다.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 연락처

프로젝트 관련 문의사항은 이슈 트래커를 이용해 주세요.

---

**마지막 업데이트**: 2025년 1월
**버전**: 2.0.0