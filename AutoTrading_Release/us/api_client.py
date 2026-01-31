"""
미국 주식 전용 API 클라이언트
"""
import os
import sys
import logging
import time
import requests
import pickle
from datetime import datetime
from typing import Optional, Dict, Any, List

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.base_api import BaseAPIClient
from us.config import USConfig
from us.token_manager import USTokenManager
from currency_utils import format_usd_krw

try:
    import mojito
    MOJITO_AVAILABLE = True
except ImportError:
    MOJITO_AVAILABLE = False


class USAPIClient(BaseAPIClient):
    """
    미국 주식 전용 API 클라이언트

    BaseAPIClient를 상속하여 미국 주식 거래에 맞게 구현
    - 이중 거래소 지원 (NASDAQ/NYSE)
    - mojito2 라이브러리 연동
    - yfinance 폴백 지원
    """

    def __init__(self, log_level: str = 'INFO'):
        super().__init__(log_level)

        # 토큰 매니저 초기화
        self.token_manager = USTokenManager()

        # 거래소 캐시
        self.exchange_cache: Dict[str, str] = {}  # {symbol: "NAS" or "NYS"}

        # mojito2 클라이언트 초기화
        self.nasdaq_broker = None
        self.nyse_broker = None
        self.broker = None

        if MOJITO_AVAILABLE:
            self._init_mojito_client()
        else:
            self.logger.error("mojito2 라이브러리를 사용할 수 없습니다.")

    def get_timezone(self) -> str:
        return USConfig.TIMEZONE

    def get_market_hours(self) -> tuple:
        return (USConfig.TRADING_START_TIME, USConfig.TRADING_END_TIME)

    def _init_mojito_client(self):
        """mojito2 클라이언트 초기화"""
        try:
            app_key, app_secret, acc_no = USConfig.get_credentials()

            # TokenManager 토큰을 mojito2와 동기화
            self.logger.info("[TOKEN_SYNC] TokenManager 토큰을 mojito2에 동기화 시작...")

            access_token = self.token_manager.get_valid_token()

            if access_token:
                token_data = {
                    'access_token': access_token,
                    'api_key': app_key,
                    'api_secret': app_secret,
                    'timestamp': int(datetime.now().timestamp()) + 86400
                }

                # US 전용 mojito2 토큰 파일 사용
                mojito_token_file = USConfig.MOJITO_TOKEN_FILE
                try:
                    with open(mojito_token_file, 'wb') as f:
                        pickle.dump(token_data, f)
                    self.logger.info(f"[TOKEN_SYNC] TokenManager 토큰을 {mojito_token_file}에 저장 완료")
                except Exception as e:
                    self.logger.warning(f"[TOKEN_SYNC] {mojito_token_file} 저장 실패: {e}")
            else:
                self.logger.warning("[TOKEN_SYNC] TokenManager 토큰 없음 - mojito2가 자체 발급")

            # 이중 거래소 브로커 초기화
            self.nasdaq_broker = mojito.KoreaInvestment(
                api_key=app_key,
                api_secret=app_secret,
                acc_no=acc_no,
                exchange="나스닥",
                mock=USConfig.is_paper_trading()
            )

            self.nyse_broker = mojito.KoreaInvestment(
                api_key=app_key,
                api_secret=app_secret,
                acc_no=acc_no,
                exchange="뉴욕",
                mock=USConfig.is_paper_trading()
            )

            self.broker = self.nasdaq_broker
            self.logger.info(f"이중 거래소 브로커 초기화 완료 (나스닥 + 뉴욕)")
            self.logger.info(f"모의투자 모드: {USConfig.is_paper_trading()}")

        except Exception as e:
            self.logger.error(f"mojito2 클라이언트 초기화 실패: {e}")
            self.broker = None

    def reinitialize_brokers(self):
        """브로커 재초기화"""
        self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 시작...")

        try:
            if hasattr(self, 'nasdaq_broker'):
                del self.nasdaq_broker
            if hasattr(self, 'nyse_broker'):
                del self.nyse_broker
            if hasattr(self, 'broker'):
                del self.broker

            self._init_mojito_client()
            self.logger.info("[TOKEN_REFRESH] mojito2 브로커 재초기화 완료")
            return True

        except Exception as e:
            self.logger.error(f"[TOKEN_REFRESH] 브로커 재초기화 실패: {e}")
            return False

    def _safe_float(self, value, default=0.0) -> float:
        """안전한 float 변환"""
        if value is None or value == '' or value == 'N/A':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _get_broker_for_symbol(self, symbol: str) -> tuple:
        """종목에 맞는 브로커 자동 선택"""
        # 캐시 확인
        if symbol in self.exchange_cache:
            excd = self.exchange_cache[symbol]
            broker = self.nasdaq_broker if excd == "NAS" else self.nyse_broker
            exchange_name = "나스닥" if excd == "NAS" else "뉴욕"
            return broker, exchange_name

        # yfinance로 거래소 감지
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
                self.exchange_cache[symbol] = excd
                return broker, exchange_name

        # 순차 시도 (나스닥 → NYSE)
        try:
            price_data = self.nasdaq_broker.fetch_price(symbol)
            if price_data and price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                if output.get('last', '').strip():
                    self.exchange_cache[symbol] = "NAS"
                    return self.nasdaq_broker, "나스닥"
        except Exception:
            pass

        try:
            price_data = self.nyse_broker.fetch_price(symbol)
            if price_data and price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                if output.get('last', '').strip():
                    self.exchange_cache[symbol] = "NYS"
                    return self.nyse_broker, "뉴욕"
        except Exception:
            pass

        return None, None

    def _detect_exchange_yfinance(self, symbol: str) -> Optional[str]:
        """yfinance로 거래소 감지"""
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            info = ticker.info
            exchange = info.get('exchange', '')

            exchange_map = {
                'NMS': 'NAS', 'NGM': 'NAS', 'NCM': 'NAS',
                'NYQ': 'NYS', 'ASE': 'AMS',
            }

            return exchange_map.get(exchange)

        except ImportError:
            return None
        except Exception:
            return None

    def get_account_balance(self) -> Dict[str, Any]:
        """계좌 잔고 조회"""
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                self.logger.error("잔고 조회: 토큰 획득 실패")
                return None

            app_key, app_secret, acc_no = USConfig.get_credentials()

            # 계좌번호 형식 검증
            if '-' not in acc_no:
                self.logger.error(f"계좌번호 형식 오류: 하이픈(-) 필요 (예: 12345678-01), 현재: {acc_no}")
                return None

            cano, acnt_prdt_cd = acc_no.split('-')

            base_url = USConfig.get_api_url()
            url = f"{base_url}/uapi/overseas-stock/v1/trading/inquire-balance"

            tr_id = "VTTS3012R" if USConfig.is_paper_trading() else "TTTS3012R"

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": tr_id,
                "custtype": "P"
            }

            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "OVRS_EXCG_CD": "",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            balance = response.json()

            if balance and balance.get('rt_cd') == '0':
                output1 = balance.get('output1', [])
                output2 = balance.get('output2', [])

                if output1 and not isinstance(output1, list):
                    output1 = [output1]

                # 예수금 조회
                cash = 0.0
                if output2 and isinstance(output2, list) and len(output2) > 0:
                    if isinstance(output2[0], dict):
                        cash = self._safe_float(output2[0].get('frcr_drwg_psbl_amt_1'))

                # 평가/매입금액 계산
                eval_amt = 0.0
                purchase_amt = 0.0
                positions = []

                for item in output1:
                    symbol = item.get('ovrs_pdno', '') or item.get('pdno', '')

                    # 수량
                    quantity = 0
                    for qty_field in ['ord_psbl_qty', 'ord_psbl_qty1', 'ovrs_cblc_qty']:
                        qty_val = self._safe_float(item.get(qty_field))
                        if qty_val > 0:
                            quantity = int(qty_val)
                            break

                    # 금액
                    item_eval = 0.0
                    for field in ['ovrs_stck_evlu_amt', 'frcr_evlu_amt2', 'frcr_evlu_amt']:
                        val = self._safe_float(item.get(field))
                        if val > 0:
                            item_eval = val
                            break

                    item_purchase = 0.0
                    for field in ['frcr_pchs_amt1', 'frcr_pchs_amt', 'pchs_amt']:
                        val = self._safe_float(item.get(field))
                        if val > 0:
                            item_purchase = val
                            break

                    eval_amt += item_eval
                    purchase_amt += item_purchase

                    if quantity > 0:
                        current_price = self._safe_float(item.get('now_pric2')) or self._safe_float(item.get('ovrs_now_pric1'))
                        avg_price = self._safe_float(item.get('pchs_avg_pric'))
                        profit_loss = item_eval - item_purchase
                        profit_rate = (profit_loss / item_purchase * 100) if item_purchase > 0 else 0

                        positions.append({
                            'symbol': symbol,
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'eval_amount': item_eval,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate,
                            'sellable_qty': quantity
                        })

                self.logger.info(f"예수금: {format_usd_krw(cash)}")
                self.logger.info(f"총 평가금액: {format_usd_krw(eval_amt)}")
                self.logger.info(f"총 매입금액: {format_usd_krw(purchase_amt)}")

                return {
                    'total_eval': eval_amt,
                    'total_profit': eval_amt - purchase_amt,
                    'available_cash': cash,
                    'positions': positions
                }

            else:
                self.logger.error(f"잔고 조회 실패: {balance}")
                return None

        except Exception as e:
            self.logger.error(f"잔고 조회 오류: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회"""
        try:
            broker, exchange_name = self._get_broker_for_symbol(symbol)

            if broker:
                price_data = broker.fetch_price(symbol)
                if price_data and price_data.get('rt_cd') == '0':
                    output = price_data.get('output', {})
                    price = self._safe_float(output.get('last'))
                    if price > 0:
                        self.logger.debug(f"{symbol} 현재가: ${price:.2f} ({exchange_name})")
                        return price

            # yfinance 폴백
            return self._fetch_price_from_yfinance(symbol)

        except Exception as e:
            self.logger.error(f"{symbol} 현재가 조회 오류: {e}")
            return None

    def _fetch_price_from_yfinance(self, symbol: str) -> Optional[float]:
        """yfinance로 현재가 조회"""
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")

            if not hist.empty:
                price = hist['Close'].iloc[-1]
                if price > 0:
                    self.logger.info(f"{symbol} 현재가: ${price:.2f} (yfinance)")
                    return float(price)

            return None

        except Exception as e:
            self.logger.error(f"{symbol} yfinance 조회 실패: {e}")
            return None

    def get_previous_close(self, symbol: str) -> Optional[float]:
        """전일 종가 조회"""
        try:
            broker, _ = self._get_broker_for_symbol(symbol)

            if broker:
                price_data = broker.fetch_price(symbol)
                if price_data and price_data.get('rt_cd') == '0':
                    output = price_data.get('output', {})

                    # 다양한 필드 시도
                    for field in ['base', 'prvs_clpr', 'stck_clpr']:
                        val = self._safe_float(output.get(field))
                        if val > 0:
                            return val

            # yfinance 폴백
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return info.get('previousClose')
            except Exception:
                pass

            return None

        except Exception as e:
            self.logger.error(f"{symbol} 전일 종가 조회 오류: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: int,
                    price: Optional[float] = None) -> Dict[str, Any]:
        """주문 실행"""
        try:
            broker, exchange_name = self._get_broker_for_symbol(symbol)

            if not broker:
                return self.format_order_result(False, message=f"{symbol}: 거래소 감지 실패")

            self.logger.info(f"=== {side.upper()} 주문 실행 ===")
            self.logger.info(f"종목: {symbol} ({exchange_name})")
            self.logger.info(f"수량: {quantity}주")
            self.logger.info(f"가격: {'시장가' if price is None else f'${price:.2f}'}")

            if side.lower() == 'buy':
                if price:
                    result = broker.create_limit_buy_order(symbol, price, quantity)
                else:
                    result = broker.create_market_buy_order(symbol, quantity)
            else:
                if price:
                    result = broker.create_limit_sell_order(symbol, price, quantity)
                else:
                    result = broker.create_market_sell_order(symbol, quantity)

            if result and result.get('rt_cd') == '0':
                order_id = result.get('output', {}).get('ODNO', '')
                self.logger.info(f"주문 성공: {order_id}")
                return self.format_order_result(
                    True,
                    order_id=order_id,
                    message="주문 성공",
                    filled_qty=quantity
                )
            else:
                msg = result.get('msg1', '알 수 없는 오류') if result else '응답 없음'
                self.logger.error(f"주문 실패: {msg}")
                return self.format_order_result(False, message=msg)

        except Exception as e:
            self.logger.error(f"주문 실행 오류: {e}")
            return self.format_order_result(False, message=str(e))
