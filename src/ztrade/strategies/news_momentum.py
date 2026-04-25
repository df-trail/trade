from __future__ import annotations

from statistics import mean

from ztrade.models import MarketSnapshot, TradeIdea
from ztrade.strategies.base import Strategy
from ztrade.strategies.helpers import directional_long_idea


class NewsMomentumStrategy(Strategy):
    name = "news_momentum"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        quote = snapshot.quote
        closes = snapshot.recent_closes
        if len(closes) < 10:
            return None

        short_avg = mean(closes[-5:])
        long_avg = mean(closes[-20:])
        trend_score = 1.0 if short_avg > long_avg else 0.0
        volume_score = min(1.0, quote.relative_volume / 2.5)
        news_score = 0.0
        if snapshot.latest_news:
            news_score = max(0.0, snapshot.latest_news.sentiment) * snapshot.latest_news.urgency

        confidence = round(0.35 * trend_score + 0.30 * volume_score + 0.35 * news_score, 3)
        if confidence < 0.55:
            return None

        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} positive catalyst with volume expansion and upward short-term trend.",
            ta_summary=(
                f"5-bar avg {short_avg:.2f} > 20-bar avg {long_avg:.2f}; "
                f"RVOL {quote.relative_volume:.2f}."
            ),
        )
