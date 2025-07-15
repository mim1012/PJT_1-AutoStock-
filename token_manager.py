"""
API 토큰 매니저 - 토큰 저장 및 재사용
"""
import json
import time
import os
import requests
from datetime import datetime, timedelta
import logging
from config import KIS_BASE_URL, KIS_PAPER_BASE_URL, USE_PAPER_TRADING

# blance02.py의 API키 설정
KIS_APP_KEY = "PS9Yr8VDczEhRt6kbhrAExgLO9mno70zMJvp"
KIS_APP_SECRET = "2mfGKemkM4CTyvkQ1oquImEb+uUKwrflzTn23wjWJ5/PoFu5dwIW1OoyKYCoY2lPxl7L7ukzQqZD8PylBkYA1/SLFQ4r110XH6YCajAcMCzQnQekj1xBNGAaZo8zltZgX7YkomUzoBKV+8kopKGm3c9+juaQU+NJfM4vwMuyk8wkGFiK4v8="

class TokenManager:
    def __init__(self, token_file="api_token.json"):
        self.token_file = token_file
        self.logger = logging.getLogger(__name__)
        
        # 로거 설정
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # 스트림 핸들러
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)
    
    def get_last_issued_time(self):
        """마지막 토큰 발급 시각을 별도 파일에서 읽기"""
        try:
            if os.path.exists('token_issued_at.dat'):
                with open('token_issued_at.dat', 'r') as f:
                    return float(f.read().strip())
        except Exception:
            pass
        return 0

    def set_last_issued_time(self, t):
        """마지막 토큰 발급 시각을 별도 파일에 저장"""
        try:
            with open('token_issued_at.dat', 'w') as f:
                f.write(str(t))
        except Exception:
            pass

    def can_issue_token(self):
        """마지막 발급시각 + 24시간 이후에만 True (토큰 파일 없어도 적용)"""
        try:
            last_issued = self.get_last_issued_time()
            return (time.time() - last_issued) > 86400  # 24시간(60*60*24)
        except Exception:
            return True

    def issue_new_token(self):
        """새 토큰 발급 (공식 문서 기준)"""
        if not self.can_issue_token():
            self.logger.warning("24시간 이내이므로 토큰 재발급 금지 (강제 차단)")
            return None
        try:
            # API 엔드포인트 설정
            base_url = KIS_PAPER_BASE_URL if USE_PAPER_TRADING else KIS_BASE_URL
            url = f"{base_url}/oauth2/tokenP"  # 공식 문서 기준 tokenP 사용
            
            headers = {"content-type": "application/json; charset=UTF-8"}
            data = {
                "grant_type": "client_credentials",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET
            }
            
            self.logger.info("새 토큰 발급 요청 중... (tokenP)")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                access_token = result.get("access_token")
                expires_in = result.get("expires_in", 86400)
                token_expired_at = result.get("access_token_token_expired", "")
                token_type = result.get("token_type", "Bearer")
                
                if access_token:
                    # 토큰 저장 (만료 일시도 함께)
                    if self.save_token(access_token, expires_in):
                        self.set_last_issued_time(time.time())
                        self.logger.info(f"✅ 새 토큰 발급 및 저장 성공 (만료: {token_expired_at})")
                        return access_token
                    else:
                        self.logger.error("❌ 토큰 저장 실패")
                        return None
                else:
                    self.logger.error(f"❌ 토큰 발급 응답에 access_token 없음: {result}")
                    return None
            else:
                self.logger.error(f"❌ 토큰 발급 실패 (HTTP {response.status_code}): {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ 토큰 발급 요청 실패: {e}")
            return None
        except Exception as e:
            self.logger.error(f"❌ 토큰 발급 중 알 수 없는 오류: {e}")
            return None
    
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

    def invalidate_token(self):
        """토큰을 강제로 만료시킴 (재발급을 위해)"""
        try:
            if os.path.exists(self.token_file):
                # 토큰 파일을 읽어서 만료 시간을 과거로 설정
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                
                # 만료 시간을 1시간 전으로 설정
                token_data['expires_at'] = time.time() - 3600
                token_data['expires_datetime'] = datetime.fromtimestamp(token_data['expires_at']).isoformat()
                
                with open(self.token_file, 'w') as f:
                    json.dump(token_data, f, indent=2)
                
                self.logger.info("토큰을 강제로 만료시켰습니다")
                return True
            else:
                self.logger.info("만료시킬 토큰 파일이 없습니다")
                return False
        except Exception as e:
            self.logger.error(f"토큰 강제 만료 실패: {e}")
            return False

    def force_token_refresh(self):
        # 24시간 정책을 반드시 따름
        if not self.can_issue_token():
            self.logger.warning("강제 재발급 요청: 24시간 이내이므로 차단")
            return None
        self.delete_token()
        return self.get_valid_token(force_refresh=True)

    def is_token_valid(self):
        """토큰이 유효한지 검사 (만료 30분 전까지 True)"""
        try:
            if not os.path.exists(self.token_file):
                return False
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            current_time = time.time()
            expires_at = token_data.get('expires_at', 0)
            # 만료 30분 전까지 유효
            return current_time < (expires_at - 1800)
        except Exception as e:
            self.logger.error(f"is_token_valid 오류: {e}")
            return False

    def get_valid_token(self, force_refresh=False):
        """유효한 토큰 반환 (24시간 이내면 재발급 금지, 토큰 파일 없어도 적용)"""
        if not force_refresh:
            existing_token = self.load_token()
            if existing_token:
                return existing_token
            # 토큰 파일이 없거나 만료여도 24시간 이내면 재발급 금지
            if not self.can_issue_token():
                self.logger.warning("토큰 만료 또는 파일 없음, 24시간 이내이므로 재발급 시도 금지")
                return None
        if self.can_issue_token():
            return self.issue_new_token()
        else:
            self.logger.warning("24시간 이내이므로 토큰 재발급 금지")
            return None

def check_token_status():
    """현재 토큰 상태 확인 및 필요시 자동 재발급"""
    manager = TokenManager()
    print("=== API 토큰 상태 확인 ===")
    print(manager.get_token_info())
    
    # 토큰 유효성 확인
    token = manager.load_token()
    if token:
        print("✅ 사용 가능한 토큰 있음")
        return True
    else:
        print("❌ 사용 가능한 토큰 없음, 재발급 시도...")
        new_token = manager.get_valid_token(force_refresh=True)
        if new_token:
            print("✅ 새 토큰 발급 성공")
            print(manager.get_token_info())
            return True
        else:
            print("❌ 토큰 재발급 실패")
            return False

def refresh_token():
    """토큰 강제 재발급"""
    manager = TokenManager()
    print("=== 토큰 재발급 ===")
    
    # 기존 토큰 삭제
    manager.delete_token()
    
    # 새 토큰 발급
    new_token = manager.get_valid_token(force_refresh=True)
    
    if new_token:
        print("✅ 토큰 재발급 성공")
        print(manager.get_token_info())
        return True
    else:
        print("❌ 토큰 재발급 실패")
        return False

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_token_status()
        elif sys.argv[1] == "delete":
            manager = TokenManager()
            manager.delete_token()
            print("토큰 삭제 완료")
        elif sys.argv[1] == "refresh":
            refresh_token()
        elif sys.argv[1] == "get":
            manager = TokenManager()
            token = manager.get_valid_token()
            if token:
                print(f"✅ 유효한 토큰 획득: {token[:20]}...")
            else:
                print("❌ 토큰 획득 실패")
        else:
            print("사용법:")
            print("  python token_manager.py check    # 토큰 상태 확인")
            print("  python token_manager.py delete   # 토큰 삭제")
            print("  python token_manager.py refresh  # 토큰 재발급")
            print("  python token_manager.py get      # 유효한 토큰 획득")
    else:
        print("사용법:")
        print("  python token_manager.py check    # 토큰 상태 확인")
        print("  python token_manager.py delete   # 토큰 삭제")
        print("  python token_manager.py refresh  # 토큰 재발급")
        print("  python token_manager.py get      # 유효한 토큰 획득") 