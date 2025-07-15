"""
현재 API 키 상태 확인
"""
import sys
import os
import requests
import json

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL

def check_api_status():
    """API 키 상태 확인"""
    print("🔍 API 키 상태 확인")
    print("=" * 50)
    print(f"API 키: {KIS_APP_KEY[:10]}...")
    print(f"엔드포인트: {KIS_BASE_URL}")
    print()
    
    # 1. 토큰 발급 시도 (form-urlencoded)
    url = f"{KIS_BASE_URL}/oauth2/token"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = f"grant_type=client_credentials&appkey={KIS_APP_KEY}&appsecret={KIS_APP_SECRET}"
    
    try:
        print("🔄 토큰 발급 시도...")
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        print(f"📊 응답 상태: {response.status_code}")
        print(f"📊 응답 내용: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 토큰 발급 성공!")
            print(f"   토큰: {result['access_token'][:20]}...")
            print(f"   만료시간: {result['expires_in']}초")
            
            # 2. 간단한 API 테스트
            test_api_with_token(result['access_token'])
            return True
            
        elif response.status_code == 403:
            print("❌ 403 Forbidden")
            print("\n🔧 해결 방법:")
            print("1. 한국투자증권 개발자센터 방문")
            print("   https://apiportal.koreainvestment.com/intro")
            print("2. API 신청 완료")
            print("3. 해외주식 API 권한 확인")
            print("4. IP 등록 확인")
            return False
            
        else:
            print(f"❌ 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False

def test_api_with_token(token):
    """토큰으로 간단한 API 테스트"""
    print("\n🧪 API 기능 테스트")
    print("=" * 30)
    
    # 현재가 조회 테스트
    url = f"{KIS_BASE_URL}/uapi/overseas-price/v1/quotations/price"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": "HHDFS00000300"
    }
    params = {"AUTH": "", "EXCD": "NAS", "SYMB": "AAPL"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"📊 현재가 조회 응답: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("rt_cd") == "0":
                print("✅ API 기능 정상")
            else:
                print(f"❌ API 기능 오류: {result.get('msg1')}")
        else:
            print(f"❌ API 기능 오류: {response.status_code}")
            
    except Exception as e:
        print(f"❌ API 테스트 오류: {e}")

if __name__ == "__main__":
    check_api_status() 