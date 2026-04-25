from __future__ import annotations

import asyncio
import unittest

from ztrade.backtest.engine import BacktestConfig, BacktestEngine
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig
from ztrade.data.factory import create_data_provider
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.execution.engine import ExecutionEngine
from ztrade.strategies.registry import default_strategies


class PipelineTests(unittest.TestCase):
    def test_demo_provider_generates_multiple_strategy_recommendations(self) -> None:
        async def run() -> set[str]:
            config = AppConfig()
            engine = RecommendationEngine(default_strategies(), GuardrailEngine(config.guardrails))
            provider = create_data_provider(config)
            strategies: set[str] = set()
            seen = 0
            async for snapshot in provider.stream():
                seen += 1
                for recommendation in engine.evaluate(snapshot):
                    strategies.add(recommendation.idea.strategy)
                if seen >= 30:
                    break
            return strategies

        strategies = asyncio.run(run())
        self.assertIn("news_momentum", strategies)
        self.assertIn("relative_volume_breakout", strategies)
        self.assertIn("options_flow_momentum", strategies)

    def test_demo_backtest_closes_trades(self) -> None:
        async def run() -> tuple[int, int, float, bool]:
            config = AppConfig()
            guardrails = GuardrailEngine(config.guardrails)
            broker = PaperBroker(config.guardrails.account_equity)
            recommender = RecommendationEngine(default_strategies(), guardrails)
            execution = ExecutionEngine(config, broker, guardrails)
            backtest = BacktestEngine(
                config,
                recommender,
                execution,
                broker,
                BacktestConfig(max_snapshots=60, max_hold_snapshots=8),
            )
            result = await backtest.run(create_data_provider(config))
            has_trade_metadata = all(
                trade.entry_index is not None
                and trade.exit_index is not None
                and trade.entry_timestamp is not None
                and trade.exit_timestamp is not None
                for trade in result.trades
            )
            return len(result.recommendations), len(result.trades), result.report.ending_equity, has_trade_metadata

        recommendations, trades, equity, has_trade_metadata = asyncio.run(run())
        self.assertGreater(recommendations, 0)
        self.assertGreater(trades, 0)
        self.assertGreater(equity, 0)
        self.assertTrue(has_trade_metadata)

    def test_backtest_can_filter_recommendations(self) -> None:
        async def run() -> int:
            config = AppConfig()
            guardrails = GuardrailEngine(config.guardrails)
            broker = PaperBroker(config.guardrails.account_equity)
            recommender = RecommendationEngine(default_strategies(), guardrails)
            execution = ExecutionEngine(config, broker, guardrails)
            backtest = BacktestEngine(
                config,
                recommender,
                execution,
                broker,
                BacktestConfig(max_snapshots=20, max_hold_snapshots=4),
                recommendation_filter=lambda _recommendation: None,
            )
            result = await backtest.run(create_data_provider(config))
            return len(result.recommendations)

        self.assertEqual(asyncio.run(run()), 0)


if __name__ == "__main__":
    unittest.main()
