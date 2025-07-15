"""
blance02.py와 start_auto_trading.py 통합 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from start_auto_trading import ProductionTradingSystem
import logging

def test_integration():
    """통합 테스트 실행"""
    print("=== 🔧 blance02.py + start_auto_trading.py 통합 테스트 ===")
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # 자동매매 시스템 초기화
        trading_system = ProductionTradingSystem()
        
        print("\n1️⃣ 토큰 발급 테스트...")
        if trading_system.api_client.ensure_token_valid():
            print("✅ 토큰 발급 성공")
        else:
            print("❌ 토큰 발급 실패")
            return False
        
        print("\n2️⃣ 잔고 조회 테스트 (blance02.py 방식)...")
        balance = trading_system.get_balance_with_mojito()
        if balance:
            print(f"✅ 잔고 조회 성공")
            print(f"   - 사용가능 외화: ${balance['cash']:,.2f}")
            print(f"   - 보유종목: {len(balance['positions'])}개")
            print(f"   - 총 평가금액: ${balance['eval_amt']:,.2f}")
            print(f"   - 총 매입금액: ${balance['purchase_amt']:,.2f}")
            print(f"   - 수익률: {balance['profit_rate']:.2f}%")
        else:
            print("❌ 잔고 조회 실패")
            return False
        
        print("\n3️⃣ 상세 잔고 출력 테스트...")
        trading_system.display_detailed_balance()
        
        print("\n4️⃣ 안전 점검 테스트...")
        if trading_system.safety_check():
            print("✅ 안전 점검 통과")
        else:
            print("❌ 안전 점검 실패")
            return False
        
        print("\n5️⃣ 운영 시간 확인...")
        if trading_system.is_trading_hours():
            print("✅ 현재 거래시간")
        else:
            print("ℹ️ 현재 거래시간 외")
            time_until = trading_system.get_time_until_trading()
            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)
            print(f"   다음 거래시간까지: {hours}시간 {minutes}분")
        
        print("\n=== ✅ 통합 테스트 완료 ===")
        print("모든 기능이 정상적으로 연동되었습니다!")
        print("이제 start_auto_trading.py를 실행하여 자동매매를 시작할 수 있습니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 통합 테스트 실패: {e}")
        logger.error(f"통합 테스트 오류: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_integration() 