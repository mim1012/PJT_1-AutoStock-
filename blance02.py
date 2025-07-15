# usstockbuyandsell.py
import time
import mojito
import yfinance as yf
from datetime import datetime

from tabulate import tabulate
from datetime import datetime, timedelta
import pprint

# 브로커 설정
key = "PS9Yr8VDczEhRt6kbhrAExgLO9mno70zMJvp"
secret = "2mfGKemkM4CTyvkQ1oquImEb+uUKwrflzTn23wjWJ5/PoFu5dwIW1OoyKYCoY2lPxl7L7ukzQqZD8PylBkYA1/SLFQ4r110XH6YCajAcMCzQnQekj1xBNGAaZo8zltZgX7YkomUzoBKV+8kopKGm3c9+juaQU+NJfM4vwMuyk8wkGFiK4v8="
acc_no = "64721801-01"

broker = mojito.KoreaInvestment(
    api_key=key,
    api_secret=secret,
    acc_no=acc_no,
    exchange='나스닥'
)

def get_current_price_with_fallback(symbol):
    """현재가 조회 (KIS API 실패 시 yfinance로 대체)"""
    try:
        # 1. 먼저 mojito로 현재가 조회 시도
        ticker_info = broker.fetch_ticker(symbol)
        if ticker_info and 'last' in ticker_info and ticker_info['last'] > 0:
            print(f"[가격][KIS] {symbol}: ${ticker_info['last']:.2f}")
            return ticker_info['last']
        
        # 2. KIS API 실패 시 yfinance로 대체
        print(f"[가격][대체] {symbol} KIS API 실패, yfinance 시도")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            current_price = hist['Close'].iloc[-1]
            if current_price > 0:
                print(f"[가격][yfinance] {symbol}: ${current_price:.2f}")
                return current_price
            else:
                print(f"[가격][오류] {symbol} yfinance 가격이 0 이하")
                return None
        else:
            print(f"[가격][오류] {symbol} yfinance 데이터 없음")
            return None
    except Exception as e:
        print(f"[가격][오류] {symbol} 조회 실패: {e}")
        return None

def display_comprehensive_balance():
    """종합 계좌 현황 출력 (보유종목별 수익률 포함)"""
    try:
        print("\n" + "="*80)
        print("📊 종합 계좌 현황 (blance02.py)")
        print("="*80)
        
        balance = broker.fetch_present_balance()
        positions = balance.get("output1", [])
        balance1 = balance.get("output2", [])
        
        # 예수금 정보
        available_cash = 0
        if balance1:
            available_cash = float(balance1[0].get("frcr_drwg_psbl_amt_1", 0))
        
        # 종합 정보
        output3 = balance.get("output3", {})
        eval_amt = float(output3.get("evlu_amt_smtl_amt", 0))  # 평가금액
        purchase_amt = float(output3.get("pchs_amt_smtl_amt", 0))  # 매입금액
        
        # 전체 수익률 계산
        profit_rate = 0
        if purchase_amt != 0:
            profit_rate = (eval_amt - purchase_amt) / purchase_amt * 100
        
        # 1. 계좌 요약 정보
        print(f"💰 사용가능 외화: ${available_cash:,.2f}")
        print(f"📈 총 평가 금액: ${eval_amt:,.2f}")
        print(f"💵 총 매입 금액: ${purchase_amt:,.2f}")
        print(f"📊 전체 수익률: {profit_rate:+.2f}%")
        
        # 2. 보유 종목 상세 정보 (수익률 포함)
        if positions:
            print(f"\n📈 보유 종목 ({len(positions)}개):")
            print("-" * 80)
            print(f"{'번호':>3} {'종목':>8} {'수량':>8} {'평균단가':>10} {'현재가':>10} {'수익률':>8} {'수익금액':>12}")
            print("-" * 80)
            
            total_profit = 0
            high_profit_targets = []
            
            for i, position in enumerate(positions, 1):
                symbol = position.get("pdno", "N/A")
                name = position.get("prdt_name", "").strip()
                quantity = float(position.get("cblc_qty13", 0))
                avg_price = float(position.get("pchs_avg_pric", 0))
                
                if quantity > 0 and avg_price > 0:
                    # 현재가 조회 (yfinance 대체 포함)
                    current_price = get_current_price_with_fallback(symbol)
                    if current_price:
                        profit_rate = ((current_price - avg_price) / avg_price) * 100
                        profit_amount = (current_price - avg_price) * quantity
                        total_profit += profit_amount
                        
                        # 수익률에 따른 이모지
                        emoji = "🔥" if profit_rate >= 5 else "💰" if profit_rate > 0 else "📉" if profit_rate < 0 else "➖"
                        
                        print(f"{i:3} {symbol:>8} {quantity:8.2f}주 ${avg_price:8.2f} ${current_price:8.2f} {profit_rate:+6.2f}% ${profit_amount:+10.2f} {emoji}")
                        
                        # 매도 조건 충족 종목 (5% 이상)
                        if profit_rate >= 5:
                            high_profit_targets.append({
                                'symbol': symbol,
                                'profit_rate': profit_rate,
                                'quantity': quantity
                            })
                    else:
                        print(f"{i:3} {symbol:>8} {quantity:8.2f}주 ${avg_price:8.2f} {'조회실패':>10} {'N/A':>8} {'N/A':>12} ⚠️")
                else:
                    print(f"{i:3} {symbol:>8} {quantity:8.2f}주 {'N/A':>10} {'N/A':>10} {'N/A':>8} {'N/A':>12} ❌")
            
            print("-" * 80)
            print(f"📊 총 평가손익: ${total_profit:+.2f}")
            
            # 3. 매도 조건 충족 종목 표시
            if high_profit_targets:
                print(f"\n🎯 매도 조건 충족 종목 ({len(high_profit_targets)}개):")
                for target in high_profit_targets:
                    print(f"   {target['symbol']}: {target['profit_rate']:+.2f}% ({target['quantity']:.2f}주)")
            else:
                print(f"\n📭 매도 조건 충족 종목: 없음")
        else:
            print("\n📭 보유 종목: 없음")
        
        print("="*80)
        
    except Exception as e:
        print(f"[잔고][오류] 종합 현황 출력 실패: {e}")

def display_simple_balance():
    """간단한 잔고 출력 (기존 방식)"""
    try:
        balance = broker.fetch_present_balance()
        positions = balance.get("output1", [])

        # 전체 종목 출력
        print("\n[INFO] 보유 종목:")
        for p in positions:
            name = p.get("prdt_name", "-").strip()
            symbol = p.get("pdno", "-")
            pric1 = p.get("ovrs_now_pric1", "-")
            qty13 = p.get("cblc_qty13", "-")
            buyin = p.get("ord_psbl_qty1", "-")
            print(f"{symbol} | {name}|{qty13}|{buyin}")

        # 예수금 출력
        balance1 = balance.get("output2", [])
        print("\n[INFO] 예수금 정보:")
        for p in balance1:
            cash = p.get("frcr_dncl_amt_2", "-")  # 외화잔고
            withdrawable = p.get("frcr_drwg_psbl_amt_1", "-")  # 사용가능 외화
            print(f"외화잔고: ${cash}")
            print(f"사용가능 외화: ${withdrawable}")

        # ✅ 매매 시작 전 잔고/수익률 출력
        balance = broker.fetch_present_balance()

        # output1은 보유 종목 리스트
        output1 = balance.get("output1", [])
        for item in output1:
            name = item.get("prdt_name", "-")
            symbol = item.get("pdno", "-")
            qty = item.get("cblc_qty13", "-")
            print(f"보유 종목: {symbol} ({name}) - 수량: {qty}")

        # output3은 평가금액/매입금액 등 종합 정보
        output3 = balance.get("output3", {})
        available_cash = float(balance1[0].get("frcr_drwg_psbl_amt_1", 0)) if balance1 else 0
        eval_amt = float(output3.get("evlu_amt_smtl_amt", 0))  # 평가금액
        purchase_amt = float(output3.get("pchs_amt_smtl_amt", 0))  # 매입금액

        print(f"\n[잔고 요약]")
        print(f"사용 가능 예수금: ${available_cash:,.2f}")
        print(f"총 평가 금액: ${eval_amt:,.2f}")
        print(f"총 매입 금액: ${purchase_amt:,.2f}")

        # 수익률 계산
        if purchase_amt != 0:
            profit_rate = (eval_amt - purchase_amt) / purchase_amt * 100
            print(f"📈 수익률: {profit_rate:.2f}%")
        else:
            print("📈 수익률: 계산 불가 (매입금액 0)")

    except Exception as e:
        print(f"[오류] 잔고 조회 실패: {e}")

if __name__ == "__main__":
    print(f"[시스템][시작] blance02.py 실행 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 종합 계좌 현황 출력 (보유종목별 수익률 포함)
    display_comprehensive_balance()
    
    print(f"\n[시스템][완료] blance02.py 실행 완료") 