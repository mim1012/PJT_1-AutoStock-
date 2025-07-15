"""
API 키 유효성 검증 도구
"""
import requests
import json
import sys
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL

def test_api_key():
    """API 키 유효성 테스트"""
    print("🔍 API 키 유효성 검증")
    print("=" * 50)
    
    # API 키 확인
    if KIS_APP_KEY == "여기에_새_API_키_입력":
        print("❌ API 키가 설정되지 않았습니다.")
        print("config.py에서 KIS_APP_KEY를 입력해주세요.")
        return False
    
    if KIS_APP_SECRET == "여기에_새_API_시크릿_입력":
        print("❌ API 시크릿이 설정되지 않았습니다.")
        print("config.py에서 KIS_APP_SECRET을 입력해주세요.")
        return False
    
    print(f"✅ API 키: {KIS_APP_KEY[:10]}...")
    print(f"✅ API 시크릿: {KIS_APP_SECRET[:10]}...")
    
    # 토큰 발급 시도
    url = f"{KIS_BASE_URL}/oauth2/token"
    headers = {"content-type": "application/json"}
    data = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET
    }
    
    try:
        print("\n🔄 토큰 발급 시도 중...")
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        
        print(f"📊 응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 토큰 발급 성공!")
            print(f"   토큰: {result['access_token'][:20]}...")
            print(f"   만료시간: {result['expires_in']}초")
            return True
            
        elif response.status_code == 403:
            print("❌ 403 Forbidden - API 키 인증 실패")
            print("\n🔧 해결 방법:")
            print("1. 한국투자증권 개발자센터에서 새 API 키 발급")
            print("2. API 키와 시크릿이 정확한지 확인")
            print("3. 계좌번호가 정확한지 확인")
            print("4. IP 등록이 되어있는지 확인")
            return False
            
        else:
            print(f"❌ 오류: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False

def main():
    success = test_api_key()
    
    if success:
        print("\n🎉 API 키가 정상입니다!")
    else:
        print("\n💡 다음 단계:")
        print("1. 한국투자증권 개발자센터 방문")
        print("2. Open API 신청/관리")
        print("3. 새 API 키 발급")
        print("4. config.py에 새 키 입력")

if __name__ == "__main__":
    main() 