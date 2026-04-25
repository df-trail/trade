from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ztrade.config import GuardrailConfig
from ztrade.models import AssetClass, GuardrailDecision, OrderSide, Recommendation, TradeIdea
from ztrade.settings import RecommendationSettingsPolicy, SettingsStore, TickerTradeSettings, TradingSettings


class SettingsTests(unittest.TestCase):
    def test_settings_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            store = SettingsStore(path)
            settings = TradingSettings(
                tickers=(
                    TickerTradeSettings(
                        symbol="aapl",
                        trade_shares=True,
                        trade_simple=False,
                        strategies=("news_momentum",),
                        max_position_fraction=0.05,
                    ),
                )
            )
            store.save(settings)
            loaded = store.load(defaults=("SPY",))
            self.assertEqual(loaded.active_symbols, ("AAPL",))
            self.assertFalse(loaded.tickers[0].trade_simple)
            self.assertEqual(loaded.tickers[0].strategies, ("news_momentum",))

    def test_policy_filters_disabled_strategy(self) -> None:
        settings = TradingSettings(
            tickers=(TickerTradeSettings(symbol="AAPL", strategies=("news_momentum",)),)
        )
        recommendation = _recommendation("relative_volume_breakout")
        self.assertIsNone(RecommendationSettingsPolicy(settings, GuardrailConfig()).apply(recommendation))

    def test_policy_adjusts_quantity_to_position_cap(self) -> None:
        settings = TradingSettings(
            tickers=(TickerTradeSettings(symbol="AAPL", max_position_fraction=0.02),)
        )
        recommendation = _recommendation("news_momentum", adjusted_quantity=10)
        filtered = RecommendationSettingsPolicy(settings, GuardrailConfig(account_equity=10_000)).apply(recommendation)
        self.assertIsNotNone(filtered)
        assert filtered is not None
        self.assertEqual(filtered.guardrail_decision.adjusted_quantity, 2)

    def test_policy_enforces_daily_symbol_limit(self) -> None:
        settings = TradingSettings(
            tickers=(TickerTradeSettings(symbol="AAPL", max_trades_per_day=1),)
        )
        policy = RecommendationSettingsPolicy(settings, GuardrailConfig(account_equity=10_000))
        self.assertIsNotNone(policy.apply(_recommendation("news_momentum")))
        self.assertIsNone(policy.apply(_recommendation("news_momentum")))


def _recommendation(strategy: str, adjusted_quantity: int | None = None) -> Recommendation:
    return Recommendation(
        idea=TradeIdea(
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=100.0,
            confidence=0.80,
            strategy=strategy,
            thesis="test",
            ta_summary="test",
        ),
        guardrail_decision=GuardrailDecision(accepted=True, adjusted_quantity=adjusted_quantity),
    )


if __name__ == "__main__":
    unittest.main()
