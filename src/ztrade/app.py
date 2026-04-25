from __future__ import annotations

import asyncio

from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, BotMode
from ztrade.data.providers import DemoDataProvider
from ztrade.execution.engine import ExecutionEngine
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.strategies.registry import default_strategies


async def run_demo() -> None:
    config = AppConfig(bot_mode=BotMode.STAGE_ONLY)
    guardrails = GuardrailEngine(config.guardrails)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    execution = ExecutionEngine(config, PaperBroker(), guardrails)
    provider = DemoDataProvider(config.default_watchlist)

    async for snapshot in provider.stream():
        for recommendation in recommender.evaluate(snapshot):
            await execution.handle_recommendation(recommendation)
            idea = recommendation.idea
            status = recommendation.status.value
            allowed = "allowed" if recommendation.guardrail_decision.accepted else "blocked"
            print(
                f"{status.upper()} {allowed}: {idea.strategy} {idea.side.value} "
                f"{idea.symbol} @ {idea.limit_price:.2f} confidence={idea.confidence:.2f} "
                f"TA='{idea.ta_summary}'"
            )


def main() -> None:
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("zTrade demo stopped.")


if __name__ == "__main__":
    main()
