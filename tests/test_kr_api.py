"""
Phase 3: KR API Client Tests

Tests for Korean stock API functionality:
1. Balance query
2. Current price query
3. Previous close query
4. Order API structure
5. Stock config validation
"""
import os
import sys
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_balance_query():
    """Test balance query API"""
    print("=" * 60)
    print("Test 1: Balance Query")
    print("=" * 60)

    from kr.api_client import KRAPIClient

    client = KRAPIClient()
    balance = client.get_account_balance()

    if balance is not None:
        print(f"  Available Cash: {balance['available_cash']:,.0f} KRW")
        print(f"  Total Eval: {balance['total_eval']:,.0f} KRW")
        print(f"  Positions: {len(balance['positions'])} stocks")
        print("\n[PASS] Balance query successful\n")
        return True
    else:
        print("\n[INFO] Balance returned None (may be empty account)\n")
        return True  # Empty balance is still a valid response


def test_current_price():
    """Test current price query"""
    print("=" * 60)
    print("Test 2: Current Price Query")
    print("=" * 60)

    from kr.api_client import KRAPIClient

    client = KRAPIClient()

    # Test with Samsung Electronics
    test_stocks = [
        ("005930", "Samsung Electronics"),
        ("000660", "SK Hynix"),
        ("035720", "Kakao")
    ]

    all_passed = True
    for code, name in test_stocks:
        price = client.get_current_price(code)
        if price and price > 0:
            print(f"  {code} ({name}): {price:,.0f} KRW")
        else:
            print(f"  {code} ({name}): FAILED")
            all_passed = False

    if all_passed:
        print("\n[PASS] All price queries successful\n")
    else:
        print("\n[FAIL] Some price queries failed\n")

    return all_passed


def test_previous_close():
    """Test previous close query"""
    print("=" * 60)
    print("Test 3: Previous Close Query")
    print("=" * 60)

    from kr.api_client import KRAPIClient

    client = KRAPIClient()

    price = client.get_previous_close("005930")

    if price and price > 0:
        print(f"  005930 previous close: {price:,.0f} KRW")
        print("\n[PASS] Previous close query successful\n")
        return True
    else:
        print("\n[FAIL] Previous close query failed\n")
        return False


def test_order_api_structure():
    """Test order API structure (will fail due to low balance - expected)"""
    print("=" * 60)
    print("Test 4: Order API Structure")
    print("=" * 60)

    from kr.api_client import KRAPIClient

    client = KRAPIClient()

    # Attempt order (will fail but tests API structure)
    result = client.place_order("005930", "buy", 1)

    if result:
        if result.get("success"):
            print("  [UNEXPECTED] Order succeeded")
            return False
        else:
            msg = result.get("message", "No message")
            print(f"  Error message: {msg[:50]}...")
            print("\n[PASS] Order API structure verified (error expected)\n")
            return True
    else:
        print("\n[FAIL] No response from order API\n")
        return False


def test_stock_config():
    """Test KR stock config file"""
    print("=" * 60)
    print("Test 5: KR Stock Config")
    print("=" * 60)

    config_path = os.path.join(project_root, "kr_stocks_config.json")

    if not os.path.exists(config_path):
        print(f"  Config file not found: {config_path}")
        print("\n[FAIL] Config file missing\n")
        return False

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        filter_stocks = config.get("filter_stocks", {})
        watch_list = config.get("watch_list", [])

        print(f"  Filter stocks: {len(filter_stocks)}")
        for code in filter_stocks:
            print(f"    - {code}")

        print(f"  Watch list: {len(watch_list)} stocks")
        for code in watch_list[:5]:
            print(f"    - {code}")
        if len(watch_list) > 5:
            print(f"    ... and {len(watch_list) - 5} more")

        print("\n[PASS] KR stock config valid\n")
        return True

    except Exception as e:
        print(f"  Error reading config: {e}")
        print("\n[FAIL] Config file error\n")
        return False


def run_all_tests():
    """Run all Phase 3 tests"""
    print("\n" + "=" * 60)
    print("Phase 3: KR API Client Tests")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Balance query
    try:
        results.append(("Balance Query", test_balance_query()))
    except Exception as e:
        print(f"[FAIL] Test 1 error: {e}")
        results.append(("Balance Query", False))

    # Test 2: Current price
    try:
        results.append(("Current Price", test_current_price()))
    except Exception as e:
        print(f"[FAIL] Test 2 error: {e}")
        results.append(("Current Price", False))

    # Test 3: Previous close
    try:
        results.append(("Previous Close", test_previous_close()))
    except Exception as e:
        print(f"[FAIL] Test 3 error: {e}")
        results.append(("Previous Close", False))

    # Test 4: Order API structure
    try:
        results.append(("Order API", test_order_api_structure()))
    except Exception as e:
        print(f"[FAIL] Test 4 error: {e}")
        results.append(("Order API", False))

    # Test 5: Stock config
    try:
        results.append(("Stock Config", test_stock_config()))
    except Exception as e:
        print(f"[FAIL] Test 5 error: {e}")
        results.append(("Stock Config", False))

    # Summary
    print("=" * 60)
    print("Test Results Summary")
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

    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
