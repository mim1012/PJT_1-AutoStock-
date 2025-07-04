"""
API 토큰 매니저 - 토큰 저장 및 재사용
"""
import json
import time
import os
from datetime import datetime, timedelta
import logging

class TokenManager:
    def __init__(self, token_file="api_token.json"):
        self.token_file = token_file
        self.logger = logging.getLogger(__name__)
    
    def save_token(self, access_token, expires_in_seconds=86400):
        """토큰을 파일에 저장"""
        try:
            expires_at = time.time() + expires_in_seconds
            token_data = {
                'access_token': access_token,
                'expires_at': expires_at,
                'created_at': time.time(),
                'expires_datetime': datetime.fromtimestamp(expires_at).isoformat()
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            self.logger.info(f"토큰 저장 완료: {self.token_file}")
            self.logger.info(f"만료 시간: {token_data['expires_datetime']}")
            return True
            
        except Exception as e:
            self.logger.error(f"토큰 저장 실패: {e}")
            return False
    
    def load_token(self):
        """저장된 토큰 로드 및 유효성 확인"""
        try:
            if not os.path.exists(self.token_file):
                self.logger.info("저장된 토큰 파일 없음")
                return None
            
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            current_time = time.time()
            expires_at = token_data.get('expires_at', 0)
            
            # 만료 30분 전까지 사용
            if current_time < (expires_at - 1800):  # 30분 여유
                remaining = int(expires_at - current_time)
                self.logger.info(f"기존 토큰 사용 (남은시간: {remaining//3600}시간 {(remaining%3600)//60}분)")
                return token_data['access_token']
            else:
                self.logger.info("기존 토큰 만료됨")
                return None
                
        except Exception as e:
            self.logger.error(f"토큰 로드 실패: {e}")
            return None
    
    def get_token_info(self):
        """토큰 정보 조회"""
        try:
            if not os.path.exists(self.token_file):
                return "저장된 토큰 없음"
            
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            current_time = time.time()
            expires_at = token_data.get('expires_at', 0)
            created_at = token_data.get('created_at', 0)
            
            if current_time < expires_at:
                remaining = int(expires_at - current_time)
                status = f"유효 (남은시간: {remaining//3600}시간 {(remaining%3600)//60}분)"
            else:
                status = "만료됨"
            
            created_datetime = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S')
            expires_datetime = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
            
            return f"""토큰 정보:
- 상태: {status}
- 생성시간: {created_datetime}
- 만료시간: {expires_datetime}
- 토큰: {token_data['access_token'][:20]}..."""
            
        except Exception as e:
            return f"토큰 정보 조회 실패: {e}"
    
    def delete_token(self):
        """저장된 토큰 삭제"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                self.logger.info("토큰 파일 삭제 완료")
                return True
            else:
                self.logger.info("삭제할 토큰 파일 없음")
                return False
        except Exception as e:
            self.logger.error(f"토큰 삭제 실패: {e}")
            return False

def check_and_renew_token():
    """토큰 상태 확인 후 필요시 자동 재발급"""
    manager = TokenManager()
    print("=== API 토큰 상태 확인 및 재발급 ===")
    print(manager.get_token_info())
    
    # 토큰 유효성 확인
    token = manager.load_token()
    if token:
        print("✅ 사용 가능한 토큰 있음")
        return True
    else:
        print("❌ 사용 가능한 토큰 없음")
        print("🔄 새 토큰 발급 시도...")
        
        try:
            # KIS API 클라이언트 임포트 및 토큰 발급
            from kis_api_with_token_manager import KISAPIClientWithTokenManager
            
            client = KISAPIClientWithTokenManager()
            if client.ensure_token_valid():
                print("✅ 새 토큰 발급 성공!")
                return True
            else:
                print("❌ 새 토큰 발급 실패!")
                return False
                
        except Exception as e:
            print(f"❌ 토큰 재발급 오류: {e}")
            return False

def check_token_status():
    """현재 토큰 상태 확인 (재발급 없음)"""
    manager = TokenManager()
    print("=== API 토큰 상태 확인 ===")
    print(manager.get_token_info())
    
    # 토큰 유효성 확인
    token = manager.load_token()
    if token:
        print("✅ 사용 가능한 토큰 있음")
        return True
    else:
        print("❌ 사용 가능한 토큰 없음")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_token_status()
        elif sys.argv[1] == "renew":
            check_and_renew_token()
        elif sys.argv[1] == "delete":
            manager = TokenManager()
            manager.delete_token()
            print("토큰 삭제 완료")
        else:
            print("사용법:")
            print("  python token_manager.py check   # 토큰 상태 확인만")
            print("  python token_manager.py renew   # 토큰 상태 확인 후 자동 재발급")
            print("  python token_manager.py delete  # 토큰 삭제")
    else:
        check_and_renew_token()  # 기본값을 자동 재발급으로 변경 