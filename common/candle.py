"""기본 데이터 모델 (StockDante 이식)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """단일 봉(분봉/일봉 공통).

    time: 식별용 문자열(예 '0930' 또는 '20260603'). 정렬은 호출자가 보장(오래된→최신).
    """
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def is_bull(self) -> bool:
        """양봉 여부 (종가 > 시가)."""
        return self.close > self.open

    @property
    def body(self) -> float:
        """몸통 길이(절대값)."""
        return abs(self.close - self.open)

    @property
    def full_range(self) -> float:
        """전체 길이(고가-저가)."""
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        """몸통/전체 비율 (0~1). 전체길이 0이면 0."""
        rng = self.full_range
        return self.body / rng if rng > 0 else 0.0

    @property
    def change_pct(self) -> float:
        """직전 시가 대비 상승률(%) — 봉 내부 등락. 시가 0이면 0."""
        return (self.close - self.open) / self.open * 100 if self.open > 0 else 0.0
