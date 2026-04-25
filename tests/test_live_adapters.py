from __future__ import annotations

import unittest
from typing import Any

from ztrade.data.live import FinnhubNewsClient, PolygonStockSnapshotProvider, TradierOptionsClient


class FakeHttp:
    def __init__(self, payload: dict[str, Any] | list[Any]) -> None:
        self.payload = payload

    def get_json(
        self,
        url: str,
        params: dict[str, str | int | float | bool | None] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self.payload


class LiveAdapterParsingTests(unittest.TestCase):
    def test_polygon_snapshot_normalizes_quote_and_bar(self) -> None:
        provider = PolygonStockSnapshotProvider(
            symbols=("AAPL",),
            api_key="test",
            http=FakeHttp(
                {
                    "ticker": {
                        "lastQuote": {"p": 199.9, "P": 200.1, "t": 1_700_000_000_000_000_000},
                        "lastTrade": {"p": 200.0, "t": 1_700_000_000_000_000_000},
                        "min": {"o": 199, "h": 201, "l": 198, "c": 200, "v": 1000, "vw": 199.5},
                        "day": {"v": 2_000_000},
                        "prevDay": {"v": 1_000_000},
                    }
                }
            ),
        )
        snapshot = provider._snapshot("AAPL")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.quote.bid, 199.9)
        self.assertEqual(snapshot.quote.ask, 200.1)
        self.assertEqual(snapshot.quote.relative_volume, 2.0)
        self.assertEqual(snapshot.recent_bars[-1].close, 200)

    def test_finnhub_news_normalizes_latest_headline(self) -> None:
        client = FinnhubNewsClient(
            api_key="test",
            http=FakeHttp(
                [
                    {"datetime": 1_700_000_001, "headline": "Older", "source": "source-a"},
                    {"datetime": 1_700_000_002, "headline": "Newer", "source": "source-b"},
                ]
            ),
        )
        news = client.latest_company_news("AAPL")
        self.assertIsNotNone(news)
        assert news is not None
        self.assertEqual(news.headline, "Newer")
        self.assertEqual(news.symbols, ("AAPL",))

    def test_tradier_option_chain_normalizes_greeks(self) -> None:
        client = TradierOptionsClient(
            token="test",
            http=FakeHttp(
                {
                    "options": {
                        "option": {
                            "symbol": "AAPL260515C00200000",
                            "expiration_date": "2026-05-15",
                            "strike": 200,
                            "option_type": "call",
                            "bid": 1.2,
                            "ask": 1.4,
                            "last": 1.3,
                            "volume": 100,
                            "open_interest": 500,
                            "days_to_expiration": 21,
                            "greeks": {"delta": 0.5, "gamma": 0.02, "theta": -0.04, "vega": 0.11, "mid_iv": 0.35},
                        }
                    }
                }
            ),
        )
        chain = client.option_chain("AAPL", "2026-05-15")
        self.assertEqual(len(chain), 1)
        contract, quote = chain[0]
        self.assertEqual(contract.strike, 200)
        self.assertEqual(quote.delta, 0.5)
        self.assertEqual(quote.implied_volatility, 0.35)


if __name__ == "__main__":
    unittest.main()
