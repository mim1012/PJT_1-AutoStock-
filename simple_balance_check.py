"""
예수금과 보유종목만 간단히 조회
종목 검증 없이 바로 계좌 현황만 확인
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient

def show_account_status():
    """계좌 현황만 간단히 표시"""
    print("=" * 60)
    print("계좌 현황 조회")
    print("=" * 60)

    # KIS API 클라이언트 사용
    api_client = KISAPIClient()
    
    print("\n[INFO] 예수금 및 보유종목 조회 중...")
    
    try:
        # 계좌 잔고 조회
        balance = api_client.get_account_balance()
        
        if not balance:
            print("[ERROR] 계좌 조회 실패")
            return
        
        # 예수금 표시
        cash = balance.get('cash', 0)
        print(f"\n[CASH] ${cash:,.2f}")
        
        # 보유종목 표시
        positions = balance.get('positions', [])
        print(f"보유종목: {len(positions)}개")

        if positions:
            print("\n" + "-" * 60)
            print("보유종목 상세:")
            print(f"{'번호':>3} {'종목':>8} {'수량':>8} {'평균가':>10}")
            print("-" * 60)

            for i, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'N/A')
                item_name = pos.get('item_name', '')
                quantity = pos.get('quantity', 0)
                avg_price = pos.get('avg_price', 0.0)

                print(f"{i:3d} {symbol:>8} {quantity:8d}주 ${avg_price:8.2f}")
            
            print("-" * 60)
        else:
            print("[INFO] 보유종목 없음")

        print("\n[SUCCESS] 계좌 현황 조회 완료")

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")

if __name__ == "__main__":
    show_account_status() 