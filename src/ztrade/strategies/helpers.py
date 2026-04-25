from __future__ import annotations

from ztrade.models import AssetClass, MarketSnapshot, OrderSide, TradeIdea


def directional_long_idea(
    *,
    snapshot: MarketSnapshot,
    strategy: str,
    confidence: float,
    thesis: str,
    ta_summary: str,
    prefer_option_threshold: float = 0.70,
    stock_stop_pct: float = 0.985,
    stock_target_pct: float = 1.025,
    option_stop_pct: float = 0.75,
    option_target_pct: float = 1.45,
) -> TradeIdea:
    use_option = snapshot.option_quote is not None and confidence >= prefer_option_threshold
    if use_option:
        option_quote = snapshot.option_quote
        return TradeIdea(
            symbol=option_quote.symbol,
            asset_class=AssetClass.OPTION,
            side=OrderSide.BUY,
            quantity=1,
            limit_price=option_quote.mid,
            confidence=confidence,
            strategy=strategy,
            thesis=thesis,
            ta_summary=ta_summary,
            stop_price=round(option_quote.mid * option_stop_pct, 2),
            target_price=round(option_quote.mid * option_target_pct, 2),
            option_contract=snapshot.option_contract,
            provider=snapshot.provider,
        )

    quote = snapshot.quote
    return TradeIdea(
        symbol=snapshot.symbol,
        asset_class=AssetClass.STOCK,
        side=OrderSide.BUY,
        quantity=1,
        limit_price=quote.ask,
        confidence=confidence,
        strategy=strategy,
        thesis=thesis,
        ta_summary=ta_summary,
        stop_price=round(quote.last * stock_stop_pct, 2),
        target_price=round(quote.last * stock_target_pct, 2),
        provider=snapshot.provider,
    )


def directional_put_idea(
    *,
    snapshot: MarketSnapshot,
    strategy: str,
    confidence: float,
    thesis: str,
    ta_summary: str,
    option_stop_pct: float = 0.70,
    option_target_pct: float = 1.55,
) -> TradeIdea | None:
    if snapshot.option_quote is None or snapshot.option_contract is None:
        return None
    if snapshot.option_contract.option_type.lower() != "put":
        return None
    option_quote = snapshot.option_quote
    return TradeIdea(
        symbol=option_quote.symbol,
        asset_class=AssetClass.OPTION,
        side=OrderSide.BUY,
        quantity=1,
        limit_price=option_quote.mid,
        confidence=confidence,
        strategy=strategy,
        thesis=thesis,
        ta_summary=ta_summary,
        stop_price=round(option_quote.mid * option_stop_pct, 2),
        target_price=round(option_quote.mid * option_target_pct, 2),
        option_contract=snapshot.option_contract,
        provider=snapshot.provider,
    )
