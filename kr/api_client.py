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
        계좌 잔고 조회 (페이징 지원)

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

            # 페이징 처리를 위한 변수
            all_positions = []
            ctx_area_fk100 = ""
            ctx_area_nk100 = ""
            page_count = 0
            max_pages = 20  # 안전장치: 최대 20페이지

            # 페이징 루프
            while page_count < max_pages:
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
                    "CTX_AREA_FK100": ctx_area_fk100,
                    "CTX_AREA_NK100": ctx_area_nk100
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                balance = response.json()

                if not balance or balance.get('rt_cd') != '0':
                    self.logger.error(f"잔고 조회 실패: {balance}")
                    return None

                output1 = balance.get('output1', [])
                output2 = balance.get('output2', [])

                if output1 and not isinstance(output1, list):
                    output1 = [output1]

                # 현재 페이지의 보유종목 파싱
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

                        all_positions.append({
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

                # 다음 페이지 체크
                tr_cont = balance.get('tr_cont', '')
                if tr_cont in ['F', 'M']:  # F: 다음 데이터 있음, M: 중간
                    ctx_area_fk100 = balance.get('ctx_area_fk100', '')
                    ctx_area_nk100 = balance.get('ctx_area_nk100', '')
                    page_count += 1
                    self.logger.info(f"다음 페이지 조회 중... (페이지 {page_count + 1})")
                    import time
                    time.sleep(0.1)  # Rate limiting
                else:
                    # 마지막 페이지
                    break

            # output2에서 계좌 정보 추출 (마지막 응답 사용)
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

            self.logger.info(f"예수금: {cash:,.0f}원")
            self.logger.info(f"총 평가금액: {eval_amt:,.0f}원")
            self.logger.info(f"총 매입금액: {purchase_amt:,.0f}원")
            self.logger.info(f"보유종목 수: {len(all_positions)}개 (페이지: {page_count + 1})")

            return {
                'total_eval': eval_amt,
                'total_profit': eval_amt - purchase_amt,
                'available_cash': cash,
                'positions': all_positions
            }

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

        한국 주식용 TR (2024년 신규 TR_ID 적용):
        - 매수: TTTC0012U (실전) / VTTC0012U (모의)
        - 매도: TTTC0011U (실전) / VTTC0011U (모의)

        ※ 구 TR_ID (TTTC0802U/0801U)는 사전고지 없이 차단될 수 있음
        """
        try:
            access_token = self.token_manager.get_valid_token()
            if not access_token:
                return self.format_order_result(False, message="토큰 획득 실패")

            app_key, app_secret, acc_no = KRConfig.get_credentials()
            cano, acnt_prdt_cd = acc_no.split('-')

            base_url = KRConfig.get_api_url()
            url = f"{base_url}/uapi/domestic-stock/v1/trading/order-cash"

            # TR ID 설정 (2024년 신규 TR_ID)
            if KRConfig.is_paper_trading():
                tr_id = "VTTC0012U" if side.lower() == 'buy' else "VTTC0011U"
            else:
                tr_id = "TTTC0012U" if side.lower() == 'buy' else "TTTC0011U"

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

    def get_candles(self, symbol: str, count: int = 120) -> list:
        """
        국내 주식 일봉 데이터 조회 (최근 count봉, 오래된→최신 정렬)
        KIS FHKST03010100 TR 사용. 100봉 제한으로 count>100 시 페이징.
        실패 시 빈 리스트 반환
        """
        try:
            from common.candle import Candle
            import datetime

            access_token = self.token_manager.get_valid_token()
            if not access_token:
                self.logger.warning(f"{symbol} 일봉 조회: 토큰 획득 실패")
                return []

            app_key, app_secret, _ = KRConfig.get_credentials()
            # 차트 조회는 모의투자 서버(VTS)가 미지원 → 항상 실전 서버 사용 (read-only)
            base_url = KRConfig.BASE_URL
            url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": "FHKST03010100",
                "custtype": "P"
            }

            all_candles = []
            # KIS API 1회 최대 100봉 → count를 100봉 단위로 나눠 페이징
            end_date = datetime.date.today()
            # 한 페이지당 100봉 = 약 140 달력일 (주말/공휴일 40% 여유)
            page_days = 140
            remaining = count

            while remaining > 0:
                start_date = end_date - datetime.timedelta(days=page_days)
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                    "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                    "FID_PERIOD_DIV_CODE": "D",
                    "FID_ORG_ADJ_PRC": "0",
                }
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                resp.raise_for_status()
                rows = resp.json().get("output2", []) or []

                page_candles = []
                for row in rows:
                    try:
                        if not row or not row.get("stck_bsop_date"):
                            continue
                        page_candles.append(Candle(
                            time=str(row["stck_bsop_date"]),
                            open=float(row.get("stck_oprc", 0)),
                            high=float(row.get("stck_hgpr", 0)),
                            low=float(row.get("stck_lwpr", 0)),
                            close=float(row.get("stck_clpr", 0)),
                            volume=int(float(row.get("acml_vol", 0))),
                        ))
                    except (ValueError, TypeError):
                        continue

                if not page_candles:
                    break

                all_candles = page_candles + all_candles  # 이전 페이지가 더 오래된 것
                remaining -= len(page_candles)

                # 다음 페이지: 현재 페이지의 가장 오래된 봉 날짜 하루 전까지
                oldest = min(c.time for c in page_candles)
                end_date = datetime.datetime.strptime(oldest, "%Y%m%d").date() - datetime.timedelta(days=1)

                if len(page_candles) < 90:  # 페이지가 거의 비었으면 더 이상 데이터 없음
                    break

            # 오래된→최신 정렬 후 최근 count봉만 반환
            all_candles.sort(key=lambda c: c.time)
            return all_candles[-count:] if len(all_candles) > count else all_candles

        except Exception as e:
            self.logger.warning(f"{symbol} 일봉 조회 실패 (스크리너 스킵): {e}")
            return []

    def get_orderbook(self, symbol: str) -> Optional[Dict[str, float]]:
        """국내주식 호가 총잔량 조회 (타점 단계용).

        KIS inquire-asking-price-exp-ccn (FHKST01010200). 차트와 달리 모의서버는
        호가를 지원하므로 BASE_URL 그대로 사용.
        반환: {'ask_total': 총매도잔량, 'bid_total': 총매수잔량,
               'ratio': 매도/매수 비율(%)} 또는 실패 시 None.
        """
        try:
            token = self.token_manager.get_valid_token()
            if not token:
                return None
            app_key, app_secret, _ = KRConfig.get_credentials()
            # 호가는 차트와 달리 모드별 도메인 사용 (모의 모드는 모의 도메인에서만 허용)
            url = f"{KRConfig.get_api_url()}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
                "appkey": app_key, "appsecret": app_secret,
                "tr_id": "FHKST01010200", "custtype": "P",
            }
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            o1 = resp.json().get("output1", {}) or {}
            ask = float(o1.get("total_askp_rsqn", 0) or 0)  # 총 매도호가 잔량
            bid = float(o1.get("total_bidp_rsqn", 0) or 0)  # 총 매수호가 잔량
            ratio = (ask / bid * 100) if bid > 0 else 0.0
            return {"ask_total": ask, "bid_total": bid, "ratio": round(ratio, 1)}
        except Exception as e:
            self.logger.debug(f"{symbol} 호가 조회 실패: {e}")
            return None

    def get_minute_candles(self, symbol: str, minutes: int = 5,
                           count: int = 80) -> list:
        """국내주식 당일 분봉 조회 후 N분봉으로 집계 (타점 단계용, 오래된→최신).

        KIS inquire-time-itemchartprice (FHKST03010200)는 1회 ~30개 1분봉을 주므로
        입력시간을 거슬러 올라가며 페이징해 1분봉을 모은 뒤 minutes분으로 집계한다.
        일목 기준선(26봉)·전환선(9봉) 계산이 목적이므로 count는 그 이상이면 충분.
        실패 시 빈 리스트.
        """
        try:
            from common.candle import Candle
            import datetime
            token = self.token_manager.get_valid_token()
            if not token:
                return []
            app_key, app_secret, _ = KRConfig.get_credentials()
            # 차트 계열은 모의서버(VTS) 미지원 → 실전 서버 사용 (read-only)
            url = f"{KRConfig.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
                "appkey": app_key, "appsecret": app_secret,
                "tr_id": "FHKST03010200", "custtype": "P",
            }
            need_1min = count * minutes + minutes * 30  # 집계 여유
            one_min = {}  # 'HHMM' -> [o,h,l,c,v] (중복 제거용)
            cursor = "153000"  # 장 마감 시각부터 거슬러
            for _ in range(need_1min // 30 + 2):
                params = {
                    "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol, "FID_INPUT_HOUR_1": cursor,
                    "FID_PW_DATA_INCU_YN": "Y",
                }
                # 페이지별 예외는 break — 누적된 분봉은 보존(레이트리밋 대비)
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=10)
                    resp.raise_for_status()
                    rows = resp.json().get("output2", []) or []
                except Exception:
                    break
                if not rows:
                    break
                for r in rows:
                    hhmm = str(r.get("stck_cntg_hour", ""))[:4]
                    if not hhmm:
                        continue
                    try:
                        o1v = (float(r.get("stck_oprc", 0)), float(r.get("stck_hgpr", 0)),
                               float(r.get("stck_lwpr", 0)), float(r.get("stck_prpr", 0)),
                               int(float(r.get("cntg_vol", 0))))
                    except (ValueError, TypeError):
                        continue
                    if o1v[0] > 0:
                        one_min[hhmm] = o1v
                # 다음 페이지: 가장 이른 시각 1분 전
                earliest = min(str(r.get("stck_cntg_hour", "9999"))[:6] for r in rows)
                if earliest <= "090000":
                    break
                t = datetime.datetime.strptime(earliest.ljust(6, "0"), "%H%M%S") - datetime.timedelta(minutes=1)
                cursor = t.strftime("%H%M%S")
                if len(one_min) >= need_1min:
                    break

            if not one_min:
                return []
            # 1분봉 → N분봉 집계 (시각 오름차순)
            items = sorted(one_min.items())  # [(HHMM,[o,h,l,c,v]), ...]
            agg = []
            bucket = []
            def _flush(b):
                if not b:
                    return None
                o = b[0][1][0]; c = b[-1][1][3]
                h = max(x[1][1] for x in b); l = min(x[1][2] for x in b)
                v = sum(x[1][4] for x in b)
                return Candle(b[0][0], o, h, l, c, v)
            for hhmm, ohlcv in items:
                bucket.append((hhmm, ohlcv))
                mm = int(hhmm[2:4])
                if mm % minutes == (minutes - 1) or len(bucket) >= minutes:
                    cd = _flush(bucket)
                    if cd:
                        agg.append(cd)
                    bucket = []
            tail = _flush(bucket)
            if tail:
                agg.append(tail)
            return agg[-count:] if len(agg) > count else agg
        except Exception as e:
            self.logger.debug(f"{symbol} 분봉 조회 실패: {e}")
            return []
