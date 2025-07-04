"""
예수금과 보유종목만 간단히 조회
종목 검증 없이 바로 계좌 현황만 확인
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kis_api_with_token_manager import KISAPIClientWithTokenManager
import time

def show_account_status():
    """계좌 현황만 간단히 표시"""
    print("=" * 60)
    print("💰 계좌 현황 조회 (종목 검증 없음)")
    print("=" * 60)
    
    # 토큰 매니저 클라이언트 사용 (기존 토큰 재활용)
    api_client = KISAPIClientWithTokenManager()
    
    # 토큰 확인 (새로 발급 안 함)
    print("🔑 기존 토큰 상태 확인...")
    if api_client.access_token:
        remaining_time = api_client.token_expires_at - time.time()
        print(f"✅ 기존 토큰 사용 (남은시간: {remaining_time/3600:.1f}시간)")
    else:
        print("🔄 토큰 발급 중...")
        if not api_client.ensure_token_valid():
            print("❌ 토큰 발급 실패")
            return
    
    print("\n💰 예수금 및 보유종목 조회 중...")
    
    try:
        # 계좌 잔고 조회
        balance = api_client.get_account_balance()
        
        if not balance:
            print("❌ 계좌 조회 실패")
            return
        
        # 예수금 표시
        cash = balance.get('cash', 0)
        print(f"\n💵 예수금: ${cash:,.2f}")
        
        # 보유종목 표시
        positions = balance.get('positions', [])
        print(f"📊 보유종목: {len(positions)}개")
        
        if positions:
            print("\n" + "-" * 60)
            print("📈 보유종목 상세:")
            print(f"{'번호':>3} {'종목':>6} {'수량':>8} {'평균가':>10}")
            print("-" * 60)
            
            for i, pos in enumerate(positions, 1):
                symbol = pos.get('ovrs_pdno', 'N/A')
                quantity = pos.get('ovrs_cblc_qty', '0')
                avg_price = pos.get('pchs_avg_pric', '0')
                
                try:
                    qty = int(quantity)
                    price = float(avg_price)
                    print(f"{i:3d} {symbol:>6} {qty:8d}주 ${price:8.2f}")
                except:
                    print(f"{i:3d} {symbol:>6} {quantity:>8} {avg_price:>10}")
            
            print("-" * 60)
        else:
            print("📭 보유종목 없음")
        
        print("\n✅ 계좌 현황 조회 완료")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    show_account_status() 