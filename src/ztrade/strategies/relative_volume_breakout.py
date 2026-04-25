from __future__ import annotations

from ztrade.analysis.indicators import atr, sma
from ztrade.models import MarketSnapshot, TradeIdea
from ztrade.strategies.base import Strategy
from ztrade.strategies.helpers import directional_long_idea


class RelativeVolumeBreakoutStrategy(Strategy):
    name = "relative_volume_breakout"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 21 or len(closes) < 21:
            return None

        previous_high = max(bar.high for bar in bars[-21:-1])
        current = bars[-1]
        short_avg = sma(closes, 5)
        long_avg = sma(closes, 20)
        current_atr = atr(bars, 14) or 0.0
        if short_avg is None or long_avg is None:
            return None

        broke_range = current.close > previous_high
        trend_ok = short_avg > long_avg
        rvol = snapshot.quote.relative_volume
        if not broke_range or not trend_ok or rvol < 1.35:
            return None

        breakout_strength = min(1.0, max(0.0, (current.close - previous_high) / max(current_atr, 0.01)))
        volume_score = min(1.0, rvol / 2.5)
        regime_score = snapshot.market_regime.risk_on_score if snapshot.market_regime else 0.5
        confidence = round(0.40 * breakout_strength + 0.35 * volume_score + 0.25 * regime_score, 3)
        if confidence < 0.58:
            return None

        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is breaking above the recent range on elevated relative volume.",
            ta_summary=(
                f"Close {current.close:.2f} > 20-bar high {previous_high:.2f}; "
                f"RVOL {rvol:.2f}; ATR {current_atr:.2f}."
            ),
            stock_stop_pct=0.99,
            stock_target_pct=1.03,
            option_stop_pct=0.72,
            option_target_pct=1.55,
        )
