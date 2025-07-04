"""
간단한 토큰 발급 테스트
"""
import requests
import time
from datetime import datetime
from config import *

def test_token_simple():
    """간단한 토큰 발급 테스트"""
    print("=== 간단한 토큰 발급 테스트 ===")
    print(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    
    data = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET
    }
    
    headers = {"content-type": "application/json"}
    
    print(f"요청 URL: {url}")
    print(f"모의투자 모드: {USE_PAPER_TRADING}")
    print(f"앱키 길이: {len(KIS_APP_KEY) if KIS_APP_KEY != 'your_app_key_here' else '설정 안됨'}")
    
    try:
        print("토큰 발급 요청 중...")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        print(f"응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if "access_token" in result:
                access_token = result["access_token"]
                expires_in = result.get("expires_in", 86400)
                
                print("✅ 토큰 발급 성공!")
                print(f"토큰: {access_token[:20]}...")
                print(f"유효시간: {expires_in}초 ({expires_in//3600}시간)")
                
                # 토큰 저장
                from token_manager import TokenManager
                manager = TokenManager()
                manager.save_token(access_token, expires_in)
                
                return access_token
            else:
                print("❌ 응답에 토큰 없음")
                print(f"응답 내용: {result}")
                
        elif response.status_code == 403:
            print("❌ 403 Forbidden - API 키 문제 또는 호출 제한")
            print("가능한 원인:")
            print("1. API 키가 잘못됨")
            print("2. 너무 많은 토큰 발급 요청 (24시간 제한)")
            print("3. 실전/모의투자 모드 불일치")
            
        elif response.status_code == 429:
            print("❌ 429 Too Many Requests - API 호출 제한")
            print("잠시 후 다시 시도하세요")
            
        else:
            print(f"❌ 예상치 못한 응답: {response.status_code}")
            print(f"응답 내용: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ 요청 타임아웃")
    except requests.exceptions.ConnectionError:
        print("❌ 연결 오류")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    
    return None

def wait_and_retry(minutes=5):
    """대기 후 재시도"""
    print(f"\n⏳ {minutes}분 대기 후 재시도...")
    for i in range(minutes * 60):
        remaining = minutes * 60 - i
        mins = remaining // 60
        secs = remaining % 60
        print(f"\r남은 시간: {mins:02d}:{secs:02d}", end="", flush=True)
        time.sleep(1)
    
    print("\n재시도 중...")
    return test_token_simple()

if __name__ == "__main__":
    import sys
    
    if KIS_APP_KEY == "your_app_key_here":
        print("❌ API 키가 설정되지 않았습니다.")
        print("config.py에서 KIS_APP_KEY와 KIS_APP_SECRET을 설정하세요.")
    else:
        token = test_token_simple()
        
        if not token and len(sys.argv) > 1 and sys.argv[1] == "wait":
            # 대기 후 재시도
            token = wait_and_retry(5)
        
        if token:
            print(f"\n🎉 토큰 발급 성공! 이제 다른 API를 사용할 수 있습니다.")
        else:
            print(f"\n❌ 토큰 발급 실패. 나중에 다시 시도하세요.") 