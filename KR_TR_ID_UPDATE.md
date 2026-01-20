# 한국 주식 TR_ID 긴급 업데이트 (2024년)

## 긴급 변경 사항

한국투자증권 공식 문서에 따르면, **구 TR_ID는 사전고지 없이 차단될 수 있습니다.**

따라서 다음과 같이 주문 TR_ID를 업데이트했습니다.

---

## TR_ID 변경 내역

### 실전 거래

| 구분 | 구 TR_ID | 신 TR_ID | 상태 |
|------|----------|----------|------|
| 매수 | ~~TTTC0802U~~ | **TTTC0012U** | ✅ 업데이트 완료 |
| 매도 | ~~TTTC0801U~~ | **TTTC0011U** | ✅ 업데이트 완료 |

### 모의 투자

| 구분 | 구 TR_ID | 신 TR_ID | 상태 |
|------|----------|----------|------|
| 매수 | ~~VTTC0802U~~ | **VTTC0012U** | ✅ 업데이트 완료 |
| 매도 | ~~VTTC0801U~~ | **VTTC0011U** | ✅ 업데이트 완료 |

---

## 업데이트된 파일

### kr/api_client.py

**변경 위치**: `place_order()` 메소드 (라인 256-335)

**변경 전**:
```python
# TR ID 설정
if KRConfig.is_paper_trading():
    tr_id = "VTTC0802U" if side.lower() == 'buy' else "VTTC0801U"
else:
    tr_id = "TTTC0802U" if side.lower() == 'buy' else "TTTC0801U"
```

**변경 후**:
```python
# TR ID 설정 (2024년 신규 TR_ID)
if KRConfig.is_paper_trading():
    tr_id = "VTTC0012U" if side.lower() == 'buy' else "VTTC0011U"
else:
    tr_id = "TTTC0012U" if side.lower() == 'buy' else "TTTC0011U"
```

---

## 검증 방법

업데이트가 올바르게 적용되었는지 확인하려면:

```bash
python verify_kr_tr_id.py
```

**기대 출력**:
```
[SUCCESS] 모든 TR_ID가 신규 버전으로 정상 업데이트됨

업데이트 내역:
  TTTC0802U (실전 매수) → TTTC0012U
  TTTC0801U (실전 매도) → TTTC0011U
  VTTC0802U (모의 매수) → VTTC0012U
  VTTC0801U (모의 매도) → VTTC0011U
```

---

## 영향 범위

### 영향을 받는 기능
- ✅ 한국 주식 매수 주문 (`place_order(..., side='buy')`)
- ✅ 한국 주식 매도 주문 (`place_order(..., side='sell')`)
- ✅ 실전 거래 모드
- ✅ 모의 투자 모드

### 영향을 받지 않는 기능
- ❌ 잔고 조회 (TR_ID: TTTC8434R / VTTC8434R)
- ❌ 현재가 조회 (TR_ID: FHKST01010100)
- ❌ 전일 종가 조회 (TR_ID: FHKST01010100)
- ❌ 미국 주식 거래 (별도 TR_ID 사용)

---

## 주의사항

### 1. 구 TR_ID 사용 금지

**구 TR_ID (사용 금지)**:
- TTTC0802U (실전 매수)
- TTTC0801U (실전 매도)
- VTTC0802U (모의 매수)
- VTTC0801U (모의 매도)

이들 TR_ID는 **사전 고지 없이 API에서 차단될 수 있습니다.**

### 2. 하위 호환성 없음

신규 TR_ID는 하위 호환성이 없으므로, **모든 코드를 즉시 업데이트해야 합니다.**

### 3. API 문서 확인

최신 TR_ID 정보는 항상 한국투자증권 공식 API 문서를 확인하세요:
- [한국투자증권 Open Trading API](https://apiportal.koreainvestment.com/)

---

## 참고 자료

### TR_ID 명명 규칙

| 접두사 | 의미 | 예시 |
|--------|------|------|
| `T` | 실전 거래 | TTTC0012U |
| `V` | 모의 투자 | VTTC0012U |

### API 엔드포인트

| 모드 | URL |
|------|-----|
| 실전 | `https://openapi.koreainvestment.com:9443` |
| 모의 | `https://openapivts.koreainvestment.com:29443` |

---

## 업데이트 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2024-01-20 | 1.0 | 주문 TR_ID 신규 버전으로 업데이트 |

---

## 문의

TR_ID 관련 문제가 발생하면:

1. `verify_kr_tr_id.py` 스크립트 실행
2. `kr/api_client.py` 파일의 `place_order()` 메소드 확인
3. 한국투자증권 Open API 고객센터 문의

---

**중요**: 이 업데이트는 긴급 보안 업데이트이므로 **즉시 적용**해야 합니다.
