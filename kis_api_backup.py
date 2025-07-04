"""
한국투자증권 OpenAPI 연동 모듈 (개선된 로깅 및 에러 처리)
"""
import requests
import json
import time
import logging
import traceback
from datetime import datetime
from config import *

class KISAPIClient:
    def __init__(self):
        self.base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.account_number = KIS_ACCOUNT_NUMBER
        self.access_token = None
        self.token_expires_at = 0  # 초기값을 0으로 설정하여 처음 실행 시 무조건 토큰 발급

        # 로거를 클래스 레벨에서 한 번만 설정하여 중복 로깅 방지
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            self.logger.setLevel(getattr(logging, LOG_LEVEL, 'INFO'))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # 파일 핸들러
            # LOG_FILE 변수가 config에 정의되어 있다고 가정
            fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

            # 스트림 핸들러 (콘솔 출력)
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)

    def get_access_token(self):
        """액세스 토큰 발급"""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result["access_token"]
            # 만료 시간을 1분(60초) 정도 여유롭게 설정
            self.token_expires_at = time.time() + result["expires_in"] - 60
            
            self.logger.info("✅ 액세스 토큰 발급 성공")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 액세스 토큰 발급 요청 실패: {e}")
            if e.response:
                self.logger.error(f"    - Status: {e.response.status_code}, Response: {e.response.text}")
            return False
        except Exception as e:
            self.logger.error(f"❌ 액세스 토큰 발급 중 알 수 없는 오류: {e}", exc_info=True)
            return False

    def ensure_token_valid(self):
        """토큰 유효성 확인 및 만료 시 갱신"""
        if time.time() >= self.token_expires_at:
            self.logger.info("토큰이 만료되어 새로 발급합니다.")
            return self.get_access_token()
        return True

    def get_headers(self, tr_id):
        """API 요청 헤더 생성"""
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P"  # 개인 투자자
        }

    def _request(self, method, url, headers, params=None, data=None, retry_count=0):
        """통합 API 요청 내부 함수 (재시도 로직 포함)"""
        if not self.ensure_token_valid():
            self.logger.error("API 요청 전 토큰 확보 실패. 요청을 중단합니다.")
            return None
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=5)
            else:
                response = requests.post(url, headers=headers, data=json.dumps(data) if data else None, timeout=5)
            
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API 요청 실패: {e.request.method} {e.request.url}")
            if e.response is not None:
                self.logger.error(f"  -> Status: {e.response.status_code}, Response: {e.response.text}")
                # 401 Unauthorized 에러 시 토큰 갱신 후 재시도
                if e.response.status_code == 401 and retry_count < 1:
                    self.logger.warning("401 오류 감지. 토큰을 강제 갱신하고 재시도합니다.")
                    self.token_expires_at = 0 # 토큰 강제 만료
                    return self._request(method, url, headers, params, data, retry_count + 1)
            else:
                self.logger.error("  -> 응답 없음 (네트워크 문제 또는 타임아웃 가능성)")

            # 설정된 횟수만큼 재시도
            if retry_count < MAX_RETRY_COUNT:
                self.logger.info(f"잠시 후 재시도합니다... ({retry_count + 1}/{MAX_RETRY_COUNT})")
                time.sleep(1)
                return self._request(method, url, headers, params, data, retry_count + 1)
            
            self.logger.error("최대 재시도 횟수 초과. 요청을 최종 실패 처리합니다.")
            return None
        except Exception as e:
            self.logger.error(f"API 요청 처리 중 알 수 없는 오류: {e}", exc_info=True)
            return None

    def get_previous_close(self, symbol):
        """전일 종가 조회"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/dailyprice"
        headers = self.get_headers("HHDFS76240000")
        params = {
            "AUTH": "", "EXCD": "NAS", "SYMB": symbol,
            "GUBN": "0", "BYMD": "", "MODP": "1"
        }
        
        self.logger.info(f"전일 종가 조회 시작: {symbol}")
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            output2 = result.get("output2", [])
            if len(output2) >= 2:
                prev_data = output2[1]  # 전일 데이터
                price_str = prev_data.get("clos")
                try:
                    price = float(price_str)
                    self.logger.info(f"✅ {symbol} 전일 종가 조회 성공: ${price:.2f}")
                    return price
                except (TypeError, ValueError):
                    self.logger.warning(f"⚠️ {symbol} 전일 종가 데이터 형식 오류: '{price_str}'")
            else:
                self.logger.warning(f"⚠️ {symbol} 전일 데이터 부족 (output2 길이: {len(output2)})")
        elif result:
            self.logger.error(f"❌ {symbol} 전일 종가 API 오류: {result.get('msg1')} (rt_cd: {result.get('rt_cd')})")
            
        return None

    def get_current_price(self, symbol):
        """현재가 조회"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
        headers = self.get_headers("HHDFS00000300")
        params = {"AUTH": "", "EXCD": "NAS", "SYMB": symbol}
        
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            price_str = result.get("output", {}).get("last")
            try:
                return float(price_str)
            except (TypeError, ValueError):
                self.logger.warning(f"⚠️ {symbol} 현재가 데이터 없음 or 형식 오류: '{price_str}'")
                return None
        
        if result:
            self.logger.error(f"❌ {symbol} 현재가 조회 API 오류: {result.get('msg1')} (rt_cd: {result.get('rt_cd')})")
        return None

    def get_account_balance(self):
        """계좌 잔고 조회 (디버깅 강화)"""
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
        tr_id = "VTTS3012R" if USE_PAPER_TRADING else "TTTS3012R"
        headers = self.get_headers(tr_id)
        
        params = {
            "CANO": self.account_number.split("-")[0],
            "ACNT_PRDT_CD": self.account_number.split("-")[1],
            "OVRS_EXCG_CD": "NASD", "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""
        }
        
        self.logger.info(f"잔고 조회 요청 (TR_ID: {tr_id})")
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            # 디버깅을 위한 전체 응답 로깅
            self.logger.debug(f"잔고 조회 API 전체 응답: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            cash = 0.0
            output2 = result.get("output2", {})
            
            self.logger.info(f"output2 구조: {type(output2)}")
            
            if isinstance(output2, dict):
                # 딕셔너리 형태인 경우 - 실제 API 응답 구조
                self.logger.info(f"딕셔너리 형태 output2 (키 개수: {len(output2)})")
                
                # 예수금 관련 필드들 확인 (실제 발견된 필드명 사용)
                cash_fields = [
                    "frcr_pchs_amt1",      # 외화매수금액1 (총 투자금액)
                    "tot_evlu_pfls_amt",   # 총평가손익금액 (현재 평가손익)
                    "frcr_buy_amt_smtl1",  # 외화매수금액합계1
                    "frcr_buy_amt_smtl2",  # 외화매수금액합계2
                ]
                
                self.logger.info(f"예수금 필드 분석:")
                for field in cash_fields:
                    if field in output2:
                        value = output2[field]
                        try:
                            field_value = float(value) if value else 0.0
                            self.logger.info(f"  - {field}: {value} (${field_value:.2f})")
                            
                            # 첫 번째로 0이 아닌 값을 예수금으로 사용
                            if cash == 0.0 and field_value > 0.0:
                                cash = field_value
                                self.logger.info(f"  ✅ {field}를 예수금으로 사용: ${cash:.2f}")
                                
                        except (ValueError, TypeError) as e:
                            self.logger.error(f"  ❌ {field} 파싱 오류: {e}")
                    else:
                        self.logger.info(f"  - {field}: 필드 없음")
                        
            elif isinstance(output2, list):
                # 리스트 형태인 경우 (이전 구조)
                self.logger.info(f"리스트 형태 output2 (길이: {len(output2)})")
                for i, currency_info in enumerate(output2):
                    self.logger.info(f"통화 정보 [{i}]: {currency_info}")
                    if isinstance(currency_info, dict) and currency_info.get("crcy_cd") == "USD":
                        # 여러 예수금 필드 확인
                        frcr_dncl_amt_2 = currency_info.get("frcr_dncl_amt_2", "0")
                        frcr_evlu_amt2 = currency_info.get("frcr_evlu_amt2", "0")
                        tot_evlu_amt = currency_info.get("tot_evlu_amt", "0")
                        
                        self.logger.info(f"USD 예수금 필드들:")
                        self.logger.info(f"  - frcr_dncl_amt_2: {frcr_dncl_amt_2}")
                        self.logger.info(f"  - frcr_evlu_amt2: {frcr_evlu_amt2}")
                        self.logger.info(f"  - tot_evlu_amt: {tot_evlu_amt}")
                        
                        try:
                            cash = float(frcr_dncl_amt_2)
                            if cash == 0.0:
                                # 다른 필드도 시도
                                cash = float(frcr_evlu_amt2) if frcr_evlu_amt2 != "0" else float(tot_evlu_amt)
                        except (ValueError, TypeError) as e:
                            self.logger.error(f"예수금 파싱 오류: {e}")
                            cash = 0.0
                        break
            else:
                self.logger.warning(f"output2가 예상치 못한 형태: {type(output2)}")

            positions = result.get("output1", [])
            self.logger.info(f"✅ 잔고 조회 성공: 예수금 ${cash:.2f}, 보유종목 {len(positions)}개")
            
            # 보유 종목 상세 정보 로깅
            if positions:
                self.logger.info("보유 종목 상세:")
                for i, pos in enumerate(positions):
                    symbol = pos.get("ovrs_pdno", "N/A")
                    qty = pos.get("ovrs_cblc_qty", "0")
                    avg_price = pos.get("pchs_avg_pric", "0")
                    self.logger.info(f"  [{i+1}] {symbol}: {qty}주, 평균단가: ${avg_price}")
            
            return {"cash": cash, "positions": positions}
        
        if result:
            self.logger.error(f"❌ 잔고 조회 API 오류: {result.get('msg1')} (rt_cd: {result.get('rt_cd')}, msg_cd: {result.get('msg_cd')})")
            self.logger.error(f"전체 오류 응답: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return None

    def place_order(self, symbol, quantity, price, order_type="buy"):
        """주문 실행 (로깅 및 안정성 강화)"""
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        
        tr_id = ""
        if USE_PAPER_TRADING:
            tr_id = "VTTS1002U" if order_type.lower() == "buy" else "VTTS1001U"
        else:
            tr_id = "JTTT1002U" if order_type.lower() == "buy" else "JTTT1006U"

        headers = self.get_headers(tr_id)
        data = {
            "CANO": self.account_number.split("-")[0],
            "ACNT_PRDT_CD": self.account_number.split("-")[1],
            "OVRS_EXCG_CD": "NASD",
            "PDNO": symbol,
            "ORD_QTY": str(int(quantity)),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_DVSN": "00"
        }
        if USE_PAPER_TRADING:
            data["ORD_SVR_DVSN_CD"] = "0"

        self.logger.info(f"➡️ {order_type.upper()} 주문 요청: {symbol} {quantity}주 @ ${price:.2f} (TR_ID: {tr_id})")
        result = self._request("POST", url, headers, data=data)
        
        if result and result.get("rt_cd") == "0":
            order_id = result.get("output", {}).get("ODNO")
            self.logger.info(f"✅ {order_type.upper()} 주문 성공: {symbol} (주문번호: {order_id})")
            return order_id
        
        if result:
            self.logger.error(f"❌ {order_type.upper()} 주문 실패: {symbol}")
            self.logger.error(f"    - API 응답 코드(rt_cd): {result.get('rt_cd')}")
            self.logger.error(f"    - API 메시지(msg1): {result.get('msg1')}")
            self.logger.error(f"    - API 메시지코드(msg_cd): {result.get('msg_cd')}")
            self.logger.error(f"    - 전체 응답: {json.dumps(result, indent=2)}")
        
        return None

    def cancel_order(self, order_id, symbol):
        """주문 취소"""
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order-rvsecncl"
        tr_id = "VTTS1004U" if USE_PAPER_TRADING else "JTTT1004U"
        headers = self.get_headers(tr_id)
        data = {
            "CANO": self.account_number.split("-")[0],
            "ACNT_PRDT_CD": self.account_number.split("-")[1],
            "OVRS_EXCG_CD": "NASD",
            "PDNO": symbol,
            "ORGN_ODNO": order_id,
            "RVSE_CNCL_DVSN_CD": "02" # 02: 취소
        }
        
        self.logger.info(f"➡️ 주문 취소 요청: {order_id}")
        result = self._request("POST", url, headers, data=data)
        
        if result and result.get("rt_cd") == "0":
            self.logger.info(f"✅ 주문 취소 성공: {order_id}")
            return True
        
        if result:
            self.logger.error(f"❌ 주문 취소 실패: {order_id}, 이유: {result.get('msg1')}")
        return False

    def get_order_status(self, order_id):
        """미체결 내역 조회로 주문 상태 확인"""
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-nccs"
        tr_id = "VTTS3018R" if USE_PAPER_TRADING else "JTTT3018R"
        headers = self.get_headers(tr_id)
        params = {
            "CANO": self.account_number.split("-")[0],
            "ACNT_PRDT_CD": self.account_number.split("-")[1],
            "OVRS_EXCG_CD": "NASD",
            "SORT_SQN": "DS",
            "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""
        }
        
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            output = result.get("output1", [])
            for order in output:
                if order.get("odno") == order_id:
                    self.logger.info(f"주문({order_id}) 상태 확인: {order.get('ord_stat_nm')}")
                    return {
                        "status_code": order.get("ord_stat_cd"),
                        "status_name": order.get("ord_stat_nm"),
                        "filled_qty": int(order.get("ccld_qty", 0)),
                        "order_qty": int(order.get("ord_qty", 0))
                    }
            self.logger.info(f"미체결 내역에서 주문({order_id})을 찾을 수 없습니다. (체결 또는 취소된 것으로 간주)")
            return None # 미체결 내역에 없으면 체결된 것으로 간주
        
        if result:
            self.logger.error(f"❌ 주문 상태 조회 API 오류: {result.get('msg1')}")
        return None

    def search_stock(self, symbol):
        """해외주식 종목 검색 및 유효성 검증"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/search"
        tr_id = "HHDFS76240000"  # 해외주식 종목 검색 TR_ID
        headers = self.get_headers(tr_id)
        
        params = {
            "PRDT_TYPE_CD": "512",  # 해외주식
            "PDNO": symbol,
            "OVRS_EXCG_CD": "NASD"  # NASDAQ
        }
        
        try:
            self.logger.info(f"🔍 종목 검색: {symbol}")
            result = self._request("GET", url, headers, params=params)
            
            if result and result.get("rt_cd") == "0":
                output = result.get("output", [])
                if output:
                    stock_info = output[0]
                    self.logger.info(f"✅ 종목 검색 성공: {symbol} - {stock_info.get('prdt_name', 'N/A')}")
                    return {
                        "symbol": symbol,
                        "name": stock_info.get("prdt_name", ""),
                        "exchange": stock_info.get("ovrs_excg_cd", ""),
                        "valid": True
                    }
                else:
                    self.logger.warning(f"⚠️ 종목 검색 결과 없음: {symbol}")
                    return {"symbol": symbol, "valid": False, "error": "No search results"}
            else:
                error_msg = result.get("msg1", "Unknown error") if result else "API request failed"
                self.logger.error(f"❌ 종목 검색 실패: {symbol}, 오류: {error_msg}")
                return {"symbol": symbol, "valid": False, "error": error_msg}
                
        except Exception as e:
            self.logger.error(f"❌ 종목 검색 예외 발생: {symbol}, {str(e)}")
            return {"symbol": symbol, "valid": False, "error": str(e)}

    def validate_stock_symbols(self, symbols):
        """여러 종목의 유효성을 일괄 검증"""
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            result = self.search_stock(symbol)
            if result.get("valid", False):
                valid_symbols.append(symbol)
            else:
                invalid_symbols.append({"symbol": symbol, "error": result.get("error", "Unknown")})
                
        self.logger.info(f"📊 종목 검증 완료: 유효 {len(valid_symbols)}개, 무효 {len(invalid_symbols)}개")
        
        if invalid_symbols:
            self.logger.warning("⚠️ 무효한 종목들:")
            for item in invalid_symbols:
                self.logger.warning(f"  - {item['symbol']}: {item['error']}")
        
        return {
            "valid_symbols": valid_symbols,
            "invalid_symbols": invalid_symbols
        }
        """전일 종가 조회"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/dailyprice"
        headers = self.get_headers("HHDFS76240000")
        params = {
            "AUTH": "", "EXCD": "NAS", "SYMB": symbol,
            "GUBN": "0", "BYMD": "", "MODP": "1"
        }
        
        self.logger.info(f"전일 종가 조회 시작: {symbol}")
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            output2 = result.get("output2", [])
            if len(output2) >= 2:
                prev_data = output2[1]  # 전일 데이터
                price_str = prev_data.get("clos")
                try:
                    price = float(price_str)
                    self.logger.info(f"✅ {symbol} 전일 종가 조회 성공: ${price:.2f}")
                    return price
                except (TypeError, ValueError):
                    self.logger.warning(f"⚠️ {symbol} 전일 종가 데이터 형식 오류: '{price_str}'")
            else:
                self.logger.warning(f"⚠️ {symbol} 전일 데이터 부족 (output2 길이: {len(output2)})")
        elif result:
            self.logger.error(f"❌ {symbol} 전일 종가 API 오류: {result.get('msg1')} (rt_cd: {result.get('rt_cd')})")
            
        return None

    def get_current_price(self, symbol):
        """현재가 조회"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
        headers = self.get_headers("HHDFS00000300")
        params = {"AUTH": "", "EXCD": "NAS", "SYMB": symbol}
        
        result = self._request("GET", url, headers, params=params)
        
        if result and result.get("rt_cd") == "0":
            price_str = result.get("output", {}).get("last")
            try:
                return float(price_str)
            except (TypeError, ValueError):
                self.logger.warning(f"⚠️ {symbol} 현재가 데이터 없음 or 형식 오류: '{price_str}'")
                return None
        
        if result:
            self.logger.error(f"❌ {symbol} 현재가 조회 API 오류: {result.get('msg1')} (rt_cd: {result.get('rt_cd')})")
        return None


    def search_stock(self, symbol):
        """해외주식 종목 검색 및 유효성 검증"""
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/search"
        tr_id = "HHDFS76240000"  # 해외주식 종목 검색 TR_ID
        headers = self.get_headers(tr_id)
        
        params = {
            "PRDT_TYPE_CD": "512",  # 해외주식
            "PDNO": symbol,
            "OVRS_EXCG_CD": "NASD"  # NASDAQ
        }
        
        try:
            self.logger.info(f"🔍 종목 검색: {symbol}")
            result = self._request("GET", url, headers, params=params)
            
            if result and result.get("rt_cd") == "0":
                output = result.get("output", [])
                if output:
                    stock_info = output[0]
                    self.logger.info(f"✅ 종목 검색 성공: {symbol} - {stock_info.get('prdt_name', 'N/A')}")
                    return {
                        "symbol": symbol,
                        "name": stock_info.get("prdt_name", ""),
                        "exchange": stock_info.get("ovrs_excg_cd", ""),
                        "valid": True
                    }
                else:
                    self.logger.warning(f"⚠️ 종목 검색 결과 없음: {symbol}")
                    return {"symbol": symbol, "valid": False, "error": "No search results"}
            else:
                error_msg = result.get("msg1", "Unknown error") if result else "API request failed"
                self.logger.error(f"❌ 종목 검색 실패: {symbol}, 오류: {error_msg}")
                return {"symbol": symbol, "valid": False, "error": error_msg}
                
        except Exception as e:
            self.logger.error(f"❌ 종목 검색 예외 발생: {symbol}, {str(e)}")
            return {"symbol": symbol, "valid": False, "error": str(e)}

    def validate_stock_symbols(self, symbols):
        """여러 종목의 유효성을 일괄 검증"""
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            result = self.search_stock(symbol)
            if result.get("valid", False):
                valid_symbols.append(symbol)
            else:
                invalid_symbols.append({"symbol": symbol, "error": result.get("error", "Unknown")})
                
        self.logger.info(f"📊 종목 검증 완료: 유효 {len(valid_symbols)}개, 무효 {len(invalid_symbols)}개")
        
        if invalid_symbols:
            self.logger.warning("⚠️ 무효한 종목들:")
            for item in invalid_symbols:
                self.logger.warning(f"  - {item['symbol']}: {item['error']}")
        
        return {
            "valid_symbols": valid_symbols,
            "invalid_symbols": invalid_symbols
        }

