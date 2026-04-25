from __future__ import annotations

from dataclasses import dataclass

from ztrade.models import Fill, MarketSnapshot, Recommendation
from ztrade.recommendations.engine import RecommendationEngine


@dataclass(frozen=True, slots=True)
class BacktestResult:
    recommendations: tuple[Recommendation, ...]
    fills: tuple[Fill, ...]


class BacktestEngine:
    def __init__(self, recommendation_engine: RecommendationEngine) -> None:
        self._recommendation_engine = recommendation_engine

    def replay(self, snapshots: list[MarketSnapshot]) -> BacktestResult:
        recommendations: list[Recommendation] = []
        for snapshot in snapshots:
            recommendations.extend(self._recommendation_engine.evaluate(snapshot))
        return BacktestResult(recommendations=tuple(recommendations), fills=())
