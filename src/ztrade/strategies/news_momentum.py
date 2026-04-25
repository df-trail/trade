from __future__ import annotations

from statistics import mean

from ztrade.models import AssetClass, MarketSnapshot, OrderSide, TradeIdea
from ztrade.strategies.base import Strategy


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

        use_option = snapshot.option_quote is not None and confidence >= 0.70
        if use_option:
            option_quote = snapshot.option_quote
            return TradeIdea(
                symbol=option_quote.symbol,
                asset_class=AssetClass.OPTION,
                side=OrderSide.BUY,
                quantity=1,
                limit_price=option_quote.mid,
                confidence=confidence,
                strategy=self.name,
                thesis=f"{snapshot.symbol} positive catalyst with volume expansion and upward short-term trend.",
                ta_summary=f"5-bar avg {short_avg:.2f} > 20-bar avg {long_avg:.2f}; RVOL {quote.relative_volume:.2f}.",
                stop_price=round(option_quote.mid * 0.75, 2),
                target_price=round(option_quote.mid * 1.45, 2),
                option_contract=snapshot.option_contract,
            )

        return TradeIdea(
            symbol=snapshot.symbol,
            asset_class=AssetClass.STOCK,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=quote.ask,
            confidence=confidence,
            strategy=self.name,
            thesis=f"{snapshot.symbol} momentum setup with volume confirmation.",
            ta_summary=f"5-bar avg {short_avg:.2f} > 20-bar avg {long_avg:.2f}; RVOL {quote.relative_volume:.2f}.",
            stop_price=round(quote.last * 0.985, 2),
            target_price=round(quote.last * 1.025, 2),
        )
