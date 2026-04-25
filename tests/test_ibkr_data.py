from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime, timedelta

from ztrade.data.ibkr import IbkrHistoricalDataProvider, IbkrSnapshotProvider
from ztrade.models import Bar, Quote


class FakeIbkrMarketDataClient:
    def __init__(self) -> None:
        self.disconnected = False

    def historical_bars(self, symbol: str, **_kwargs: object) -> tuple[Bar, ...]:
        start = datetime(2026, 4, 24, 13, 30, tzinfo=UTC)
        return tuple(
            Bar(
                symbol=symbol,
                open=100 + index,
                high=101 + index,
                low=99 + index,
                close=100.5 + index,
                volume=1_000 + index * 100,
                timestamp=start + timedelta(minutes=index),
            )
            for index in range(3)
        )

    def quote_snapshot(self, symbol: str, **_kwargs: object) -> Quote:
        return Quote(
            symbol=symbol,
            bid=103.0,
            ask=103.1,
            last=103.05,
            volume=10_000,
            relative_volume=1.0,
            timestamp=datetime(2026, 4, 24, 14, 0, tzinfo=UTC),
        )

    def disconnect(self) -> None:
        self.disconnected = True


class IbkrDataProviderTests(unittest.TestCase):
    def test_historical_provider_replays_ibkr_bars_as_snapshots(self) -> None:
        async def run() -> list[float]:
            provider = IbkrHistoricalDataProvider(("AAPL",), client=FakeIbkrMarketDataClient())
            closes: list[float] = []
            async for snapshot in provider.stream():
                closes.append(snapshot.quote.last)
            return closes

        self.assertEqual(asyncio.run(run()), [100.5, 101.5, 102.5])

    def test_snapshot_provider_combines_quote_and_recent_bars(self) -> None:
        async def run() -> tuple[float, int]:
            provider = IbkrSnapshotProvider(
                ("AAPL",),
                client=FakeIbkrMarketDataClient(),
                poll_interval_seconds=0.0,
            )
            async for snapshot in provider.stream():
                return snapshot.quote.last, len(snapshot.recent_bars)
            raise AssertionError("provider yielded no snapshots")

        last, bars = asyncio.run(run())
        self.assertEqual(last, 103.05)
        self.assertEqual(bars, 3)


if __name__ == "__main__":
    unittest.main()
