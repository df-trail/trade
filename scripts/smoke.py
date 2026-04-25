from __future__ import annotations

import asyncio

from ztrade.backtest.engine import BacktestConfig, BacktestEngine
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig
from ztrade.data.factory import create_data_provider
from ztrade.execution.engine import ExecutionEngine
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.strategies.registry import default_strategies


async def main() -> None:
    config = AppConfig()
    guardrails = GuardrailEngine(config.guardrails)
    broker = PaperBroker(config.guardrails.account_equity)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    execution = ExecutionEngine(config, broker, guardrails)
    provider = create_data_provider(config)

    counts: dict[str, int] = {}
    seen = 0
    async for snapshot in provider.stream():
        seen += 1
        for recommendation in recommender.evaluate(snapshot):
            counts[recommendation.idea.strategy] = counts.get(recommendation.idea.strategy, 0) + 1
        if seen >= 30:
            break

    backtest = BacktestEngine(
        config,
        recommender,
        execution,
        broker,
        BacktestConfig(max_snapshots=60, max_hold_snapshots=8),
    )
    result = await backtest.run(create_data_provider(config))
    print(f"strategy_counts={counts}")
    print(
        "backtest "
        f"recommendations={len(result.recommendations)} "
        f"fills={len(result.fills)} "
        f"trades={len(result.trades)} "
        f"ending_equity={result.report.ending_equity:.2f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
