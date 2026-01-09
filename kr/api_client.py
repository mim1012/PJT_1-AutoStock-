"""
한국 주식 전용 API 클라이언트 (Phase 2에서 상세 구현)
"""
import os
import sys
import logging
import requests
from typing import Optional, Dict, Any, List

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.base_api import BaseAPIClient
from kr.config import KRConfig
from kr.token_manager import KRTokenManager


class KRAPIClient(BaseAPIClient):
    """
    한국 주식 전용 API 클라이언트

    BaseAPIClient를 상속하여 한국 주식 거래에 맞게 구현
    - KRX (KOSPI/KOSDAQ) 지원
    - 호가 단위 처리
    - T+2 결제 처리
    """

    def __init__(self, log_level: str = 'INFO'):
        super().__init__(log_level)

        # 토큰 매니저 초기화
        self.token_manager = KRTokenManager()

        self.logger.info("한국 주식 API 클라이언트 초기화")

    def get_timezone(self) -> str:
        return KRConfig.TIMEZONE

    def get_market_hours(self) -> tuple:
        return (KRConfig.TRADING_START_TIME, KRConfig.TRADING_END_TIME)

    def _safe_float(self, value, default=0.0) -> float:
        """안전한 float 변환"""
        if value is None or value == '' or value == 'N/A':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_account_balance(self) -> Dict[str, Any]:
        """
        계좌 잔고 조회 (Phase 2에서 상세 구현)

        한국 주식용 TR: TTTC8434R (실전) / VTTC8434R (모의)
        """
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                self.logger.error("잔고 조회: 토큰 획득 실패")
                return None

            app_key, app_secret, acc_no = KRConfig.get_credentials()
            cano, acnt_prdt_cd = acc_no.split('-')

            base_url = KRConfig.get_api_url()
            url = f"{base_url}/uapi/domestic-stock/v1/trading/inquire-balance"

            tr_id = "VTTC8434R" if KRConfig.is_paper_trading() else "TTTC8434R"

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
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",  # 대출일별
                "UNPR_DVSN": "01",  # 기준가
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            balance = response.json()

            if balance and balance.get('rt_cd') == '0':
                output1 = balance.get('output1', [])
                output2 = balance.get('output2', [])

                if output1 and not isinstance(output1, list):
                    output1 = [output1]

                # output2가 리스트인 경우 첫 번째 요소 사용
                if output2 and isinstance(output2, list) and len(output2) > 0:
                    output2_data = output2[0]
                elif isinstance(output2, dict):
                    output2_data = output2
                else:
                    output2_data = {}

                # 예수금 (주문가능현금)
                cash = self._safe_float(output2_data.get('dnca_tot_amt', 0))

                # 총 평가/매입금액
                eval_amt = self._safe_float(output2_data.get('tot_evlu_amt', 0))
                purchase_amt = self._safe_float(output2_data.get('pchs_amt_smtl_amt', 0))

                # 보유종목 파싱
                positions = []
                for item in output1:
                    symbol = item.get('pdno', '')  # 종목코드
                    quantity = int(self._safe_float(item.get('hldg_qty', 0)))

                    if quantity > 0:
                        current_price = self._safe_float(item.get('prpr', 0))  # 현재가
                        avg_price = self._safe_float(item.get('pchs_avg_pric', 0))  # 평균단가
                        item_eval = self._safe_float(item.get('evlu_amt', 0))
                        profit_loss = self._safe_float(item.get('evlu_pfls_amt', 0))
                        profit_rate = self._safe_float(item.get('evlu_pfls_rt', 0))
                        sellable_qty = int(self._safe_float(item.get('ord_psbl_qty', 0)))

                        positions.append({
                            'symbol': symbol,
                            'name': item.get('prdt_name', ''),
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'eval_amount': item_eval,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate,
                            'sellable_qty': sellable_qty
                        })

                self.logger.info(f"예수금: {cash:,.0f}원")
                self.logger.info(f"총 평가금액: {eval_amt:,.0f}원")
                self.logger.info(f"총 매입금액: {purchase_amt:,.0f}원")

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
        """
        현재가 조회 (Phase 2에서 상세 구현)

        한국 주식용 TR: FHKST01010100
        """
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                return None

            app_key, app_secret, _ = KRConfig.get_credentials()
            base_url = KRConfig.get_api_url()
            url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": "FHKST01010100",
                "custtype": "P"
            }

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # 주식
                "FID_INPUT_ISCD": symbol
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result and result.get('rt_cd') == '0':
                output = result.get('output', {})
                price = self._safe_float(output.get('stck_prpr'))  # 주식현재가

                if price > 0:
                    self.logger.debug(f"{symbol} 현재가: {price:,.0f}원")
                    return price

            return None

        except Exception as e:
            self.logger.error(f"{symbol} 현재가 조회 오류: {e}")
            return None

    def get_previous_close(self, symbol: str) -> Optional[float]:
        """전일 종가 조회"""
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                return None

            app_key, app_secret, _ = KRConfig.get_credentials()
            base_url = KRConfig.get_api_url()
            url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": "FHKST01010100",
                "custtype": "P"
            }

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result and result.get('rt_cd') == '0':
                output = result.get('output', {})
                prev_close = self._safe_float(output.get('stck_sdpr'))  # 전일종가

                if prev_close > 0:
                    return prev_close

            return None

        except Exception as e:
            self.logger.error(f"{symbol} 전일 종가 조회 오류: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: int,
                    price: Optional[float] = None) -> Dict[str, Any]:
        """
        주문 실행 (Phase 2에서 상세 구현)

        한국 주식용 TR:
        - 매수: TTTC0802U (실전) / VTTC0802U (모의)
        - 매도: TTTC0801U (실전) / VTTC0801U (모의)
        """
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                return self.format_order_result(False, message="토큰 획득 실패")

            app_key, app_secret, acc_no = KRConfig.get_credentials()
            cano, acnt_prdt_cd = acc_no.split('-')

            base_url = KRConfig.get_api_url()
            url = f"{base_url}/uapi/domestic-stock/v1/trading/order-cash"

            # TR ID 설정
            if KRConfig.is_paper_trading():
                tr_id = "VTTC0802U" if side.lower() == 'buy' else "VTTC0801U"
            else:
                tr_id = "TTTC0802U" if side.lower() == 'buy' else "TTTC0801U"

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": tr_id,
                "custtype": "P"
            }

            # 주문 구분: 00=지정가, 01=시장가
            if price:
                # 호가 단위에 맞게 조정
                adjusted_price = KRConfig.round_to_tick(price)
                ord_dvsn = "00"
                ord_unpr = str(adjusted_price)
            else:
                ord_dvsn = "01"
                ord_unpr = "0"

            data = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "PDNO": symbol,
                "ORD_DVSN": ord_dvsn,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": ord_unpr
            }

            self.logger.info(f"=== {side.upper()} 주문 실행 ===")
            self.logger.info(f"종목: {symbol}")
            self.logger.info(f"수량: {quantity}주")
            self.logger.info(f"가격: {'시장가' if price is None else f'{price:,.0f}원'}")

            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()

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
