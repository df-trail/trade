from __future__ import annotations

from ztrade.analysis.indicators import sma, vwap
from ztrade.models import MarketSnapshot, TradeIdea
from ztrade.strategies.base import Strategy
from ztrade.strategies.helpers import directional_long_idea


class VwapReclaimStrategy(Strategy):
    name = "vwap_reclaim"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 20 or len(closes) < 20:
            return None

        current_vwap = vwap(bars, 20)
        previous_vwap = vwap(bars[:-1], 20)
        short_avg = sma(closes, 5)
        if current_vwap is None or previous_vwap is None or short_avg is None:
            return None

        previous_close = bars[-2].close
        current_close = bars[-1].close
        reclaimed = previous_close < previous_vwap and current_close > current_vwap
        if not reclaimed or snapshot.quote.relative_volume < 1.1:
            return None

        reclaim_score = min(1.0, (current_close - current_vwap) / max(current_vwap * 0.003, 0.01))
        trend_score = 1.0 if current_close > short_avg else 0.5
        volume_score = min(1.0, snapshot.quote.relative_volume / 2.0)
        confidence = round(0.45 * reclaim_score + 0.25 * trend_score + 0.30 * volume_score, 3)
        if confidence < 0.56:
            return None

        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} reclaimed VWAP with confirming volume.",
            ta_summary=(
                f"Close {current_close:.2f} > VWAP {current_vwap:.2f}; "
                f"previous close {previous_close:.2f} was below VWAP; RVOL {snapshot.quote.relative_volume:.2f}."
            ),
            prefer_option_threshold=0.72,
            stock_stop_pct=0.992,
            stock_target_pct=1.022,
            option_stop_pct=0.78,
            option_target_pct=1.35,
        )
