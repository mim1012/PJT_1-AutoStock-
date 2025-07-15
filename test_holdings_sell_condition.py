"""
현재 보유주식의 매도조건(수익률) 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from start_auto_trading import ProductionTradingSystem, PROFIT_THRESHOLD
import logging

def test_holdings_sell_condition():
    print("=== 🔧 보유주식 매도조건 테스트 ===")
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        trading_system = ProductionTradingSystem()
        
        # 잔고 조회
        balance = trading_system.get_balance_with_mojito()
        if not balance or not balance['positions']:
            print("❌ 보유 종목이 없습니다.")
            return
        
        print(f"보유 종목 수: {len(balance['positions'])}")
        print("\n[보유주식 매도조건 테스트 결과]")
        for p in balance['positions']:
            symbol = p.get("pdno", "-")
            name = p.get("prdt_name", "-").strip()
            qty = float(p.get("cblc_qty13", 0))
            avg_price = float(p.get("pchs_avg_pric", 0))
            
            # 현재가 조회 (KIS API + yfinance fallback)
            current_price = trading_system.get_current_price_with_fallback(symbol)
            if current_price is None or avg_price == 0 or qty == 0:
                print(f"- {symbol} ({name}): 데이터 부족 (현재가/평균가/수량 확인 필요)")
                continue
            
            profit_rate = ((current_price - avg_price) / avg_price) * 100
            profit_amount = (current_price - avg_price) * qty
            
            print(f"- {symbol} ({name}) | 수량: {qty:.2f} | 평균가: ${avg_price:.2f} | 현재가: ${current_price:.2f} | 수익률: {profit_rate:.2f}% | 손익: ${profit_amount:.2f}")
            if profit_rate >= PROFIT_THRESHOLD * 100:
                print(f"  ✅ 매도조건 충족 (수익률 {profit_rate:.2f}% ≥ {PROFIT_THRESHOLD*100:.2f}%)")
            elif profit_rate > 0:
                print(f"  💰 일반 매도조건 (수익 중) (수익률 {profit_rate:.2f}%)")
            else:
                print(f"  📉 매도조건 미충족 (손실 중)")
        print("\n=== 테스트 완료 ===")
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        logger.error(f"테스트 오류: {e}", exc_info=True)

if __name__ == "__main__":
    test_holdings_sell_condition() 