"""
토큰 발급 및 잔고 조회 테스트 (수정된 버전)
"""
import logging
from kis_api import KISAPIClient
from token_manager import TokenManager
from utils_balance import print_positions_table

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_token_and_balance():
    """토큰 발급 및 잔고 조회 테스트"""
    print("=== 토큰 발급 및 잔고 조회 테스트 ===")
    
    # 1. TokenManager 직접 테스트
    print("\n1. TokenManager 직접 테스트")
    token_manager = TokenManager()
    
    # 토큰 정보 확인
    print("현재 토큰 상태:")
    print(token_manager.get_token_info())
    
    # 유효한 토큰 가져오기
    print("\n유효한 토큰 가져오기 시도...")
    token = token_manager.get_valid_token()
    if token:
        print(f"✅ 토큰 발급 성공: {token[:20]}...")
    else:
        print("❌ 토큰 발급 실패")
        return
    
    # 2. KISAPIClient 테스트
    print("\n2. KISAPIClient 테스트")
    client = KISAPIClient()
    
    # 토큰 유효성 확인
    print("토큰 유효성 확인...")
    if client.ensure_token_valid():
        print("✅ 토큰 유효성 확인 성공")
    else:
        print("❌ 토큰 유효성 확인 실패")
        return
    
    # 잔고 조회
    print("\n잔고 조회 시도...")
    balance = client.get_account_balance()
    if balance:
        print("✅ 잔고 조회 성공")
        print(f"예수금: ${balance['cash']:.2f}")
        print(f"보유종목 수: {len(balance['positions'])}")
        positions = balance['positions']
        if positions:
            print("\n[보유종목 상세]")
            print_positions_table(positions)
        else:
            print("보유종목 없음")
    else:
        print("❌ 잔고 조회 실패")

if __name__ == "__main__":
    test_token_and_balance() 