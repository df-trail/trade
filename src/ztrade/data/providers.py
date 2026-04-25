from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ztrade.models import MarketSnapshot, NewsItem, OptionContract, Quote


class DataProvider:
    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        raise NotImplementedError


class DemoDataProvider(DataProvider):
    """Small deterministic stream for UI and pipeline smoke testing."""

    def __init__(self, symbols: tuple[str, ...]) -> None:
        self._symbols = symbols

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        seed_prices = {
            "SPY": 525.0,
            "QQQ": 445.0,
            "AAPL": 195.0,
            "NVDA": 890.0,
            "TSLA": 175.0,
        }
        tick = 0
        while True:
            for symbol in self._symbols:
                base = seed_prices.get(symbol, 100.0)
                drift = (tick % 8) * 0.18
                last = round(base + drift, 2)
                quote = Quote(
                    symbol=symbol,
                    bid=round(last - 0.02, 2),
                    ask=round(last + 0.02, 2),
                    last=last,
                    volume=900_000 + tick * 12_000,
                    relative_volume=1.35 + (tick % 3) * 0.2,
                )
                option_contract = OptionContract(
                    underlying=symbol,
                    expiration="2026-05-15",
                    strike=round(last * 1.01, 2),
                    option_type="call",
                    symbol=f"{symbol}-20260515-C-{round(last * 1.01, 2)}",
                )
                option_quote = Quote(
                    symbol=option_contract.symbol,
                    bid=1.8,
                    ask=1.94,
                    last=1.87,
                    volume=180 + tick,
                    relative_volume=1.7,
                    open_interest=650,
                    implied_volatility=0.42,
                    delta=0.48,
                    gamma=0.04,
                    theta=-0.08,
                    vega=0.11,
                    days_to_expiration=21,
                )
                news = None
                if tick % 5 == 0 and symbol in {"NVDA", "TSLA"}:
                    news = NewsItem(
                        headline=f"{symbol} breaking catalyst hits high-urgency feed",
                        symbols=(symbol,),
                        source="demo-news",
                        sentiment=0.72,
                        urgency=0.86,
                    )
                yield MarketSnapshot(
                    symbol=symbol,
                    quote=quote,
                    recent_closes=tuple(round(base + i * 0.11, 2) for i in range(20)),
                    recent_volumes=tuple(750_000 + i * 10_000 for i in range(20)),
                    option_quote=option_quote,
                    option_contract=option_contract,
                    latest_news=news,
                )
                await asyncio.sleep(0.25)
            tick += 1
