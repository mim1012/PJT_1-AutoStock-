"""
한국/미국 주식 잔고 통합 조회 (테스트용)
사용법: python check_balance.py [us|kr|all]
  - us: 미국 주식만 조회
  - kr: 한국 주식만 조회
  - all: 둘 다 조회 (기본값)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def show_us_balance():
    """미국 주식 잔고 조회"""
    print("=" * 60)
    print("  미국 주식 계좌 현황 (US Stocks)")
    print("=" * 60)

    try:
        from kis_api import KISAPIClient
        api = KISAPIClient()
        balance = api.get_account_balance()

        if not balance:
            print("[ERROR] 미국 주식 잔고 조회 실패")
            return

        cash = balance.get("available_cash", balance.get("cash", 0))
        print(f"\n  예수금: ${cash:,.2f}")

        positions = balance.get("positions", [])
        print(f"  보유종목: {len(positions)}개")

        if positions:
            print()
            print(f"  {'번호':>3}  {'종목':>6}  {'수량':>6}  {'평균가':>10}  {'현재가':>10}  {'수익률':>8}")
            print("  " + "-" * 56)
            for i, p in enumerate(positions, 1):
                sym = p.get("symbol", "N/A")
                qty = p.get("quantity", 0)
                avg = p.get("avg_price", 0.0)
                cur = p.get("current_price", 0.0)
                rate = p.get("profit_rate", 0.0)
                print(f"  {i:3d}  {sym:>6}  {qty:6d}주  ${avg:9.2f}  ${cur:9.2f}  {rate:7.2f}%")
            print("  " + "-" * 56)
        else:
            print("  보유종목 없음")

        print()

    except Exception as e:
        print(f"[ERROR] 미국 주식 조회 오류: {e}")
        print()


def show_kr_balance():
    """한국 주식 잔고 조회"""
    print("=" * 60)
    print("  한국 주식 계좌 현황 (KR Stocks)")
    print("=" * 60)

    try:
        from kr.api_client import KRAPIClient
        api = KRAPIClient()
        balance = api.get_account_balance()

        if not balance:
            print("[ERROR] 한국 주식 잔고 조회 실패")
            return

        cash = balance.get("available_cash", 0)
        total_eval = balance.get("total_eval", 0)
        total_profit = balance.get("total_profit", 0)

        print(f"\n  예수금: {cash:,.0f}원")
        print(f"  총 평가금액: {total_eval:,.0f}원")
        print(f"  총 손익: {total_profit:,.0f}원")

        positions = balance.get("positions", [])
        print(f"  보유종목: {len(positions)}개")

        if positions:
            print()
            print(f"  {'번호':>3}  {'종목코드':>8}  {'종목명':<12}  {'수량':>6}  {'평단가':>10}  {'현재가':>10}  {'수익률':>8}")
            print("  " + "-" * 72)
            for i, p in enumerate(positions, 1):
                sym = p.get("symbol", "N/A")
                name = p.get("name", "")
                qty = p.get("quantity", 0)
                avg = p.get("avg_price", 0.0)
                cur = p.get("current_price", 0.0)
                rate = p.get("profit_rate", 0.0)
                print(f"  {i:3d}  {sym:>8}  {name:<12}  {qty:6d}주  {avg:9,.0f}원  {cur:9,.0f}원  {rate:7.2f}%")
            print("  " + "-" * 72)
        else:
            print("  보유종목 없음")

        print()

    except Exception as e:
        print(f"[ERROR] 한국 주식 조회 오류: {e}")
        print()


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print()
    if mode == "us":
        show_us_balance()
    elif mode == "kr":
        show_kr_balance()
    else:
        show_us_balance()
        show_kr_balance()

    print("[DONE] 잔고 조회 완료")
