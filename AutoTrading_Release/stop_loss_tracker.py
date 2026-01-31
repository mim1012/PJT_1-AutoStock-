"""
손절 블랙리스트 추적 시스템

CSV(영구 히스토리) + JSON(활성 블랙리스트 캐시) 하이브리드 방식
- JSON: 빠른 조회용 (메모리 캐시)
- CSV: transaction_logger 통합 (영구 기록)
"""
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import pytz


class StopLossTracker:
    """
    손절 블랙리스트 관리 클래스

    주요 기능:
    1. JSON 파일 캐싱 (초기화 시 한 번만 로드)
    2. 원자적 쓰기 (임시 파일 → os.replace)
    3. 백업 파일 (.bak) 자동 생성
    4. transaction_logger와 연동
    5. 타임존 일관성 유지
    """

    def __init__(self,
                 blacklist_file: str,
                 cooldown_days: int,
                 timezone: str,
                 transaction_logger=None):
        """
        Args:
            blacklist_file: JSON 블랙리스트 파일 경로
            cooldown_days: 재매수 금지 기간 (일)
            timezone: 타임존 (예: "Asia/Seoul", "US/Eastern")
            transaction_logger: TransactionLogger 인스턴스 (선택)
        """
        self.blacklist_file = blacklist_file
        self.backup_file = f"{blacklist_file}.bak"
        self.cooldown_days = cooldown_days
        self.timezone = pytz.timezone(timezone)
        self.transaction_logger = transaction_logger
        self.logger = logging.getLogger(self.__class__.__name__)

        # JSON 파일 로드 (캐싱)
        self.blacklist = self._load_blacklist()

    def _load_blacklist(self) -> Dict[str, Dict]:
        """
        블랙리스트 JSON 파일 로드

        실패 시 .bak 파일에서 복구 시도

        Returns:
            블랙리스트 딕셔너리
        """
        # 메인 파일 시도
        if os.path.exists(self.blacklist_file):
            try:
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    blacklist = json.load(f)
                self.logger.info(f"블랙리스트 로드 완료: {len(blacklist)}개 종목")
                return blacklist
            except Exception as e:
                self.logger.error(f"블랙리스트 로드 실패: {e}")

        # 백업 파일 시도
        if os.path.exists(self.backup_file):
            try:
                with open(self.backup_file, 'r', encoding='utf-8') as f:
                    blacklist = json.load(f)
                self.logger.warning(f"백업 파일에서 복구 완료: {len(blacklist)}개 종목")
                # 복구된 데이터로 메인 파일 재생성
                self._save_blacklist(blacklist)
                return blacklist
            except Exception as e:
                self.logger.error(f"백업 파일 복구 실패: {e}")

        # 새 파일 생성
        self.logger.info("새 블랙리스트 파일 생성")
        return {}

    def _save_blacklist(self, blacklist: Dict = None):
        """
        블랙리스트를 JSON 파일에 저장 (원자적 쓰기)

        1. 임시 파일에 기록
        2. 백업 파일 생성
        3. os.replace()로 원자적 교체

        Args:
            blacklist: 저장할 블랙리스트 (None이면 self.blacklist 사용)
        """
        if blacklist is None:
            blacklist = self.blacklist

        temp_file = f"{self.blacklist_file}.tmp"

        try:
            # 1. 임시 파일에 기록
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(blacklist, f, ensure_ascii=False, indent=2)

            # 2. 백업 파일 생성 (기존 파일이 있을 경우)
            if os.path.exists(self.blacklist_file):
                try:
                    # 기존 백업 삭제
                    if os.path.exists(self.backup_file):
                        os.remove(self.backup_file)
                    # 현재 파일을 백업으로 복사
                    with open(self.blacklist_file, 'r', encoding='utf-8') as src:
                        with open(self.backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                except Exception as e:
                    self.logger.warning(f"백업 파일 생성 실패: {e}")

            # 3. 원자적 교체
            os.replace(temp_file, self.blacklist_file)

        except Exception as e:
            self.logger.error(f"블랙리스트 저장 실패: {e}")
            # 임시 파일 정리
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise

    def add_stop_loss(self,
                      symbol: str,
                      avg_price: float,
                      loss_price: float,
                      loss_rate: float):
        """
        손절 종목을 블랙리스트에 추가

        1. JSON 블랙리스트 업데이트
        2. transaction_logger에 CSV 기록

        Args:
            symbol: 종목 코드
            avg_price: 평균 매수가
            loss_price: 손절 매도가
            loss_rate: 손실률 (소수, 예: -0.15 = -15%)
        """
        now = datetime.now(self.timezone)
        cooldown_until = now + timedelta(days=self.cooldown_days)

        # JSON 블랙리스트 업데이트
        self.blacklist[symbol] = {
            'stop_loss_date': now.isoformat(),
            'cooldown_until': cooldown_until.isoformat(),
            'avg_buy_price': avg_price,
            'stop_loss_price': loss_price,
            'loss_rate': loss_rate,
            'timezone': str(self.timezone)
        }

        # 파일 저장 (원자적 쓰기)
        self._save_blacklist()

        self.logger.warning(
            f"손절 블랙리스트 추가: {symbol} "
            f"(손실률: {loss_rate*100:.2f}%, "
            f"재매수 금지: {self.cooldown_days}일)"
        )

        # transaction_logger에도 기록 (CSV 영구 히스토리)
        # 주의: 실제 매도 주문은 strategy에서 실행하므로
        # 여기서는 블랙리스트 추가만 로깅

    def is_blocked(self, symbol: str) -> bool:
        """
        매수 금지 여부 확인 (메모리 캐시에서 O(1) 조회)

        만료된 종목은 자동 삭제

        Args:
            symbol: 종목 코드

        Returns:
            True: 재매수 금지 중
            False: 매수 가능 (블랙리스트 없음 또는 만료됨)
        """
        if symbol not in self.blacklist:
            return False

        # 만료 확인
        try:
            cooldown_until_str = self.blacklist[symbol]['cooldown_until']
            cooldown_until = datetime.fromisoformat(cooldown_until_str)

            # 타임존이 없으면 추가
            if cooldown_until.tzinfo is None:
                cooldown_until = self.timezone.localize(cooldown_until)

            now = datetime.now(self.timezone)

            if now > cooldown_until:
                # 만료됨 → 블랙리스트에서 제거
                del self.blacklist[symbol]
                self._save_blacklist()
                self.logger.info(f"{symbol}: 손절 쿨다운 만료 (블랙리스트 제거)")
                return False

            return True

        except Exception as e:
            self.logger.error(f"{symbol} 블랙리스트 체크 오류: {e}")
            # 오류 발생 시 안전하게 차단
            return True

    def get_remaining_days(self, symbol: str) -> Optional[int]:
        """
        남은 쿨다운 일수 반환

        Args:
            symbol: 종목 코드

        Returns:
            남은 일수 (블랙리스트에 없으면 None)
        """
        if symbol not in self.blacklist:
            return None

        try:
            cooldown_until_str = self.blacklist[symbol]['cooldown_until']
            cooldown_until = datetime.fromisoformat(cooldown_until_str)

            # 타임존이 없으면 추가
            if cooldown_until.tzinfo is None:
                cooldown_until = self.timezone.localize(cooldown_until)

            now = datetime.now(self.timezone)
            remaining = (cooldown_until - now).days

            return max(0, remaining)

        except Exception as e:
            self.logger.error(f"{symbol} 남은 일수 계산 오류: {e}")
            return None

    def list_active_blocks(self) -> List[Dict[str, Any]]:
        """
        현재 활성 블랙리스트 종목 리스트 반환 (관리용)

        Returns:
            [{'symbol': str, 'remaining_days': int, ...}, ...]
        """
        active_blocks = []
        now = datetime.now(self.timezone)

        for symbol, info in list(self.blacklist.items()):
            try:
                cooldown_until_str = info['cooldown_until']
                cooldown_until = datetime.fromisoformat(cooldown_until_str)

                # 타임존이 없으면 추가
                if cooldown_until.tzinfo is None:
                    cooldown_until = self.timezone.localize(cooldown_until)

                if now <= cooldown_until:
                    remaining_days = (cooldown_until - now).days
                    active_blocks.append({
                        'symbol': symbol,
                        'remaining_days': remaining_days,
                        'stop_loss_date': info['stop_loss_date'],
                        'loss_rate': info['loss_rate'],
                        'avg_buy_price': info['avg_buy_price'],
                        'stop_loss_price': info['stop_loss_price']
                    })
                else:
                    # 만료된 종목은 제거
                    del self.blacklist[symbol]

            except Exception as e:
                self.logger.error(f"{symbol} 블랙리스트 조회 오류: {e}")
                continue

        # 만료된 종목이 있으면 저장
        if len(active_blocks) < len(self.blacklist):
            self._save_blacklist()

        # 남은 일수 순으로 정렬
        active_blocks.sort(key=lambda x: x['remaining_days'])

        return active_blocks

    def manual_unblock(self, symbol: str, reason: str = "수동 해제"):
        """
        수동 블랙리스트 해제 (긴급 상황 대응)

        Args:
            symbol: 종목 코드
            reason: 해제 사유
        """
        if symbol not in self.blacklist:
            self.logger.warning(f"{symbol}: 블랙리스트에 없음")
            return

        # 블랙리스트에서 제거
        info = self.blacklist.pop(symbol)
        self._save_blacklist()

        self.logger.warning(f"{symbol}: 블랙리스트 수동 해제 (사유: {reason})")

        # transaction_logger에 해제 이력 기록 (감사 추적)
        if self.transaction_logger:
            try:
                self.transaction_logger.log_strategy_execution(
                    action="manual_unblock",
                    status="completed",
                    notes=f"{symbol} 블랙리스트 해제 - {reason}"
                )
            except Exception as e:
                self.logger.error(f"해제 이력 로그 실패: {e}")

    def get_blacklist_status(self) -> Dict[str, Any]:
        """
        블랙리스트 전체 상태 반환 (모니터링용)

        Returns:
            {'total': int, 'expired': int, 'active': list}
        """
        active_blocks = self.list_active_blocks()

        return {
            'total': len(self.blacklist),
            'active': len(active_blocks),
            'cooldown_days': self.cooldown_days,
            'timezone': str(self.timezone),
            'blocks': active_blocks
        }
