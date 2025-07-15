"""
한국투자증권 API 연결 테스트 (공식 문서 기준)
"""
import requests
import json
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL, USE_PAPER_TRADING

def test_api_connection():
    """API 연결 및 토큰 발급 테스트"""
    print("🔍 한국투자증권 API 연결 테스트")
    print("=" * 50)
    print(f"모드: {'모의투자' if USE_PAPER_TRADING else '실거래'}")
    print(f"엔드포인트: {KIS_BASE_URL}")
    print(f"API 키: {KIS_APP_KEY[:10]}...")
    print()
    
    # 한국투자증권 공식 문서 기준 요청 형식
    url = f"{KIS_BASE_URL}/oauth2/token"
    
    # 방법 1: application/x-www-form-urlencoded
    headers_form = {"content-type": "application/x-www-form-urlencoded"}
    data_form = f"grant_type=client_credentials&appkey={KIS_APP_KEY}&appsecret={KIS_APP_SECRET}"
    
    try:
        print("🔄 토큰 발급 요청 중... (form-urlencoded)")
        print(f"📤 요청 데이터: {data_form}")
        
        response = requests.post(url, headers=headers_form, data=data_form, timeout=10)
        
        print(f"📊 응답 상태: {response.status_code}")
        print(f"📊 응답 내용: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 토큰 발급 성공!")
            print(f"   토큰: {result['access_token'][:20]}...")
            print(f"   만료시간: {result['expires_in']}초")
            return True
            
        elif response.status_code == 403:
            print("❌ 403 Forbidden - form-urlencoded 방식 실패")
            print("\n🔄 JSON 방식으로 재시도...")
            
            # 방법 2: application/json
            headers_json = {"content-type": "application/json"}
            data_json = {
                "grant_type": "client_credentials",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET
            }
            
            response_json = requests.post(url, headers=headers_json, json=data_json, timeout=10)
            
            print(f"📊 JSON 응답 상태: {response_json.status_code}")
            print(f"📊 JSON 응답 내용: {response_json.text}")
            
            if response_json.status_code == 200:
                result = response_json.json()
                print("✅ 토큰 발급 성공! (JSON 방식)")
                print(f"   토큰: {result['access_token'][:20]}...")
                print(f"   만료시간: {result['expires_in']}초")
                return True
            else:
                print("❌ JSON 방식도 실패")
                print("\n🔧 가능한 원인:")
                print("1. API 키가 만료됨")
                print("2. API 키 권한이 없음")
                print("3. 계좌번호가 잘못됨")
                print("4. IP 등록이 필요함")
                print("5. 해외주식 API 권한이 없음")
                print("6. API 키 형식이 잘못됨")
                return False
            
        else:
            print(f"❌ 오류: {response.status_code}")
            print(f"   응답 내용: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False

if __name__ == "__main__":
    test_api_connection() 