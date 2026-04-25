from __future__ import annotations

from ztrade.models import MarketSnapshot, Recommendation
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.strategies.base import Strategy


class RecommendationEngine:
    def __init__(self, strategies: tuple[Strategy, ...], guardrails: GuardrailEngine) -> None:
        self._strategies = strategies
        self._guardrails = guardrails

    def evaluate(self, snapshot: MarketSnapshot) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        for strategy in self._strategies:
            idea = strategy.evaluate(snapshot)
            if idea is None:
                continue
            decision = self._guardrails.check(idea, snapshot)
            recommendations.append(Recommendation(idea=idea, guardrail_decision=decision))
        return recommendations
