# 실시간 조건검색 연동 조사 — 키움 / LS증권 / KIS

> 질문: "키움이나 LS증권으로 검색기(조건검색식)를 구현하면, Mac Mini에서 돌아가는 내 프로그램(KIS 자동매매)에 **실시간 소켓**으로 연동 가능한가?"
> 결론: **둘 다 가능.** 단 KIS엔 이 기능이 없어, "검색=키움/LS · 주문=KIS" 하이브리드가 타당.
> 조사일: 2026-06-12 · 공식 문서·PyPI·GitHub 교차확인 (출처는 각 절 하단)

---

## 한눈에 — 3사 비교

| 항목 | **키움 신 REST/WS** | **LS증권 신 OpenAPI** | **KIS (현 시스템)** |
|---|---|---|---|
| 조건검색 실시간 편입/이탈 push | ✅ (ka10173) | ✅ (t1860 + AFR) | ❌ **없음** |
| **Mac/Linux + Python** | ✅ OS 무관 | ✅ OS 무관 | ✅ (이미 사용 중) |
| 방식 | 단일 WebSocket + JSON | REST + WebSocket | REST + WebSocket |
| 조건식 동시 등록 한도 | **최대 10개** | 2개[불확실, 구 기준] | — |
| 결과 종목 한도 | **100종목 초과 시 실시간 불가** | [불확실] | — |
| push 유지 | 세션 유지 | **60초마다 재등록 필요** | — |
| 조건식 작성 | 영웅문4 HTS(**Windows 1회 필요**) | LS HTS/MTS에 사전 저장 | HTS 조건식 1회성 조회만 |
| 출시 | 2025-03 (역사 짧음) | 2024-01 조건검색 개시 | 기존 |

→ **OS 자유도는 LS·키움 모두 확보**(구버전 OCX/XingAPI는 Windows 전용이었으나, 신 API는 순수 HTTP+WebSocket). **실시간 조건검색 성숙도·한도는 키움 우위**(10개 vs 2개, 세션유지 vs 60초 재등록). **단 키움은 조건식을 영웅문4(Windows)에서 한 번 만들어 서버에 저장해야** 함.

---

## A. 키움증권 — 신 REST/WebSocket OpenAPI

- **출시/도메인**: 2025-03 출시. WebSocket `wss://api.kiwoom.com:10000/api/dostk/websocket` (모의: `wss://mockapi.kiwoom.com:10000`, KRX만).
- **인증**: 앱키+시크릿키 → REST로 접근토큰 발급 → WebSocket LOGIN 메시지에 토큰.
- **조건검색 TR 4종** (모두 단일 WebSocket 위 JSON):

  | TR | 기능 | trnm |
  |----|------|------|
  | ka10171 | 조건검색 목록조회 | `CNSRLST` |
  | ka10172 | 조건검색 (일반 1회성) | `CNSRREQ` + `search_type:"0"` |
  | **ka10173** | **조건검색 실시간(편입/이탈 등록)** | `CNSRREQ` + `search_type:"1"` |
  | ka10174 | 실시간 해제 | — |

- **흐름**: 토큰발급 → WS연결+LOGIN → **ka10171(목록조회 먼저 — 필수 선행)** → ka10173(seq=조건식번호) 실시간 등록 → push 수신 → ka10174 해제.
- **OS**: 공식 명시 "윈도우, 맥, 리눅스 등 다양한 OS 이용 가능", "OCX 방식에서 벗어나 설치 불필요". → **Mac OK.**
- **조건식 저장 = 서버 저장이 유일** (확인됨): 영웅문4 `[0150]` 조건검색 → 작성 → **"내조건식 저장"** 버튼 → 조건명 → 끝. **그냥 저장하면 자동으로 키움 서버에 저장**되며 로컬 전용 경로 없음(그래서 영웅문S·다른 PC·API에서 동일 조회). 별도 "서버저장" 선택 불필요. 이 서버 조건식이 그대로 `ka10171`에 뜸. (출처: 영웅문4 [0150] 도움말)
- **한도**: 서버 저장 조건식 **총 20개**[불확실, 커뮤니티 기준·공식 재확인 권장] · API 동시 실시간 등록 **최대 10개** · 결과 **100종목 초과 시 실시간 불가** · 요청 1초 5회(조건검색+시세+관심 합산) · 조건검색 최소 1분 1회.
- **함정**: ① ka10171 미선행 시 이후 요청 전부 실패. ② **조건식 자체는 영웅문4(Windows)에서만 작성** — Mac에서 신규 조건식 생성 불가, 서버 저장된 것만 호출. ③ 2025-03 출시라 엣지케이스 미검증 가능성.
- **Python 래퍼**: `pip install kiwoom-rest-api` (younghwan91/kiwoom-rest-api, macOS/Linux 명시 지원), `kiwoomRest` (PyPI).

**출처**:
- 공식 가이드(조건검색): https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=15
- 공식 소개(OS·한도): https://openapi.kiwoom.com/intro?dummyVal=0
- 출시 기사(2025-03-24): https://www.sedaily.com/NewsView/2GQDBOKLH7
- Python 래퍼: https://github.com/younghwan91/kiwoom-rest-api · https://pypi.org/project/kiwoomRest/
- 실사용 예제(WS URL·순서제약): https://www.pabburi.co.kr/content/php/키움증권-rest-api-실시간시세조회-및-조건검색/

---

## B. LS증권(구 이베스트) — 신 REST/WebSocket OpenAPI

- **라인업**: 구 XingAPI(COM/OCX, **Windows 전용**) + 신 REST/WebSocket(크로스플랫폼). 조건검색 서비스 2024-01-15 개시, 사명변경(이베스트→LS) 2024-06-01.
- **도메인**: 토큰 `https://openapi.ls-sec.co.kr:8080/oauth2/token`, WS 실거래 `wss://openapi.ls-sec.co.kr:9443/websocket`, 모의 `:29443`.
- **인증**: APP_KEY+APP_SECRET → 액세스 토큰 → WS 헤더.
- **조건검색 TR**:

  | TR | 역할 | 방식 |
  |----|------|------|
  | t1866 | 서버저장조건 리스트 조회 | REST |
  | t1859 | 조건검색 1회성 결과 | REST |
  | **t1860** | 실시간 조건검색 등록/해제(`sFlag='E'/'D'`) | REST→WS |
  | **AFR** | 실시간 편입/이탈 push 수신 | WebSocket |

- **흐름**: auth → t1866(목록) → t1860(등록, `sAlertNum` 반환) → `add_realtime("AFR", sAlertNum)` → push → **60초 유효 → 재등록 루프 필요**.
- **OS**: 신 API 순수 HTTP+WS, PyPI 메타 "OS Independent". → **Mac OK** (단 Mac 실환경 공식 검증 사례는 문서화 안 됨[불확실]).
- **한도**: 구 XingAPI 기준 **동시 2개**(키움 대비 열위 통념의 근거). 신 API 공식 한도는 미확인[불확실]. AFR 유효 60초.
- **Python 래퍼**: `pip install ebest` (v1.0.2, asyncio, OS Independent), 공식 샘플 teranum/ls-openapi-samples (Python 100%, MIT).

**출처**:
- 공식 포털: https://openapi.ls-sec.co.kr/intro · https://openapi.ls-sec.co.kr/howto-use
- 조건검색 개시(2024-01-16): https://www.newspim.com/news/view/20240116000904
- ebest PyPI: https://pypi.org/project/ebest/ · 소스: https://github.com/teranum/python-packages/tree/master/ebest
- 공식 Python 샘플: https://github.com/teranum/ls-openapi-samples

---

## C. KIS(한국투자증권) — 조건검색 실시간 **없음**

- KIS WebSocket 실시간은 **시세·호가·체결 중심**(실시간체결가/호가/예상체결/회원사/프로그램매매/지수/ELW). **조건식 편입·이탈 push는 목록에 없음.**
- REST에 "종목조건검색 목록조회/조회"가 있으나 **1회성 조회**(HTS 조건식을 한 번 불러올 뿐, 실시간 등록 아님).
- → **KIS 단독으로는 "조건식 실시간 발굴"이 불가.** 그래서 키움/LS를 신호 소스로 끌어오는 하이브리드가 합리적.

**출처**: KIS 포털 https://apiportal.koreainvestment.com/apiservice · 공식 GitHub https://github.com/koreainvestment/open-trading-api
> [불확실] 포털 일부 상세는 로그인 제한. 공식 문서·GitHub에 근거 없어 현 시점 "없음"으로 판단.

---

## D. 권장 아키텍처 + 현재 코드 연결

```
[발굴 Stage 0]  EOD 일봉 스캔(scripts/eod_scan.py)  ← 지금 그대로 유지 (FDR/yfinance)
        │  마감 후 후보군·워치리스트
        ▼
[타점 Stage 2]  키움(또는 LS) 실시간 조건검색  ──push(편입/이탈)──┐   ← 지금 TODO인 부분
        │  워치 수십 종목만 실시간 감시                          │
        ▼                                                        │
[정밀타점]  KIS 분봉 + common/screener_dante_intraday.py        ◀┘
        │  (일목 기준선/볼린저/5일선 회복 2차 확정)
        ▼
[진입 8관문]  should_buy  →  [주문/계좌]  KIS mojito2 (현행 유지)
```

- 키움/LS 조건검색이 **장중 1차 후보를 실시간으로 좁혀주면**, 그 종목만 KIS 분봉으로 받아 `screen_dante_intraday_*`로 2차 타점 확정 → `should_buy`.
- 즉 **키움/LS = 깔때기 입구(발굴·타점 신호), KIS = 정밀타점 + 주문**. `dante_strategy_pipeline.md`의 Stage 2 TODO를 이걸로 채움.

---

## E. 키움 vs LS — 무엇을 고를까

| 기준 | 키움 | LS |
|------|------|-----|
| 실시간 조건식 한도 | **10개** ✅ | 2개[불확실] |
| push 유지 편의 | **세션 유지** ✅ | 60초 재등록 루프 |
| 조건식 작성 환경 | 영웅문4 **Windows 1회 필요** ⚠️ | LS HTS(동일 제약) |
| Mac/Python 연동 | ✅ | ✅ |
| API 성숙도/사용례 | 사용자 많음, 단 신API는 2025-03 | 2024-01부터, ebest 패키지 성숙 |

- **단테식 워치리스트(수십 종목·복수 조건식)** 운용엔 **키움(10개 한도·세션유지)이 유리.**
- 단 **조건식 작성을 위해 Windows(영웅문4) 1회 접속**이 필요 — Mac Mini만으론 조건식 신규 작성 불가, 작성은 윈도우/원격, 운영(push 수신)은 Mac.

---

## F. 다음 단계 (실증)

1. 증권사 택1 + 계좌·OpenAPI 신청 (검색=키움/LS, 주문=KIS 계좌 별도 유지).
2. (키움) 영웅문4에서 단테 조건식 작성·서버 저장 → Mac Mini `pip install kiwoom-rest-api` → ka10171→ka10173 실시간 수신 테스트.
   (LS) LS HTS에 조건식 저장 → `pip install ebest` → t1866→t1860→AFR, 60초 재등록 루프 테스트.
3. 수신 종목 → 기존 KIS 분봉/`should_buy` 파이프라인에 주입 (Stage 2 배선).
4. 시세 시점차(검색 호가 vs KIS 체결 호가) 슬리피지·이중 세션(토큰갱신·재연결) 운영 점검.

---

## 핵심 한 줄
**키움·LS 둘 다 Mac+Python 실시간 조건검색 연동 가능. KIS엔 없음 → 검색(키움/LS)+주문(KIS) 하이브리드가 정답.** 워치리스트 다중 조건식엔 **키움(10개·세션유지)이 우위**, 단 조건식 작성용 Windows(영웅문4) 1회 필요. LS는 OS 자유도 동일·`ebest`로 간편하나 60초 재등록·한도 불확실.
