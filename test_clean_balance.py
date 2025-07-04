"""
깨끗한 KIS API 클라이언트로 예수금 조회 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_clean import KISAPIClient
from kis_api_with_token_manager import KISAPIClientWithTokenManager

def test_clean_balance():
    """깨끗한 API 클라이언트로 예수금 조회"""
    print("🧪 깨끗한 KIS API 클라이언트 테스트")
    print("=" * 50)
    
    # 토큰 매니저 클라이언트로 토큰 준비
    token_client = KISAPIClientWithTokenManager()
    print("🔑 토큰 준비 중...")
    
    if not token_client.ensure_token_valid():
        print("❌ 토큰 준비 실패")
        return False
    
    print("✅ 토큰 준비 완료")
    
    # 깨끗한 API 클라이언트 생성하고 토큰 복사
    clean_client = KISAPIClient()
    clean_client.access_token = token_client.access_token
    clean_client.token_expires_at = getattr(token_client, 'token_expires_at', 0)
    
    print("\n💰 깨끗한 클라이언트로 예수금 조회...")
    
    try:
        balance = clean_client.get_account_balance()
        
        if balance:
            print(f"✅ 예수금 조회 성공!")
            print(f"💵 예수금: ${balance['cash']:.2f}")
            print(f"📊 보유종목: {len(balance['positions'])}개")
            
            if balance['positions']:
                print("\n📋 보유 종목:")
                for i, pos in enumerate(balance['positions'][:3]):  # 최대 3개만 표시
                    symbol = pos.get('ovrs_pdno', 'N/A')
                    qty = pos.get('ovrs_cblc_qty', '0')
                    price = pos.get('pchs_avg_pric', '0')
                    print(f"  {i+1}. {symbol}: {qty}주 @ ${price}")
            
            return True
        else:
            print("❌ 예수금 조회 실패")
            return False
            
    except Exception as e:
        print(f"❌ 예수금 조회 중 오류: {e}")
        return False

if __name__ == "__main__":
    test_clean_balance() 