# -*- coding: utf-8 -*-
"""키움 조건검색 실시간 PoC 실행기.

단테 발굴(Stage 0-B)을 키움 조건검색 실시간 push로 받는 흐름을 검증한다.
받은 종목은 ConditionUniverse(discover() 인터페이스)로 모여, 기존 단테 파이프라인의
동적 유니버스로 그대로 주입할 수 있다. (RESEARCH/dante_strategy_pipeline.md Stage 0-B)

실행 — 드라이런 (키/네트워크 없이 어댑터·흐름만 검증):
    python scripts/kiwoom_condition_poc.py --dry-run

실행 — 실연동 (.env에 KIWOOM_APP_KEY/KIWOOM_SECRET_KEY, 영웅문4에서 조건식 저장 후):
    python scripts/kiwoom_condition_poc.py --seq 0 --duration 60
    # --seq = ka10171 목록의 조건식 일련번호(영웅문4 [0150] 저장 순서)

연동 지점 (이 PoC는 출력만; 실배선은 별도):
    kr/strategy.py `_get_active_watch_list()` 의 USE_DYNAMIC_UNIVERSE 경로에서
    get_kr_provider().discover() 대신/병행으로 ConditionUniverse.discover() 를 사용하면
    조건검색 편입 종목이 매수 후보(watch_list)로 자동 유입된다.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.kiwoom_condition import (
    ConditionUniverse,
    KiwoomConditionClient,
    KiwoomCredentials,
    simulate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kiwoom_poc")

# 드라이런용 가짜 편입 종목 (오늘 KR EOD 역배열/B-2 결과 일부)
_DEMO_CODES = ["009450", "373220", "248070", "016380", "064960"]


def _print_handoff(universe: ConditionUniverse) -> None:
    members = universe.discover()
    print("\n" + "=" * 56)
    print(f"ConditionUniverse.discover() → {len(members)}종목")
    print(f"  {members}")
    print("=" * 56)
    print("이 리스트를 KRStrategy 동적 유니버스로 주입 → should_buy 8관문 → 주문")
    print("배선: kr/strategy.py _get_active_watch_list() USE_DYNAMIC_UNIVERSE 경로\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="키움 조건검색 실시간 PoC")
    ap.add_argument("--dry-run", action="store_true", help="키 없이 가짜 편입으로 흐름 검증")
    ap.add_argument("--seq", default="0", help="실시간 등록할 조건식 일련번호(ka10171 목록)")
    ap.add_argument("--duration", type=int, default=60, help="실연동 수신 시간(초)")
    args = ap.parse_args()

    universe = ConditionUniverse()
    creds = KiwoomCredentials.from_env()

    if args.dry_run or not creds.is_valid():
        if not args.dry_run:
            logger.warning("KIWOOM_APP_KEY/SECRET 미설정 → 드라이런으로 전환")
        simulate(universe, enter_codes=_DEMO_CODES, exit_codes=["016380"])
        _print_handoff(universe)
        return 0

    # ── 실연동 ──────────────────────────────────────────────────────────
    logger.info(f"실연동 시작: paper={creds.is_paper}, seq={args.seq}, {args.duration}초 수신")
    client = KiwoomConditionClient(creds, universe, target_seq=args.seq)
    try:
        client.start()
        time.sleep(args.duration)
    except KeyboardInterrupt:
        logger.info("중단 요청")
    finally:
        client.stop()
    _print_handoff(universe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
