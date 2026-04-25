from __future__ import annotations

from ztrade.analysis.indicators import sma
from ztrade.models import AssetClass, MarketSnapshot, OrderSide, TradeIdea
from ztrade.strategies.base import Strategy


class OptionsFlowMomentumStrategy(Strategy):
    name = "options_flow_momentum"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.option_flow is None or snapshot.option_quote is None:
            return None
        if snapshot.option_flow.sentiment < 0.55:
            return None

        closes = snapshot.recent_closes
        if len(closes) < 20:
            return None
        short_avg = sma(closes, 5)
        long_avg = sma(closes, 20)
        if short_avg is None or long_avg is None:
            return None

        flow = snapshot.option_flow
        trend_score = 1.0 if short_avg > long_avg else 0.4
        premium_score = min(1.0, flow.premium / 25_000)
        participation_score = min(1.0, flow.volume / max(flow.open_interest, 1))
        volume_score = min(1.0, snapshot.quote.relative_volume / 2.0)
        confidence = round(
            0.30 * flow.sentiment
            + 0.25 * trend_score
            + 0.20 * premium_score
            + 0.15 * participation_score
            + 0.10 * volume_score,
            3,
        )
        if confidence < 0.60:
            return None

        option_quote = snapshot.option_quote
        return TradeIdea(
            symbol=option_quote.symbol,
            asset_class=AssetClass.OPTION,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=option_quote.mid,
            confidence=confidence,
            strategy=self.name,
            thesis=f"{snapshot.symbol} has bullish unusual options flow aligned with short-term momentum.",
            ta_summary=(
                f"Flow {flow.side}; premium ${flow.premium:,.0f}; "
                f"5-bar avg {short_avg:.2f} vs 20-bar avg {long_avg:.2f}; RVOL {snapshot.quote.relative_volume:.2f}."
            ),
            stop_price=round(option_quote.mid * 0.70, 2),
            target_price=round(option_quote.mid * 1.60, 2),
            option_contract=snapshot.option_contract,
            provider=snapshot.provider,
        )
