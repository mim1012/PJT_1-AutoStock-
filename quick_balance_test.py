"""
수정된 예수금 조회 기능 빠른 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient
from kis_api_with_token_manager import KISAPIClientWithTokenManager
from config import *
# 
def test_balance_fix():
    """수정된 예수금 조회 테스트"""
    print("💰 수정된 예수금 조회 기능 테스트")
    print("="*50)
    
    # 토큰 매니저 클라이언트 사용
    client = KISAPIClientWithTokenManager()
    
    print("🔑 토큰 확인 중...")
    if not client.ensure_token_valid():
        print("❌ 토큰 준비 실패")
        return False
    
    print("✅ 토큰 준비 완료")
    
    # 직접 API 클라이언트에 토큰 복사
    direct_client = KISAPIClient()
    direct_client.access_token = client.access_token
    direct_client.token_expires_at = getattr(client, 'token_expires_at', 0)
    
    print("\n💰 예수금 조회 테스트 중...")
    try:
        balance = direct_client.get_account_balance()
        
        if balance:
            print("🎉 예수금 조회 성공!")
            print(f"   💵 예수금: ${balance['cash']:,.2f}")
            print(f"   📊 보유종목: {len(balance['positions'])}개")
            
            if balance['positions']:
                print("\n📋 보유종목:")
                for i, pos in enumerate(balance['positions']):
                    symbol = pos.get('ovrs_pdno', 'N/A')
                    qty = pos.get('ovrs_cblc_qty', '0')
                    avg_price = float(pos.get('pchs_avg_pric', '0'))
                    current_value = float(pos.get('ovrs_stck_evlu_amt', '0'))
                    profit_rate = float(pos.get('evlu_pfls_rt', '0'))
                    
                    print(f"   {i+1}. {symbol}: {qty}주")
                    print(f"      평균가: ${avg_price:.2f}")
                    print(f"      평가액: ${current_value:.2f}")
                    print(f"      수익률: {profit_rate:.1f}%")
            
            return True
        else:
            print("❌ 예수금 조회 실패")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        return False

if __name__ == "__main__":
    test_balance_fix() 