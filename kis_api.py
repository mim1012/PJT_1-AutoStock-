"""
한국투자증권 OpenAPI 연동 모듈 (수정 버전)
해외주식 거래를 위한 올바른 API 호출 구현
"""
import logging
import time
import requests
from datetime import datetime, time as dt_time
import pytz
from config import USE_PAPER_TRADING, KIS_ACCOUNT_NUMBER, LOG_LEVEL, LOG_FILE, KIS_BASE_URL, KIS_PAPER_BASE_URL, KIS_APP_KEY, KIS_APP_SECRET, TRADING_START_TIME, TRADING_END_TIME
from token_manager import TokenManager
from currency_utils import format_usd_krw

try:
    import mojito
    MOJITO_AVAILABLE = True
except ImportError:
    MOJITO_AVAILABLE = False
    print("Warning: mojito2 library not installed. Run: pip install mojito2")

class KISAPIClient:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # 기본 로거 사용 (main.py에서 설정된 것 사용)
        self.logger.setLevel(getattr(logging, LOG_LEVEL, 'INFO'))

        # TokenManager 초기화 (실현손익 API용)
        try:
            from token_manager import TokenManager
            self.token_manager = TokenManager()
        except Exception as e:
            self.logger.error(f"TokenManager 초기화 실패: {e}")
            self.token_manager = None

        # 시장 시간 설정 (US Eastern Time)
        self.et_tz = pytz.timezone('US/Eastern')
        self.start_time = dt_time.fromisoformat(TRADING_START_TIME)
        self.end_time = dt_time.fromisoformat(TRADING_END_TIME)

        # 캐시 시스템 추가 (거래소 자동 감지 및 성능 최적화)
        self.exchange_cache = {}  # {symbol: "NAS" or "NYS" or "AMS"}
        self.price_cache = {}     # {symbol: (price, timestamp)}
        self.cache_timeout = 60   # 60초

        # mojito2 클라이언트 초기화
        if MOJITO_AVAILABLE:
            self._init_mojito_client()
        else:
            self.logger.error("mojito2 라이브러리를 사용할 수 없습니다.")
            self.broker = None
    
    def is_market_open(self):
        """현재 시장이 열려있는지 확인 (US Eastern Time 기준)"""
        try:
            et_now = datetime.now(self.et_tz)
            current_time = et_now.time()

            # 주말 체크 (토요일=5, 일요일=6)
            if et_now.weekday() >= 5:
                return False

            # 시장 시간 체크 (09:30-16:00 ET)
            return self.start_time <= current_time <= self.end_time

        except Exception as e:
            self.logger.error(f"시장 시간 확인 오류: {e}")
            return False

    def _init_mojito_client(self):
        """mojito2 클라이언트 초기화 (TokenManager 토큰 통합)"""
        try:
            from config import KIS_APP_KEY, KIS_APP_SECRET
            import pickle
            import datetime

            # 계좌번호 형식 확인 (하이픈 포함)
            acc_no = KIS_ACCOUNT_NUMBER

            # ===== 핵심: TokenManager 토큰을 mojito2와 동기화 =====
            self.logger.info("[TOKEN_SYNC] TokenManager 토큰을 mojito2에 동기화 시작...")

            # 1. TokenManager로 먼저 토큰 발급 (마스터 토큰)
            if self.token_manager:
                access_token = self.token_manager.get_valid_token()

                if access_token:
                    # 2. token.dat 파일 생성 (mojito2가 읽을 수 있게)
                    token_data = {
                        'access_token': access_token,  # Bearer 없이 순수 토큰
                        'api_key': KIS_APP_KEY,
                        'api_secret': KIS_APP_SECRET,
                        'timestamp': int(datetime.datetime.now().timestamp()) + 86400  # 24시간 후
                    }

                    try:
                        with open('token.dat', 'wb') as f:
                            pickle.dump(token_data, f)
                        self.logger.info("[TOKEN_SYNC] ✅ TokenManager 토큰을 token.dat에 저장 완료")
                    except Exception as e:
                        self.logger.warning(f"[TOKEN_SYNC] token.dat 저장 실패 (계속 진행): {e}")
                else:
                    self.logger.warning("[TOKEN_SYNC] TokenManager 토큰 없음 - mojito2가 자체 발급")
            else:
                self.logger.warning("[TOKEN_SYNC] TokenManager 없음 - mojito2가 자체 발급")

            # 3. 이중 거래소 브로커 초기화 (token.dat를 자동으로 읽어감)
            self.nasdaq_broker = mojito.KoreaInvestment(
                api_key=KIS_APP_KEY,
                api_secret=KIS_APP_SECRET,
                acc_no=acc_no,
                exchange="나스닥",
                mock=USE_PAPER_TRADING
            )

            self.nyse_broker = mojito.KoreaInvestment(
                api_key=KIS_APP_KEY,
                api_secret=KIS_APP_SECRET,
                acc_no=acc_no,
                exchange="뉴욕",
                mock=USE_PAPER_TRADING
            )

            # 기본 브로커는 나스닥 (호환성)
            self.broker = self.nasdaq_broker

            # mojito2 토큰 상태 확인
            if hasattr(self.broker, 'access_token') and self.broker.access_token:
                self.logger.info(f"[TOKEN_SYNC] mojito2 토큰 로드 성공: {self.broker.access_token[:30]}...")
            else:
                self.logger.warning("[TOKEN_SYNC] mojito2 토큰 상태를 확인할 수 없음")

            # 기본 API 테스트 (토큰 유효성 간접 확인)
            try:
                test_result = self.broker.fetch_present_balance()
                if test_result:
                    self.logger.info("[TOKEN_SYNC] ✅ mojito2 클라이언트 초기화 및 토큰 확인 성공")
                else:
                    self.logger.warning("[TOKEN_SYNC] mojito2 클라이언트 초기화됨, 토큰 상태 불확실")
            except Exception as token_test_e:
                self.logger.warning(f"[TOKEN_SYNC] 토큰 테스트 실패 (계속 진행): {token_test_e}")

            self.logger.info(f"이중 거래소 브로커 초기화 완료 (나스닥 + 뉴욕)")
            self.logger.info(f"모의투자 모드: {USE_PAPER_TRADING}")

        except KeyError as ke:
            self.logger.error(f"mojito2 클라이언트 초기화 실패 - 키 오류: {ke}")
            self.logger.info("Fallback: TokenManager를 사용한 수동 토큰 관리로 전환")
            self._init_fallback_mode()
        except Exception as e:
            self.logger.error(f"mojito2 클라이언트 초기화 실패: {e}")
            self.logger.info("Fallback: TokenManager를 사용한 수동 토큰 관리로 전환")
            self._init_fallback_mode()

    def reinitialize_brokers(self):
        """
        브로커를 재초기화하여 새 토큰 적용
        TokenManager 토큰을 token.dat에 동기화 후 재초기화
        """
        self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 시작...")

        try:
            # 1. TokenManager의 최신 토큰을 token.dat에 먼저 동기화
            if self.token_manager:
                import pickle
                import datetime
                from config import KIS_APP_KEY, KIS_APP_SECRET

                access_token = self.token_manager.get_valid_token()

                if access_token:
                    token_data = {
                        'access_token': access_token,
                        'api_key': KIS_APP_KEY,
                        'api_secret': KIS_APP_SECRET,
                        'timestamp': int(datetime.datetime.now().timestamp()) + 86400
                    }

                    try:
                        with open('token.dat', 'wb') as f:
                            pickle.dump(token_data, f)
                        self.logger.info("[TOKEN_REFRESH] ✅ 최신 토큰을 token.dat에 동기화 완료")
                    except Exception as e:
                        self.logger.warning(f"[TOKEN_REFRESH] token.dat 동기화 실패: {e}")
                else:
                    self.logger.warning("[TOKEN_REFRESH] TokenManager에서 유효한 토큰을 가져올 수 없음")

            # 2. 기존 브로커 정리
            if hasattr(self, 'nasdaq_broker'):
                del self.nasdaq_broker
            if hasattr(self, 'nyse_broker'):
                del self.nyse_broker
            if hasattr(self, 'broker'):
                del self.broker

            # 3. 브로커 재생성 (token.dat를 읽어감)
            self._init_mojito_client()

            self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 완료")
            return True

        except Exception as e:
            self.logger.error(f"[TOKEN_REFRESH] 브로커 재초기화 실패: {e}")
            return False

    def _safe_float(self, value, default=0.0):
        """
        안전한 float 변환 (빈 문자열/None 처리)

        Args:
            value: 변환할 값 (str, int, float, None 등)
            default: 변환 실패 시 기본값 (기본: 0.0)

        Returns:
            float: 변환된 값 또는 기본값
        """
        if value is None or value == '' or value == 'N/A':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _detect_exchange_yfinance(self, symbol):
        """
        yfinance로 거래소 감지

        Args:
            symbol (str): 종목 코드

        Returns:
            str: "NAS", "NYS", "AMS" 또는 None
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            info = ticker.info
            exchange = info.get('exchange', '')

            # yfinance 거래소 코드 → KIS EXCD 매핑
            exchange_map = {
                'NMS': 'NAS',  # NasdaqGS (Global Select Market)
                'NGM': 'NAS',  # NasdaqGM (Global Market)
                'NCM': 'NAS',  # NasdaqCM (Capital Market)
                'NYQ': 'NYS',  # NYSE
                'ASE': 'AMS',  # AMEX
            }

            mapped_excd = exchange_map.get(exchange)
            if mapped_excd:
                self.logger.debug(f"[DETECT] {symbol} yfinance 감지: {exchange} -> {mapped_excd}")
                return mapped_excd

            return None

        except ImportError:
            self.logger.debug("yfinance 모듈이 설치되지 않았습니다")
            return None
        except Exception:
            self.logger.exception(f"yfinance 거래소 감지 실패")
            return None

    def _fetch_price_from_yfinance(self, symbol):
        """
        yfinance로 현재가 직접 조회 (최종 대체 수단)

        Args:
            symbol (str): 종목 코드

        Returns:
            float: 현재가 (실패 시 None)
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")

            if not hist.empty:
                price = hist['Close'].iloc[-1]
                if price > 0:
                    self.logger.info(f"[OK] {symbol} 현재가: ${price:.2f} (yfinance)")
                    return float(price)
                else:
                    self.logger.warning(f"[WARN] {symbol} yfinance 가격이 0 이하: {price}")
                    return None
            else:
                self.logger.warning(f"[WARN] {symbol} yfinance 히스토리 데이터 없음 (빈 DataFrame)")
                return None

        except ImportError:
            self.logger.error("yfinance 모듈이 설치되지 않았습니다 - pip install yfinance 실행 필요")
            return None
        except Exception as e:
            self.logger.error(f"[ERROR] {symbol} yfinance 조회 실패: {type(e).__name__}: {str(e)}")
            return None

    def _get_broker_for_symbol(self, symbol):
        """
        종목에 맞는 브로커 자동 선택 (캐시 우선 + yfinance 감지)

        Returns:
            tuple: (broker, exchange_name) 또는 (None, None)
        """
        # 1단계: 캐시된 거래소 코드 확인
        if symbol in self.exchange_cache:
            excd = self.exchange_cache[symbol]
            broker = self.nasdaq_broker if excd == "NAS" else self.nyse_broker
            exchange_name = "나스닥" if excd == "NAS" else "뉴욕"
            self.logger.debug(f"[CACHE] {symbol} 캐시된 거래소 사용: {exchange_name}")
            return broker, exchange_name

        # 2단계: yfinance로 거래소 감지
        excd = self._detect_exchange_yfinance(symbol)
        if excd:
            if excd == "NAS":
                broker = self.nasdaq_broker
                exchange_name = "나스닥"
            elif excd == "NYS":
                broker = self.nyse_broker
                exchange_name = "뉴욕"
            else:
                broker = None
                exchange_name = None

            if broker:
                # 감지 성공 시 캐시 저장
                self.exchange_cache[symbol] = excd
                self.logger.info(f"[DETECT] {symbol} yfinance 거래소 감지: {exchange_name}")
                return broker, exchange_name

        # 3단계: 순차 시도 (나스닥 → NYSE)
        # 나스닥 시도
        try:
            price_data = self.nasdaq_broker.fetch_price(symbol)
            if price_data and price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                last_price = output.get('last', '').strip()

                if last_price:
                    self.exchange_cache[symbol] = "NAS"
                    return self.nasdaq_broker, "나스닥"
        except Exception:
            self.logger.exception(f"{symbol} (나스닥) 조회 실패")

        # NYSE 시도
        try:
            price_data = self.nyse_broker.fetch_price(symbol)
            if price_data and price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                last_price = output.get('last', '').strip()

                if last_price:
                    self.exchange_cache[symbol] = "NYS"
                    return self.nyse_broker, "뉴욕"
        except Exception:
            self.logger.exception(f"{symbol} (NYSE) 조회 실패")

        return None, None
    
    def _init_fallback_mode(self):
        """Fallback: TokenManager를 사용한 수동 토큰 관리"""
        try:
            from config import KIS_APP_KEY, KIS_APP_SECRET
            
            # TokenManager로 유효한 토큰 확보
            self.token_manager = TokenManager()
            access_token = self.token_manager.get_valid_token()
            
            if not access_token:
                self.logger.error("Fallback 모드: 유효한 access_token을 가져올 수 없습니다.")
                self.broker = None
                return
            
            # 계좌번호 형식 확인
            acc_no = KIS_ACCOUNT_NUMBER
            
            # 수동 토큰 설정으로 mojito2 초기화
            self.broker = mojito.KoreaInvestment(
                api_key=KIS_APP_KEY,
                api_secret=KIS_APP_SECRET,
                acc_no=acc_no,
                exchange="나스닥",
                mock=USE_PAPER_TRADING
            )
            
            # 수동으로 토큰 설정
            if hasattr(self.broker, '_token'):
                self.broker._token = access_token
            elif hasattr(self.broker, 'token'):
                self.broker.token = access_token
            
            self.logger.info("Fallback 모드: 수동 토큰 설정 완료")
            
        except Exception as e:
            self.logger.error(f"Fallback 모드 초기화 실패: {e}")
            self.broker = None
    
    def get_account_balance(self):
        """
        계좌 잔고 조회 (직접 API 호출 방식 - NASD로 미국 전체 조회)
        """
        try:
            import requests

            # 토큰 가져오기
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                self.logger.error("잔고 조회: 토큰 획득 실패")
                return None

            # 계좌번호 분리
            cano, acnt_prdt_cd = KIS_ACCOUNT_NUMBER.split('-')

            # API 엔드포인트
            base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
            url = f"{base_url}/uapi/overseas-stock/v1/trading/inquire-balance"

            # TR ID 설정
            if USE_PAPER_TRADING:
                tr_id = "VTTS3012R"  # 모의투자
            else:
                tr_id = "TTTS3012R"  # 실전투자

            # 헤더 설정
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET,
                "tr_id": tr_id,
                "custtype": "P"
            }

            # 전체 거래소 조회 (빈 문자열)
            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "OVRS_EXCG_CD": "",  # 빈 문자열 = 전체 거래소
                "TR_CRCY_CD": "USD",  # 통화코드
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }

            # API 호출
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            balance = response.json()

            if balance and balance.get('rt_cd') == '0':
                output1 = balance.get('output1', [])
                output2 = balance.get('output2', [])
                output3 = balance.get('output3', {})

                # output1이 단일 객체인 경우 리스트로 변환
                if output1 and not isinstance(output1, list):
                    output1 = [output1]

                # 예수금 조회 - 다중 필드 fallback 방식
                cash = 0.0

                # 방법 1: output2의 인출가능금액 (가장 정확)
                try:
                    if output2 and isinstance(output2, list) and len(output2) > 0:
                        if isinstance(output2[0], dict):
                            currency = output2[0].get('crcy_cd', '')
                            cash = self._safe_float(output2[0].get('frcr_drwg_psbl_amt_1'))

                            if cash > 0:
                                self.logger.info(f"예수금 (output2): ${cash:.2f} ({currency})")
                except Exception as e:
                    self.logger.debug(f"output2 예수금 조회 실패: {e}")

                # 방법 2: output3의 사용가능금액 (fallback)
                if cash == 0.0 and output3:
                    try:
                        # 총 외화잔고 - 미결제 매수금액 = 사용가능금액
                        tot_frcr = self._safe_float(output3.get('tot_frcr_cblc_smtl'))  # 총 외화잔고
                        ustl_buy = self._safe_float(output3.get('ustl_buy_amt_smtl'))   # 미결제 매수

                        if tot_frcr > 0:
                            cash = tot_frcr - ustl_buy
                            self.logger.info(f"예수금 (output3 계산): 총잔고 ${tot_frcr:.2f} - 미결제 ${ustl_buy:.2f} = ${cash:.2f}")
                    except Exception as e:
                        self.logger.debug(f"output3 예수금 계산 실패: {e}")

                # 방법 3: mojito2 방식 (최후 수단)
                if cash == 0.0:
                    try:
                        if self.broker and hasattr(self.broker, 'fetch_present_balance'):
                            mojito_balance = self.broker.fetch_present_balance()
                            if mojito_balance and mojito_balance.get('rt_cd') == '0':
                                mojito_output2 = mojito_balance.get('output2', [])
                                if mojito_output2 and isinstance(mojito_output2, list) and len(mojito_output2) > 0:
                                    if isinstance(mojito_output2[0], dict):
                                        cash = self._safe_float(mojito_output2[0].get('frcr_drwg_psbl_amt_1'))
                                        if cash > 0:
                                            self.logger.info(f"예수금 (mojito2): ${cash:.2f}")
                    except Exception as e:
                        self.logger.debug(f"mojito2 예수금 조회 실패: {e}")
                
                # 총 평가/매입 금액 - output1에서 직접 계산 (정확한 USD 값)
                eval_amt = 0.0
                purchase_amt = 0.0

                # 디버깅: output1 내용 확인
                if output1:
                    self.logger.debug(f"DEBUG: output1 항목 수: {len(output1)}")
                    for idx, item in enumerate(output1):
                        # 각 항목의 주요 필드들 확인
                        symbol = item.get('ovrs_pdno', '') or item.get('pdno', '')
                        qty = self._safe_float(item.get('ovrs_cblc_qty'))

                        # 다양한 평가금액 필드 시도 (실제 API 응답에서 확인된 필드)
                        eval_fields = ['ovrs_stck_evlu_amt', 'frcr_evlu_amt2', 'frcr_evlu_amt', 'evlu_amt']
                        purchase_fields = ['frcr_pchs_amt1', 'frcr_pchs_amt', 'pchs_amt', 'tot_evlu_amt']

                        item_eval_amt = 0.0
                        item_purchase_amt = 0.0

                        for field in eval_fields:
                            val = self._safe_float(item.get(field))
                            if val > 0:
                                item_eval_amt = val
                                self.logger.debug(f"DEBUG [{idx}] {symbol}: 평가금액 필드 '{field}' = ${val:.2f}")
                                break

                        for field in purchase_fields:
                            val = self._safe_float(item.get(field))
                            if val > 0:
                                item_purchase_amt = val
                                self.logger.debug(f"DEBUG [{idx}] {symbol}: 매입금액 필드 '{field}' = ${val:.2f}")
                                break

                        eval_amt += item_eval_amt
                        purchase_amt += item_purchase_amt

                        # 수량이 있는데 금액이 0인 경우 경고
                        if qty > 0 and (item_eval_amt == 0 or item_purchase_amt == 0):
                            self.logger.warning(f"[WARNING] {symbol}: 수량 {qty}주 있으나 평가금액(${item_eval_amt:.2f}) 또는 매입금액(${item_purchase_amt:.2f})이 0")
                            # 전체 필드 덤프 (디버깅용)
                            self.logger.debug(f"DEBUG: {symbol} 전체 필드: {list(item.keys())}")

                self.logger.info(f"사용가능 예수금: {format_usd_krw(cash)}")
                self.logger.info(f"총 평가금액: {format_usd_krw(eval_amt)}")
                self.logger.info(f"총 매입금액: {format_usd_krw(purchase_amt)}")
                
                # 수익률 계산
                profit_rate = 0.0
                if purchase_amt != 0:
                    profit_rate = (eval_amt - purchase_amt) / purchase_amt * 100
                    profit_loss = eval_amt - purchase_amt
                    self.logger.info(f"손익: {format_usd_krw(profit_loss)} ({profit_rate:+.2f}%)")
                
                # 보유종목 정보 파싱 (Downloads 참조파일과 동일한 필드명 사용)
                positions = []

                # DEBUG: output1의 첫 번째 항목의 모든 필드 출력
                if output1 and len(output1) > 0:
                    self.logger.debug(f"=== API 응답 필드 목록 (첫 번째 종목) ===")
                    first_item = output1[0]
                    for key in sorted(first_item.keys()):
                        self.logger.debug(f"  {key}: {first_item.get(key)}")
                    self.logger.debug("=" * 50)

                for item in output1:
                    try:
                        # 새 API 응답 필드 매핑
                        symbol = item.get('ovrs_pdno', '') or item.get('pdno', '')  # 종목코드
                        item_name = item.get('ovrs_item_name', '') or item.get('prdt_name', '').strip()  # 종목명

                        # 수량 필드 확인 (주문가능수량을 최우선으로 사용!)
                        # ord_psbl_qty / ord_psbl_qty1 = 실제 매도 가능 수량 (T+2 결제 완료된 것만)
                        # API에 따라 ord_psbl_qty 또는 ord_psbl_qty1 사용
                        quantity = 0
                        qty_fields = ['ord_psbl_qty', 'ord_psbl_qty1', 'ovrs_cblc_qty', 'ccld_qty_smtl1', 'cblc_qty13']
                        for qty_field in qty_fields:
                            qty_val = self._safe_float(item.get(qty_field))
                            if qty_val > 0:
                                quantity = int(qty_val)
                                self.logger.debug(f"보유종목 {symbol}: {qty_field}={qty_val} 사용")
                                break

                        # 가격 정보
                        current_price = self._safe_float(item.get('now_pric2')) or self._safe_float(item.get('ovrs_now_pric1'))  # 현재가
                        avg_price = self._safe_float(item.get('avg_unpr3')) or self._safe_float(item.get('pchs_avg_pric'))  # 매입평균가격
                        pchs_amt = self._safe_float(item.get('frcr_pchs_amt')) or self._safe_float(item.get('frcr_pchs_amt1'))  # 외화매입금액
                        evlu_amt = self._safe_float(item.get('frcr_evlu_amt2')) or self._safe_float(item.get('ovrs_stck_evlu_amt'))  # 외화평가금액

                        # 평가손익 (ovrs_ernr_amt가 없으면 evlu_pfls_amt2 사용)
                        profit_loss = 0.0
                        ovrs_ernr_amt_val = item.get('ovrs_ernr_amt')
                        evlu_pfls_amt2_val = item.get('evlu_pfls_amt2')


                        # 디버깅 로그
                        self.logger.debug(f"{symbol} - ovrs_ernr_amt: {ovrs_ernr_amt_val}, evlu_pfls_amt2: {evlu_pfls_amt2_val}")

                        profit_loss = self._safe_float(ovrs_ernr_amt_val)
                        if profit_loss == 0.0:
                            profit_loss = self._safe_float(evlu_pfls_amt2_val)

                        # profit_loss가 0이고 평가금액과 매입금액이 있으면 직접 계산
                        if profit_loss == 0 and evlu_amt > 0 and pchs_amt > 0:
                            profit_loss = evlu_amt - pchs_amt

                        # 평가손익률 (ovrs_ernr_rt가 없으면 evlu_pfls_rt1 사용)
                        profit_rate = 0.0
                        ovrs_ernr_rt_val = item.get('ovrs_ernr_rt')
                        evlu_pfls_rt1_val = item.get('evlu_pfls_rt1')

                        profit_rate = self._safe_float(ovrs_ernr_rt_val)
                        if profit_rate == 0.0:
                            profit_rate = self._safe_float(evlu_pfls_rt1_val)

                        # profit_rate가 0이고 profit_loss가 있으면 직접 계산
                        if profit_rate == 0 and profit_loss != 0 and pchs_amt > 0:
                            profit_rate = (profit_loss / pchs_amt) * 100

                        # 평균단가가 없으면 계산
                        if avg_price == 0 and quantity > 0 and pchs_amt > 0:
                            avg_price = pchs_amt / quantity
                        
                        # 보유수량이 0인 종목은 제외 (이미 매도된 종목)
                        if quantity <= 0:
                            self.logger.info(f"보유종목: {item_name} ({symbol}) - 보유수량 0주, 포지션 목록에서 제외")
                            continue
                        
                        position = {
                            "symbol": symbol,
                            "item_name": item_name,
                            "quantity": quantity,
                            "current_price": current_price,
                            "avg_price": avg_price,  # 평균단가 추가
                            "pchs_amt": pchs_amt,
                            "evlu_amt": evlu_amt,
                            "profit_loss": profit_loss,
                            "profit_rate": profit_rate
                        }
                        
                        # 상세 로깅
                        self.logger.info(f"보유종목: {item_name} ({symbol})")
                        self.logger.info(f"  보유수량: {quantity}주")
                        self.logger.info(f"  현재가: ${current_price:.4f}, 평균단가: ${avg_price:.4f}")
                        self.logger.info(f"  매입금액: {format_usd_krw(pchs_amt)}")
                        self.logger.info(f"  평가금액: {format_usd_krw(evlu_amt)}")
                        self.logger.info(f"  손익: {format_usd_krw(profit_loss)} ({profit_rate:+.2f}%)")
                        
                        positions.append(position)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"보유종목 데이터 파싱 오류: {e}")
                        continue
                
                result = {
                    "cash": cash,
                    "positions": positions,
                    "total_positions": len(positions),
                    "raw_output2": output2  # 디버깅용 원본 데이터 추가
                }

                self.logger.info(f"잔고 조회 완료: 예수금 {format_usd_krw(cash)}, 보유종목 {len(positions)}개")
                self.logger.debug(f"output2 원본: {output2}")
                return result
                
            else:
                error_msg = balance.get('msg1', '알 수 없는 오류') if balance else 'API 응답 없음'
                self.logger.error(f"잔고 조회 실패: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"잔고 조회 중 오류: {e}")
            return None
    
    def get_current_price(self, symbol, retry_count=0):
        """
        현재가 조회 (4단계 폴백 전략 + 자동 복구)
        1단계: 캠시 확인 (60초 이내)
        2단계: KIS API 조회 (자동 거래소 감지)
        3단계: yfinance 직접 조회 (최종 대체)
        4단계: None 반환
        
        Args:
            symbol (str): 종목 코드
            retry_count (int): 재시도 횟수 (내부용, 최대 1회)
        """
        # 시장 시간 체크를 경고로만 변경 (yfinance fallback 허용)
        if not self.is_market_open():
            self.logger.warning(f"{symbol} 현재가 조회: 시장 폐장 중, yfinance로 최신 종가 조회 시도")
            # 시장 폐장 시 KIS API는 스킵하고 yfinance로 직접 이동
            yfinance_price = self._fetch_price_from_yfinance(symbol)
            if yfinance_price:
                self.price_cache[symbol] = (yfinance_price, time.time())
                return yfinance_price
            else:
                self.logger.critical(f"{symbol} 현재가 조회 완전 실패 (시장 폐장 + yfinance 실패)")
                return None

        if not hasattr(self, 'nasdaq_broker') or not hasattr(self, 'nyse_broker'):
            return None

        # 1단계: 캐시 확인 (60초 이내)
        if symbol in self.price_cache:
            price, timestamp = self.price_cache[symbol]
            age = time.time() - timestamp
            if age < self.cache_timeout:
                self.logger.debug(f"💾 {symbol} 캐시된 현재가: ${price:.2f} (캐시 수명: {age:.1f}초)")
                return price

        # 2단계: KIS API 조회 (자동 거래소 감지)
        broker, exchange = self._get_broker_for_symbol(symbol)

        if broker:
            try:
                price_data = broker.fetch_price(symbol)

                if price_data and price_data.get('rt_cd') == '0':
                    output = price_data.get('output', {})
                    current_price = output.get('last', '').strip()

                    if current_price and current_price != '':
                        price_float = float(current_price)
                        # 캠시에 저장
                        self.price_cache[symbol] = (price_float, time.time())
                        self.logger.info(f"[OK] {symbol} 현재가: ${price_float:.2f} ({exchange})")
                        return price_float
                
                # rt_cd != '0' 시 토큰 오류 체크
                elif price_data and price_data.get('rt_cd') != '0':
                    msg = price_data.get('msg1', '')
                    self.logger.warning(f"{symbol} KIS API 오류: rt_cd={price_data.get('rt_cd')}, msg={msg}")
                    
                    # 토큰 오류 감지
                    if ('token' in msg.lower() or 
                        'auth' in msg.lower() or 
                        '접근토큰' in msg or
                        '인증' in msg):
                        
                        if retry_count < 1:
                            self.logger.warning(f"[AUTO_RECOVER] {symbol} 토큰 오류 감지, 자동 복구 시도...")

                            # 1. TokenManager 토큰 재발급 (긴급 복구 모드)
                            if self.token_manager:
                                self.logger.info("[AUTO_RECOVER] TokenManager 토큰 재발급 (긴급 복구)...")

                                # 토큰 파일 + 발급 시간 기록 모두 삭제
                                self.token_manager.delete_token()

                                # 발급 시간 기록이 남아있으면 강제 삭제 (24시간 제한 우회)
                                import os
                                if os.path.exists(self.token_manager.issued_at_file):
                                    os.remove(self.token_manager.issued_at_file)
                                    self.logger.warning("[AUTO_RECOVER] 발급 시간 기록 강제 삭제 (24시간 제한 우회)")

                                # 긴급 재발급 시도
                                new_token = self.token_manager.get_valid_token(force_refresh=True)

                                if new_token:
                                    self.logger.info("[AUTO_RECOVER] ✅ TokenManager 토큰 재발급 성공")
                                else:
                                    self.logger.error("[AUTO_RECOVER] ❌ TokenManager 토큰 재발급 실패")
                                    self.logger.error("[AUTO_RECOVER] 24시간 제한으로 재발급 불가능할 수 있습니다")

                            # 2. mojito2 브로커 재초기화 (TokenManager 토큰을 token.dat에 자동 동기화)
                            self.logger.info("[AUTO_RECOVER] mojito2 브로커 재초기화 (토큰 동기화)...")
                            if self.reinitialize_brokers():
                                self.logger.info("[AUTO_RECOVER] ✅ 토큰 동기화 및 브로커 재초기화 성공, 재시도...")
                                return self.get_current_price(symbol, retry_count + 1)
                            else:
                                self.logger.error("[AUTO_RECOVER] ❌ 자동 복구 실패")

            except Exception as e:
                self.logger.exception(f"{symbol} KIS API 조회 중 오류")
                
                # 예외에서도 토큰 오류 체크
                error_msg = str(e).lower()
                if ('token' in error_msg or 
                    'auth' in error_msg or 
                    '접근토큰' in error_msg or
                    '인증' in error_msg):
                    
                    if retry_count < 1:
                        self.logger.warning(f"[AUTO_RECOVER] {symbol} 예외에서 토큰 오류 감지, 자동 복구 시도...")

                        if self.token_manager:
                            # 토큰 파일 + 발급 시간 기록 모두 삭제
                            self.token_manager.delete_token()

                            # 발급 시간 기록이 남아있으면 강제 삭제 (24시간 제한 우회)
                            import os
                            if os.path.exists(self.token_manager.issued_at_file):
                                os.remove(self.token_manager.issued_at_file)
                                self.logger.warning("[AUTO_RECOVER] 발급 시간 기록 강제 삭제 (예외 처리)")

                            # 긴급 재발급 시도
                            new_token = self.token_manager.get_valid_token(force_refresh=True)

                            if new_token:
                                self.logger.info("[AUTO_RECOVER] ✅ TokenManager 토큰 재발급 성공 (예외 복구)")
                            else:
                                self.logger.error("[AUTO_RECOVER] ❌ TokenManager 토큰 재발급 실패 (예외 복구)")

                        # mojito2 브로커 재초기화 (TokenManager 토큰을 token.dat에 자동 동기화)
                        if self.reinitialize_brokers():
                            self.logger.info("[AUTO_RECOVER] ✅ 토큰 동기화 및 브로커 재초기화 성공, 재시도...")
                            return self.get_current_price(symbol, retry_count + 1)

        # 3단계: yfinance 직접 조회 (최종 대체)
        self.logger.warning(f"[FALLBACK] {symbol} KIS API 실패, yfinance 대체 시도")
        yfinance_price = self._fetch_price_from_yfinance(symbol)
        if yfinance_price:
            # 캐시에 저장
            self.price_cache[symbol] = (yfinance_price, time.time())
            return yfinance_price

        # 4단계: 실패
        self.logger.critical(f"[FAIL] {symbol} 현재가 조회 완전 실패 (KIS API + yfinance 모두 실패)")
        return None
    
    def place_order(self, symbol, quantity, price, order_type="buy"):
        """
        주문 실행 (개선된 mojito2 사용법)
        해외주식 매수/매도 주문
        """
        if not self.broker:
            self.logger.error("broker가 초기화되지 않았습니다.")
            return None
        
        try:
            action = "매수" if order_type.lower() == "buy" else "매도"
            self.logger.info(f"[{action}][시도] 종목: {symbol}, 수량: {quantity}, 가격: ${price:.2f}")
            
            # mojito2 라이브러리의 올바른 사용법
            order_result = None
            
            # 방법 1: 직접 API 호출 (권장)
            if order_type.lower() == "buy":
                # 해외주식 매수 주문
                order_result = self._place_oversea_buy_order(symbol, quantity, price)
            else:
                # 해외주식 매도 주문 - 먼저 매도 가능 수량 확인
                sellable_qty = self._get_sellable_quantity(symbol)
                if sellable_qty is None:
                    self.logger.error(f"[{action}][실패] {symbol}: 매도 가능 수량 확인 불가")
                    return None
                elif quantity > sellable_qty:
                    self.logger.error(f"[{action}][실패] {symbol}: 요청수량({quantity}) > 매도가능수량({sellable_qty})")
                    return None

                order_result = self._place_oversea_sell_order(symbol, quantity, price)
            
            if order_result and order_result.get('rt_cd') == '0':
                order_id = order_result.get('output', {}).get('ODNO', 'N/A')
                self.logger.info(f"[{action}][성공] 종목: {symbol}, 주문번호: {order_id}, 수량: {quantity}, 가격: ${price:.2f}")
                return order_id
            else:
                error_msg = order_result.get('msg1', '알 수 없는 오류') if order_result else 'API 응답 없음'
                
                # 디버그: 전체 API 응답 로깅
                self.logger.error(f"[DEBUG] 전체 API 응답: {order_result}")
                self.logger.error(f"[{action}][실패] 종목: {symbol}, 수량: {quantity}, 가격: ${price:.2f}, 사유: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"주문 실행 중 오류: {e}")
            return None

    def _get_sellable_quantity(self, symbol):
        """
        특정 종목의 매도 가능 수량 조회
        """
        try:
            balance = self.get_account_balance()
            if not balance or not balance.get('positions'):
                return None

            for position in balance['positions']:
                if position['symbol'] == symbol:
                    return position['quantity']  # 이미 매도 가능 수량으로 계산됨

            self.logger.warning(f"{symbol}: 보유 포지션에서 찾을 수 없음")
            return None

        except Exception as e:
            self.logger.error(f"매도 가능 수량 조회 실패: {e}")
            return None
    
    def _place_oversea_buy_order(self, symbol, quantity, price):
        """
        해외주식 매수 주문 (직접 구현)
        TR: TTTT1002U
        """
        try:
            # 직접 API 호출 우선 사용 (더 안정적)
            return self._direct_api_call_buy(symbol, quantity, price)
                
        except Exception as e:
            self.logger.error(f"해외주식 매수 주문 실패: {e}")
            return None
    
    def _place_oversea_sell_order(self, symbol, quantity, price):
        """
        해외주식 매도 주문 (직접 구현)
        TR: TTTT1006U
        """
        try:
            # 직접 API 호출 우선 사용 (더 안정적)
            return self._direct_api_call_sell(symbol, quantity, price)
                
        except Exception as e:
            self.logger.error(f"해외주식 매도 주문 실패: {e}")
            return None
    
    def _direct_api_call_buy(self, symbol, quantity, price):
        """
        직접 API 호출로 매수 주문 (mojito2 우회)
        """
        import requests
        from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL, KIS_PAPER_BASE_URL
        
        # 토큰 매니저로 액세스 토큰 가져오기
        token_manager = TokenManager()
        access_token = token_manager.get_valid_token()
        
        if not access_token:
            self.logger.error("액세스 토큰을 가져올 수 없습니다.")
            return None
        
        # API URL 설정
        base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
        url = f"{base_url}/uapi/overseas-stock/v1/trading/order"
        
        # 헤더 설정
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": "TTTT1002U" if not USE_PAPER_TRADING else "VTTT1002U",  # 실전/모의 구분
            "custtype": "P"
        }
        
        # 동적 거래소 감지
        broker, exchange_name = self._get_broker_for_symbol(symbol)
        if not broker:
            self.logger.error(f"[매수][실패] {symbol}: 거래소 감지 실패 (나스닥/NYSE 모두 실패)")
            return False

        # 거래소 이름을 API 코드로 변환
        exchange_code = "NYSE" if exchange_name == "뉴욕" else "NASD"
        self.logger.info(f"[매수][거래소] {symbol}: {exchange_name} ({exchange_code})")
        
        # 요청 데이터
        data = {
            "CANO": KIS_ACCOUNT_NUMBER.split('-')[0],
            "ACNT_PRDT_CD": KIS_ACCOUNT_NUMBER.split('-')[1],
            "OVRS_EXCG_CD": exchange_code,  # 종목별 거래소 코드
            "PDNO": symbol,
            "ORD_DVSN": "00",  # 지정가
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": str(price),
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "ORD_SVR_DVSN_CD": "0"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            return response.json()
        except Exception:
            self.logger.exception("직접 API 호출 실패")
            return None
    
    def _direct_api_call_sell(self, symbol, quantity, price):
        """
        직접 API 호출로 매도 주문 (mojito2 우회)
        """
        import requests
        from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL, KIS_PAPER_BASE_URL
        
        # 토큰 매니저로 액세스 토큰 가져오기
        token_manager = TokenManager()
        access_token = token_manager.get_valid_token()
        
        if not access_token:
            self.logger.error("액세스 토큰을 가져올 수 없습니다.")
            return None
        
        # API URL 설정
        base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
        url = f"{base_url}/uapi/overseas-stock/v1/trading/order"
        
        # 헤더 설정
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": "TTTT1006U" if not USE_PAPER_TRADING else "VTTT1006U",  # 실전/모의 구분 (매도)
            "custtype": "P"
        }
        
        # 동적 거래소 감지
        broker, exchange_name = self._get_broker_for_symbol(symbol)
        if not broker:
            self.logger.error(f"[매도][실패] {symbol}: 거래소 감지 실패 (나스닥/NYSE 모두 실패)")
            return False

        # 거래소 이름을 API 코드로 변환
        exchange_code = "NYSE" if exchange_name == "뉴욕" else "NASD"
        self.logger.info(f"[매도][거래소] {symbol}: {exchange_name} ({exchange_code})")
        
        # 요청 데이터
        data = {
            "CANO": KIS_ACCOUNT_NUMBER.split('-')[0],
            "ACNT_PRDT_CD": KIS_ACCOUNT_NUMBER.split('-')[1],
            "OVRS_EXCG_CD": exchange_code,  # 종목별 거래소 코드
            "PDNO": symbol,
            "ORD_DVSN": "00",  # 지정가
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": str(price),
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "ORD_SVR_DVSN_CD": "0"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            return response.json()
        except Exception:
            self.logger.exception("직접 API 호출 실패")
            return None
    
    def get_previous_close(self, symbol):
        """
        전일 종가 조회 (자동 거래소 감지)
        """
        # 시장 시간 체크를 경고로만 변경 (장 시작 전에도 전일 종가는 조회 가능)
        if not self.is_market_open():
            self.logger.warning(f"{symbol} 전일 종가 조회: 시장 폐장 중이나 API 조회 시도")

        if not hasattr(self, 'nasdaq_broker') or not hasattr(self, 'nyse_broker'):
            return None

        # 자동 거래소 감지
        broker, exchange = self._get_broker_for_symbol(symbol)

        if not broker:
            self.logger.critical(f"{symbol} 전일 종가 데이터 없음 (나스닥/NYSE 모두 실패)")
            return None
        
        try:
            # 해외주식 일별 데이터 조회
            daily_data = broker.fetch_ohlcv_overesea(symbol)
            
            if daily_data and daily_data.get('rt_cd') == '0':
                output2 = daily_data.get('output2', [])
                
                # output2에서 전일 데이터 찾기
                if output2 and len(output2) >= 2:
                    prev_data = output2[1]  # 전일 데이터
                    
                    # 가능한 종가 필드들 확인
                    close_fields = ['clos', 'stck_clpr', 'prvs_clpr', 'base_pric']
                    
                    for field in close_fields:
                        if field in prev_data:
                            field_value = prev_data[field]
                            # 빈 문자열이나 None 체크
                            if field_value and str(field_value).strip() != '':
                                try:
                                    prev_close = float(field_value)
                                    self.logger.debug(f"{symbol} 전일 종가: ${prev_close:.2f} ({exchange})")
                                    return prev_close
                                except (ValueError, TypeError):
                                    continue
                
                self.logger.warning(f"{symbol} 전일 종가 데이터 없음 ({exchange})")
                return None
            else:
                error_msg = daily_data.get('msg1', '알 수 없는 오류') if daily_data else 'API 응답 없음'
                self.logger.warning(f"{symbol} 전일 종가 조회 실패: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"{symbol} 전일 종가 조회 중 오류: {e}")
            return None

    def get_realized_profit_today(self):
        """
        오늘 실현손익 조회 (해외주식 기간손익조회 API)
        TR_ID: CTRP6504R
        """
        try:
            import requests
            from datetime import datetime
            from config import USE_PAPER_TRADING, KIS_BASE_URL, KIS_PAPER_BASE_URL, KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NUMBER

            base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
            url = f"{base_url}/uapi/overseas-stock/v1/trading/inquire-period-profit"

            # 토큰 가져오기
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                self.logger.error("실현손익 조회: 토큰 획득 실패")
                return None

            today = datetime.now().strftime("%Y%m%d")

            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET,
                "tr_id": "CTRP6504R",  # 해외주식 기간손익조회
                "custtype": "P"
            }

            params = {
                "CANO": KIS_ACCOUNT_NUMBER.split('-')[0],
                "ACNT_PRDT_CD": KIS_ACCOUNT_NUMBER.split('-')[1],
                "INQR_STRT_DT": today,  # 오늘 날짜
                "INQR_END_DT": today,   # 오늘 날짜
                "WCRC_FRCR_DVSN_CD": "02",  # 원화외화구분코드 (02: 외화)
                "TR_MKET_CD": "00",  # 거래시장코드 (00: 전체)
                "NATN_CD": "840",  # 국가코드 (840: 미국)
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }

            self.logger.info(f"[실현손익][조회] 기간: {today} ~ {today}")

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            result = response.json()

            if result.get('rt_cd') == '0':
                output1 = result.get('output1', [])  # 개별 종목 실현손익
                output2 = result.get('output2', {})  # 합계 정보

                total_realized_profit = 0.0
                realized_trades = []

                # 개별 종목 실현손익 파싱
                for item in output1:
                    symbol = item.get('ovrs_pdno', '')  # 해외상품번호
                    symbol_name = item.get('ovrs_item_name', '')  # 해외종목명
                    realized_profit = self._safe_float(item.get('ovrs_rlzt_pfls_amt'))  # 해외실현손익금액

                    if realized_profit != 0:  # 실현손익이 있는 종목만
                        realized_trades.append({
                            'symbol': symbol,
                            'name': symbol_name,
                            'realized_profit': realized_profit
                        })
                        total_realized_profit += realized_profit

                # 합계 정보에서 총 실현손익 확인
                if output2:
                    api_total = self._safe_float(output2.get('ovrs_rlzt_pfls_smtl_amt'))  # 해외실현손익합계금액
                    if api_total != 0:
                        total_realized_profit = api_total

                self.logger.info(f"[실현손익][성공] 오늘 총 실현손익: ${total_realized_profit:.2f}")
                if realized_trades:
                    for trade in realized_trades:
                        self.logger.info(f"  - {trade['symbol']} ({trade['name']}): ${trade['realized_profit']:.2f}")

                return {
                    'total_realized_profit': total_realized_profit,
                    'trades': realized_trades,
                    'date': today
                }

            else:
                error_msg = result.get('msg1', '알 수 없는 오류')
                self.logger.error(f"[실현손익][실패] {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"[실현손익][오류] 조회 실패: {e}")
            return None