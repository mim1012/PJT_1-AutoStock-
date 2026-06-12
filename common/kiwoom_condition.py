from __future__ import annotations
"""키움 조건검색 실시간 연동 — PoC 스켈레톤.

목적
----
키움 신 REST/WebSocket OpenAPI로 **서버 저장된 조건검색식**의 실시간 편입/이탈을
수신해, 기존 단테 파이프라인(동적 유니버스 → should_buy)에 종목을 자동 주입한다.

흐름 (RESEARCH/realtime_screener_integration.md A절)
---------------------------------------------------
  토큰발급(REST)  →  WS연결  →  LOGIN
    →  ka10171(CNSRLST: 서버 조건식 목록)
    →  ka10173(CNSRREQ search_type="1": 조건식 실시간 등록)
    →  편입/이탈 push  →  ConditionUniverse 갱신  →  discover()로 파이프라인에 주입

⚠️ PoC/스켈레톤
---------------
- WebSocket 메시지의 **정확한 필드명(return_code, data 구조, 편입/이탈 플래그 등)은
  키움 공식 가이드와 대조 후 확정**해야 한다. [불확실] 표시 지점 참고.
  공식 가이드: https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=15
- 키/네트워크 없이 `--dry-run`(scripts/kiwoom_condition_poc.py)으로 어댑터·흐름만 검증 가능.
- 조건식 자체는 영웅문4 [0150]에서 작성·저장(자동 서버저장)하며, 여기선 seq(일련번호)로 호출만 한다.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── 엔드포인트 (realtime_screener_integration.md) ──────────────────────────
_REST_HOST_REAL = "https://api.kiwoom.com"
_REST_HOST_PAPER = "https://mockapi.kiwoom.com"
_WS_URL_REAL = "wss://api.kiwoom.com:10000/api/dostk/websocket"
_WS_URL_PAPER = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"  # 모의: KRX 한정


# ===========================================================================
# 인증
# ===========================================================================
@dataclass
class KiwoomCredentials:
    app_key: str
    secret_key: str
    is_paper: bool = False

    @classmethod
    def from_env(cls) -> "KiwoomCredentials":
        return cls(
            app_key=os.getenv("KIWOOM_APP_KEY", ""),
            secret_key=os.getenv("KIWOOM_SECRET_KEY", ""),
            is_paper=os.getenv("KIWOOM_PAPER", "False").lower() in ("true", "1", "yes"),
        )

    def is_valid(self) -> bool:
        return bool(self.app_key and self.secret_key)


def issue_access_token(creds: KiwoomCredentials) -> str:
    """REST로 접근토큰 발급. [불확실] 엔드포인트/필드명은 공식 가이드 대조 필요."""
    import requests  # 이미 프로젝트 의존성

    host = _REST_HOST_PAPER if creds.is_paper else _REST_HOST_REAL
    resp = requests.post(
        f"{host}/oauth2/token",
        json={
            "grant_type": "client_credentials",
            "appkey": creds.app_key,
            "secretkey": creds.secret_key,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"토큰 발급 응답에 토큰 없음: {data}")
    return token


# ===========================================================================
# 동적 유니버스 어댑터 — common/universe.py provider 와 동일한 discover() 인터페이스
# ===========================================================================
@dataclass
class ConditionUniverse:
    """조건검색 실시간 편입/이탈을 반영하는 동적 유니버스.

    `discover(limit)` 시그니처가 KRUniverseProvider 와 동일하므로,
    kr/strategy.py `_get_active_watch_list()`의 동적 유니버스 경로에 그대로 주입 가능.
    """

    _members: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def on_enter(self, code: str) -> None:
        with self._lock:
            is_new = code not in self._members
            self._members.add(code)
        if is_new:
            logger.info(f"[조건검색] 편입 +{code} (현재 {self.size()}종목)")

    def on_exit(self, code: str) -> None:
        with self._lock:
            existed = code in self._members
            self._members.discard(code)
        if existed:
            logger.info(f"[조건검색] 이탈 -{code} (현재 {self.size()}종목)")

    def discover(self, limit: int = 0) -> list[str]:
        with self._lock:
            members = sorted(self._members)
        return members[:limit] if limit else members

    def size(self) -> int:
        with self._lock:
            return len(self._members)


# ===========================================================================
# WebSocket 클라이언트
# ===========================================================================
class KiwoomConditionClient:
    """키움 조건검색 실시간 WebSocket 클라이언트 (동기 + 백그라운드 스레드).

    Args:
        creds: 키움 앱키/시크릿
        universe: 편입/이탈을 반영할 ConditionUniverse
        target_seq: 실시간 등록할 조건식 일련번호(ka10171 목록의 seq). 영웅문4에서 만든 순서.
        on_event: (선택) 원시 수신 메시지 후크 — 디버깅/로깅용 Callable[[dict], None]
    """

    def __init__(
        self,
        creds: KiwoomCredentials,
        universe: ConditionUniverse,
        target_seq: str = "0",
        on_event: Optional[Callable[[dict], None]] = None,
    ):
        self.creds = creds
        self.universe = universe
        self.target_seq = str(target_seq)
        self.on_event = on_event
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._token: Optional[str] = None
        self._conditions: dict[str, str] = {}  # seq -> 조건식 이름

    # ── 수명주기 ──────────────────────────────────────────────────────────
    def start(self) -> None:
        self._token = issue_access_token(self.creds)
        try:
            import websocket  # websocket-client (requirements.txt)
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("websocket-client 필요: pip install websocket-client") from e

        url = _WS_URL_PAPER if self.creds.is_paper else _WS_URL_REAL
        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={"ping_interval": 30},
            daemon=True,
            name="kiwoom-condition",
        )
        self._thread.start()
        logger.info("[키움WS] 클라이언트 시작")

    def stop(self) -> None:
        if self._ws:
            self._ws.close()
        logger.info("[키움WS] 클라이언트 종료")

    # ── 내부: 전송 ────────────────────────────────────────────────────────
    def _send(self, payload: dict) -> None:
        assert self._ws is not None
        self._ws.send(json.dumps(payload))

    def _register_realtime(self, seq: str) -> None:
        name = self._conditions.get(seq, "?")
        logger.info(f"[키움WS] 조건식 [{seq}:{name}] 실시간 등록(ka10173)")
        # [불확실] stex_tp(거래소구분) 등 부가 필드는 공식 가이드 확인
        self._send({"trnm": "CNSRREQ", "seq": seq, "search_type": "1", "stex_tp": "K"})

    # ── 내부: 콜백 ────────────────────────────────────────────────────────
    def _on_open(self, ws) -> None:
        logger.info("[키움WS] 연결됨 → LOGIN 전송")
        self._send({"trnm": "LOGIN", "token": self._token})

    def _on_error(self, ws, err) -> None:
        logger.error(f"[키움WS] 오류: {err}")

    def _on_close(self, ws, code, msg) -> None:
        logger.warning(f"[키움WS] 연결 종료: {code} {msg}")

    def _on_message(self, ws, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            logger.warning(f"[키움WS] JSON 파싱 불가: {raw[:200]}")
            return

        if self.on_event:
            try:
                self.on_event(msg)
            except Exception:
                logger.exception("on_event 콜백 오류")

        dispatch(msg, self)


# ===========================================================================
# 메시지 디스패치 — 순수 함수(테스트 용이). [불확실] 필드명은 공식 가이드 대조 필요.
# ===========================================================================
def dispatch(msg: dict, client: KiwoomConditionClient) -> None:
    trnm = msg.get("trnm")

    # 연결 유지용 PING → 그대로 echo
    if trnm == "PING":
        client._send(msg)
        return

    if trnm == "LOGIN":
        if _is_ok(msg):
            logger.info("[키움WS] 로그인 성공 → 조건식 목록(ka10171) 요청")
            client._send({"trnm": "CNSRLST"})
        else:
            logger.error(f"[키움WS] 로그인 실패: {msg}")
        return

    if trnm == "CNSRLST":
        # [불확실] data 포맷: [[seq, name], ...] 가정
        for item in msg.get("data", []):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                client._conditions[str(item[0])] = str(item[1])
        logger.info(f"[키움WS] 서버 조건식 {len(client._conditions)}개: {client._conditions}")
        client._register_realtime(client.target_seq)
        return

    if trnm == "CNSRREQ":
        # 실시간 등록 직후 현재 편입 종목 일괄 스냅샷
        for item in msg.get("data", []):
            code = _extract_code(item)
            if code:
                client.universe.on_enter(code)
        return

    if trnm == "REAL":
        # 실시간 편입('I')/이탈('D') push
        for item in msg.get("data", [msg]):
            code = _extract_code(item)
            if not code:
                continue
            if _extract_flag(item) == "D":
                client.universe.on_exit(code)
            else:
                client.universe.on_enter(code)
        return

    logger.debug(f"[키움WS] 미처리 trnm={trnm}: {str(msg)[:200]}")


# ── 필드 추출 헬퍼 ([불확실] — 공식 응답 샘플로 교정 필요) ──────────────────
def _is_ok(msg: dict) -> bool:
    rc = str(msg.get("return_code", msg.get("rt_cd", "")))
    return rc in ("0", "0000") or rc == ""


def _extract_code(item) -> str:
    """편입/이탈 메시지에서 6자리 종목코드 추출."""
    if isinstance(item, dict):
        for k in ("9001", "jmcode", "code", "stk_cd", "item"):
            v = item.get(k)
            if v:
                return str(v).lstrip("A")[:6]
        return ""
    if isinstance(item, (list, tuple)) and item:
        return str(item[0]).lstrip("A")[:6]
    if isinstance(item, str):
        return item.lstrip("A")[:6]
    return ""


def _extract_flag(item) -> str:
    """편입/이탈 플래그: 'I'(편입, insert) / 'D'(이탈, delete)."""
    if isinstance(item, dict):
        return str(item.get("843", item.get("flag", item.get("type", "I")))).upper()[:1]
    return "I"


# ===========================================================================
# dry-run 시뮬레이터 — 키/네트워크 없이 어댑터·흐름 검증
# ===========================================================================
def simulate(universe: ConditionUniverse, enter_codes: list[str],
             exit_codes: Optional[list[str]] = None) -> None:
    """가짜 편입/이탈 이벤트로 ConditionUniverse 동작을 검증한다."""
    logger.info(f"[DRY-RUN] 가짜 편입 {len(enter_codes)}종목 주입")
    for c in enter_codes:
        universe.on_enter(c)
    for c in (exit_codes or []):
        universe.on_exit(c)
