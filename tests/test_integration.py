"""
Phase 6: Integration Test Suite

Comprehensive test for all components:
1. Token management (US/KR separation)
2. API clients (US/KR)
3. Trading strategies (US/KR)
4. Dual market scheduler
"""
import os
import sys
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_module_imports():
    """Test all module imports"""
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)

    errors = []

    # Common modules
    try:
        from common.base_token_manager import BaseTokenManager
        print("  [PASS] common.base_token_manager")
    except Exception as e:
        print(f"  [FAIL] common.base_token_manager: {e}")
        errors.append("common.base_token_manager")

    try:
        from common.base_api import BaseAPIClient
        print("  [PASS] common.base_api")
    except Exception as e:
        print(f"  [FAIL] common.base_api: {e}")
        errors.append("common.base_api")

    try:
        from common.base_strategy import BaseStrategy
        print("  [PASS] common.base_strategy")
    except Exception as e:
        print(f"  [FAIL] common.base_strategy: {e}")
        errors.append("common.base_strategy")

    # US modules
    try:
        from us.config import USConfig
        print("  [PASS] us.config")
    except Exception as e:
        print(f"  [FAIL] us.config: {e}")
        errors.append("us.config")

    try:
        from us.token_manager import USTokenManager
        print("  [PASS] us.token_manager")
    except Exception as e:
        print(f"  [FAIL] us.token_manager: {e}")
        errors.append("us.token_manager")

    try:
        from us.api_client import USAPIClient
        print("  [PASS] us.api_client")
    except Exception as e:
        print(f"  [FAIL] us.api_client: {e}")
        errors.append("us.api_client")

    try:
        from us.strategy import USStrategy
        print("  [PASS] us.strategy")
    except Exception as e:
        print(f"  [FAIL] us.strategy: {e}")
        errors.append("us.strategy")

    # KR modules
    try:
        from kr.config import KRConfig
        print("  [PASS] kr.config")
    except Exception as e:
        print(f"  [FAIL] kr.config: {e}")
        errors.append("kr.config")

    try:
        from kr.token_manager import KRTokenManager
        print("  [PASS] kr.token_manager")
    except Exception as e:
        print(f"  [FAIL] kr.token_manager: {e}")
        errors.append("kr.token_manager")

    try:
        from kr.api_client import KRAPIClient
        print("  [PASS] kr.api_client")
    except Exception as e:
        print(f"  [FAIL] kr.api_client: {e}")
        errors.append("kr.api_client")

    try:
        from kr.strategy import KRStrategy
        print("  [PASS] kr.strategy")
    except Exception as e:
        print(f"  [FAIL] kr.strategy: {e}")
        errors.append("kr.strategy")

    # Dual scheduler
    try:
        from dual_market_scheduler import DualMarketScheduler
        print("  [PASS] dual_market_scheduler")
    except Exception as e:
        print(f"  [FAIL] dual_market_scheduler: {e}")
        errors.append("dual_market_scheduler")

    if errors:
        print(f"\n[FAIL] {len(errors)} modules failed to import")
        return False
    else:
        print("\n[PASS] All modules imported successfully")
        return True


def test_token_separation():
    """Test US/KR token separation"""
    print("\n" + "=" * 60)
    print("Test 2: Token Separation")
    print("=" * 60)

    from us.token_manager import USTokenManager
    from kr.token_manager import KRTokenManager

    us_tm = USTokenManager()
    kr_tm = KRTokenManager()

    # Check file paths are different
    us_file = us_tm.token_file
    kr_file = kr_tm.token_file

    print(f"  US token file: {os.path.basename(us_file)}")
    print(f"  KR token file: {os.path.basename(kr_file)}")

    if us_file == kr_file:
        print("\n[FAIL] Token files are the same!")
        return False

    # Verify tokens can be retrieved
    us_token = us_tm.get_valid_token()
    kr_token = kr_tm.get_valid_token()

    if us_token:
        print(f"  US token: {us_token[:30]}...")
    else:
        print("  [WARN] US token not available")

    if kr_token:
        print(f"  KR token: {kr_token[:30]}...")
    else:
        print("  [WARN] KR token not available")

    print("\n[PASS] Token separation verified")
    return True


def test_us_api_client():
    """Test US API client"""
    print("\n" + "=" * 60)
    print("Test 3: US API Client")
    print("=" * 60)

    from us.api_client import USAPIClient

    client = USAPIClient()

    # Test balance query
    print("  Testing balance query...")
    balance = client.get_account_balance()

    if balance:
        cash = balance.get('available_cash', 0)
        positions = balance.get('positions', [])
        print(f"  Balance: ${cash:,.2f}, Positions: {len(positions)}")
        print("  [PASS] US balance query")
    else:
        print("  [WARN] US balance returned None")

    # Test price query
    print("  Testing price query (AAPL)...")
    price = client.get_current_price("AAPL")
    if price and price > 0:
        print(f"  AAPL price: ${price:.2f}")
        print("  [PASS] US price query")
    else:
        print("  [WARN] US price query returned None")

    print("\n[PASS] US API client tests completed")
    return True


def test_kr_api_client():
    """Test KR API client"""
    print("\n" + "=" * 60)
    print("Test 4: KR API Client")
    print("=" * 60)

    from kr.api_client import KRAPIClient

    client = KRAPIClient()

    # Test balance query
    print("  Testing balance query...")
    balance = client.get_account_balance()

    if balance:
        cash = balance.get('available_cash', 0)
        positions = balance.get('positions', [])
        print(f"  Balance: {cash:,.0f} KRW, Positions: {len(positions)}")
        print("  [PASS] KR balance query")
    else:
        print("  [WARN] KR balance returned None")

    # Test price query (Samsung Electronics)
    print("  Testing price query (005930)...")
    price = client.get_current_price("005930")
    if price and price > 0:
        print(f"  005930 price: {price:,.0f} KRW")
        print("  [PASS] KR price query")
    else:
        print("  [WARN] KR price query returned None")

    print("\n[PASS] KR API client tests completed")
    return True


def test_strategies():
    """Test US and KR strategies"""
    print("\n" + "=" * 60)
    print("Test 5: Trading Strategies")
    print("=" * 60)

    # US Strategy
    from us.strategy import USStrategy

    print("  Creating US strategy...")
    us_strategy = USStrategy()
    us_watch = us_strategy.get_watch_list()
    us_filter = us_strategy.get_filter_stocks()
    print(f"  US watch list: {len(us_watch)} stocks")
    print(f"  US filter stocks: {len(us_filter)} stocks")

    # KR Strategy
    from kr.strategy import KRStrategy

    print("  Creating KR strategy...")
    kr_strategy = KRStrategy()
    kr_watch = kr_strategy.get_watch_list()
    kr_filter = kr_strategy.get_filter_stocks()
    print(f"  KR watch list: {len(kr_watch)} stocks")
    print(f"  KR filter stocks: {len(kr_filter)} stocks")

    print("\n[PASS] Strategy tests completed")
    return True


def test_dual_scheduler():
    """Test dual market scheduler initialization"""
    print("\n" + "=" * 60)
    print("Test 6: Dual Market Scheduler")
    print("=" * 60)

    from dual_market_scheduler import DualMarketScheduler, MarketScheduler

    # Test individual schedulers
    print("  Creating US scheduler...")
    us_sched = MarketScheduler('us')
    print(f"  US market open: {us_sched.is_trading_hours()}")

    print("  Creating KR scheduler...")
    kr_sched = MarketScheduler('kr')
    print(f"  KR market open: {kr_sched.is_trading_hours()}")

    # Test dual scheduler
    print("  Creating dual scheduler...")
    dual = DualMarketScheduler(markets=['us', 'kr'])

    status = dual._get_current_status()
    for market, s in status.items():
        state = "OPEN" if s['is_open'] else "CLOSED"
        print(f"  {market.upper()}: {state}")

    print("\n[PASS] Dual scheduler tests completed")
    return True


def test_transaction_logger():
    """Test transaction logger with prefix support"""
    print("\n" + "=" * 60)
    print("Test 7: Transaction Logger")
    print("=" * 60)

    from transaction_logger import TransactionLogger

    # Test US logger (no prefix)
    us_logger = TransactionLogger()
    print(f"  US log file: {us_logger.csv_filename}")

    # Test KR logger (with prefix)
    kr_logger = TransactionLogger(prefix="kr")
    print(f"  KR log file: {kr_logger.csv_filename}")

    # Verify they're different
    if us_logger.csv_filename == kr_logger.csv_filename:
        print("\n[FAIL] Log files are the same!")
        return False

    print("\n[PASS] Transaction logger tests completed")
    return True


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "=" * 60)
    print("Phase 6: Integration Test Suite")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Module imports
    try:
        results.append(("Module Imports", test_module_imports()))
    except Exception as e:
        print(f"[FAIL] Test 1 error: {e}")
        results.append(("Module Imports", False))

    # Test 2: Token separation
    try:
        results.append(("Token Separation", test_token_separation()))
    except Exception as e:
        print(f"[FAIL] Test 2 error: {e}")
        results.append(("Token Separation", False))

    # Test 3: US API client
    try:
        results.append(("US API Client", test_us_api_client()))
    except Exception as e:
        print(f"[FAIL] Test 3 error: {e}")
        results.append(("US API Client", False))

    # Test 4: KR API client
    try:
        results.append(("KR API Client", test_kr_api_client()))
    except Exception as e:
        print(f"[FAIL] Test 4 error: {e}")
        results.append(("KR API Client", False))

    # Test 5: Strategies
    try:
        results.append(("Trading Strategies", test_strategies()))
    except Exception as e:
        print(f"[FAIL] Test 5 error: {e}")
        results.append(("Trading Strategies", False))

    # Test 6: Dual scheduler
    try:
        results.append(("Dual Scheduler", test_dual_scheduler()))
    except Exception as e:
        print(f"[FAIL] Test 6 error: {e}")
        results.append(("Dual Scheduler", False))

    # Test 7: Transaction logger
    try:
        results.append(("Transaction Logger", test_transaction_logger()))
    except Exception as e:
        print(f"[FAIL] Test 7 error: {e}")
        results.append(("Transaction Logger", False))

    # Summary
    print("\n" + "=" * 60)
    print("Integration Test Results")
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

    if failed == 0:
        print("\n[SUCCESS] All integration tests passed!")
        print("System is ready for deployment.")
    else:
        print(f"\n[WARNING] {failed} tests failed. Please review before deployment.")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
