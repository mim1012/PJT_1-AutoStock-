"""
매수가능금액 vs 인출가능금액 비교
"""
import requests
from token_manager import TokenManager
from config import *

tm = TokenManager()
token = tm.get_valid_token()

if not token:
    print("토큰 획득 실패")
    exit(1)

cano, acnt = KIS_ACCOUNT_NUMBER.split('-')
base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL

headers = {
    'authorization': f'Bearer {token}',
    'appkey': KIS_APP_KEY,
    'appsecret': KIS_APP_SECRET,
    'tr_id': 'VTTS3012R' if USE_PAPER_TRADING else 'TTTS3012R',
    'custtype': 'P'
}

params = {
    'CANO': cano,
    'ACNT_PRDT_CD': acnt,
    'OVRS_EXCG_CD': '',
    'TR_CRCY_CD': 'USD',
    'CTX_AREA_FK200': '',
    'CTX_AREA_NK200': ''
}

r = requests.get(f'{base_url}/uapi/overseas-stock/v1/trading/inquire-balance',
                 headers=headers, params=params)

if r.status_code != 200:
    print(f"API 오류: {r.status_code}")
    exit(1)

result = r.json()
if result.get('rt_cd') != '0':
    print(f"API 실패: {result.get('msg1')}")
    exit(1)

output2 = result.get('output2', [])
if not output2 or len(output2) == 0:
    print("output2 데이터 없음")
    print(f"전체 응답: {result}")
    exit(1)

if isinstance(output2, list):
    data = output2[0]
else:
    data = output2

print("=" * 60)
print("한국투자증권 API - 예수금 필드 비교")
print("=" * 60)

# 주요 필드
drwg = float(data.get('frcr_drwg_psbl_amt_1', 0))  # 인출가능
buy = float(data.get('frcr_buy_psbl_amt1', 0))      # 매수가능
dncl = float(data.get('frcr_dncl_amt_2', 0))        # 총 잔고

print(f"\n1. 외화 총잔고 (frcr_dncl_amt_2):        ${dncl:>10,.2f}")
print(f"2. 인출가능금액 (frcr_drwg_psbl_amt_1):  ${drwg:>10,.2f} <- Available Cash")
print(f"3. 매수가능금액 (frcr_buy_psbl_amt1):    ${buy:>10,.2f} <- 실제 매수 가능")

print("\n" + "=" * 60)
print("차이 분석")
print("=" * 60)

diff = buy - drwg
print(f"\n매수가능 - 인출가능 = ${diff:,.2f}")

if diff > 0:
    print(f"\n✅ 매수가능금액이 ${diff:,.2f} 더 많습니다")
    print("   (신용/미수 또는 담보대출 가능)")
elif diff < 0:
    print(f"\n⚠️ 인출가능금액이 ${abs(diff):,.2f} 더 많습니다")
    print("   (비정상 - 확인 필요)")
else:
    print("\n✅ 두 금액이 동일합니다")

print("\n" + "=" * 60)
print("결론")
print("=" * 60)
print(f"\n시스템이 사용 중인 값: ${drwg:,.2f} (인출가능금액)")
print(f"실제 매수 가능한 금액: ${buy:,.2f} (매수가능금액)")

if drwg == 0 and buy == 0:
    print("\n현재 상태: 매수 불가 (예수금 부족)")
elif drwg == 0 and buy > 0:
    print(f"\n⚠️ 중요: 신용매수 ${buy:,.2f} 가능하지만")
    print("   시스템은 현금매수만 사용 중 (안전)")
