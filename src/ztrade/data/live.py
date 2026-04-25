from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ztrade.data.http import JsonHttpClient
from ztrade.data.providers import DataProvider
from ztrade.models import Bar, MarketSnapshot, NewsItem, OptionContract, Quote


class FinnhubNewsClient:
    base_url = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, http: JsonHttpClient | None = None) -> None:
        self._api_key = api_key
        self._http = http or JsonHttpClient()

    def latest_company_news(self, symbol: str, days_back: int = 1) -> NewsItem | None:
        today = date.today()
        payload = self._http.get_json(
            f"{self.base_url}/company-news",
            params={
                "symbol": symbol,
                "from": (today - timedelta(days=days_back)).isoformat(),
                "to": today.isoformat(),
                "token": self._api_key,
            },
        )
        if not isinstance(payload, list) or not payload:
            return None
        latest = max(payload, key=lambda item: item.get("datetime", 0))
        timestamp = datetime.fromtimestamp(latest.get("datetime", 0), tz=UTC)
        return NewsItem(
            headline=str(latest.get("headline") or ""),
            symbols=(symbol,),
            source=str(latest.get("source") or "finnhub"),
            sentiment=0.5,
            urgency=_urgency_from_age(timestamp),
            timestamp=timestamp,
        )


class TradierOptionsClient:
    base_url = "https://api.tradier.com/v1"

    def __init__(self, token: str, http: JsonHttpClient | None = None, sandbox: bool = False) -> None:
        self._token = token
        self._http = http or JsonHttpClient()
        self.base_url = "https://sandbox.tradier.com/v1" if sandbox else self.base_url

    def option_chain(self, symbol: str, expiration: str) -> list[tuple[OptionContract, Quote]]:
        payload = self._http.get_json(
            f"{self.base_url}/markets/options/chains",
            params={"symbol": symbol, "expiration": expiration, "greeks": "true"},
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )
        options = _dig(payload, "options", "option") if isinstance(payload, dict) else None
        if isinstance(options, dict):
            options = [options]
        if not isinstance(options, list):
            return []
        results: list[tuple[OptionContract, Quote]] = []
        for item in options:
            if not isinstance(item, dict):
                continue
            greeks = item.get("greeks") if isinstance(item.get("greeks"), dict) else {}
            option_symbol = str(item.get("symbol") or "")
            contract = OptionContract(
                underlying=symbol,
                expiration=str(item.get("expiration_date") or expiration),
                strike=float(item.get("strike") or 0),
                option_type=str(item.get("option_type") or ""),
                symbol=option_symbol,
            )
            quote = Quote(
                symbol=option_symbol,
                bid=float(item.get("bid") or 0),
                ask=float(item.get("ask") or 0),
                last=float(item.get("last") or 0),
                volume=int(item.get("volume") or 0),
                relative_volume=1.0,
                open_interest=int(item.get("open_interest") or 0),
                implied_volatility=_optional_float(greeks.get("mid_iv")),
                delta=_optional_float(greeks.get("delta")),
                gamma=_optional_float(greeks.get("gamma")),
                theta=_optional_float(greeks.get("theta")),
                vega=_optional_float(greeks.get("vega")),
                days_to_expiration=int(item.get("days_to_expiration") or 0),
            )
            results.append((contract, quote))
        return results


class PolygonStockSnapshotProvider(DataProvider):
    name = "polygon_snapshot"
    base_url = "https://api.polygon.io"

    def __init__(
        self,
        symbols: tuple[str, ...],
        api_key: str,
        poll_interval_seconds: float = 1.0,
        news_client: FinnhubNewsClient | None = None,
        http: JsonHttpClient | None = None,
    ) -> None:
        self._symbols = symbols
        self._api_key = api_key
        self._poll_interval_seconds = poll_interval_seconds
        self._news_client = news_client
        self._http = http or JsonHttpClient()
        self._bars: dict[str, list[Bar]] = {symbol: [] for symbol in symbols}

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        while True:
            for symbol in self._symbols:
                snapshot = self._snapshot(symbol)
                if snapshot:
                    yield snapshot
            await asyncio.sleep(self._poll_interval_seconds)

    def _snapshot(self, symbol: str) -> MarketSnapshot | None:
        payload = self._http.get_json(
            f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}",
            params={"apiKey": self._api_key},
        )
        if not isinstance(payload, dict):
            return None
        ticker = payload.get("ticker")
        if not isinstance(ticker, dict):
            return None
        quote_payload = ticker.get("lastQuote") if isinstance(ticker.get("lastQuote"), dict) else {}
        trade_payload = ticker.get("lastTrade") if isinstance(ticker.get("lastTrade"), dict) else {}
        minute_payload = ticker.get("min") if isinstance(ticker.get("min"), dict) else {}
        day_payload = ticker.get("day") if isinstance(ticker.get("day"), dict) else {}
        previous_day = ticker.get("prevDay") if isinstance(ticker.get("prevDay"), dict) else {}

        last = _first_float(trade_payload, "p", "price") or _first_float(minute_payload, "c", "close")
        bid = _first_float(quote_payload, "p", "bp", "bid") or last
        ask = _first_float(quote_payload, "P", "ap", "ask") or last
        if last is None or bid is None or ask is None:
            return None
        volume = int(_first_float(day_payload, "v", "volume") or _first_float(minute_payload, "v", "volume") or 0)
        previous_volume = _first_float(previous_day, "v", "volume") or volume
        relative_volume = round(volume / previous_volume, 3) if previous_volume else 1.0
        timestamp = _timestamp_from_ns(
            _first_float(trade_payload, "t", "timestamp")
            or _first_float(quote_payload, "t", "timestamp")
            or _first_float(minute_payload, "t", "timestamp")
        )
        bar = _bar_from_minute(symbol, minute_payload, timestamp)
        if bar:
            self._bars[symbol].append(bar)
            self._bars[symbol] = self._bars[symbol][-240:]
        recent_bars = tuple(self._bars[symbol])
        news = self._news_client.latest_company_news(symbol) if self._news_client else None
        return MarketSnapshot(
            symbol=symbol,
            quote=Quote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                last=last,
                volume=volume,
                relative_volume=relative_volume,
                timestamp=timestamp,
            ),
            recent_closes=tuple(item.close for item in recent_bars),
            recent_volumes=tuple(item.volume for item in recent_bars),
            recent_bars=recent_bars,
            latest_news=news,
            provider=self.name,
            received_at=datetime.now(UTC),
        )


def polygon_provider_from_env(
    symbols: tuple[str, ...],
    api_key_env: str,
    poll_interval_seconds: float,
    finnhub_api_key_env: str | None = None,
) -> PolygonStockSnapshotProvider:
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} is required for polygon_snapshot provider.")
    news_client = None
    if finnhub_api_key_env:
        finnhub_key = os.getenv(finnhub_api_key_env)
        if finnhub_key:
            news_client = FinnhubNewsClient(finnhub_key)
    return PolygonStockSnapshotProvider(
        symbols=symbols,
        api_key=api_key,
        poll_interval_seconds=poll_interval_seconds,
        news_client=news_client,
    )


def _bar_from_minute(symbol: str, payload: dict[str, Any], fallback_timestamp: datetime) -> Bar | None:
    if not payload:
        return None
    close = _first_float(payload, "c", "close")
    if close is None:
        return None
    return Bar(
        symbol=symbol,
        open=_first_float(payload, "o", "open") or close,
        high=_first_float(payload, "h", "high") or close,
        low=_first_float(payload, "l", "low") or close,
        close=close,
        volume=int(_first_float(payload, "v", "volume") or 0),
        timestamp=_timestamp_from_ns(_first_float(payload, "t", "timestamp")) or fallback_timestamp,
        vwap=_first_float(payload, "vw", "vwap"),
    )


def _timestamp_from_ns(value: float | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    if value > 10_000_000_000_000:
        return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
    if value > 10_000_000_000:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    return datetime.fromtimestamp(value, tz=UTC)


def _first_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        parsed = _optional_float(value)
        if parsed is not None:
            return parsed
    return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _urgency_from_age(timestamp: datetime) -> float:
    age_seconds = max(0.0, (datetime.now(UTC) - timestamp).total_seconds())
    if age_seconds <= 300:
        return 1.0
    if age_seconds <= 1800:
        return 0.75
    if age_seconds <= 7200:
        return 0.5
    return 0.25
