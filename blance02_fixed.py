# usstockbuyandsell.py
import time
from ustime import is_us_market_open
import mojito

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



balance = broker.fetch_present_balance()
#pprint.pprint(balance)
positions = balance.get("output1", [])

# 전체 종목 출력
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


