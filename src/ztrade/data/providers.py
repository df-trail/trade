from __future__ import annotations

import asyncio
import csv
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from ztrade.models import Bar, MarketRegime, MarketSnapshot, NewsItem, OptionContract, OptionFlowSignal, Quote


class DataProvider:
    name = "base"

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        raise NotImplementedError

    async def health(self) -> str:
        return self.name


class DemoDataProvider(DataProvider):
    """Small deterministic stream for UI and pipeline smoke testing."""

    name = "demo"

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
                bars = _demo_bars(symbol, base, tick)
                quote = Quote(
                    symbol=symbol,
                    bid=round(last - 0.02, 2),
                    ask=round(last + 0.02, 2),
                    last=last,
                    volume=900_000 + tick * 12_000,
                    relative_volume=1.35 + (tick % 3) * 0.2,
                )
                option_strike = round(base * 1.01, 2)
                option_contract = OptionContract(
                    underlying=symbol,
                    expiration="2026-05-15",
                    strike=option_strike,
                    option_type="call",
                    symbol=f"{symbol}-20260515-C-{option_strike}",
                )
                option_last = round(1.70 + max(0.0, last - base) * 0.18 + (tick % 4) * 0.02, 2)
                option_quote = Quote(
                    symbol=option_contract.symbol,
                    bid=round(option_last - 0.07, 2),
                    ask=round(option_last + 0.07, 2),
                    last=option_last,
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
                option_flow = None
                if tick % 7 == 0 and symbol in {"NVDA", "AAPL", "TSLA"}:
                    option_flow = OptionFlowSignal(
                        underlying=symbol,
                        symbol=option_contract.symbol,
                        side="call_sweep",
                        premium=option_quote.mid * 100 * 100,
                        volume=option_quote.volume,
                        open_interest=option_quote.open_interest or 0,
                        sentiment=0.65,
                        source="demo-flow",
                    )
                yield MarketSnapshot(
                    symbol=symbol,
                    quote=quote,
                    recent_closes=tuple(bar.close for bar in bars),
                    recent_volumes=tuple(bar.volume for bar in bars),
                    recent_bars=bars,
                    option_quote=option_quote,
                    option_contract=option_contract,
                    latest_news=news,
                    option_flow=option_flow,
                    market_regime=MarketRegime(
                        spy_trend=0.35,
                        qqq_trend=0.45,
                        volatility_bias=-0.1,
                        breadth=0.58,
                        risk_on_score=0.63,
                    ),
                    provider=self.name,
                )
                await asyncio.sleep(0.25)
            tick += 1


class ReplayDataProvider(DataProvider):
    name = "replay"

    def __init__(self, snapshots: list[MarketSnapshot], delay_seconds: float = 0.0) -> None:
        self._snapshots = snapshots
        self._delay_seconds = delay_seconds

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        for snapshot in self._snapshots:
            yield snapshot
            if self._delay_seconds > 0:
                await asyncio.sleep(self._delay_seconds)


class CsvReplayDataProvider(DataProvider):
    """Replay OHLCV rows from CSV into normalized snapshots.

    Required columns: symbol,timestamp,open,high,low,close,volume
    Optional columns: bid,ask,relative_volume,vwap
    """

    name = "csv_replay"

    def __init__(self, path: str | Path, delay_seconds: float = 0.0) -> None:
        self._path = Path(path)
        self._delay_seconds = delay_seconds

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        history: dict[str, list[Bar]] = {}
        with self._path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                symbol = row["symbol"].upper()
                timestamp = _parse_timestamp(row["timestamp"])
                close = float(row["close"])
                bar = Bar(
                    symbol=symbol,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=close,
                    volume=int(float(row["volume"])),
                    timestamp=timestamp,
                    vwap=_optional_float(row.get("vwap")),
                )
                symbol_history = history.setdefault(symbol, [])
                symbol_history.append(bar)
                recent_bars = tuple(symbol_history[-120:])
                bid = _optional_float(row.get("bid")) or round(close * 0.9999, 4)
                ask = _optional_float(row.get("ask")) or round(close * 1.0001, 4)
                relative_volume = _optional_float(row.get("relative_volume")) or _relative_volume(recent_bars)
                yield MarketSnapshot(
                    symbol=symbol,
                    quote=Quote(
                        symbol=symbol,
                        bid=bid,
                        ask=ask,
                        last=close,
                        volume=bar.volume,
                        relative_volume=relative_volume,
                        timestamp=timestamp,
                    ),
                    recent_closes=tuple(item.close for item in recent_bars),
                    recent_volumes=tuple(item.volume for item in recent_bars),
                    recent_bars=recent_bars,
                    provider=self.name,
                    received_at=datetime.now(UTC),
                )
                if self._delay_seconds > 0:
                    await asyncio.sleep(self._delay_seconds)


def _demo_bars(symbol: str, base: float, tick: int) -> tuple[Bar, ...]:
    bars: list[Bar] = []
    for index in range(40):
        trend = index * 0.11
        pulse = ((tick + index) % 6) * 0.025
        close = round(base + trend + pulse, 2)
        if index == 39 and tick % 4 == 0:
            close = round(close + 0.35, 2)
        high = round(close + 0.08, 2)
        low = round(close - 0.09, 2)
        open_price = round(close - 0.04, 2)
        bars.append(
            Bar(
                symbol=symbol,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=750_000 + index * 10_000 + tick * 12_000,
                vwap=round((high + low + close) / 3, 4),
            )
        )
    return tuple(bars)


def _parse_timestamp(raw: str) -> datetime:
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _optional_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


def _relative_volume(bars: tuple[Bar, ...]) -> float:
    if len(bars) < 2:
        return 1.0
    current = bars[-1].volume
    baseline = sum(bar.volume for bar in bars[:-1]) / (len(bars) - 1)
    if baseline <= 0:
        return 1.0
    return round(current / baseline, 3)
