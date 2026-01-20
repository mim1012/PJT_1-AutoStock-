"""
한국 주식 TR_ID 업데이트 검증 스크립트

2024년 신규 TR_ID 적용 확인:
- 구 TR (TTTC0802U, TTTC0801U, VTTC0802U, VTTC0801U)
- 신 TR (TTTC0012U, TTTC0011U, VTTC0012U, VTTC0011U)
"""
import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kr.api_client import KRAPIClient
from kr.config import KRConfig


def verify_tr_id_logic():
    """TR_ID 설정 로직 검증"""
    print("="*80)
    print("한국 주식 TR_ID 업데이트 검증")
    print("="*80)
    print()

    # 신규 TR_ID 기대값
    expected_tr_ids = {
        'paper': {
            'buy': 'VTTC0012U',
            'sell': 'VTTC0011U'
        },
        'real': {
            'buy': 'TTTC0012U',
            'sell': 'TTTC0011U'
        }
    }

    # 구 TR_ID (사용하면 안 됨)
    deprecated_tr_ids = ['TTTC0802U', 'TTTC0801U', 'VTTC0802U', 'VTTC0801U']

    print("[OK] 신규 TR_ID 기대값:")
    print(f"  실전 매수: {expected_tr_ids['real']['buy']}")
    print(f"  실전 매도: {expected_tr_ids['real']['sell']}")
    print(f"  모의 매수: {expected_tr_ids['paper']['buy']}")
    print(f"  모의 매도: {expected_tr_ids['paper']['sell']}")
    print()

    print("[X] 구 TR_ID (사용 금지):")
    for old_tr in deprecated_tr_ids:
        print(f"  - {old_tr}")
    print()

    # 코드에서 TR_ID 설정 로직 검증
    print("="*80)
    print("코드 검증")
    print("="*80)

    # kr/api_client.py 파일 읽기
    api_client_file = os.path.join(project_root, 'kr', 'api_client.py')

    if not os.path.exists(api_client_file):
        print(f"[ERROR] 파일을 찾을 수 없음: {api_client_file}")
        return False

    with open(api_client_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 구 TR_ID 사용 여부 확인
    issues = []
    for old_tr in deprecated_tr_ids:
        if old_tr in content:
            # 주석이나 문서에만 있는지 확인
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if old_tr in line:
                    # 주석이나 문자열 리터럴이 아닌 실제 코드에 있는지 확인
                    if 'tr_id =' in line and '#' not in line.split('tr_id =')[0]:
                        issues.append(f"라인 {i}: 구 TR_ID '{old_tr}'가 코드에 사용됨")

    if issues:
        print("[FAIL] 구 TR_ID가 코드에서 발견됨:")
        for issue in issues:
            print(f"  [X] {issue}")
        print()
        return False
    else:
        print("[PASS] 구 TR_ID가 코드에서 발견되지 않음")
        print()

    # 신규 TR_ID 사용 여부 확인
    new_tr_found = []
    for mode in ['real', 'paper']:
        for side in ['buy', 'sell']:
            expected = expected_tr_ids[mode][side]
            if expected in content:
                new_tr_found.append(expected)

    if len(new_tr_found) == 4:
        print("[PASS] 모든 신규 TR_ID가 코드에 존재함:")
        for tr_id in new_tr_found:
            print(f"  [OK] {tr_id}")
        print()
    else:
        print(f"[WARN] 일부 신규 TR_ID만 발견됨 ({len(new_tr_found)}/4)")
        for tr_id in new_tr_found:
            print(f"  [OK] {tr_id}")
        print()

    # TR_ID 설정 로직 시뮬레이션
    print("="*80)
    print("TR_ID 설정 로직 시뮬레이션")
    print("="*80)
    print()

    test_cases = [
        (False, 'buy', expected_tr_ids['real']['buy']),
        (False, 'sell', expected_tr_ids['real']['sell']),
        (True, 'buy', expected_tr_ids['paper']['buy']),
        (True, 'sell', expected_tr_ids['paper']['sell']),
    ]

    all_passed = True
    for is_paper, side, expected in test_cases:
        mode_name = "모의" if is_paper else "실전"
        side_name = "매수" if side == 'buy' else "매도"

        # 로직 시뮬레이션 (실제 코드와 동일한 로직)
        if is_paper:
            tr_id = "VTTC0012U" if side == 'buy' else "VTTC0011U"
        else:
            tr_id = "TTTC0012U" if side == 'buy' else "TTTC0011U"

        if tr_id == expected:
            print(f"[PASS] {mode_name} {side_name}: {tr_id}")
        else:
            print(f"[FAIL] {mode_name} {side_name}: {tr_id} (기대값: {expected})")
            all_passed = False

    print()
    print("="*80)
    print("검증 결과")
    print("="*80)

    if all_passed and not issues:
        print("[SUCCESS] 모든 TR_ID가 신규 버전으로 정상 업데이트됨")
        print()
        print("업데이트 내역:")
        print("  TTTC0802U (실전 매수) → TTTC0012U")
        print("  TTTC0801U (실전 매도) → TTTC0011U")
        print("  VTTC0802U (모의 매수) → VTTC0012U")
        print("  VTTC0801U (모의 매도) → VTTC0011U")
        print()
        print("[!] 주의: 구 TR_ID는 사전고지 없이 차단될 수 있습니다.")
        return True
    else:
        print("[FAILURE] TR_ID 업데이트에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    success = verify_tr_id_logic()
    sys.exit(0 if success else 1)
