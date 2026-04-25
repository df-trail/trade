from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ztrade.analytics.performance import TradeRecord
from ztrade.models import Fill, MarketSnapshot, Recommendation


class BacktestEventType(StrEnum):
    BAR = "bar"
    SIGNAL = "signal"
    FILTERED_SIGNAL = "filtered_signal"
    ENTRY_FILL = "entry_fill"
    EXIT_FILL = "exit_fill"
    TRADE_CLOSED = "trade_closed"
    EQUITY = "equity"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class BacktestEvent:
    event_type: BacktestEventType
    snapshot_index: int
    symbol: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    snapshot: MarketSnapshot | None = None
    recommendation: Recommendation | None = None
    fill: Fill | None = None
    trade: TradeRecord | None = None
    equity: float | None = None
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
