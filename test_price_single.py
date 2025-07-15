from kis_api_with_token_manager import KISAPIClientWithTokenManager
import pprint

def test_single_price(symbol):
    client = KISAPIClientWithTokenManager()
    if not client.ensure_token_valid():
        print("❌ 토큰 발급 실패")
        return
    print(f"=== {symbol} 현재가 조회 테스트 ===")
    # 내부적으로 API 응답 원문도 확인
    try:
        # get_current_price 내부를 직접 호출해 원본 응답도 확인
        url = f"{client.base_url}/uapi/overseas-price/v1/quotations/price"
        headers = client.get_headers("HHDFS00000300")
        params = {"AUTH": "", "EXCD": "NAS", "SYMB": symbol}
        import requests
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"[HTTP STATUS] {resp.status_code}")
        try:
            data = resp.json()
            pprint.pprint(data)
            price_str = data.get("output", {}).get("last")
            if price_str:
                print(f"✅ {symbol} 현재가: ${price_str}")
            else:
                print(f"❌ {symbol} 현재가 데이터 없음 (output.last: '{price_str}')")
        except Exception as e:
            print(f"❌ JSON 파싱 오류: {e}")
            print(resp.text)
    except Exception as e:
        print(f"❌ API 요청 오류: {e}")

if __name__ == '__main__':
    test_single_price('SES')  # 여기서 심볼을 바꿔가며 테스트 가능 