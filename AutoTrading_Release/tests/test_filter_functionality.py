"""
필터 기능 단위 테스트

필터 로직이 정상적으로 작동하는지 검증:
1. 모든 필터 종목이 상승할 때 → 매수 허용 (True)
2. 하나라도 하락/보합일 때 → 매수 차단 (False)
3. 필터가 비어있을 때 → 매수 허용 (True)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 상위 디렉토리를 path에 추가하여 import 가능하게 함
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.base_strategy import BaseStrategy


class TestableStrategy(BaseStrategy):
    """테스트용 구체 클래스 - 추상 메서드 구현"""

    def get_filter_stocks(self):
        """테스트용 더미 구현"""
        return self.filter_stocks

    def get_watch_list(self):
        """테스트용 더미 구현"""
        return []

    def should_buy(self, symbol):
        """테스트용 더미 구현"""
        return False

    def should_sell(self, symbol):
        """테스트용 더미 구현"""
        return False

    def execute_buy_strategy(self):
        """테스트용 더미 구현"""
        pass

    def execute_sell_strategy(self):
        """테스트용 더미 구현"""
        pass


class TestFilterFunctionality:
    """필터 기능 테스트 클래스"""

    @pytest.fixture
    def mock_strategy(self):
        """Mock Strategy 인스턴스 생성"""
        # Mock API 클라이언트 생성
        mock_api_client = Mock()

        # TestableStrategy 인스턴스 생성 (api_client 필수)
        strategy = TestableStrategy(
            api_client=mock_api_client,
            enable_filter_check=True
        )

        # Logger를 Mock 객체로 교체
        strategy.logger = Mock()

        return strategy

    def test_filter_all_rising(self, mock_strategy):
        """
        테스트: 모든 필터 종목이 상승할 때
        예상: True 반환 (매수 허용)
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True,  # 삼성전자
            "000660": True   # SK하이닉스
        }

        # Mock API 응답: 모든 종목이 상승
        def mock_get_current_price(symbol):
            prices = {
                "005930": 75000,  # 현재가
                "000660": 130000   # 현재가
            }
            return prices.get(symbol)

        def mock_get_previous_close(symbol):
            prices = {
                "005930": 74000,  # 전일가
                "000660": 128000  # 전일가
            }
            return prices.get(symbol)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: True 반환 (매수 허용)
        assert result is True
        assert mock_strategy.stats['filter_blocks'] == 0

    def test_filter_one_declining(self, mock_strategy):
        """
        테스트: 필터 종목 중 하나가 하락할 때
        예상: False 반환 (매수 차단)
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True,  # 삼성전자
            "000660": True   # SK하이닉스
        }

        # Mock API 응답: 하나는 상승, 하나는 하락
        def mock_get_current_price(symbol):
            prices = {
                "005930": 75000,  # 현재가 (상승)
                "000660": 127000   # 현재가 (하락)
            }
            return prices.get(symbol)

        def mock_get_previous_close(symbol):
            prices = {
                "005930": 74000,  # 전일가
                "000660": 128000  # 전일가
            }
            return prices.get(symbol)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: False 반환 (매수 차단)
        assert result is False
        assert mock_strategy.stats['filter_blocks'] == 1

    def test_filter_one_unchanged(self, mock_strategy):
        """
        테스트: 필터 종목 중 하나가 보합일 때
        예상: False 반환 (매수 차단, <= 조건이므로)
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True,  # 삼성전자
            "000660": True   # SK하이닉스
        }

        # Mock API 응답: 하나는 상승, 하나는 보합
        def mock_get_current_price(symbol):
            prices = {
                "005930": 75000,  # 현재가 (상승)
                "000660": 128000   # 현재가 (보합)
            }
            return prices.get(symbol)

        def mock_get_previous_close(symbol):
            prices = {
                "005930": 74000,  # 전일가
                "000660": 128000  # 전일가
            }
            return prices.get(symbol)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: False 반환 (매수 차단)
        assert result is False
        assert mock_strategy.stats['filter_blocks'] == 1

    def test_filter_empty(self, mock_strategy):
        """
        테스트: 필터가 비어있을 때
        예상: True 반환 (필터 비활성화)
        """
        # Given: 빈 필터
        mock_strategy.filter_stocks = {}

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: True 반환 (필터가 없으므로 통과)
        assert result is True
        assert mock_strategy.stats['filter_blocks'] == 0

    def test_filter_price_fetch_failure(self, mock_strategy):
        """
        테스트: 가격 조회 실패 시
        예상: None 반환 시 해당 종목 스킵하고 계속 진행
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True,  # 삼성전자
            "000660": True,  # SK하이닉스
            "035420": True   # NAVER
        }

        # Mock API 응답: 하나는 실패, 나머지는 상승
        def mock_get_current_price(symbol):
            prices = {
                "005930": 75000,  # 현재가
                "000660": None,    # 조회 실패
                "035420": 200000   # 현재가
            }
            return prices.get(symbol)

        def mock_get_previous_close(symbol):
            prices = {
                "005930": 74000,  # 전일가
                "000660": None,    # 조회 실패
                "035420": 195000  # 전일가
            }
            return prices.get(symbol)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: True 반환 (실패 종목은 스킵, 나머지 모두 상승)
        assert result is True
        assert mock_strategy.stats['filter_blocks'] == 0

    def test_filter_all_declining(self, mock_strategy):
        """
        테스트: 모든 필터 종목이 하락할 때
        예상: False 반환 (첫 번째 종목에서 차단)
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True,  # 삼성전자
            "000660": True   # SK하이닉스
        }

        # Mock API 응답: 모든 종목 하락
        def mock_get_current_price(symbol):
            prices = {
                "005930": 73000,  # 현재가 (하락)
                "000660": 127000   # 현재가 (하락)
            }
            return prices.get(symbol)

        def mock_get_previous_close(symbol):
            prices = {
                "005930": 74000,  # 전일가
                "000660": 128000  # 전일가
            }
            return prices.get(symbol)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: False 반환 (첫 번째 종목에서 즉시 차단)
        assert result is False
        assert mock_strategy.stats['filter_blocks'] == 1

    def test_filter_log_message_accuracy(self, mock_strategy):
        """
        테스트: 로그 메시지가 하락/보합을 정확히 표현하는지
        예상: "하락/보합 중" 메시지 출력
        """
        # Given: 필터 종목 설정
        mock_strategy.filter_stocks = {
            "005930": True
        }

        # Mock API 응답: 보합
        def mock_get_current_price(symbol):
            return 74000  # 현재가

        def mock_get_previous_close(symbol):
            return 74000  # 전일가 (보합)

        mock_strategy.api_client.get_current_price.side_effect = mock_get_current_price
        mock_strategy.api_client.get_previous_close.side_effect = mock_get_previous_close

        # When: 필터 조건 체크
        result = mock_strategy.check_filter_condition()

        # Then: 로그에 "하락/보합 중" 포함
        assert result is False
        mock_strategy.logger.info.assert_called()
        log_message = mock_strategy.logger.info.call_args[0][0]
        assert "하락/보합 중" in log_message


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
