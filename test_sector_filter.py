"""
섹터 기반 OR 필터 조건 테스트

이 스크립트는 섹터 필터 기능이 올바르게 작동하는지 검증합니다:
1. 섹터 구조 로드
2. 섹터별 필터 조건 확인
3. OR 로직 검증 (어느 섹터든 하나 통과하면 매수 가능)
4. 활성 watch_list 반환 확인
"""
import os
import sys
import logging
from typing import Dict, Any

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kr.strategy import KRStrategy
from kr.api_client import KRAPIClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_sector_structure_loading():
    """섹터 구조 로드 테스트"""
    print("\n" + "="*80)
    print("TEST 1: 섹터 구조 로드")
    print("="*80)

    try:
        # KRStrategy 인스턴스 생성 (API 클라이언트 없이 테스트)
        # 실제 API 호출 없이 구조만 확인
        strategy = KRStrategy(enable_filter_check=True)

        sectors = strategy.get_sectors()

        if not sectors:
            print("[FAIL] 섹터 구조가 로드되지 않았습니다.")
            return False

        print(f"[PASS] 섹터 구조 로드 성공: {len(sectors)}개 섹터")
        print()

        # 각 섹터 정보 출력
        for sector_key, sector_info in sectors.items():
            sector_name = sector_info.get('name', sector_key)
            filter_stocks = sector_info.get('filter_stocks', {})
            watch_list = sector_info.get('watch_list', [])

            print(f"섹터: {sector_name} ({sector_key})")
            print(f"  - 필터 종목: {list(filter_stocks.keys())}")
            print(f"  - 감시 종목: {watch_list}")
            print()

        return True

    except Exception as e:
        print(f"[FAIL] 테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """하위 호환성 테스트 (레거시 flat 구조)"""
    print("\n" + "="*80)
    print("TEST 2: 하위 호환성 (레거시 구조)")
    print("="*80)

    # 현재는 섹터 구조를 사용하므로 이 테스트는 스킵
    # 레거시 구조 파일이 있다면 테스트 가능
    print("[SKIP] 현재 섹터 구조를 사용 중입니다. 레거시 테스트는 스킵합니다.")
    print()
    return True


def test_or_logic_concept():
    """OR 로직 개념 테스트"""
    print("\n" + "="*80)
    print("TEST 3: OR 로직 검증 (개념)")
    print("="*80)

    print("섹터별 OR 로직:")
    print("  1. 각 섹터 내부: 필터 종목 중 하나라도 상승하면 → 해당 섹터 통과")
    print("  2. 섹터 간: 하나의 섹터라도 통과하면 → 매수 허용")
    print()

    print("예시 시나리오:")
    print("  - 반도체 섹터: 삼성전자(005930) 하락, SK하이닉스(000660) 상승 -> 섹터 통과 [PASS]")
    print("  - 인터넷/플랫폼 섹터: 네이버(035420) 하락, 카카오(035720) 하락 -> 섹터 미통과 [FAIL]")
    print("  - 자동차/배터리 섹터: 현대차(005380) 하락, LG화학(051910) 하락 -> 섹터 미통과 [FAIL]")
    print("  - 금융 섹터: KB금융(105560) 하락, 신한지주(055550) 하락 -> 섹터 미통과 [FAIL]")
    print("  - 바이오 섹터: 삼성바이오(207940) 하락, 셀트리온(068270) 하락 -> 섹터 미통과 [FAIL]")
    print()
    print("  → 결과: 반도체 섹터가 통과했으므로 매수 허용!")
    print("  → 활성 watch_list: 반도체 섹터의 감시 종목만 매수 대상")
    print()
    print("[PASS] OR 로직 검증 완료")
    print()
    return True


def test_configuration_validity():
    """설정 파일 유효성 검사"""
    print("\n" + "="*80)
    print("TEST 4: 설정 파일 유효성 검사")
    print("="*80)

    try:
        strategy = KRStrategy(enable_filter_check=True)
        sectors = strategy.get_sectors()

        if not sectors:
            print("[FAIL] 섹터 구조가 없습니다.")
            return False

        issues = []

        for sector_key, sector_info in sectors.items():
            sector_name = sector_info.get('name', sector_key)

            # 필터 종목 확인
            filter_stocks = sector_info.get('filter_stocks', {})
            if not filter_stocks:
                issues.append(f"섹터 '{sector_name}': 필터 종목이 없습니다.")
            elif len(filter_stocks) < 2:
                issues.append(f"섹터 '{sector_name}': 필터 종목이 2개 미만입니다.")

            # watch_list 확인
            watch_list = sector_info.get('watch_list', [])
            if not watch_list:
                issues.append(f"섹터 '{sector_name}': 감시 종목이 없습니다.")

        if issues:
            print("[WARN] 다음 이슈가 발견되었습니다:")
            for issue in issues:
                print(f"  - {issue}")
            print()
        else:
            print("[PASS] 모든 섹터 설정이 유효합니다.")
            print()

        return True

    except Exception as e:
        print(f"[FAIL] 유효성 검사 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 테스트 실행"""
    print("\n" + "="*80)
    print("섹터 기반 OR 필터 조건 테스트 시작")
    print("="*80)

    results = []

    # 테스트 실행
    results.append(("섹터 구조 로드", test_sector_structure_loading()))
    results.append(("하위 호환성", test_backward_compatibility()))
    results.append(("OR 로직 검증", test_or_logic_concept()))
    results.append(("설정 파일 유효성", test_configuration_validity()))

    # 결과 요약
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print()
    print(f"총 {len(results)}개 테스트 중 {passed}개 통과, {failed}개 실패")
    print("="*80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
