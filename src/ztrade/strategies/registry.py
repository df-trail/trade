from __future__ import annotations

from ztrade.strategies.base import Strategy
from ztrade.strategies.news_momentum import NewsMomentumStrategy


def default_strategies() -> tuple[Strategy, ...]:
    return (NewsMomentumStrategy(),)
