# 한국 주식 API 분석 - Excel 스펙 vs 구현 현황

**분석 일자**: 2026-01-22
**참고 문서**: `[국내주식] 주문_계좌.xlsx`
**구현 파일**: `kr/api_client.py`

---

## ✅ 구현 완료된 API (3개)

### 1. 주식주문(현금) - Stock Order (Cash)
**API ID**: v1_국내주식-001
**실전 TR_ID**: `TTTC0011U` (매도), `TTTC0012U` (매수)
**모의 TR_ID**: `VTTC0011U` (매도), `VTTC0012U` (매수)
**URL**: `/uapi/domestic-stock/v1/trading/order-cash`
**Method**: POST
**구현 위치**: `kr/api_client.py:256-337` (`place_order()`)

#### Request Body 파라미터
| 파라미터 | 설명 | 타입 | 필수 | 비고 |
|---------|------|------|------|------|
| CANO | 종합계좌번호 | string | Y | 8자리 |
| ACNT_PRDT_CD | 계좌상품코드 | string | Y | 2자리 |
| PDNO | 상품번호(종목코드) | string | Y | 6자리 |
| ORD_DVSN | 주문구분 | string | Y | 00=지정가, 01=시장가 |
| ORD_QTY | 주문수량 | string | Y | - |
| ORD_UNPR | 주문단가 | string | Y | 시장가 시 "0" |
| SLL_TYPE | 매도유형 | string | N | 01=일반매도 (매도 시만) |
| EXCG_ID_DVSN_CD | 거래소ID구분코드 | string | N | KRX/NXT/SOR (미입력 시 KRX) |

#### 구현 상태
- ✅ 기본 매수/매도 구현 완료
- ✅ 지정가/시장가 지원
- ✅ 호가 단위 조정 (`KRConfig.round_to_tick()`)
- ✅ 2024년 신규 TR_ID 적용 (TTTC0012U/0011U)
- ⚠️ `SLL_TYPE`, `EXCG_ID_DVSN_CD` 파라미터 미구현 (선택사항)

---

### 2. 주식잔고조회 - Stock Balance Query
**API ID**: v1_국내주식-006
**실전 TR_ID**: `TTTC8434R`
**모의 TR_ID**: `VTTC8434R`
**URL**: `/uapi/domestic-stock/v1/trading/inquire-balance`
**Method**: GET
**구현 위치**: `kr/api_client.py:53-165` (`get_account_balance()`)

#### Request Query Parameters
| 파라미터 | 설명 | 타입 | 필수 | 값 |
|---------|------|------|------|-----|
| CANO | 종합계좌번호 | string | Y | 8자리 |
| ACNT_PRDT_CD | 계좌상품코드 | string | Y | 2자리 |
| AFHR_FLPR_YN | 시간외단일가여부 | string | Y | N=기본값, Y=시간외, X=NXT |
| OFL_YN | 오프라인여부 | string | N | 공란 |
| INQR_DVSN | 조회구분 | string | Y | 01=대출일별, 02=종목별 |
| UNPR_DVSN | 단가구분 | string | Y | 01=기본값 |
| FUND_STTL_ICLD_YN | 펀드결제분포함여부 | string | Y | N/Y |
| FNCG_AMT_AUTO_RDPT_YN | 융자금액자동상환여부 | string | Y | N=기본값 |
| PRCS_DVSN | 처리구분 | string | Y | 00=전일매매포함, 01=전일매매미포함 |
| CTX_AREA_FK100 | 연속조회검색조건100 | string | N | 페이징용 |
| CTX_AREA_NK100 | 연속조회키100 | string | N | 페이징용 |

#### Response Output Fields (output1 - 보유종목)
| 필드명 | 설명 | 사용중 |
|-------|------|--------|
| pdno | 종목코드 | ✅ |
| prdt_name | 종목명 | ✅ |
| hldg_qty | 보유수량 | ✅ |
| ord_psbl_qty | 주문가능수량(매도가능) | ✅ |
| prpr | 현재가 | ✅ (prpr 필드) |
| pchs_avg_pric | 매입평균가 | ✅ |
| evlu_amt | 평가금액 | ✅ |
| evlu_pfls_amt | 평가손익금액 | ✅ |
| evlu_pfls_rt | 평가손익율 | ✅ |

#### Response Output Fields (output2 - 계좌총합)
| 필드명 | 설명 | 사용중 |
|-------|------|--------|
| dnca_tot_amt | 예수금총금액 | ✅ (cash) |
| tot_evlu_amt | 총평가금액 | ✅ |
| pchs_amt_smtl_amt | 매입금액합계 | ✅ |

#### 구현 상태
- ✅ 잔고 조회 완료
- ✅ 보유종목 파싱 완료
- ✅ 예수금, 평가금액, 손익 계산 완료
- ✅ 매도가능수량 (`ord_psbl_qty`) 처리
- ⚠️ 페이징 처리 미구현 (대부분의 경우 불필요)

---

### 3. 현재가 조회
**TR_ID**: `FHKST01010100`
**URL**: `/uapi/domestic-stock/v1/quotations/inquire-price`
**Method**: GET
**구현 위치**: `kr/api_client.py:167-212` (`get_current_price()`)

#### 구현 상태
- ✅ 종목별 현재가 조회
- ✅ 전일종가 조회 (`get_previous_close()`)
- ✅ 안전한 float 변환 (`_safe_float()`)

---

## ❌ 미구현된 API (4개 주요)

### 1. 주식주문(정정취소) - Order Modify/Cancel ⚠️ **우선순위 높음**
**API ID**: v1_국내주식-003
**실전 TR_ID**: `TTTC0013U`
**모의 TR_ID**: `VTTC0013U`
**URL**: `/uapi/domestic-stock/v1/trading/order-rvsecncl`
**Method**: POST

#### Request Body 파라미터
```python
{
    "CANO": "12345678",          # 계좌번호
    "ACNT_PRDT_CD": "01",        # 상품코드
    "KRX_FWDG_ORD_ORGNO": "",    # 원주문조직번호
    "ORGN_ODNO": "",             # 원주문번호 (필수)
    "ORD_DVSN": "00",            # 주문구분
    "RVSE_CNCL_DVSN_CD": "01",   # 정정취소구분 (01=정정, 02=취소)
    "ORD_QTY": "0",              # 정정수량 (취소 시 "0")
    "ORD_UNPR": "0",             # 정정가격 (취소 시 "0")
    "QTY_ALL_ORD_YN": "Y"        # 전량정정취소여부 (Y=전량취소)
}
```

#### 필요성
- ⚠️ **주문 취소 기능 없음!** (OrderManager가 `cancel_order()` 호출하지만 구현 없음)
- ⚠️ 타임아웃된 주문 처리 불가
- ⚠️ 가격 정정 불가

---

### 2. 주식정정취소가능주문조회 - Query Cancellable Orders
**API ID**: v1_국내주식-004
**실전 TR_ID**: `TTTC0084R`
**모의**: 미지원
**URL**: `/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl`
**Method**: GET

#### Query Parameters
```python
{
    "CANO": "12345678",
    "ACNT_PRDT_CD": "01",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": "",
    "INQR_DVSN_1": "0",    # 0=전체, 1=매도, 2=매수
    "INQR_DVSN_2": "0"     # 0=전체
}
```

#### Response Output Fields
- `ODNO`: 주문번호
- `pdno`: 종목코드
- `prdt_name`: 종목명
- `psbl_qty`: 정정취소가능수량
- `ord_qty`: 주문수량
- `ccld_qty`: 체결수량

#### 필요성
- ⚠️ 주문 취소 전 가능 수량 확인 필요
- ⚠️ 부분 체결 시 정정취소 가능 수량 확인

---

### 3. 주식일별주문체결조회 - Daily Order Filled Query
**API ID**: v1_국내주식-005
**실전 TR_ID**: `TTTC0081R` (3개월 이내), `CTSC9215R` (3개월 이전)
**모의 TR_ID**: `VTTC0081R`, `VTSC9215R`
**URL**: `/uapi/domestic-stock/v1/trading/inquire-daily-ccld`
**Method**: GET

#### Query Parameters
```python
{
    "CANO": "12345678",
    "ACNT_PRDT_CD": "01",
    "INQR_STRT_DT": "20260101",   # 조회시작일
    "INQR_END_DT": "20260122",    # 조회종료일
    "SLL_BUY_DVSN_CD": "00",      # 00=전체, 01=매도, 02=매수
    "INQR_DVSN": "00",            # 00=역순, 01=정순
    "PDNO": "",                   # 종목코드 (전체 시 공란)
    "CCLD_DVSN": "00",            # 00=전체, 01=체결, 02=미체결
    "ORD_GNO_BRNO": "",
    "ODNO": "",                   # 주문번호
    "INQR_DVSN_3": "00",
    "INQR_DVSN_1": "",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": ""
}
```

#### Response Output Fields
- `ord_dt`: 주문일자
- `ord_gno_brno`: 주문조직번호
- `odno`: 주문번호
- `orgn_odno`: 원주문번호
- `pdno`: 종목코드
- `ord_qty`: 주문수량
- `ord_unpr`: 주문단가
- `ord_tmd`: 주문시각
- `tot_ccld_qty`: 총체결수량
- `avg_prvs`: 평균가
- `ccld_amt`: 체결금액

#### 필요성
- 체결 내역 확인
- 주문 상태 추적 (미체결/부분체결/전량체결)
- `OrderManager.get_order_status()` 구현에 필요

---

### 4. 매수가능조회 - Buy Available Query
**API ID**: v1_국내주식-007
**실전 TR_ID**: `TTTC8908R`
**모의 TR_ID**: `VTTC8908R`
**URL**: `/uapi/domestic-stock/v1/trading/inquire-psbl-order`
**Method**: GET

#### Query Parameters
```python
{
    "CANO": "12345678",
    "ACNT_PRDT_CD": "01",
    "PDNO": "005930",        # 종목코드
    "ORD_UNPR": "70000",     # 주문단가
    "ORD_DVSN": "00",        # 주문구분 (00=지정가)
    "CMA_EVLU_AMT_ICLD_YN": "Y",
    "OVRS_ICLD_YN": "N"      # 해외포함여부
}
```

#### Response Output Fields
- `ord_psbl_cash`: 주문가능현금
- `ord_psbl_qty`: 주문가능수량
- `max_buy_amt`: 최대매수금액
- `ord_psbl_frcr_amt`: 주문가능외화금액

#### 필요성
- 매수 가능 수량 사전 확인
- 계좌 잔고 부족 방지

---

## 📊 API 구현 통계

| 카테고리 | 구현 | 미구현 | 구현률 |
|---------|------|--------|--------|
| 주문 API | 1 | 1 | 50% |
| 조회 API | 2 | 3 | 40% |
| 전체 | 3 | 4 | 43% |

---

## 🚨 Critical Issues (Codex Review와 연계)

### 1. OrderManager의 미구현 메서드
**위치**: `order_manager.py:61-88`

```python
# 호출되지만 구현 없음!
status = self.api_client.get_order_status(order_id)  # ❌
self.api_client.cancel_order(order_id, symbol)       # ❌
```

**해결 방법**:
1. `kr/api_client.py`에 다음 메서드 추가:
   - `get_order_status(order_id)` → `TTTC0081R` (주식일별주문체결조회) 사용
   - `cancel_order(order_id, symbol)` → `TTTC0013U` (주식주문정정취소) 사용

2. `주식정정취소가능주문조회` (`TTTC0084R`)로 취소 가능 수량 확인 후 취소

---

### 2. 매도가능수량 필드 불일치
**현재 구현**: `ord_psbl_qty` 사용 ✅
**Excel 스펙**: `ord_psbl_qty` (주문가능수량) = 매도가능수량
**상태**: ✅ **정확함**

---

### 3. 호가 단위 처리
**위치**: `kr/config.py` (`round_to_tick()`)
**상태**: ✅ 구현 완료

---

## 📝 구현 우선순위

### Priority 1 (High) - 실거래 필수
1. ⚠️ **주문 취소 API** (`TTTC0013U`) - OrderManager 오류 해결
2. ⚠️ **주문 상태 조회 API** (`TTTC0081R`) - 체결 여부 확인

### Priority 2 (Medium) - 안정성 향상
3. **정정취소가능조회 API** (`TTTC0084R`) - 취소 전 검증
4. **매수가능조회 API** (`TTTC8908R`) - 주문 전 검증

### Priority 3 (Low) - 편의 기능
5. 잔고 조회 페이징 처리
6. 주문 정정 기능 (`TTTC0013U` 정정 모드)

---

## 🔧 권장 구현 순서

### Step 1: 주문 취소 구현 (30분)
```python
def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
    """주문 취소"""
    tr_id = "VTTC0013U" if KRConfig.is_paper_trading() else "TTTC0013U"

    data = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "ORGN_ODNO": order_id,
        "RVSE_CNCL_DVSN_CD": "02",  # 02=취소
        "ORD_QTY": "0",
        "ORD_UNPR": "0",
        "QTY_ALL_ORD_YN": "Y"
    }

    response = requests.post(url, headers=headers, json=data)
    # 응답 처리...
```

### Step 2: 주문 상태 조회 구현 (45분)
```python
def get_order_status(self, order_id: str) -> Optional[str]:
    """주문 상태 조회"""
    tr_id = "VTTC0081R" if KRConfig.is_paper_trading() else "TTTC0081R"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "INQR_STRT_DT": today,
        "INQR_END_DT": today,
        "ODNO": order_id,
        # ... 기타 파라미터
    }

    response = requests.get(url, headers=headers, params=params)
    # 응답 파싱하여 'filled', 'partially_filled', 'pending' 반환
```

### Step 3: OrderManager 연동 테스트 (15분)
```python
# order_manager.py의 cleanup_orders()가 정상 작동하는지 확인
```

---

## 📚 참고 문서

### Excel 파일 구조
- **파일명**: `[국내주식] 주문_계좌.xlsx`
- **총 시트 수**: 24개
- **주요 시트**:
  1. API 목록 (전체 API 리스트)
  2. 주식주문(현금) - ✅ 구현
  3. 주식주문(신용) - 미구현
  4. 주식주문(정정취소) - ❌ 미구현 (필수!)
  5. 주식정정취소가능주문조회 - ❌ 미구현
  6. 주식일별주문체결조회 - ❌ 미구현 (필수!)
  7. 주식잔고조회 - ✅ 구현
  8. 매수가능조회 - ❌ 미구현
  9. 매도가능수량조회 - 미구현

### API 버전 정보
- **실전 Domain**: `https://openapi.koreainvestment.com:9443`
- **모의 Domain**: `https://openapivts.koreainvestment.com:29443`
- **API Base Path**: `/uapi/domestic-stock/v1/trading/`

---

## ✅ 다음 단계 (Next Steps)

1. **즉시 조치 필요**:
   - [ ] `cancel_order()` 구현 (`TTTC0013U`)
   - [ ] `get_order_status()` 구현 (`TTTC0081R`)
   - [ ] OrderManager 통합 테스트

2. **안정성 개선**:
   - [ ] 정정취소가능조회 추가 (`TTTC0084R`)
   - [ ] 매수가능조회 추가 (`TTTC8908R`)

3. **테스트**:
   - [ ] 모의투자 환경에서 주문 취소 테스트
   - [ ] 타임아웃 시나리오 테스트
   - [ ] 부분 체결 시나리오 테스트

---

**작성자**: Claude Code
**분석 기준**: `overseas_stock/kis_auth.py`, `kr/api_client.py`, Excel 스펙
**최종 업데이트**: 2026-01-22
