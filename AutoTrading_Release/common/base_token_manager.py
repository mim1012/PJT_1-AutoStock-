"""
베이스 토큰 매니저 - 미국/한국 주식 공통 토큰 관리 기능
"""
import json
import time
import os
import requests
import logging
from abc import ABC, abstractmethod
from datetime import datetime


class BaseTokenManager(ABC):
    """
    토큰 관리 베이스 클래스

    서브클래스에서 구현해야 할 메서드:
    - get_api_url(): API 엔드포인트 반환
    - get_app_credentials(): (app_key, app_secret) 튜플 반환
    - get_token_file_prefix(): 토큰 파일 접두사 반환 (예: 'us', 'kr')
    """

    # 토큰 정책 상수
    TOKEN_EXPIRY_HOURS = 24  # KIS API 토큰 유효 기간
    REFRESH_THRESHOLD_HOURS = 5  # 이 시간 이하 남으면 갱신

    def __init__(self, token_dir=None):
        """
        Args:
            token_dir: 토큰 파일 저장 디렉토리 (기본값: 현재 디렉토리)
        """
        self.token_dir = token_dir or os.getcwd()
        self.logger = logging.getLogger(self.__class__.__name__)

        # 로거 설정
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)

    @property
    def token_file(self):
        """토큰 파일 경로"""
        prefix = self.get_token_file_prefix()
        filename = f"{prefix}_api_token.json" if prefix else "api_token.json"
        return os.path.join(self.token_dir, filename)

    @property
    def issued_at_file(self):
        """발급 시간 기록 파일 경로"""
        prefix = self.get_token_file_prefix()
        filename = f"{prefix}_token_issued_at.dat" if prefix else "token_issued_at.dat"
        return os.path.join(self.token_dir, filename)

    @abstractmethod
    def get_api_url(self) -> str:
        """API 베이스 URL 반환 (실전/모의 구분 포함)"""
        pass

    @abstractmethod
    def get_app_credentials(self) -> tuple:
        """(app_key, app_secret) 튜플 반환"""
        pass

    @abstractmethod
    def get_token_file_prefix(self) -> str:
        """토큰 파일 접두사 반환 (예: 'us', 'kr', 또는 빈 문자열)"""
        pass

    def get_last_issued_time(self) -> float:
        """마지막 토큰 발급 시각 조회"""
        try:
            if os.path.exists(self.issued_at_file):
                with open(self.issued_at_file, 'r') as f:
                    return float(f.read().strip())
        except Exception as e:
            self.logger.debug(f"발급 시간 읽기 실패: {e}")
        return 0

    def set_last_issued_time(self, t: float):
        """마지막 토큰 발급 시각 저장"""
        try:
            os.makedirs(os.path.dirname(self.issued_at_file) or '.', exist_ok=True)
            with open(self.issued_at_file, 'w') as f:
                f.write(str(t))
        except Exception as e:
            self.logger.error(f"발급 시간 저장 실패: {e}")

    def can_issue_token(self, force_if_expired=False) -> bool:
        """
        토큰 재발급 가능 여부 확인

        허용 조건:
        1. 마지막 발급 후 24시간 이상 경과
        2. 토큰이 완전 만료됨
        3. 토큰 남은시간 REFRESH_THRESHOLD_HOURS 이하
        4. force_if_expired=True이고 토큰 파일이 없는 경우
        """
        try:
            last_issued = self.get_last_issued_time()
            current_time = time.time()
            time_since_issued = current_time - last_issued

            # 24시간 경과
            if time_since_issued >= 86400:
                self.logger.info(f"[TOKEN] 24시간 경과 ({time_since_issued/3600:.1f}시간) - 재발급 허용")
                return True

            # 토큰 파일 확인
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    expires_at = token_data.get('expires_at', 0)
                    remaining = int(expires_at - current_time)

                    # 완전 만료
                    if remaining <= 0:
                        self.logger.warning(f"[TOKEN] 토큰 완전 만료 - 재발급 허용")
                        return True

                    # 임계값 이하
                    threshold_seconds = self.REFRESH_THRESHOLD_HOURS * 3600
                    if remaining <= threshold_seconds:
                        self.logger.warning(f"[TOKEN] 긴급 재발급 허용 (남은시간: {remaining//3600}시간)")
                        return True
            else:
                # 토큰 파일 없음 + 긴급 모드
                if force_if_expired:
                    self.logger.warning(f"[TOKEN] 긴급 복구 모드 - 재발급 허용")
                    if os.path.exists(self.issued_at_file):
                        os.remove(self.issued_at_file)
                    return True

            self.logger.debug(f"[TOKEN] 재발급 불가 - 24시간 미경과")
            return False

        except Exception as e:
            self.logger.error(f"[TOKEN] can_issue_token 오류: {e} - 안전을 위해 재발급 허용")
            # Fail-safe: 오류 발생 시 재발급 차단 (24시간 제한 우회 방지)
            return False

    def issue_new_token(self) -> str:
        """새 토큰 발급"""
        if not self.can_issue_token():
            self.logger.error("[TOKEN] 재발급 차단 - 24시간 미경과")
            return None

        try:
            app_key, app_secret = self.get_app_credentials()
            url = f"{self.get_api_url()}/oauth2/tokenP"

            headers = {"content-type": "application/json; charset=UTF-8"}
            data = {
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret
            }

            self.logger.info("[TOKEN] 새 토큰 발급 API 호출 중...")
            response = requests.post(url, headers=headers, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                access_token = result.get("access_token")
                expires_in = result.get("expires_in", 86400)

                if access_token:
                    if self.save_token(access_token, expires_in):
                        self.set_last_issued_time(time.time())
                        self.logger.info(f"[TOKEN] 새 토큰 발급 성공 (유효기간: {expires_in//3600}시간)")
                        return access_token
                    else:
                        self.logger.error("[TOKEN] 토큰 저장 실패")
                        return None
                else:
                    self.logger.error(f"[TOKEN] 응답에 access_token 없음: {result}")
                    return None
            else:
                self.logger.error(f"[TOKEN] 발급 실패 (HTTP {response.status_code}): {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[TOKEN] 요청 실패: {e}")
            return None
        except Exception as e:
            self.logger.error(f"[TOKEN] 알 수 없는 오류: {e}")
            return None

    def save_token(self, access_token: str, expires_in_seconds: int = 86400) -> bool:
        """토큰을 파일에 저장"""
        try:
            os.makedirs(os.path.dirname(self.token_file) or '.', exist_ok=True)

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
            return True

        except Exception as e:
            self.logger.error(f"토큰 저장 실패: {e}")
            return False

    def load_token(self) -> str:
        """저장된 토큰 로드 및 유효성 확인"""
        try:
            if not os.path.exists(self.token_file):
                self.logger.info("[TOKEN] 저장된 토큰 파일 없음")
                return None

            with open(self.token_file, 'r') as f:
                token_data = json.load(f)

            current_time = time.time()
            expires_at = token_data.get('expires_at', 0)
            remaining = int(expires_at - current_time)

            # 완전 만료
            if remaining <= 0:
                self.logger.warning(f"[TOKEN] 토큰 완전 만료 - 파일 삭제")
                self._cleanup_expired_token_files()
                return None

            # 임계값 이하
            threshold_seconds = self.REFRESH_THRESHOLD_HOURS * 3600
            if remaining <= threshold_seconds:
                self.logger.warning(f"[TOKEN] 토큰 남은시간 {self.REFRESH_THRESHOLD_HOURS}시간 이하 - 재발급 필요")
                self._cleanup_expired_token_files()
                return None

            remaining_hours = remaining // 3600
            remaining_minutes = (remaining % 3600) // 60
            self.logger.info(f"[TOKEN] 기존 토큰 사용 (남은시간: {remaining_hours}시간 {remaining_minutes}분)")
            return token_data['access_token']

        except Exception as e:
            self.logger.error(f"[TOKEN] 토큰 로드 실패: {e}")
            return None

    def _cleanup_expired_token_files(self):
        """만료된 토큰 관련 파일 정리"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                self.logger.info(f"[TOKEN] 토큰 파일 삭제: {self.token_file}")
            if os.path.exists(self.issued_at_file):
                os.remove(self.issued_at_file)
                self.logger.info(f"[TOKEN] 발급 시간 기록 삭제: {self.issued_at_file}")
        except Exception as e:
            self.logger.error(f"[TOKEN] 파일 삭제 오류: {e}")

    def get_valid_token(self, force_refresh=False) -> str:
        """유효한 토큰 반환 (만료 시 자동 재발급)"""
        if not force_refresh:
            existing_token = self.load_token()
            if existing_token:
                return existing_token

        self.logger.info("[TOKEN] 유효한 토큰 없음 - 재발급 시도")

        if self.can_issue_token(force_if_expired=True):
            new_token = self.issue_new_token()
            if new_token:
                self.logger.info("[TOKEN] 새 토큰 발급 성공")
                return new_token
            else:
                self.logger.error("[TOKEN] 토큰 재발급 실패")
                return None
        else:
            self.logger.error("[TOKEN] 재발급 조건 미충족")
            return None

    def delete_token(self) -> bool:
        """저장된 토큰 삭제"""
        try:
            deleted = False
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                self.logger.info(f"토큰 파일 삭제: {self.token_file}")
                deleted = True
            if os.path.exists(self.issued_at_file):
                os.remove(self.issued_at_file)
                self.logger.info(f"발급 시간 기록 삭제: {self.issued_at_file}")
                deleted = True
            return deleted
        except Exception as e:
            self.logger.error(f"토큰 삭제 실패: {e}")
            return False

    def get_token_info(self) -> str:
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

    def is_token_valid(self) -> bool:
        """토큰이 유효한지 검사 (만료 30분 전까지 True)"""
        try:
            if not os.path.exists(self.token_file):
                return False
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            current_time = time.time()
            expires_at = token_data.get('expires_at', 0)
            return current_time < (expires_at - 1800)
        except Exception as e:
            self.logger.error(f"is_token_valid 오류: {e}")
            return False
