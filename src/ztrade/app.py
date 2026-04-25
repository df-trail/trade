from __future__ import annotations

import asyncio

from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, BotMode
from ztrade.data.factory import create_data_provider
from ztrade.env import load_env_file
from ztrade.execution.engine import ExecutionEngine
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.storage.sqlite import TradingStore
from ztrade.strategies.registry import default_strategies


async def run_demo() -> None:
    load_env_file()
    config = AppConfig(bot_mode=BotMode.STAGE_ONLY)
    store = TradingStore(config.database_path)
    store.initialize()
    guardrails = GuardrailEngine(config.guardrails)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    broker = PaperBroker(config.guardrails.account_equity, store=store)
    execution = ExecutionEngine(config, broker, guardrails, store=store)
    provider = create_data_provider(config)

    async for snapshot in provider.stream():
        if config.record_market_events:
            store.record_market_snapshot(snapshot)
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
