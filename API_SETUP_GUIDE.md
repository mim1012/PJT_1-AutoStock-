# 해외주식 API 설정 가이드

## 📋 목차
1. [API 키 발급](#api-키-발급)
2. [설정 파일 수정](#설정-파일-수정)
3. [테스트 실행](#테스트-실행)
4. [주의사항](#주의사항)

## 🔑 API 키 발급

### 1. 한국투자증권 Open Trading API 신청
1. [한국투자증권 Open Trading API](https://securities.koreainvestment.com/main/index.jsp) 접속
2. 로그인 후 "API 서비스 신청" 클릭
3. 해외주식 API 서비스 신청
4. 실전투자와 모의투자 앱키 모두 발급 권장

### 2. 필요한 정보
- **실전투자 앱키**: 실제 거래용
- **실전투자 앱시크릿**: 실제 거래용
- **모의투자 앱키**: 테스트용
- **모의투자 앱시크릿**: 테스트용
- **HTS ID**: 계좌번호 앞 8자리
- **계좌번호**: 종합계좌번호 (8자리-2자리)

## ⚙️ 설정 파일 수정

### 1. 설정 파일 위치
```
overseas_stock/kis_devlp.yaml
```

### 2. 설정 파일 내용 수정
```yaml
#홈페이지에서 API서비스 신청시 받은 Appkey, Appsecret 값 설정
#실전투자
my_app: "실제_앱키_입력"
my_sec: "실제_앱시크릿_입력"

#모의투자
paper_app: "모의투자_앱키_입력"
paper_sec: "모의투자_앱시크릿_입력"

# HTS ID
my_htsid: "사용자_HTS_ID"

#계좌번호 앞 8자리
my_acct_stock: "증권계좌_8자리"
my_acct_future: "선물옵션계좌_8자리"
my_paper_stock: "모의투자_증권계좌_8자리"
my_paper_future: "모의투자_선물옵션계좌_8자리"

#계좌번호 뒤 2자리
my_prod: "01" # 종합계좌

#domain infos
prod: "https://openapi.koreainvestment.com:9443" # 서비스
ops: "ws://ops.koreainvestment.com:21000" # 웹소켓
vps: "https://openapivts.koreainvestment.com:29443" # 모의투자 서비스
vops: "ws://ops.koreainvestment.com:31000" # 모의투자 웹소켓

my_token: ""

# User-Agent
my_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
```

### 3. 설정 예시
```yaml
#실전투자
my_app: "PS2023123456789012345678901234567890"
my_sec: "abcdefghijklmnopqrstuvwxyz1234567890"

#모의투자
paper_app: "PS2023123456789012345678901234567890"
paper_sec: "abcdefghijklmnopqrstuvwxyz1234567890"

# HTS ID
my_htsid: "12345678"

#계좌번호 앞 8자리
my_acct_stock: "12345678"
my_paper_stock: "12345678"

#계좌번호 뒤 2자리
my_prod: "01"
```

## 🧪 테스트 실행

### 1. 기본 기능 테스트 (API 키 불필요)
```bash
python test_basic_functions.py
```

### 2. 시뮬레이션 테스트 (API 키 필요)
```bash
python test_orders_simulation.py
```
또는
```bash
test_orders_simulation.bat
```

### 3. 실제 주문 테스트 (API 키 필요, 실제 거래 발생)
```bash
python test_buy_sell_orders.py
```
또는
```bash
test_orders_real.bat
```

## ⚠️ 주의사항

### 1. 보안
- **절대 API 키를 공개하지 마세요**
- **Git에 API 키를 커밋하지 마세요**
- **설정 파일을 안전한 곳에 보관하세요**

### 2. 거래 주의사항
- **실제 주문 테스트는 실제 돈이 사용됩니다**
- **시장 개장 시간에만 거래가 가능합니다**
- **소액으로 테스트 후 본격 거래를 시작하세요**

### 3. 시장 시간
- **미국 동부시간 기준**: 09:30 - 16:00 (평일)
- **한국시간 기준**: 22:30 - 05:00 (다음날, 평일)
- **주말 및 공휴일**: 거래 불가

### 4. 테스트 순서
1. ✅ 기본 기능 테스트
2. 🔧 API 키 설정
3. 🎯 시뮬레이션 테스트
4. 🚀 실제 주문 테스트 (신중하게)

## 🔧 문제 해결

### 1. 인증 실패
- API 키가 올바르게 설정되었는지 확인
- 계좌번호가 정확한지 확인
- API 서비스 신청이 승인되었는지 확인

### 2. 주문 실패
- 시장이 개장 중인지 확인
- 잔고가 충분한지 확인
- 주문 수량과 가격이 올바른지 확인

### 3. 연결 오류
- 인터넷 연결 상태 확인
- 방화벽 설정 확인
- API 서버 상태 확인

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 로그 파일 확인 (`test_orders.log`, `simulation_test.log`)
2. 한국투자증권 API 문서 참조
3. 개발자 커뮤니티 문의

---

**⚠️ 중요**: 이 가이드는 교육 목적으로 작성되었습니다. 실제 거래는 신중하게 진행하시기 바랍니다.
