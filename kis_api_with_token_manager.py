"""
토큰 매니저를 사용하는 개선된 KIS API 클라이언트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient
from token_manager import TokenManager
import logging

class KISAPIClientWithTokenManager(KISAPIClient):
    """토큰 매니저를 사용하는 개선된 API 클라이언트"""
    
    def __init__(self):
        super().__init__()
        self.token_manager = TokenManager()
        self.logger = logging.getLogger(__name__)
    
    def ensure_token_valid(self):
        """토큰 유효성 확인 (저장된 토큰 우선 사용)"""
        # 1. 저장된 토큰 확인
        saved_token = self.token_manager.load_token()
        if saved_token:
            self.access_token = saved_token
            # 만료 시간도 설정 (대략적으로)
            import time
            self.token_expires_at = time.time() + 82800  # 23시간으로 안전하게 설정
            self.logger.info("저장된 토큰 사용")
            return True
        
        # 2. 저장된 토큰이 없으면 새로 발급
        self.logger.info("새 토큰 발급 시도...")
        success = self.get_access_token()
        
        if success and self.access_token:
            # 새로 발급받은 토큰 저장
            self.token_manager.save_token(self.access_token, 86400)
            self.logger.info("새 토큰 발급 및 저장 완료")
        
        return success

def test_improved_client():
    """개선된 클라이언트 테스트"""
    print("=== 개선된 KIS API 클라이언트 테스트 ===")
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    client = KISAPIClientWithTokenManager()
    
    # 토큰 확인
    if client.ensure_token_valid():
        print("✅ 토큰 준비 완료")
        
        # 간단한 API 테스트
        print("\n📊 현재가 조회 테스트:")
        test_symbols = ["QSI", "RR"]
        
        for symbol in test_symbols:
            price = client.get_current_price(symbol)
            if price:
                print(f"   {symbol}: ${price:.2f}")
            else:
                print(f"   {symbol}: 조회 실패")
        
        # 계좌 조회 테스트
        print("\n💰 계좌 조회 테스트:")
        balance = client.get_account_balance()
        if balance:
            print(f"   예수금: ${balance['cash']:.2f}")
            print(f"   보유종목: {len(balance['positions'])}개")
        else:
            print("   계좌 조회 실패")
            
        return True
    else:
        print("❌ 토큰 준비 실패")
        return False

if __name__ == "__main__":
    test_improved_client() 