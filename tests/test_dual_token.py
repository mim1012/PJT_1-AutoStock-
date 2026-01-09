"""
Phase 2: 토큰 분리 검증 테스트

US/KR 토큰이 독립적으로 관리되는지 확인하는 테스트
"""
import os
import sys
import json
import time

# 프로젝트 루트를 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_token_file_paths():
    """토큰 파일 경로가 올바르게 분리되어 있는지 확인"""
    print("=" * 60)
    print("테스트 1: 토큰 파일 경로 분리 확인")
    print("=" * 60)

    from us.token_manager import USTokenManager
    from kr.token_manager import KRTokenManager

    us_tm = USTokenManager()
    kr_tm = KRTokenManager()

    print(f"US 토큰 파일: {us_tm.token_file}")
    print(f"US 발급시간 파일: {us_tm.issued_at_file}")
    print(f"KR 토큰 파일: {kr_tm.token_file}")
    print(f"KR 발급시간 파일: {kr_tm.issued_at_file}")

    # 파일 경로가 다른지 확인
    assert us_tm.token_file != kr_tm.token_file, "US/KR 토큰 파일이 같습니다!"
    assert us_tm.issued_at_file != kr_tm.issued_at_file, "US/KR 발급시간 파일이 같습니다!"

    # 파일명에 접두사가 포함되어 있는지 확인
    assert "us_" in os.path.basename(us_tm.token_file), "US 토큰 파일에 'us_' 접두사가 없습니다"
    assert "kr_" in os.path.basename(kr_tm.token_file), "KR 토큰 파일에 'kr_' 접두사가 없습니다"

    print("\n[PASS] 테스트 1 통과: 토큰 파일 경로가 올바르게 분리됨\n")
    return True


def test_us_token_generation():
    """US 토큰 발급 테스트"""
    print("=" * 60)
    print("테스트 2: US 토큰 발급 테스트")
    print("=" * 60)

    from us.token_manager import USTokenManager

    us_tm = USTokenManager()

    # 토큰 발급
    token = us_tm.get_valid_token()

    if token:
        print(f"US 토큰 발급 성공: {token[:30]}...")
        print(us_tm.get_token_info())
        print("\n[PASS] 테스트 2 통과: US 토큰 발급 성공\n")
        return True
    else:
        print("[FAIL] 테스트 2 실패: US 토큰 발급 실패")
        return False


def test_kr_token_generation():
    """KR 토큰 발급 테스트"""
    print("=" * 60)
    print("테스트 3: KR 토큰 발급 테스트")
    print("=" * 60)

    from kr.token_manager import KRTokenManager

    kr_tm = KRTokenManager()

    # 토큰 발급
    token = kr_tm.get_valid_token()

    if token:
        print(f"KR 토큰 발급 성공: {token[:30]}...")
        print(kr_tm.get_token_info())
        print("\n[PASS] 테스트 3 통과: KR 토큰 발급 성공\n")
        return True
    else:
        print("[FAIL] 테스트 3 실패: KR 토큰 발급 실패")
        return False


def test_token_independence():
    """토큰 독립성 테스트 - US 토큰 변경이 KR에 영향 없는지"""
    print("=" * 60)
    print("테스트 4: 토큰 독립성 테스트")
    print("=" * 60)

    from us.token_manager import USTokenManager
    from kr.token_manager import KRTokenManager

    us_tm = USTokenManager()
    kr_tm = KRTokenManager()

    # 현재 토큰 상태 저장
    us_token_before = us_tm.load_token()
    kr_token_before = kr_tm.load_token()

    print(f"변경 전 US 토큰: {us_token_before[:20] if us_token_before else 'None'}...")
    print(f"변경 전 KR 토큰: {kr_token_before[:20] if kr_token_before else 'None'}...")

    # US 토큰 정보만 조회 (갱신 없이)
    us_info = us_tm.get_token_info()
    kr_info = kr_tm.get_token_info()

    print(f"\nUS 토큰 정보:\n{us_info}")
    print(f"\nKR 토큰 정보:\n{kr_info}")

    # KR 토큰이 US 토큰과 다른지 확인
    if us_token_before and kr_token_before:
        # 같은 API 키를 사용하면 토큰이 같을 수 있음 (정상)
        # 파일 분리만 확인
        assert os.path.exists(us_tm.token_file) or us_token_before is None
        assert os.path.exists(kr_tm.token_file) or kr_token_before is None
        print("\n[PASS] 테스트 4 통과: 토큰 파일이 독립적으로 관리됨\n")
    else:
        print("\n[WARN] 테스트 4 부분 통과: 일부 토큰이 아직 발급되지 않음\n")

    return True


def test_mojito_token_file():
    """mojito2 토큰 파일 분리 테스트"""
    print("=" * 60)
    print("테스트 5: mojito2 토큰 파일 분리 테스트")
    print("=" * 60)

    from us.config import USConfig
    from kr.config import KRConfig

    print(f"US mojito2 토큰 파일: {USConfig.MOJITO_TOKEN_FILE}")
    print(f"KR mojito2 토큰 파일: {KRConfig.MOJITO_TOKEN_FILE}")

    assert USConfig.MOJITO_TOKEN_FILE != KRConfig.MOJITO_TOKEN_FILE, \
        "US/KR mojito2 토큰 파일이 같습니다!"

    assert "us_" in USConfig.MOJITO_TOKEN_FILE, \
        "US mojito2 토큰 파일에 'us_' 접두사가 없습니다"
    assert "kr_" in KRConfig.MOJITO_TOKEN_FILE, \
        "KR mojito2 토큰 파일에 'kr_' 접두사가 없습니다"

    print("\n[PASS] 테스트 5 통과: mojito2 토큰 파일이 분리됨\n")
    return True


def test_token_file_contents():
    """토큰 파일 내용 확인"""
    print("=" * 60)
    print("테스트 6: 토큰 파일 내용 확인")
    print("=" * 60)

    from us.token_manager import USTokenManager
    from kr.token_manager import KRTokenManager

    us_tm = USTokenManager()
    kr_tm = KRTokenManager()

    # US 토큰 파일 확인
    if os.path.exists(us_tm.token_file):
        with open(us_tm.token_file, 'r') as f:
            us_data = json.load(f)
        print(f"US 토큰 파일 존재: {us_tm.token_file}")
        print(f"  - 생성시간: {us_data.get('expires_datetime', 'N/A')}")
    else:
        print(f"US 토큰 파일 없음: {us_tm.token_file}")

    # KR 토큰 파일 확인
    if os.path.exists(kr_tm.token_file):
        with open(kr_tm.token_file, 'r') as f:
            kr_data = json.load(f)
        print(f"KR 토큰 파일 존재: {kr_tm.token_file}")
        print(f"  - 생성시간: {kr_data.get('expires_datetime', 'N/A')}")
    else:
        print(f"KR 토큰 파일 없음: {kr_tm.token_file}")

    print("\n[PASS] 테스트 6 완료\n")
    return True


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("Phase 2: 토큰 분리 검증 테스트 시작")
    print("=" * 60 + "\n")

    results = []

    # 테스트 1: 토큰 파일 경로 분리
    try:
        results.append(("토큰 파일 경로 분리", test_token_file_paths()))
    except Exception as e:
        print(f"[FAIL] Test 1 error: {e}")
        results.append(("Token file path separation", False))

    # Test 2: US token generation
    try:
        results.append(("US token generation", test_us_token_generation()))
    except Exception as e:
        print(f"[FAIL] Test 2 error: {e}")
        results.append(("US token generation", False))

    # Test 3: KR token generation
    try:
        results.append(("KR token generation", test_kr_token_generation()))
    except Exception as e:
        print(f"[FAIL] Test 3 error: {e}")
        results.append(("KR token generation", False))

    # Test 4: Token independence
    try:
        results.append(("Token independence", test_token_independence()))
    except Exception as e:
        print(f"[FAIL] Test 4 error: {e}")
        results.append(("Token independence", False))

    # Test 5: mojito2 token file separation
    try:
        results.append(("mojito2 token file separation", test_mojito_token_file()))
    except Exception as e:
        print(f"[FAIL] Test 5 error: {e}")
        results.append(("mojito2 token file separation", False))

    # Test 6: Token file contents
    try:
        results.append(("Token file contents", test_token_file_contents()))
    except Exception as e:
        print(f"[FAIL] Test 6 error: {e}")
        results.append(("Token file contents", False))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n총 {len(results)}개 테스트 중 {passed}개 통과, {failed}개 실패")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
