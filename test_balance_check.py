# test_balance_check.py
"""
예수금, 잔고, 수익률 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from start_auto_trading import ProductionTradingSystem

def test_balance_status():
    """잔고 상태 테스트"""
    print("=" * 60)
    print("💰 예수금, 잔고, 수익률 테스트")
    print("=" * 60)
    
    try:
        # ProductionTradingSystem 인스턴스 생성
        system = ProductionTradingSystem()
        
        # 잔고 조회
        print("🔍 잔고 조회 중...")
        balance = system.get_balance_with_kis_api()
        
        if not balance:
            print("❌ 잔고 조회 실패")
            return
        
        print("✅ 잔고 조회 성공!")
        print()
        
        # 예수금
        cash = float(balance.get("cash", 0))
        print(f"💰 예수금: ${cash:,.2f}")
        print()
        
        # 보유 종목
        positions = balance.get("positions", [])
        print(f"📈 보유 종목 수: {len(positions)}개")
        
        if positions:
            print("-" * 70)
            print(f"{'번호':>3} {'종목':>8} {'수량':>8} {'평균단가':>10} {'현재가':>10} {'수익률':>8} {'수익금액':>12}")
            print("-" * 70)
            
            total_profit = 0
            total_invested = 0
            
            for i, position in enumerate(positions, 1):
                symbol = position.get("ovrs_pdno", "N/A")
                quantity = float(position.get("ovrs_cblc_qty", 0))
                avg_price = float(position.get("pchs_avg_pric", 0))
                current_price = float(position.get("ovrs_now_pric1", 0))
                
                if quantity > 0 and avg_price > 0:
                    profit = (current_price - avg_price) * quantity
                    profit_rate = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
                    invested = avg_price * quantity
                    
                    total_profit += profit
                    total_invested += invested
                    
                    emoji = "🔥" if profit_rate >= 5 else "💰" if profit_rate > 0 else "📉"
                    print(f"{i:3} {symbol:>8} {quantity:8.2f} ${avg_price:8.2f} ${current_price:8.2f} {profit_rate:+6.2f}% ${profit:+10.2f} {emoji}")
                else:
                    print(f"{i:3} {symbol:>8} {'N/A':>8} {'N/A':>10} {'N/A':>10} {'N/A':>8} {'N/A':>12} ⚠️")
            
            print("-" * 70)
            print(f"📊 총 투자금액: ${total_invested:,.2f}")
            print(f"📈 총 평가손익: ${total_profit:+,.2f}")
            if total_invested > 0:
                total_profit_rate = (total_profit / total_invested) * 100
                print(f"📊 전체 수익률: {total_profit_rate:+.2f}%")
        else:
            print("📭 보유 종목 없음")
        
        # 총 평가금액, 총 매입금액
        total_eval_amt = float(balance.get("total_eval_amt", 0))
        total_purchase_amt = float(balance.get("total_purchase_amt", 0))
        
        print()
        print("📋 계좌 요약:")
        print(f"   💰 예수금: ${cash:,.2f}")
        print(f"   📈 총 평가금액: ${total_eval_amt:,.2f}")
        print(f"   💵 총 매입금액: ${total_purchase_amt:,.2f}")
        
        if total_purchase_amt > 0:
            overall_profit_rate = (total_eval_amt - total_purchase_amt) / total_purchase_amt * 100
            print(f"   📊 전체 수익률: {overall_profit_rate:+.2f}%")
        
        total_account_value = cash + total_eval_amt
        print(f"   💎 총 계좌가치: ${total_account_value:,.2f}")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_balance_status() 