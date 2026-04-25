from __future__ import annotations

from ztrade.brokers.base import Broker
from ztrade.config import AppConfig, BotMode
from ztrade.models import Fill, Order, OrderType, Recommendation, RecommendationStatus
from ztrade.risk.guardrails import GuardrailEngine


class ExecutionEngine:
    def __init__(self, config: AppConfig, broker: Broker, guardrails: GuardrailEngine) -> None:
        self._config = config
        self._broker = broker
        self._guardrails = guardrails

    async def handle_recommendation(self, recommendation: Recommendation) -> Fill | None:
        if not recommendation.guardrail_decision.accepted:
            recommendation.status = RecommendationStatus.BLOCKED
            return None

        if self._config.bot_mode == BotMode.STAGE_ONLY:
            recommendation.status = RecommendationStatus.STAGED
            return None

        if self._config.bot_mode == BotMode.AUTO_EXIT_ONLY:
            recommendation.status = RecommendationStatus.STAGED
            return None

        if self._config.bot_mode == BotMode.AUTO_TRADE_LIMITED and not self._config.guardrails.live_trading_enabled:
            recommendation.status = RecommendationStatus.STAGED
            return None

        if self._config.bot_mode == BotMode.AUTO_PAPER:
            return await self.approve(recommendation)

        recommendation.status = RecommendationStatus.STAGED
        return None

    async def approve(self, recommendation: Recommendation) -> Fill | None:
        if not recommendation.guardrail_decision.accepted:
            recommendation.status = RecommendationStatus.BLOCKED
            return None

        idea = recommendation.idea
        quantity = recommendation.guardrail_decision.adjusted_quantity or idea.quantity
        order = Order(
            symbol=idea.symbol,
            asset_class=idea.asset_class,
            side=idea.side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=idea.limit_price,
            option_contract=idea.option_contract,
        )
        recommendation.status = RecommendationStatus.APPROVED
        fill = await self._broker.place_order(order)
        self._guardrails.record_trade(idea, quantity)
        recommendation.status = RecommendationStatus.EXECUTED
        return fill
