"""
가격 조회 수정사항 테스트 스크립트
시장 폐장 시에도 yfinance로 가격을 가져오는지 확인
"""
import logging
from kis_api import KISAPIClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_price_fetching():
    """가격 조회 테스트"""
    print("=" * 60)
    print("가격 조회 수정사항 테스트")
    print("=" * 60)

    # API 클라이언트 초기화
    client = KISAPIClient()

    # 시장 개장 여부 확인
    is_open = client.is_market_open()
    print(f"\n현재 시장 상태: {'개장' if is_open else '폐장'}")

    # 테스트 종목 목록
    test_symbols = ['SOUN', 'RGTI', 'SMCI', 'QUBT', 'INOD', 'PDYN']

    print(f"\n테스트 종목: {', '.join(test_symbols)}")
    print("-" * 60)

    results = []
    for symbol in test_symbols:
        print(f"\n[{symbol}] 가격 조회 중...")
        price = client.get_current_price(symbol)

        if price:
            print(f"✅ {symbol}: ${price:.2f}")
            results.append((symbol, price, "성공"))
        else:
            print(f"❌ {symbol}: 가격 조회 실패")
            results.append((symbol, None, "실패"))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    success_count = sum(1 for _, _, status in results if status == "성공")
    fail_count = len(results) - success_count

    for symbol, price, status in results:
        status_icon = "✅" if status == "성공" else "❌"
        price_str = f"${price:.2f}" if price else "N/A"
        print(f"{status_icon} {symbol:6s}: {price_str:>10s}  ({status})")

    print("-" * 60)
    print(f"총 {len(results)}개 종목 중 {success_count}개 성공, {fail_count}개 실패")
    print(f"성공률: {success_count/len(results)*100:.1f}%")

    if success_count == len(results):
        print("\n🎉 모든 종목 가격 조회 성공!")
        return True
    else:
        print(f"\n⚠️ {fail_count}개 종목 가격 조회 실패")
        return False

if __name__ == "__main__":
    try:
        success = test_price_fetching()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
