"""
SES 종목 현재가 조회 및 매매 조건 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from start_auto_trading import ProductionTradingSystem
import logging

def test_ses_trading():
    """SES 종목 매매 테스트"""
    print("=== 🔧 SES 종목 매매 테스트 ===")
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # 자동매매 시스템 초기화
        trading_system = ProductionTradingSystem()
        
        # 토큰 발급 확인
        if not trading_system.api_client.ensure_token_valid():
            print("❌ 토큰 발급 실패")
            return False
        
        print("✅ 토큰 발급 성공")
        
        # SES 현재가 조회 테스트
        print("\n1️⃣ SES 현재가 조회 테스트...")
        ses_price = trading_system.get_current_price_with_fallback("SES")
        if ses_price:
            print(f"✅ SES 현재가: ${ses_price:.2f}")
        else:
            print("❌ SES 현재가 조회 실패")
            return False
        
        # 다른 종목들도 테스트
        test_symbols = ["AAPL", "MSFT", "NVDA", "SES"]
        print("\n2️⃣ 여러 종목 현재가 조회 테스트...")
        for symbol in test_symbols:
            price = trading_system.get_current_price_with_fallback(symbol)
            if price:
                print(f"✅ {symbol}: ${price:.2f}")
            else:
                print(f"❌ {symbol}: 조회 실패")
        
        # 매수 조건 테스트 (SES가 하락 종목에 포함되는지)
        print("\n3️⃣ 매수 조건 테스트...")
        filter_passed = trading_system.strategy.check_filter_condition()
        print(f"필터 조건: {'충족' if filter_passed else '미충족'}")
        
        if filter_passed:
            top_declining = trading_system.strategy.get_top_declining_stocks(5)
            print(f"상위 하락 종목: {top_declining}")
            
            if "SES" in top_declining:
                print("✅ SES가 하락 종목에 포함됨 - 매수 대상")
            else:
                print("ℹ️ SES가 하락 종목에 포함되지 않음")
        
        # 매도 조건 테스트 (SES 보유 시)
        print("\n4️⃣ 매도 조건 테스트...")
        # 가상의 SES 보유 상황 시뮬레이션
        avg_buy_price = 2.00  # 가상 매수 가격
        current_price = ses_price
        profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
        
        print(f"SES 가상 매수가: ${avg_buy_price:.2f}")
        print(f"SES 현재가: ${current_price:.2f}")
        print(f"SES 수익률: {profit_rate:.2f}%")
        
        if profit_rate >= 5:
            print("✅ SES 매도 조건 충족 (5% 이상 수익)")
        elif profit_rate > 0:
            print("💰 SES 일반 매도 조건 충족 (수익 중)")
        else:
            print("📉 SES 매도 조건 미충족 (손실 중)")
        
        print("\n=== ✅ SES 종목 매매 테스트 완료 ===")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        logger.error(f"테스트 오류: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_ses_trading() 