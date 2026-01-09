"""
미국 주식 전용 토큰 매니저
"""
import os
import sys

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.base_token_manager import BaseTokenManager
from us.config import USConfig


class USTokenManager(BaseTokenManager):
    """
    미국 주식 전용 토큰 매니저

    BaseTokenManager를 상속하여 미국 주식 API에 맞게 구현
    토큰 파일: us_api_token.json, us_token_issued_at.dat
    """

    def __init__(self, token_dir=None):
        """
        Args:
            token_dir: 토큰 파일 저장 디렉토리 (기본값: 프로젝트 루트)
        """
        # 기본 디렉토리는 프로젝트 루트
        if token_dir is None:
            token_dir = project_root

        super().__init__(token_dir)
        self.logger.info(f"[US_TOKEN] 미국 주식 토큰 매니저 초기화")

    def get_api_url(self) -> str:
        """미국 주식 API URL 반환"""
        return USConfig.get_api_url()

    def get_app_credentials(self) -> tuple:
        """API 인증 정보 반환"""
        app_key, app_secret, _ = USConfig.get_credentials()
        return (app_key, app_secret)

    def get_token_file_prefix(self) -> str:
        """토큰 파일 접두사 반환"""
        return USConfig.TOKEN_FILE_PREFIX


# 하위 호환성을 위한 함수들
def check_token_status():
    """현재 토큰 상태 확인"""
    manager = USTokenManager()
    print("=== 미국 주식 API 토큰 상태 확인 ===")
    print(manager.get_token_info())

    token = manager.load_token()
    if token:
        print("사용 가능한 토큰 있음")
        return True
    else:
        print("사용 가능한 토큰 없음, 재발급 시도...")
        new_token = manager.get_valid_token(force_refresh=True)
        if new_token:
            print("새 토큰 발급 성공")
            print(manager.get_token_info())
            return True
        else:
            print("토큰 재발급 실패")
            return False


def refresh_token():
    """토큰 강제 재발급"""
    manager = USTokenManager()
    print("=== 미국 주식 토큰 재발급 ===")

    manager.delete_token()
    new_token = manager.get_valid_token(force_refresh=True)

    if new_token:
        print("토큰 재발급 성공")
        print(manager.get_token_info())
        return True
    else:
        print("토큰 재발급 실패")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_token_status()
        elif sys.argv[1] == "delete":
            manager = USTokenManager()
            manager.delete_token()
            print("토큰 삭제 완료")
        elif sys.argv[1] == "refresh":
            refresh_token()
        elif sys.argv[1] == "get":
            manager = USTokenManager()
            token = manager.get_valid_token()
            if token:
                print(f"유효한 토큰 획득: {token[:20]}...")
            else:
                print("토큰 획득 실패")
        else:
            print("사용법:")
            print("  python -m us.token_manager check    # 토큰 상태 확인")
            print("  python -m us.token_manager delete   # 토큰 삭제")
            print("  python -m us.token_manager refresh  # 토큰 재발급")
            print("  python -m us.token_manager get      # 유효한 토큰 획득")
    else:
        print("사용법:")
        print("  python -m us.token_manager check    # 토큰 상태 확인")
        print("  python -m us.token_manager delete   # 토큰 삭제")
        print("  python -m us.token_manager refresh  # 토큰 재발급")
        print("  python -m us.token_manager get      # 유효한 토큰 획득")
