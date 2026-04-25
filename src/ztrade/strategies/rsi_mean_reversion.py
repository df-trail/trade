from __future__ import annotations

from ztrade.analysis.indicators import rsi
from ztrade.models import AssetClass, MarketSnapshot, OrderSide, TradeIdea
from ztrade.strategies.base import Strategy


class RsiMeanReversionStrategy(Strategy):
    name = "rsi_mean_reversion"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 20 or len(closes) < 15:
            return None

        current_rsi = rsi(closes, 14)
        if current_rsi is None or current_rsi > 32:
            return None

        current = bars[-1]
        range_low = min(bar.low for bar in bars[-20:])
        range_high = max(bar.high for bar in bars[-20:])
        range_width = max(range_high - range_low, 0.01)
        near_low_score = 1 - min(1.0, (current.close - range_low) / range_width)
        if near_low_score < 0.55:
            return None

        volume_score = min(1.0, snapshot.quote.relative_volume / 1.8)
        confidence = round(0.50 * ((32 - current_rsi) / 32) + 0.35 * near_low_score + 0.15 * volume_score, 3)
        if confidence < 0.55:
            return None

        return TradeIdea(
            symbol=snapshot.symbol,
            asset_class=AssetClass.STOCK,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=snapshot.quote.ask,
            confidence=confidence,
            strategy=self.name,
            thesis=f"{snapshot.symbol} is oversold near the recent range low with enough volume to attempt a bounce.",
            ta_summary=(
                f"RSI {current_rsi:.1f}; close {current.close:.2f}; "
                f"20-bar low {range_low:.2f}; RVOL {snapshot.quote.relative_volume:.2f}."
            ),
            stop_price=round(current.close * 0.985, 2),
            target_price=round(current.close * 1.018, 2),
            provider=snapshot.provider,
        )
