"""
계좌 설정 문제 진단 및 해결 도구
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
from config import *
import json

class AccountDebugger:
    def __init__(self):
        self.api_client = KISAPIClientWithTokenManager()
        
        print("🔍 계좌 설정 문제 진단 도구")
        print("="*50)
    
    def check_account_config(self):
        """계좌 설정 확인"""
        print("\n📋 현재 설정 확인")
        print("-"*30)
        
        print(f"🏦 계좌번호: {KIS_ACCOUNT_NUMBER}")
        print(f"🔑 API 키: {KIS_APP_KEY[:10]}...")
        print(f"🌐 Base URL: {KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL}")
        print(f"📊 모의투자 모드: {'ON' if USE_PAPER_TRADING else 'OFF'}")
        
        # 계좌번호 형식 확인
        if "-" in KIS_ACCOUNT_NUMBER:
            parts = KIS_ACCOUNT_NUMBER.split("-")
            print(f"   📄 계좌코드: {parts[0]}")
            print(f"   📄 상품코드: {parts[1]}")
        else:
            print("❌ 계좌번호 형식 오류 (XX-XX 형태여야 함)")
    
    def test_token_and_balance(self):
        """토큰 및 잔고 확인"""
        print("\n🔑 토큰 및 API 연결 테스트")
        print("-"*30)
        
        # 토큰 갱신
        if not self.api_client.ensure_token_valid():
            print("❌ 토큰 발급 실패")
            return False
        
        print("✅ 토큰 발급 성공")
        
        # 잔고 조회 시도
        try:
            balance = self.api_client.get_account_balance()
            if balance:
                print("✅ 계좌 조회 성공")
                print(f"   💵 예수금: ${balance['cash']:,.2f}")
                print(f"   📦 보유종목: {len(balance['positions'])}개")
                
                # 예수금이 0인 경우 경고
                if balance['cash'] == 0:
                    print("⚠️ 예수금이 $0입니다. 모의투자 계좌에 가상 자금이 없을 수 있습니다.")
                    return False
                    
                return True
            else:
                print("❌ 계좌 조회 실패")
                return False
        except Exception as e:
            print(f"❌ 계좌 조회 오류: {e}")
            return False
    
    def test_different_tr_ids(self):
        """다양한 TR_ID로 주문 테스트"""
        print("\n🧪 다양한 TR_ID 주문 테스트")
        print("-"*30)
        
        # 테스트할 TR_ID 조합들
        tr_id_combinations = [
            ("VTTS1002U", "모의투자 매수 (현재 설정)"),
            ("VTTC0802U", "모의투자 해외주식 주문"),
            ("JTTT1002U", "실전투자 매수 (테스트용)"),
        ]
        
        test_symbol = "AAPL"
        test_quantity = 1
        
        # 현재가 조회
        current_price = self.api_client.get_current_price(test_symbol)
        if not current_price:
            print(f"❌ {test_symbol} 현재가 조회 실패")
            return
        
        print(f"📊 테스트 종목: {test_symbol} @ ${current_price:.2f}")
        print("\n각 TR_ID별 주문 테스트 (실제 주문은 하지 않음):")
        
        for tr_id, description in tr_id_combinations:
            print(f"\n🔬 {description} ({tr_id})")
            
            # API 직접 호출로 테스트
            url = f"{self.api_client.base_url}/uapi/overseas-stock/v1/trading/order"
            headers = self.api_client.get_headers(tr_id)
            
            data = {
                "CANO": KIS_ACCOUNT_NUMBER.split("-")[0],
                "ACNT_PRDT_CD": KIS_ACCOUNT_NUMBER.split("-")[1],
                "OVRS_EXCG_CD": "NASD",
                "PDNO": test_symbol,
                "ORD_QTY": str(test_quantity),
                "OVRS_ORD_UNPR": f"{current_price:.2f}",
                "ORD_DVSN": "00"
            }
            
            if USE_PAPER_TRADING:
                data["ORD_SVR_DVSN_CD"] = "0"
            
            try:
                # 실제로는 주문하지 않고 헤더와 데이터만 준비해서 에러 확인
                print(f"   📤 요청 데이터: {json.dumps(data, indent=2)}")
                print(f"   📤 TR_ID: {tr_id}")
                
                # 실제 요청 (주석 처리하여 안전)
                # result = self.api_client._request("POST", url, headers, data=data)
                print(f"   ⏭️ 실제 요청은 건너뜀 (안전을 위해)")
                
            except Exception as e:
                print(f"   ❌ 오류: {e}")
    
    def suggest_solutions(self):
        """해결책 제안"""
        print("\n💡 가능한 해결책들")
        print("="*50)
        
        print("1. 🏦 계좌 타입 확인")
        print("   - 한국투자증권 홈페이지/HTS에서 모의투자 계좌가 개설되어 있는지 확인")
        print("   - 모의투자 계좌에 가상 자금이 입금되어 있는지 확인")
        
        print("\n2. 🔑 API 키 확인")
        print("   - 모의투자용 API 키로 발급받았는지 확인")
        print("   - 실전투자용 API 키를 사용하고 있지 않은지 확인")
        
        print("\n3. ⚙️ 설정 변경 시도")
        print("   - config.py에서 다른 계좌번호 사용")
        print("   - 주석 처리된 다른 API 키 시도")
        
        print("\n4. 🌐 URL 확인")
        print("   - 모의투자 URL이 올바른지 확인")
        print("   - 실전투자 모드로 변경해서 테스트 (주의!)")
        
        print("\n5. 📞 고객센터 문의")
        print("   - 한국투자증권 API 고객센터에 모의투자 계좌 활성화 문의")
        
    def run_full_diagnosis(self):
        """전체 진단 실행"""
        print("🩺 계좌 설정 전체 진단 시작")
        print("="*50)
        
        # 1. 설정 확인
        self.check_account_config()
        
        # 2. 토큰 및 잔고 확인
        balance_ok = self.test_token_and_balance()
        
        # 3. TR_ID 테스트
        self.test_different_tr_ids()
        
        # 4. 해결책 제안
        self.suggest_solutions()
        
        # 5. 임시 해결책 제안
        print("\n🔧 임시 해결책")
        print("="*50)
        
        if not balance_ok:
            print("❗ 모의투자 계좌에 문제가 있는 것 같습니다.")
            print("📋 다음 중 하나를 시도해보세요:")
            print("   1. config.py에서 주석 처리된 다른 계좌/API 키 사용")
            print("   2. 실전투자 모드로 변경 (USE_PAPER_TRADING = False)")
            print("   3. 한국투자증권에서 모의투자 계좌 재개설")
            
            choice = input("\n주석 처리된 다른 계좌 설정을 시도해보시겠습니까? (y/n): ")
            if choice.lower() == 'y':
                self.try_alternative_config()
    
    def try_alternative_config(self):
        """다른 계좌 설정 시도"""
        print("\n🔄 다른 계좌 설정으로 테스트")
        print("-"*30)
        
        # config.py 읽기
        try:
            with open('config.py', 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 주석 처리된 계좌 정보 찾기
            if "64721801-01" in config_content:
                print("📋 주석 처리된 다른 계좌 발견: 64721801-01")
                choice = input("이 계좌로 시도해보시겠습니까? (y/n): ")
                
                if choice.lower() == 'y':
                    # config.py 백업 및 수정 안내
                    print("⚠️ config.py 파일을 직접 수정해야 합니다:")
                    print("1. 현재 계좌 정보를 주석 처리")
                    print("2. 주석 처리된 계좌 정보의 주석 해제")
                    print("3. 파일 저장 후 다시 테스트")
            else:
                print("❌ 다른 계좌 정보를 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"❌ config.py 읽기 오류: {e}")

if __name__ == "__main__":
    debugger = AccountDebugger()
    debugger.run_full_diagnosis() 