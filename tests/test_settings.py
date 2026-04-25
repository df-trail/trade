from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ztrade.config import GuardrailConfig
from ztrade.models import AssetClass, GuardrailDecision, OptionContract, OrderSide, Recommendation, TradeIdea
from ztrade.settings import RecommendationSettingsPolicy, SettingsStore, StrategySettings, TickerTradeSettings, TradingSettings


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

    def test_policy_filters_disabled_option_transaction(self) -> None:
        settings = TradingSettings(
            tickers=(TickerTradeSettings(symbol="AAPL", allowed_transactions=("long_shares",)),)
        )
        recommendation = _recommendation("news_momentum", asset_class=AssetClass.OPTION, option_type="call")
        self.assertIsNone(RecommendationSettingsPolicy(settings, GuardrailConfig()).apply(recommendation))

    def test_policy_uses_strategy_specific_confidence(self) -> None:
        settings = TradingSettings(
            tickers=(
                TickerTradeSettings(
                    symbol="AAPL",
                    strategy_settings={
                        "news_momentum": StrategySettings(enabled=True, min_confidence=0.90),
                    },
                ),
            )
        )
        self.assertIsNone(RecommendationSettingsPolicy(settings, GuardrailConfig()).apply(_recommendation("news_momentum")))


def _recommendation(
    strategy: str,
    adjusted_quantity: int | None = None,
    asset_class: AssetClass = AssetClass.STOCK,
    option_type: str = "call",
) -> Recommendation:
    option_contract = None
    symbol = "AAPL"
    if asset_class == AssetClass.OPTION:
        option_contract = OptionContract(
            underlying="AAPL",
            expiration="2026-05-15",
            strike=200,
            option_type=option_type,
            symbol=f"AAPL-20260515-{option_type.upper()}-200",
        )
        symbol = option_contract.symbol
    return Recommendation(
        idea=TradeIdea(
            symbol=symbol,
            asset_class=asset_class,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=100.0,
            confidence=0.80,
            strategy=strategy,
            thesis="test",
            ta_summary="test",
            option_contract=option_contract,
        ),
        guardrail_decision=GuardrailDecision(accepted=True, adjusted_quantity=adjusted_quantity),
    )


if __name__ == "__main__":
    unittest.main()
