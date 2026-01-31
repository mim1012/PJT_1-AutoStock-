"""
장 시작 전 설정 검증 및 요약 표시 모듈

시스템 시작 시 다음을 수행:
1. 국장/미장 종목 설정 로드
2. 종목 코드 유효성 검증 (API 호출)
3. 설정 요약 화면 출력
4. 사용자 확인 대기
"""
import os
import sys
import json
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import PROFIT_THRESHOLD, USE_PAPER_TRADING
from kr.config import KRConfig
from us.config import USConfig


class StartupValidator:
    """시스템 시작 전 설정 검증 및 요약 표시"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.errors = []
        self.warnings = []

        # API 클라이언트 (종목 검증용)
        self.kr_api = None
        self.us_api = None

    def _init_api_clients(self):
        """API 클라이언트 초기화 (종목 검증용)"""
        try:
            from kr.api_client import KRAPIClient
            from us.api_client import USAPIClient

            self.kr_api = KRAPIClient()
            self.us_api = USAPIClient()
            self.logger.info("API 클라이언트 초기화 완료")
        except Exception as e:
            self.warnings.append(f"API 클라이언트 초기화 실패: {e}")
            self.logger.warning(f"API 클라이언트 초기화 실패 (종목 검증 불가): {e}")

    def _load_kr_config(self) -> Optional[Dict]:
        """한국 주식 설정 파일 로드"""
        try:
            config_file = KRConfig.STOCKS_CONFIG_FILE

            if not os.path.exists(config_file):
                self.errors.append(f"한국 주식 설정 파일 없음: {config_file}")
                return None

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            return config

        except Exception as e:
            self.errors.append(f"한국 주식 설정 로드 실패: {e}")
            return None

    def _load_us_config(self) -> Optional[Dict]:
        """미국 주식 설정 파일 로드"""
        try:
            config_file = USConfig.STOCKS_CONFIG_FILE

            if not os.path.exists(config_file):
                self.errors.append(f"미국 주식 설정 파일 없음: {config_file}")
                return None

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            return config

        except Exception as e:
            self.errors.append(f"미국 주식 설정 로드 실패: {e}")
            return None

    def _validate_kr_stock(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        한국 종목 코드 검증

        Returns:
            (유효 여부, 종목명 또는 오류 메시지)
        """
        if not self.kr_api:
            return (False, "API 초기화 안됨")

        try:
            # 종목 코드 형식 체크 (6자리 숫자)
            if not symbol.isdigit() or len(symbol) != 6:
                return (False, f"잘못된 형식 (6자리 숫자 필요)")

            # API로 종목명 조회 (존재 여부 확인)
            current_price = self.kr_api.get_current_price(symbol)

            if current_price is None:
                return (False, f"종목 조회 실패 (존재하지 않거나 API 오류)")

            # 종목명은 별도 API 필요하므로 일단 "확인됨"으로 표시
            return (True, "확인됨")

        except Exception as e:
            return (False, f"검증 오류: {str(e)}")

    def _validate_us_stock(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        미국 종목 티커 검증

        Returns:
            (유효 여부, 종목명 또는 오류 메시지)
        """
        if not self.us_api:
            return (False, "API 초기화 안됨")

        try:
            # 티커 형식 체크 (대문자, 1-5자리)
            if not symbol.isupper() or len(symbol) < 1 or len(symbol) > 5:
                return (False, f"잘못된 형식 (대문자 1-5자리)")

            # API로 현재가 조회 (존재 여부 확인)
            current_price = self.us_api.get_current_price(symbol)

            if current_price is None:
                return (False, f"종목 조회 실패 (존재하지 않거나 API 오류)")

            return (True, "확인됨")

        except Exception as e:
            return (False, f"검증 오류: {str(e)}")

    def validate_kr_stocks(self, config: Dict) -> Dict[str, Dict]:
        """
        한국 주식 종목 검증

        Returns:
            {
                'symbol': {'valid': bool, 'name': str, 'type': 'filter'|'watch'},
                ...
            }
        """
        results = {}

        # filter_stocks 검증
        filter_stocks = config.get('filter_stocks', {})
        if isinstance(filter_stocks, dict):
            for symbol in filter_stocks.keys():
                valid, name = self._validate_kr_stock(symbol)
                results[symbol] = {
                    'valid': valid,
                    'name': name,
                    'type': 'filter'
                }
                if not valid:
                    self.errors.append(f"[국장 필터] {symbol}: {name}")

        # watch_list 검증
        watch_list = config.get('watch_list', [])
        for symbol in watch_list:
            valid, name = self._validate_kr_stock(symbol)
            results[symbol] = {
                'valid': valid,
                'name': name,
                'type': 'watch'
            }
            if not valid:
                self.errors.append(f"[국장 감시] {symbol}: {name}")

        return results

    def validate_us_stocks(self, config: Dict) -> Dict[str, Dict]:
        """
        미국 주식 종목 검증

        Returns:
            {
                'symbol': {'valid': bool, 'name': str, 'exchange': str},
                ...
            }
        """
        results = {}

        for symbol, info in config.items():
            exchange = info.get('exchange', 'UNKNOWN')
            valid, name = self._validate_us_stock(symbol)
            results[symbol] = {
                'valid': valid,
                'name': name,
                'exchange': exchange
            }
            if not valid:
                self.errors.append(f"[미장] {symbol} ({exchange}): {name}")

        return results

    def display_kr_summary(self, config: Dict, validation_results: Dict):
        """한국 주식 설정 요약 표시"""
        print("\n" + "="*80)
        print("🇰🇷 한국 주식 (국장) 설정")
        print("="*80)

        # 거래 모드
        mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        print(f"📌 거래 모드: {mode}")

        # 손절 설정
        print(f"📌 손절률: {KRConfig.STOP_LOSS_THRESHOLD*100:.1f}%")
        print(f"📌 재매수 금지: {KRConfig.STOP_LOSS_COOLDOWN_DAYS}일")
        print(f"📌 목표 수익률: {PROFIT_THRESHOLD*100:.1f}%")

        # filter_stocks 표시
        print("\n[필터 종목] - 이 종목들이 모두 상승해야 매수 실행")
        print("-"*80)
        filter_stocks = config.get('filter_stocks', {})

        if filter_stocks:
            for symbol in filter_stocks.keys():
                result = validation_results.get(symbol, {})
                valid = result.get('valid', False)
                name = result.get('name', '알 수 없음')
                status = "✅" if valid else "❌"
                print(f"{status} {symbol}: {name}")
        else:
            print("⚠️  필터 종목 없음 (모든 시간에 매수 가능)")

        # watch_list 표시
        print("\n[감시 종목] - 실제 매수 후보 (하락률 상위 3개 매수)")
        print("-"*80)
        watch_list = config.get('watch_list', [])

        if watch_list:
            for i, symbol in enumerate(watch_list, 1):
                result = validation_results.get(symbol, {})
                valid = result.get('valid', False)
                name = result.get('name', '알 수 없음')
                status = "✅" if valid else "❌"
                print(f"{status} {i:2d}. {symbol}: {name}")
        else:
            print("⚠️  감시 종목 없음")

        print("="*80)

    def display_us_summary(self, config: Dict, validation_results: Dict):
        """미국 주식 설정 요약 표시"""
        print("\n" + "="*80)
        print("🇺🇸 미국 주식 (미장) 설정")
        print("="*80)

        # 거래 모드
        mode = "모의투자" if USE_PAPER_TRADING else "실전투자"
        print(f"📌 거래 모드: {mode}")

        # 손절 설정
        print(f"📌 손절률: {USConfig.STOP_LOSS_THRESHOLD*100:.1f}%")
        print(f"📌 재매수 금지: {USConfig.STOP_LOSS_COOLDOWN_DAYS}일")
        print(f"📌 목표 수익률: {PROFIT_THRESHOLD*100:.1f}%")

        # 종목 표시
        print("\n[거래 종목]")
        print("-"*80)

        if config:
            for i, (symbol, info) in enumerate(config.items(), 1):
                exchange = info.get('exchange', 'UNKNOWN')
                result = validation_results.get(symbol, {})
                valid = result.get('valid', False)
                name = result.get('name', '알 수 없음')
                status = "✅" if valid else "❌"
                print(f"{status} {i:2d}. {symbol:6s} ({exchange:6s}): {name}")
        else:
            print("⚠️  거래 종목 없음")

        print("="*80)

    def display_errors_warnings(self):
        """오류 및 경고 메시지 표시"""
        if self.errors:
            print("\n" + "!"*80)
            print("❌ 오류 발견:")
            print("!"*80)
            for error in self.errors:
                print(f"  - {error}")
            print("!"*80)

        if self.warnings:
            print("\n" + "⚠"*80)
            print("⚠️  경고:")
            print("⚠"*80)
            for warning in self.warnings:
                print(f"  - {warning}")
            print("⚠"*80)

    def wait_for_user_confirmation(self) -> bool:
        """
        사용자 확인 대기

        Returns:
            True: 계속 진행
            False: 종료
        """
        print("\n" + "="*80)

        if self.errors:
            print("❌ 오류가 발견되었습니다.")
            print("\n계속 진행하시겠습니까?")
            print("  - Enter: 계속 진행 (위험할 수 있음)")
            print("  - q: 종료 후 설정 수정")
        else:
            print("✅ 모든 설정이 정상입니다.")
            print("\n자동매매를 시작하시겠습니까?")
            print("  - Enter: 시작")
            print("  - q: 종료")

        print("="*80)

        try:
            user_input = input("\n입력: ").strip().lower()

            if user_input == 'q':
                print("\n프로그램을 종료합니다.")
                return False

            return True

        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다.")
            return False
        except Exception as e:
            self.logger.error(f"사용자 입력 오류: {e}")
            return False

    def run_startup_check(self, check_kr: bool = True, check_us: bool = True) -> bool:
        """
        시작 전 전체 검증 실행

        Args:
            check_kr: 한국 주식 검증 여부
            check_us: 미국 주식 검증 여부

        Returns:
            True: 검증 통과 및 사용자 확인
            False: 검증 실패 또는 사용자 취소
        """
        print("\n")
        print("="*80)
        print("🚀 한국투자증권 자동매매 시스템 v4.7")
        print("="*80)
        print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # API 클라이언트 초기화
        self._init_api_clients()

        kr_config = None
        us_config = None
        kr_results = {}
        us_results = {}

        # 한국 주식 검증
        if check_kr:
            kr_config = self._load_kr_config()
            if kr_config:
                print("\n🔍 한국 주식 종목 검증 중...")
                kr_results = self.validate_kr_stocks(kr_config)
                self.display_kr_summary(kr_config, kr_results)

        # 미국 주식 검증
        if check_us:
            us_config = self._load_us_config()
            if us_config:
                print("\n🔍 미국 주식 종목 검증 중...")
                us_results = self.validate_us_stocks(us_config)
                self.display_us_summary(us_config, us_results)

        # 오류/경고 표시
        self.display_errors_warnings()

        # 사용자 확인 대기
        return self.wait_for_user_confirmation()


def run_startup_validation(check_kr: bool = True, check_us: bool = True) -> bool:
    """
    시작 전 검증 실행 (외부 호출용)

    Args:
        check_kr: 한국 주식 검증 여부
        check_us: 미국 주식 검증 여부

    Returns:
        True: 계속 진행
        False: 종료
    """
    validator = StartupValidator()
    return validator.run_startup_check(check_kr=check_kr, check_us=check_us)


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    success = run_startup_validation(check_kr=True, check_us=True)

    if success:
        print("\n✅ 검증 완료 - 자동매매 시작 가능")
    else:
        print("\n❌ 검증 실패 또는 사용자 취소")
        sys.exit(1)
