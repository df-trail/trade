from __future__ import annotations

import unittest

from ztrade.analysis.indicators import atr, ema, percent_change, rsi, sma, vwap, zscore
from ztrade.models import Bar


class IndicatorTests(unittest.TestCase):
    def test_sma_and_ema(self) -> None:
        values = [1, 2, 3, 4, 5]
        self.assertEqual(sma(values, 3), 4)
        self.assertAlmostEqual(ema(values, 3), 4.0)

    def test_rsi_handles_strong_uptrend(self) -> None:
        values = tuple(float(value) for value in range(1, 20))
        self.assertEqual(rsi(values, 14), 100.0)

    def test_vwap_and_atr(self) -> None:
        bars = tuple(
            Bar(symbol="T", open=10, high=11, low=9, close=10 + index, volume=100 + index)
            for index in range(20)
        )
        self.assertIsNotNone(vwap(bars, 10))
        self.assertIsNotNone(atr(bars, 14))

    def test_percent_change_and_zscore(self) -> None:
        self.assertEqual(percent_change(100, 110), 10)
        self.assertGreater(zscore([1, 2, 3, 4, 10]) or 0, 0)


if __name__ == "__main__":
    unittest.main()
