"""
예수금 조회 전용 테스트 도구
한국투자증권 API의 예수금 조회 기능만 집중적으로 테스트
"""
import sys
import os
import json
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from kis_api import KISAPIClient  # 직접 import 추가
from config import *

class BalanceTester:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        # 혹시 상속 문제가 있을 경우를 대비해 직접 클래스도 준비
        self.direct_api_client = KISAPIClient()
        self.setup_logging()
        
    def setup_logging(self):
        """디버깅용 로깅 설정"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('balance_test.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def test_token_first(self):
        """토큰 상태 먼저 확인"""
        print("\n" + "="*60)
        print("🔑 토큰 상태 확인")
        print("="*60)
        
        if self.api_client.ensure_token_valid():
            print("✅ 토큰 준비 완료")
            if hasattr(self.api_client, 'access_token') and self.api_client.access_token:
                print(f"🔗 토큰: {self.api_client.access_token[:20]}...")
            
            # 직접 API 클라이언트에도 토큰 복사
            if hasattr(self.api_client, 'access_token'):
                self.direct_api_client.access_token = self.api_client.access_token
                self.direct_api_client.token_expires_at = getattr(self.api_client, 'token_expires_at', 0)
            
            return True
        else:
            print("❌ 토큰 준비 실패")
            return False
    
    def test_basic_balance(self):
        """기본 예수금 조회 테스트"""
        print("\n" + "="*60)
        print("💰 기본 예수금 조회 테스트")
        print("="*60)
        
        try:
            # 상속된 메소드 확인
            if hasattr(self.api_client, 'get_account_balance'):
                print("✅ get_account_balance 메소드 존재 확인")
                balance = self.api_client.get_account_balance()
            else:
                print("⚠️ 상속 문제로 직접 API 클라이언트 사용")
                balance = self.direct_api_client.get_account_balance()
            
            if balance:
                print(f"✅ 예수금 조회 성공:")
                print(f"   💵 예수금: ${balance['cash']:.2f}")
                print(f"   📊 보유종목: {len(balance['positions'])}개")
                
                if balance['positions']:
                    print("   📋 보유종목 목록:")
                    for i, pos in enumerate(balance['positions'][:5]):  # 최대 5개만 표시
                        symbol = pos.get('ovrs_pdno', 'N/A')
                        qty = pos.get('ovrs_cblc_qty', '0')
                        avg_price = pos.get('pchs_avg_pric', '0')
                        print(f"      {i+1}. {symbol}: {qty}주 @ ${avg_price}")
                
                return balance
            else:
                print("❌ 예수금 조회 실패")
                return None
                
        except Exception as e:
            print(f"❌ 예수금 조회 중 오류: {e}")
            return None
    
    def test_raw_api_call(self):
        """원시 API 호출로 상세 분석"""
        print("\n" + "="*60)
        print("🔍 원시 API 호출 분석")
        print("="*60)
        
        url = f"{self.api_client.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
        tr_id = "VTTS3012R" if USE_PAPER_TRADING else "TTTS3012R"
        
        print(f"🌐 호출 URL: {url}")
        print(f"📋 TR_ID: {tr_id}")
        print(f"🏦 계좌번호: {self.api_client.account_number}")
        print(f"🔄 모드: {'모의투자' if USE_PAPER_TRADING else '실전투자'}")
        
        headers = self.api_client.get_headers(tr_id)
        params = {
            "CANO": self.api_client.account_number.split("-")[0],
            "ACNT_PRDT_CD": self.api_client.account_number.split("-")[1],
            "OVRS_EXCG_CD": "NASD", 
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "", 
            "CTX_AREA_NK200": ""
        }
        
        print(f"📨 요청 파라미터:")
        for key, value in params.items():
            print(f"   {key}: {value}")
        
        try:
            result = self.api_client._request("GET", url, headers, params=params)
            
            if result:
                print(f"\n📦 API 응답 분석:")
                print(f"   응답 코드(rt_cd): {result.get('rt_cd')}")
                print(f"   응답 메시지(msg1): {result.get('msg1')}")
                print(f"   메시지 코드(msg_cd): {result.get('msg_cd')}")
                
                # 전체 응답 구조 분석
                print(f"\n🏗️ 응답 구조:")
                for key in result.keys():
                    if key in ['output1', 'output2']:
                        data = result[key]
                        if isinstance(data, list):
                            print(f"   {key}: 리스트 (길이: {len(data)})")
                        elif isinstance(data, dict):
                            print(f"   {key}: 딕셔너리 (키 개수: {len(data)})")
                        else:
                            print(f"   {key}: {type(data)}")
                    else:
                        print(f"   {key}: {result[key]}")
                
                return result
            else:
                print("❌ API 응답 없음")
                return None
                
        except Exception as e:
            print(f"❌ 원시 API 호출 오류: {e}")
            return None
    
    def analyze_balance_fields(self, result):
        """예수금 필드 상세 분석 (수정된 버전)"""
        if not result:
            return
            
        print("\n" + "="*60)
        print("🔬 예수금 필드 상세 분석")
        print("="*60)
        
        # output2 분석 (dict 또는 list 모두 처리)
        output2 = result.get("output2", {})
        print(f"💱 통화 정보 (output2): {type(output2)}")
        
        if isinstance(output2, dict):
            print(f"   📊 딕셔너리 형태 - 키 개수: {len(output2)}")
            print(f"   🔑 키 목록: {list(output2.keys())}")
            
            # 딕셔너리인 경우 모든 키-값 쌍 출력
            print(f"\n   💵 모든 필드 분석:")
            for key, value in output2.items():
                print(f"      {key}: {value}")
                
            # USD 관련 필드 찾기
            print(f"\n   🔍 USD 관련 필드 검색:")
            usd_fields = []
            for key, value in output2.items():
                if 'usd' in key.lower() or 'crcy' in key.lower() or 'amt' in key.lower():
                    usd_fields.append((key, value))
                    try:
                        float_value = float(value) if value else 0.0
                        print(f"      ✅ {key}: {value} (${float_value:.2f})")
                    except (ValueError, TypeError):
                        print(f"      ⚠️ {key}: {value} (변환 불가)")
            
            if not usd_fields:
                print("      ❌ USD 관련 필드를 찾지 못했습니다")
                
        elif isinstance(output2, list):
            print(f"   📊 리스트 형태 - 길이: {len(output2)}")
            for i, currency_info in enumerate(output2):
                print(f"\n   통화 정보 [{i}]:")
                if isinstance(currency_info, dict):
                    for key, value in currency_info.items():
                        print(f"      {key}: {value}")
                        
                    # USD 통화인 경우 예수금 관련 필드들 특별 분석
                    if currency_info.get("crcy_cd") == "USD":
                        print(f"\n   💵 USD 예수금 분석:")
                        
                        # 가능한 예수금 필드들
                        balance_fields = [
                            "frcr_dncl_amt_2",  # 외화예수금2
                            "frcr_evlu_amt2",   # 외화평가금액2  
                            "tot_evlu_amt",     # 총평가금액
                            "frcr_buy_amt_smtl", # 외화매수금액합계
                            "evlu_amt_smtl_amt", # 평가금액합계
                            "frcr_dncl_amt",    # 외화예수금
                            "thdt_buy_amt",     # 당일매수금액
                            "dnca_tot_amt",     # 예수금총액
                        ]
                        
                        for field in balance_fields:
                            if field in currency_info:
                                value = currency_info[field]
                                try:
                                    float_value = float(value) if value else 0.0
                                    print(f"      ✅ {field}: {value} (${float_value:.2f})")
                                except (ValueError, TypeError):
                                    print(f"      ⚠️ {field}: {value} (변환 불가)")
                            else:
                                print(f"      ❌ {field}: 필드 없음")
        else:
            print(f"   ⚠️ 예상치 못한 output2 타입: {type(output2)}")
            print(f"   📄 내용: {output2}")
        
        # output1 (보유종목) 분석
        output1 = result.get("output1", [])
        print(f"\n📊 보유종목 (output1): {len(output1)}개")
        
        if output1 and len(output1) > 0:
            print(f"   첫 번째 종목 필드 예시:")
            first_position = output1[0]
            for key, value in first_position.items():
                print(f"      {key}: {value}")
    
    def test_different_tr_ids(self):
        """다른 TR_ID로도 테스트"""
        print("\n" + "="*60)
        print("🔄 다른 TR_ID 테스트")
        print("="*60)
        
        # 모의투자와 실전투자 TR_ID 모두 테스트
        tr_ids = [
            ("VTTS3012R", "모의투자"),
            ("TTTS3012R", "실전투자")
        ]
        
        for tr_id, mode in tr_ids:
            print(f"\n🧪 {mode} TR_ID 테스트: {tr_id}")
            
            url = f"{self.api_client.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
            headers = self.api_client.get_headers(tr_id)
            params = {
                "CANO": self.api_client.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.api_client.account_number.split("-")[1],
                "OVRS_EXCG_CD": "NASD", 
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "", 
                "CTX_AREA_NK200": ""
            }
            
            try:
                result = self.api_client._request("GET", url, headers, params=params)
                
                if result and result.get("rt_cd") == "0":
                    print(f"   ✅ {mode} 호출 성공")
                    
                    # output2에서 예수금 찾기 (dict/list 모두 처리)
                    output2 = result.get("output2", {})
                    cash_found = False
                    
                    if isinstance(output2, dict):
                        print(f"      📊 응답 타입: 딕셔너리")
                        for key, value in output2.items():
                            if 'amt' in key.lower() or 'cash' in key.lower():
                                try:
                                    cash = float(value) if value else 0.0
                                    if cash > 0:
                                        print(f"      💰 {key}에서 예수금 발견: ${cash:.2f}")
                                        cash_found = True
                                except:
                                    pass
                    elif isinstance(output2, list):
                        print(f"      📊 응답 타입: 리스트")
                        for currency_info in output2:
                            if isinstance(currency_info, dict) and currency_info.get("crcy_cd") == "USD":
                                for field in ["frcr_dncl_amt_2", "frcr_evlu_amt2", "tot_evlu_amt"]:
                                    value = currency_info.get(field, "0")
                                    try:
                                        cash = float(value)
                                        if cash > 0:
                                            print(f"      💰 {field}에서 예수금 발견: ${cash:.2f}")
                                            cash_found = True
                                    except:
                                        pass
                    
                    if not cash_found:
                        print(f"      ⚠️ {mode}에서 예수금 찾지 못함")
                        
                elif result:
                    print(f"   ❌ {mode} 호출 실패: {result.get('msg1')}")
                else:
                    print(f"   ❌ {mode} 응답 없음")
                    
            except Exception as e:
                print(f"   ❌ {mode} 테스트 오류: {e}")
    
    def run_comprehensive_test(self):
        """종합 테스트 실행"""
        print("🚀 예수금 조회 종합 테스트 시작")
        print(f"⏰ 테스트 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 토큰 확인
        if not self.test_token_first():
            print("❌ 토큰 문제로 테스트 중단")
            return False
        
        # 2. 기본 예수금 조회
        balance = self.test_basic_balance()
        
        # 3. 원시 API 호출 분석
        result = self.test_raw_api_call()
        
        # 4. 필드 상세 분석
        if result:
            self.analyze_balance_fields(result)
        
        # 5. 다른 TR_ID 테스트
        self.test_different_tr_ids()
        
        print("\n" + "="*60)
        print("✅ 예수금 조회 종합 테스트 완료")
        print("="*60)
        
        return True

def main():
    """메인 실행 함수"""
    print("💰 한국투자증권 예수금 조회 전용 테스트 (수정된 버전)")
    print("="*60)
    
    tester = BalanceTester()
    tester.run_comprehensive_test()

if __name__ == "__main__":
    main() 