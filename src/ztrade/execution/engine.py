from __future__ import annotations

from ztrade.brokers.base import Broker, OrderRejectedError
from ztrade.config import AppConfig, BotMode
from ztrade.models import Fill, Order, OrderType, Recommendation, RecommendationStatus
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.storage.sqlite import TradingStore


class ExecutionEngine:
    def __init__(
        self,
        config: AppConfig,
        broker: Broker,
        guardrails: GuardrailEngine,
        store: TradingStore | None = None,
    ) -> None:
        self._config = config
        self._broker = broker
        self._guardrails = guardrails
        self._store = store

    async def handle_recommendation(self, recommendation: Recommendation) -> Fill | None:
        if not recommendation.guardrail_decision.accepted:
            recommendation.status = RecommendationStatus.BLOCKED
            self._record_recommendation(recommendation)
            return None

        if self._config.bot_mode == BotMode.STAGE_ONLY:
            recommendation.status = RecommendationStatus.STAGED
            self._record_recommendation(recommendation)
            return None

        if self._config.bot_mode == BotMode.AUTO_EXIT_ONLY:
            recommendation.status = RecommendationStatus.STAGED
            self._record_recommendation(recommendation)
            return None

        if self._config.bot_mode == BotMode.AUTO_TRADE_LIMITED and not self._config.guardrails.live_trading_enabled:
            recommendation.status = RecommendationStatus.STAGED
            self._record_recommendation(recommendation)
            return None

        if self._config.bot_mode == BotMode.AUTO_PAPER:
            self._record_recommendation(recommendation)
            return await self.approve(recommendation)

        recommendation.status = RecommendationStatus.STAGED
        self._record_recommendation(recommendation)
        return None

    async def approve(self, recommendation: Recommendation) -> Fill | None:
        if not recommendation.guardrail_decision.accepted:
            recommendation.status = RecommendationStatus.BLOCKED
            self._record_recommendation(recommendation)
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
        if self._store:
            self._store.update_recommendation_status(recommendation)
            self._store.record_order(order, recommendation_id=recommendation.id, status="approved")
        try:
            fill = await self._broker.place_order(order)
        except (OrderRejectedError, ValueError) as exc:
            recommendation.status = RecommendationStatus.BLOCKED
            if self._store:
                self._store.record_order(order, recommendation_id=recommendation.id, status="rejected")
                self._store.record_event(
                    "order_rejected",
                    {"recommendation_id": recommendation.id, "reason": str(exc), "order": order},
                    symbol=order.symbol,
                )
                self._store.update_recommendation_status(recommendation)
            return None
        if self._store:
            self._store.record_fill(fill, recommendation_id=recommendation.id)
            self._store.record_order(order, recommendation_id=recommendation.id, status="filled")
        self._guardrails.record_trade(idea, quantity)
        recommendation.status = RecommendationStatus.EXECUTED
        if self._store:
            self._store.update_recommendation_status(recommendation)
        return fill

    def _record_recommendation(self, recommendation: Recommendation) -> None:
        if self._store:
            self._store.record_recommendation(recommendation)

    def record_manual_status(self, recommendation: Recommendation) -> None:
        if self._store:
            self._store.update_recommendation_status(recommendation)
