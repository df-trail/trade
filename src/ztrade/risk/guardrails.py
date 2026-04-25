from __future__ import annotations

from datetime import UTC, datetime

from ztrade.config import GuardrailConfig
from ztrade.models import AssetClass, GuardrailDecision, MarketSnapshot, TradeIdea


class GuardrailEngine:
    def __init__(self, config: GuardrailConfig) -> None:
        self._config = config
        self._open_positions = 0
        self._open_option_contracts = 0
        self._trades_today = 0
        self._day_trade_count_rolling = 0
        self._daily_pnl = 0.0

    def check(self, idea: TradeIdea, snapshot: MarketSnapshot) -> GuardrailDecision:
        reasons: list[str] = []
        cfg = self._config

        if cfg.kill_switch_enabled:
            reasons.append("Kill switch is enabled.")
        if idea.confidence < cfg.min_confidence_to_stage:
            reasons.append(f"Confidence {idea.confidence:.2f} is below staging threshold.")
        if cfg.margin_enabled:
            reasons.append("Margin is not allowed for this project.")
        if self._open_positions >= cfg.max_open_positions:
            reasons.append("Max open positions reached.")
        if self._trades_today >= cfg.max_trades_per_day:
            reasons.append("Max trades per day reached.")
        if cfg.account_under_25k and cfg.pdt_protection_enabled and self._day_trade_count_rolling >= 3:
            reasons.append("PDT guardrail blocks another day trade for account under $25k.")
        if self._daily_pnl <= -(cfg.account_equity * cfg.max_daily_loss_fraction):
            reasons.append("Daily loss circuit breaker is active.")

        quote = snapshot.option_quote if idea.asset_class == AssetClass.OPTION else snapshot.quote
        age_ms = (datetime.now(UTC) - quote.timestamp).total_seconds() * 1000
        if age_ms > cfg.max_quote_age_ms:
            reasons.append("Quote is stale.")

        if idea.asset_class == AssetClass.STOCK:
            if quote.spread_bps > cfg.max_stock_spread_bps:
                reasons.append("Stock spread is too wide.")
            if quote.volume < cfg.min_stock_volume:
                reasons.append("Stock volume is below minimum.")
            if quote.relative_volume < cfg.min_relative_volume:
                reasons.append("Relative volume is below minimum.")
        else:
            if quote.spread_pct > cfg.max_option_spread_pct:
                reasons.append("Option spread is too wide.")
            if (quote.open_interest or 0) < cfg.min_option_open_interest:
                reasons.append("Option open interest is below minimum.")
            if quote.volume < cfg.min_option_volume:
                reasons.append("Option volume is below minimum.")
            if quote.mid > cfg.max_option_premium:
                reasons.append("Option premium is above maximum.")
            dte = quote.days_to_expiration
            if dte is None or dte < cfg.min_days_to_expiration or dte > cfg.max_days_to_expiration:
                reasons.append("Option expiration is outside allowed DTE range.")
            if self._open_option_contracts + idea.quantity > cfg.max_open_option_contracts:
                reasons.append("Max open option contracts reached.")

        adjusted_quantity = self._confidence_sized_quantity(idea)
        if adjusted_quantity < 1:
            reasons.append("Confidence-sized quantity is below one unit.")

        return GuardrailDecision(
            accepted=not reasons,
            reasons=tuple(reasons),
            adjusted_quantity=adjusted_quantity if adjusted_quantity != idea.quantity else None,
        )

    def record_trade(self, idea: TradeIdea, quantity: int | None = None) -> None:
        executed_quantity = quantity or idea.quantity
        self._trades_today += 1
        self._open_positions += 1
        if idea.asset_class == AssetClass.OPTION:
            self._open_option_contracts += executed_quantity

    def _confidence_sized_quantity(self, idea: TradeIdea) -> int:
        cfg = self._config
        confidence_span = max(0.0, min(1.0, (idea.confidence - cfg.min_confidence_to_stage) / 0.45))
        fraction = cfg.min_position_fraction + confidence_span * (
            cfg.max_position_fraction - cfg.min_position_fraction
        )
        notional_cap = cfg.account_equity * fraction
        multiplier = 100 if idea.asset_class == AssetClass.OPTION else 1
        unit_cost = idea.limit_price * multiplier
        if unit_cost <= 0:
            return 0
        return max(1, int(notional_cap // unit_cost))
