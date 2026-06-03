# PJT v4.7 업그레이드 설계 문서

> 작성: analyst-architect 에이전트
> 목적: PJT v4.7 자동매매 시스템에 StockDante(단테식 세력봉 전략)의 지표/스크리닝/리스크 로직과
> 동적 종목 발굴(pykrx / yfinance)을 통합한다.

---

## 1. 현황 분석

### 1.1 PJT api_client 인터페이스 목록

`common/base_api.py`의 `BaseAPIClient`(ABC)가 정의하는 계약과 KR/US 구현체의 실제 메서드:

**추상 메서드 (서브클래스 필수 구현)**
| 메서드 | 시그니처 | 반환 |
|---|---|---|
| `get_timezone()` | `() -> str` | 'Asia/Seoul' / 'US/Eastern' |
| `get_market_hours()` | `() -> tuple` | `('09:00', '15:30')` 형태 |
| `get_account_balance()` | `() -> Dict` | `total_eval, total_profit, available_cash, positions[]` |
| `get_current_price(symbol)` | `(str) -> Optional[float]` | 현재가 |
| `place_order(symbol, side, quantity, price=None)` | | `success, order_id, message, filled_qty, filled_price` |

**베이스 클래스가 제공하는 구현된 메서드**
- `is_market_open() -> bool` (타임존/주말/시간 체크)
- `get_market_status() -> Dict`
- `get_cached_price / set_cached_price / get_price_with_cache` (60초 캐시)
- `calculate_position_size(available_cash, price, max_positions=3, max_shares=100) -> int`
  → **현재 사이징 로직: `available_cash / max_positions / price` 후 `max_shares`로 클램프.** 리스크 기반 아님.
- `format_order_result(...)`

**KR/US 구현체가 추가로 제공 (베이스에는 없음)**
- `get_previous_close(symbol) -> Optional[float]`
  - KR: KIS `inquire-price` TR `FHKST01010100`의 `stck_sdpr`(전일종가) 사용
  - US: 브로커 `fetch_price` → `['base','prvs_clpr','stck_clpr']` 폴백, 실패 시 yfinance `info['previousClose']`
- `_safe_float(value, default=0.0)` (KR)
- `_get_broker_for_symbol(symbol)` (US — NASD/NYS 자동 감지)

### 1.2 PJT 데이터 흐름 (봉 데이터 접근 방법)

**결론: PJT에는 봉(OHLCV) 데이터를 가져오는 메서드가 전혀 없다.**

- 현재 전략은 **현재가(`get_current_price`) + 전일종가(`get_previous_close`) 2개 스칼라 값**만으로 동작한다.
- 매수 판단은 `decline_rate = (previous_close - current_price) / previous_close` 단일 지표.
- `get_candles()`, `get_ohlcv()`, `inquire_daily_*` 같은 메서드는 KR/US api_client에 **존재하지 않음** (코드베이스 grep 확인 완료).
- 단, KIS SDK 샘플(`open-trading-api/`)에는 일봉 조회 함수가 이미 존재하므로 참고 가능:
  - KR 국내: `inquire_daily_itemchartprice(env_dv, fid_cond_mrkt_div_code='J', fid_input_iscd, fid_input_date_1, fid_input_date_2, fid_period_div_code='D', fid_org_adj_prc='0')` → `(df1, df2)` 반환, **1회 최대 100건**
  - US 해외: `inquire_daily_chartprice(...)` (overseas_stock_functions.py:4591)
- StockDante는 정반대로 **봉 데이터(`list[Candle]`)를 입력 전제**로 모든 지표/스크리너/룰이 설계되어 있다.

→ **이것이 두 시스템 통합의 핵심 갭이다. (3절·2.4절 참조)**

### 1.3 StockDante 재사용 가능 모듈

| 파일 | 재사용도 | 판정 | 비고 |
|---|---|---|---|
| `dante/models.py` (`Candle`) | ★★★ | **그대로 사용** | frozen dataclass, 순수 도메인 모델. `is_bull/body_ratio/change_pct` 등 property 포함. 의존성 0 |
| `dante/indicators.py` | ★★★ | **그대로 사용** | `sma/volume_ratio/is_volume_high/disparity/ma_alignment` 전부 순수 함수. Candle만 의존. RSI는 없음 → 추가 필요 시 직접 구현 |
| `dante/params.py` (`StrategyParams`) | ★★★ | **그대로 사용** | 모든 임계값 dataclass. PJT config와 매핑만 하면 됨 |
| `dante/screener.py` (`screen`, `ScreenResult`) | ★★★ | **그대로 사용** | indicators+params+models만 의존. 봉 리스트만 주면 동작 |
| `dante/rules.py` (`Position`, `entry_signal`, `exit_signal`) | ★★☆ | **수정 후 사용** | `exit_signal`의 트레일링/손절/익절 로직은 그대로 이식 가치 높음. 단 PJT는 `Position`을 자체적으로 갖지 않고 KIS 잔고(positions[])에서 받으므로, `high_watermark` 추적 상태를 PJT 측에서 별도 관리해야 함(4.2절) |
| `dante/risk.py` (`RiskManager`, `Portfolio`) | ★★☆ | **선택적 이식** | `position_size()`(리스크 기반)와 `check_kill_switch()`는 매우 유용. 단 `Portfolio`는 인메모리 현금/포지션 상태 기계라, KIS API 실잔고와 이중 소스가 됨 → **사이징/킬스위치 계산식만 발췌**하고 상태는 KIS 잔고를 진실원본으로 사용 권장 |
| `dante/broker.py` (`Broker` Protocol, `MockBroker`) | ★☆☆ | **참고만** | `Broker` Protocol의 `get_candles(code)` 계약은 PJT api_client에 추가할 메서드의 설계 지침으로 활용. `MockBroker`는 테스트용으로만 |

### 1.4 충돌 포인트

1. **봉 데이터 부재 (최대 갭)**: StockDante 전체가 `list[Candle]` 전제. PJT는 봉 데이터 접근 메서드 없음 → `get_candles()` 신규 추가 필수.

2. **수익률 단위 불일치**:
   - StockDante `rules.exit_signal`: `pnl_pct`는 **퍼센트 단위(예: 4.0 = 4%)**, `stop_pct/tp_pct/trail_pct`도 퍼센트.
   - PJT `should_sell`: `profit_rate`는 **소수 단위(예: 0.05 = 5%)**, `STOP_LOSS_THRESHOLD = -0.10`.
   - → 이식 시 단위 변환 주의. (PJT는 KIS 잔고의 `profit_rate`를 `/100`하여 소수로 변환해 사용 중)

3. **포지션 상태 모델 이중화**:
   - StockDante: `Portfolio.positions: dict[str, Position]` (인메모리, `high_watermark` 보유).
   - PJT: 매번 `get_account_balance()['positions']`로 KIS에서 실시간 조회 (avg_price, profit_rate 포함). 인메모리 상태 없음.
   - → 트레일링 스탑에 필요한 `high_watermark`(peak_price)는 KIS 잔고에 없으므로 PJT가 별도 영속화 필요(4.2절).

4. **파라미터 임계값 차이**:
   - StockDante `stop_pct=3.0`(%) vs PJT KR `-0.10`(-10%), US `-0.15`(-15%). 단테 전략이 훨씬 타이트.
   - → config로 시장별 분리 관리. 단테 기본값을 그대로 쓰지 말고 PJT 시장 특성에 맞게 조정.

5. **`change_pct` 의미 차이**:
   - StockDante `Candle.change_pct = (close - open) / open`(봉 내부 등락, 시가 대비).
   - PJT decline_rate = (전일종가 - 현재가)/전일종가 (전일 대비).
   - → "상승률" 개념이 봉내부 vs 전일대비로 다름. 세력봉 판정은 봉내부 기준이 맞음(단테 의도대로).

6. **Python 버전/문법**: StockDante는 `from __future__ import annotations` + `list[Candle]` / `float | None` (PEP 604, 3.10+ 스타일). PJT는 `typing.Optional/List/Dict` 사용. `__future__` import 덕에 런타임 호환되나, 이식 파일에 해당 import 유지 필요.

7. **의존성**: StockDante는 외부 라이브러리 의존 0 (순수 파이썬). pykrx/yfinance/pandas-ta는 PJT 발굴 모듈에서 신규 도입.

---

## 2. 통합 아키텍처

### 2.1 신규 파일 목록

#### `common/candle.py` (또는 dante/models.py 그대로 복사)
- `Candle` dataclass 이식 (frozen, `is_bull/body/full_range/body_ratio/change_pct`).
- StockDante `models.py`를 거의 그대로 복사.

#### `common/indicators.py`
구현(이식)할 함수:
- `sma(values, period) -> float | None`
- `closes(candles) / volumes(candles)`
- `volume_ratio(candles, period) -> float | None`
- `is_volume_high(candles, lookback) -> bool`
- `disparity(candles, period) -> float | None`
- `ma_alignment(candles, periods) -> str` ('bullish'/'bearish'/'mixed'/'insufficient')
- **신규 추가**: `rsi(values, period=14) -> float | None` (단테에는 없음, 요구사항에 RSI 언급 → 직접 구현 or `ta` 라이브러리 위임)

#### `common/screener.py`
- `screen(candles, params) -> ScreenResult` 이식 (StockDante screener.py 그대로).
- `ScreenResult(passed, reasons, metrics)` dataclass.
- `is_power_candle(candle, params) -> bool`.
- 인터페이스: `screen(candles: list[Candle], params: StrategyParams) -> ScreenResult`.

#### `common/params.py`
- `StrategyParams` 이식 + PJT config 값과 매핑(아래 `from_config()` 클래스메서드 추가 권장).

#### `common/universe.py` (신규, 종목 발굴)
인터페이스 명세:
```python
class UniverseProvider(ABC):
    def discover(self, limit: int = 50) -> list[str]:
        """필터 조건 통과 종목 코드 리스트 반환"""

class KRUniverseProvider(UniverseProvider):
    # pykrx 기반
    def discover(self, limit=50) -> list[str]: ...

class USUniverseProvider(UniverseProvider):
    # yfinance 기반
    def discover(self, limit=50) -> list[str]: ...
```

### 2.2 기존 파일 수정 명세

#### `common/base_api.py`
- **신규 추상 메서드 추가**: `get_candles(self, symbol, count=120, period='D') -> List['Candle']`
  - 또는 추상으로 강제하지 말고 **기본 구현(NotImplementedError 또는 빈 리스트)** 으로 두고 KR/US에서 오버라이드 (기존 서브클래스 깨짐 방지).
- `calculate_position_size()`에 **리스크 기반 옵션 추가** (4.3절):
  - 시그니처 확장: `calculate_position_size(available_cash, price, stop_pct=None, account_risk_pct=None, ...)`.
  - `stop_pct/account_risk_pct`가 주어지면 단테식 `risk_cap_amount = capital * (account_risk_pct / stop_pct)` 적용, 아니면 기존 로직 유지(하위호환).

#### `kr/api_client.py`
- **`get_candles(symbol, count=120, period='D')` 신규 구현**:
  - KIS `inquire-daily-itemchartprice` TR 사용 (`/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`).
  - 파라미터: `FID_COND_MRKT_DIV_CODE='J'`, `FID_INPUT_ISCD=symbol`, `FID_INPUT_DATE_1/2`(기간), `FID_PERIOD_DIV_CODE='D'`, `FID_ORG_ADJ_PRC='0'`(수정주가).
  - 응답 output2를 `Candle(time, open, high, low, close, volume)` 리스트로 변환 (**오래된→최신 정렬** 보장 — 단테 전제).
  - 1회 100건 제한 → 120봉 필요 시 2회 호출/날짜 페이징.

#### `us/api_client.py`
- **`get_candles(symbol, count=120, period='D')` 신규 구현**:
  - 1차: KIS `inquire_daily_chartprice`(overseas). 2차 폴백: `yfinance.Ticker(symbol).history(period=...)` → DataFrame을 Candle 리스트로.
  - yfinance 폴백이 US에서는 이미 가격조회에 쓰이므로 가장 간단하고 안정적.

#### `common/base_strategy.py`
- `__init__`에 `StrategyParams` 주입 인자 추가 (`params: StrategyParams = None`).
- `peak_prices: Dict[str, float]` 상태 필드 추가 (트레일링용 high_watermark 캐시, 4.2절).
- 헬퍼 메서드 추가:
  - `update_peak(symbol, price)`: 보유 종목 고점 갱신.
  - `get_peak(symbol) -> float`.
  - `passes_screen(symbol) -> ScreenResult`: `api_client.get_candles(symbol)` → `screen(candles, params)` 호출 래퍼.
- 킬스위치 헬퍼: `is_trading_halted() -> bool` (4.1절, transaction_logger 기반 당일 손익 집계).

#### `kr/strategy.py`
- **`should_buy(symbol)` 추가 조건**:
  - 기존(블랙리스트 + 이전매도가) 유지.
  - **신규**: `self.passes_screen(symbol).passed` 가 True여야 매수 (세력봉+거래량급증+이평배열+이격도 과열차단).
  - **신규**: 킬스위치 활성 시 매수 차단 (`if self.is_trading_halted(): return False`).
- **`should_sell(symbol, profit_rate)` 트레일링 스탑 구현**:
  - 기존 익절(`>= profit_threshold`) / 손절(`<= STOP_LOSS_THRESHOLD`) 유지.
  - **신규**: peak 대비 하락 트레일링. 현재가/peak 조회 →
    `drop_from_peak = (peak - current) / peak`; `if profit_rate > 0 and drop_from_peak >= TRAIL_PCT: return True`.
  - 단테 `exit_signal` 우선순위(손절 > 익절 > 트레일링) 차용.
- **`execute_buy_strategy()` 변경**:
  - 매수 후보를 정적 watch_list 대신 (선택) `universe.discover()` 결과로 확장 가능하게.
  - 매수 직후 `self.update_peak(symbol, current_price)` 초기화.
  - 사이징을 리스크 기반(`calculate_position_size(..., stop_pct, account_risk_pct)`)으로 교체.
- **`execute_sell_strategy()` 변경**:
  - 루프 진입 시 각 포지션 `update_peak(symbol, current_price)` 호출 후 `should_sell` 판정.
  - 매도 성공 시 당일 실현손익 누적(킬스위치용) — transaction_logger 기록과 연동.

#### `us/strategy.py`
- KR과 **동일 패턴**, 다른 파라미터:
  - `STOP_LOSS_THRESHOLD = -0.15`, cooldown 100일, `max_shares=100`, 매도는 시장가 미지원 → 지정가(현재가) 유지.
  - 봉 데이터 소스는 yfinance 폴백 우선.
  - 트레일링/스크리너/킬스위치 로직은 KR과 공유 (base_strategy로 최대한 끌어올림).

#### `config.py`
추가할 파라미터와 기본값:
```python
# --- 단테 전략 통합 파라미터 ---
USE_SCREENER = True              # 세력봉 스크리너 매수 게이트 사용
ENABLE_TRAILING_STOP = True      # 트레일링 스탑 사용
TRAIL_PCT = 0.02                 # 트레일링 스탑 (2%, 고점 대비)
ACCOUNT_RISK_PCT = 0.02          # 종목당 최대 손실 허용 (총자금 2%)
DAILY_LOSS_LIMIT_PCT = 0.05      # 일일 손실 한도 (5%) → 킬스위치
PER_TRADE_PCT = 0.15             # 종목당 투입 비중 (15%)
MAX_POSITIONS = 4                # 동시 보유 종목 수

# --- 스크리너 임계값 (StrategyParams 매핑) ---
SCREEN_RISE_PCT = 5.0            # 세력봉 최소 상승률(%)
SCREEN_BODY_RATIO = 0.6          # 몸통 비율
SCREEN_VOL_MULT = 3.0            # 거래량 배수
SCREEN_VOL_AVG_PERIOD = 20
SCREEN_VOL_HIGH_LOOKBACK = 20
SCREEN_MA_PERIODS = [5, 20, 60, 120, 240]
SCREEN_DISPARITY_MAX = 120.0
SCREEN_DISPARITY_BASE_MA = 20

# --- 종목 발굴 ---
USE_DYNAMIC_UNIVERSE = False     # True면 watch_list 대신 동적 발굴 사용
UNIVERSE_LIMIT = 50              # 발굴 종목 최대 수
UNIVERSE_MIN_MARKET_CAP = 5e10   # 최소 시총 (500억)
CANDLE_COUNT = 120               # get_candles 기본 조회 봉 수
```

### 2.3 의존성 추가 (requirements.txt)
- `pykrx` — KR 전종목 시세/시총/거래량 조회 (종목 발굴용).
- `yfinance` — US 주가/봉 데이터 (이미 us/api_client에서 사용 중, 명시 고정).
- `ta` 또는 `pandas-ta` — RSI 등 기술지표 (단테 indicators만 쓸 거면 **불필요**. RSI 추가 시에만).
  - 권장: 외부 의존 최소화를 위해 RSI도 `common/indicators.py`에 직접 구현 → `ta` 생략 가능.
- `pandas` — 이미 설치됨(KIS SDK가 DataFrame 반환). 명시 고정.

### 2.4 봉 데이터 접근 전략

**`get_candles()` 추가 필요: YES (필수).**

- 이유: StockDante의 스크리너/지표/룰 전체가 `list[Candle]`을 전제로 하는데 PJT에는 봉 데이터 접근 수단이 0개.
- 구현 방향:
  1. `common/base_api.py`에 `get_candles(symbol, count=120, period='D')` 를 **비추상 기본 메서드**로 추가하고 `NotImplementedError` 또는 `[]` 반환 → 기존 서브클래스 무파손.
  2. KR: KIS `inquire-daily-itemchartprice` TR(`FHKST03010100`) 사용, output2 → Candle 변환, 오래된→최신 정렬.
  3. US: KIS `inquire_daily_chartprice` 1차 + `yfinance.history()` 폴백.
  4. 60초 가격 캐시와 별도로 **봉 캐시(일봉은 장중 변동 적음 → TTL 길게, 예 5~10분)** 두어 API 호출 절감.
- 정렬 계약 주의: 단테는 **반드시 오래된→최신**. KIS 응답은 보통 최신→과거이므로 **역순 정렬 필수**.

---

## 3. 종목 발굴 전략 (universe.py)

### 3.1 KR 발굴 로직 (pykrx)
- API 호출:
  - `from pykrx import stock`
  - `stock.get_market_ticker_list(date, market="ALL")` → 전 종목 코드.
  - `stock.get_market_cap_by_ticker(date)` → 시총 DataFrame (시총 필터: `>= UNIVERSE_MIN_MARKET_CAP`).
  - `stock.get_market_ohlcv_by_ticker(date, market="ALL")` → 당일 등락률/거래량 일괄.
- 필터 조건(1차, 저비용 일괄):
  1. 시총 >= 500억 (UNIVERSE_MIN_MARKET_CAP).
  2. 당일 등락률 >= SCREEN_RISE_PCT(세력봉 후보).
  3. 거래대금/거래량 상위.
  4. (제외) 관리종목/거래정지/우선주.
- 2차(정밀): 1차 통과 종목에 대해서만 `api_client.get_candles()` → `screen()` 적용해 최종 발굴.
- 출력: 종목 코드 list (limit개).

### 3.2 US 발굴 로직 (yfinance)
- yfinance는 전종목 스크리닝 API가 약함 → **2가지 옵션**:
  - (a) 사전 정의 유니버스(S&P500/NASDAQ100 티커 리스트, 정적 파일)에서 시작 → yfinance로 봉/거래량 받아 `screen()` 필터.
  - (b) `yfinance.Ticker(sym).history()` 배치 + `fast_info`(시총/거래량)로 1차 필터 후 `screen()`.
- 필터 조건: 시총, 평균 거래량(유동성), 당일 상승률 >= SCREEN_RISE_PCT.
- 주의: yfinance 레이트리밋/지연 → 배치 크기 제한 + 캐시.

### 3.3 auto_market_scheduler.py 연동 방법
- 현재 흐름: `AutoMarketScheduler` → 10초 폴링으로 활성 시장 감지 → `current_scheduler.execute_sell_strategy()`(30분) / `execute_buy_strategy()`(60분) 호출 (auto_market_scheduler.py:122/126/158/162/194/197).
- 연동:
  - `execute_buy_strategy()` 내부에서 `USE_DYNAMIC_UNIVERSE` True면 `UniverseProvider.discover()`로 후보 종목 갱신 → `_watch_list`/`_get_active_watch_list()`를 동적 결과로 대체.
  - 발굴은 매 매수 주기(60분)마다 수행하되, pykrx 일괄 호출은 비싸므로 **장 시작 1회 + N분 캐시** 권장.
  - 스케줄러 자체 수정은 최소화: 전략 메서드 내부에서 발굴을 흡수하면 스케줄러는 무변경.

---

## 4. 리스크 관리 업그레이드

### 4.1 킬스위치 구현 방법
- 단테 `RiskManager.check_kill_switch()`: 당일 실현손실이 `-initial_capital * daily_loss_limit/100` 이하면 `halted=True`.
- PJT 적용:
  - **당일 실현손익 집계 소스 = transaction_logger** (CSV: `transaction_logs/`, 매도 시 `profit_loss` 기록됨).
  - `base_strategy.is_trading_halted()`:
    1. transaction_logger에서 **당일자 매도 로그**의 `profit_loss` 합산 → `daily_realized_pnl`.
    2. 기준자본(예: 장 시작 시 `get_account_balance()['total_eval']` 또는 config 고정값) × `DAILY_LOSS_LIMIT_PCT`.
    3. `daily_realized_pnl <= -limit` 이면 halt.
  - transaction_logger에 **당일 손익 조회 헬퍼**가 없으면 추가 필요 (CSV 당일 행 필터 + 합산). → executor 확인 항목.
  - halt 상태는 `execute_buy_strategy()` 진입부와 `should_buy()`에서 차단. 매도는 허용(리스크 축소 방향).
  - 영속화: 프로세스 재시작 대비 당일 halt 상태를 파일/CSV 재계산으로 복원(메모리 플래그만으로는 재시작 시 리셋됨).

### 4.2 트레일링 스탑 구현 방법
- 단테 `Position.high_watermark` + `exit_signal`의 `drop_from_high >= trail_pct and pnl > 0`.
- PJT는 인메모리 Position이 없고 매번 KIS 잔고 조회 → **peak_price를 별도 추적해야 함**.
- **peak_price 추적 위치: 파일 영속화 권장** (메모리 vs 파일 중):
  - 메모리(`self.peak_prices` dict)만 쓰면 **프로세스 재시작/시장 전환 시 peak 소실** → 트레일링 무력화.
  - 권장: `StopLossTracker`와 동일한 패턴(JSON + 원자적 쓰기 + .bak)으로 `kr_peak_prices.json` / `us_peak_prices.json` 영속화.
  - 또는 경량으로 `peak_prices`를 메모리 캐시로 두되 매도 루프마다 `max(저장된peak, current_price)`로 갱신하고 주기적 flush.
- 갱신 시점:
  - 매수 직후: `update_peak(symbol, entry_price)`.
  - 매 매도 주기: 보유 종목별 `update_peak(symbol, current_price)` 후 `should_sell` 평가.
  - 전량 매도 시: `peak_prices`에서 해당 종목 제거.

### 4.3 포지션 사이징 업그레이드
- **현재**: `calculate_position_size`에서 `budget_per_position = available_cash / max_positions`, `qty = int(budget/price)`, `min(qty, max_shares)`. (단순 균등분할)
- **새 방식 (단테 `RiskManager.position_size` 차용)**:
  ```
  per_trade_amount = capital * PER_TRADE_PCT          # 종목당 투입 비중
  risk_cap_amount  = capital * (ACCOUNT_RISK_PCT / STOP_PCT)
                     # 손절 시 손실이 capital*ACCOUNT_RISK_PCT 를 넘지 않는 최대 금액
  budget = min(per_trade_amount, risk_cap_amount, available_cash)
  qty = floor(budget / price)
  ```
  - `STOP_PCT`는 시장별 손절폭(KR 0.10, US 0.15)을 양수 비율로 사용.
  - 예: capital 1,000만, ACCOUNT_RISK_PCT 0.02, STOP_PCT 0.10 → risk_cap = 1,000만×0.2 = 200만. PER_TRADE 0.15 → 150만. budget=150만.
  - 효과: 손절폭이 큰 종목일수록 자동으로 수량 축소 → 종목당 손실 상한 통제.
- 하위호환: `stop_pct/account_risk_pct` 인자가 없으면 기존 균등분할 유지.

---

## 부록 A. StrategyParams ↔ PJT config 매핑표

| StrategyParams | PJT config | KR값 | US값 |
|---|---|---|---|
| `rise_pct=5.0` | `SCREEN_RISE_PCT` | 5.0 | 5.0 |
| `body_ratio=0.6` | `SCREEN_BODY_RATIO` | 0.6 | 0.6 |
| `vol_mult=3.0` | `SCREEN_VOL_MULT` | 3.0 | 3.0 |
| `stop_pct=3.0(%)` | `STOP_LOSS_THRESHOLD` | -0.10 | -0.15 |
| `tp_pct=4.0(%)` | `PROFIT_THRESHOLD` | 0.05 | 0.05 |
| `trail_pct=1.5(%)` | `TRAIL_PCT` | 0.02 | 0.02 |
| `account_risk_pct=3.0(%)` | `ACCOUNT_RISK_PCT` | 0.02 | 0.02 |
| `daily_loss_limit=5.0(%)` | `DAILY_LOSS_LIMIT_PCT` | 0.05 | 0.05 |
| `per_trade_pct=15.0(%)` | `PER_TRADE_PCT` | 0.15 | 0.15 |
| `max_positions=4` | `MAX_POSITIONS` | 4 | 4 |

> 주의: 단테는 퍼센트 단위(5.0), PJT는 소수 단위(0.05)가 혼재. 이식 시 **단일 기준으로 통일**하고 변환 지점을 1곳으로 모을 것.
