import logging
from kis_api import KISAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=== Available Cash 확인 ===\n")

client = KISAPIClient()
balance = client.get_account_balance()

if balance:
    cash = balance.get('cash', 0)
    positions = balance.get('positions', [])

    print(f"사용가능 예수금: ${cash:.2f}")
    print(f"보유종목: {len(positions)}개\n")

    for p in positions:
        print(f"  - {p['item_name']} ({p['symbol']}): {p['quantity']}주")
else:
    print("잔고 조회 실패")
