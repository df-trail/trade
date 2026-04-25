from __future__ import annotations

from abc import ABC, abstractmethod

from ztrade.models import MarketSnapshot, TradeIdea


class Strategy(ABC):
    name: str

    @abstractmethod
    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        """Return a trade idea when the snapshot meets this strategy's setup."""
