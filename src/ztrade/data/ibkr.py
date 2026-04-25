from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from itertools import count
from typing import Any

from ztrade.brokers.ibkr import IbkrConnectionConfig
from ztrade.data.providers import DataProvider
from ztrade.models import Bar, MarketSnapshot, Quote

_CLIENT_ID_OFFSETS = count(100)


@dataclass(slots=True)
class IbkrMarketDataSettings:
    historical_duration: str = "2 D"
    historical_bar_size: str = "5 mins"
    historical_what_to_show: str = "TRADES"
    use_rth: bool = True
    market_data_type: int = 3
    quote_timeout_seconds: float = 8.0
    history_timeout_seconds: float = 20.0


@dataclass(slots=True)
class _RequestState:
    event: threading.Event = field(default_factory=threading.Event)
    bars: list[Bar] = field(default_factory=list)
    prices: dict[int, float] = field(default_factory=dict)
    sizes: dict[int, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class IbkrMarketDataClient:
    def __init__(
        self,
        config: IbkrConnectionConfig | None = None,
        settings: IbkrMarketDataSettings | None = None,
    ) -> None:
        self.config = config or IbkrConnectionConfig.from_env()
        self.settings = settings or IbkrMarketDataSettings()
        self._app: Any | None = None
        self._thread: threading.Thread | None = None

    def connect(self, timeout_seconds: float = 8.0) -> None:
        if self._app is not None and self._app.isConnected():
            return
        app = _make_ibkr_app()
        app.connect(self.config.host, self.config.port, self.config.client_id)
        self._thread = threading.Thread(target=app.run, name="ibkr-api", daemon=True)
        self._thread.start()
        if not app.connected_event.wait(timeout_seconds):
            app.disconnect()
            raise TimeoutError(f"Timed out connecting to IBKR API at {self.config.host}:{self.config.port}.")
        app.reqMarketDataType(self.settings.market_data_type)
        self._app = app

    def disconnect(self) -> None:
        if self._app is not None:
            self._app.disconnect()
            self._app = None

    def historical_bars(
        self,
        symbol: str,
        duration: str | None = None,
        bar_size: str | None = None,
        what_to_show: str | None = None,
        use_rth: bool | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[Bar, ...]:
        self.connect()
        assert self._app is not None
        request_id, state = self._app.new_request()
        self._app.reqHistoricalData(
            request_id,
            _stock_contract(symbol),
            "",
            duration or self.settings.historical_duration,
            bar_size or self.settings.historical_bar_size,
            what_to_show or self.settings.historical_what_to_show,
            1 if (self.settings.use_rth if use_rth is None else use_rth) else 0,
            2,
            False,
            [],
        )
        timeout = timeout_seconds or self.settings.history_timeout_seconds
        if not state.event.wait(timeout):
            self._app.cancelHistoricalData(request_id)
            raise TimeoutError(f"Timed out waiting for IBKR historical bars for {symbol}.")
        if not state.bars:
            detail = f" Details: {'; '.join(state.errors)}" if state.errors else ""
            raise ValueError(f"IBKR returned no historical bars for {symbol}.{detail}")
        return tuple(state.bars)

    def quote_snapshot(
        self,
        symbol: str,
        timeout_seconds: float | None = None,
    ) -> Quote:
        self.connect()
        assert self._app is not None
        request_id, state = self._app.new_request()
        self._app.reqMktData(request_id, _stock_contract(symbol), "", True, False, [])
        timeout = timeout_seconds or self.settings.quote_timeout_seconds
        if not state.event.wait(timeout):
            self._app.cancelMktData(request_id)
            raise TimeoutError(f"Timed out waiting for IBKR quote snapshot for {symbol}.")
        return _quote_from_state(symbol, state)


class IbkrHistoricalDataProvider(DataProvider):
    name = "ibkr_historical"

    def __init__(
        self,
        symbols: tuple[str, ...],
        client: IbkrMarketDataClient | None = None,
        settings: IbkrMarketDataSettings | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._symbols = symbols
        self._settings = settings or IbkrMarketDataSettings()
        self._client = client or _owned_market_data_client(self._settings)
        self._owns_client = client is None
        self._delay_seconds = delay_seconds

    async def stream(self):
        histories = {
            symbol: self._client.historical_bars(
                symbol,
                duration=self._settings.historical_duration,
                bar_size=self._settings.historical_bar_size,
                what_to_show=self._settings.historical_what_to_show,
                use_rth=self._settings.use_rth,
                timeout_seconds=self._settings.history_timeout_seconds,
            )
            for symbol in self._symbols
        }
        try:
            max_length = max((len(bars) for bars in histories.values()), default=0)
            for index in range(max_length):
                for symbol, bars in histories.items():
                    if index >= len(bars):
                        continue
                    recent_bars = tuple(bars[max(0, index - 119) : index + 1])
                    yield _snapshot_from_bar(symbol, recent_bars, provider=self.name)
                    if self._delay_seconds > 0:
                        await asyncio.sleep(self._delay_seconds)
        finally:
            if self._owns_client:
                self._client.disconnect()


class IbkrSnapshotProvider(DataProvider):
    name = "ibkr_snapshot"

    def __init__(
        self,
        symbols: tuple[str, ...],
        client: IbkrMarketDataClient | None = None,
        settings: IbkrMarketDataSettings | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._symbols = symbols
        self._settings = settings or IbkrMarketDataSettings()
        self._client = client or _owned_market_data_client(self._settings)
        self._owns_client = client is None
        self._poll_interval_seconds = poll_interval_seconds

    async def stream(self):
        try:
            while True:
                for symbol in self._symbols:
                    bars = self._client.historical_bars(
                        symbol,
                        duration=self._settings.historical_duration,
                        bar_size=self._settings.historical_bar_size,
                        what_to_show=self._settings.historical_what_to_show,
                        use_rth=self._settings.use_rth,
                        timeout_seconds=self._settings.history_timeout_seconds,
                    )
                    quote = self._client.quote_snapshot(symbol, timeout_seconds=self._settings.quote_timeout_seconds)
                    yield _snapshot_from_quote(symbol, quote, bars, provider=self.name)
                await asyncio.sleep(self._poll_interval_seconds)
        finally:
            if self._owns_client:
                self._client.disconnect()


def ibkr_settings_from_config(config: Any) -> IbkrMarketDataSettings:
    return IbkrMarketDataSettings(
        historical_duration=config.ibkr_historical_duration,
        historical_bar_size=config.ibkr_historical_bar_size,
        historical_what_to_show=config.ibkr_historical_what_to_show,
        use_rth=config.ibkr_use_rth,
        market_data_type=config.ibkr_market_data_type,
        quote_timeout_seconds=config.ibkr_quote_timeout_seconds,
        history_timeout_seconds=config.ibkr_history_timeout_seconds,
    )


def _owned_market_data_client(settings: IbkrMarketDataSettings) -> IbkrMarketDataClient:
    base = IbkrConnectionConfig.from_env()
    process_offset = (os.getpid() % 10_000) * 100
    return IbkrMarketDataClient(
        config=replace(base, client_id=base.client_id + process_offset + next(_CLIENT_ID_OFFSETS)),
        settings=settings,
    )


def _make_ibkr_app():
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
    except ImportError as exc:
        raise RuntimeError("Install the IBKR TWS API package with `pip install ibapi` to use IBKR data.") from exc

    class _IbkrApp(EWrapper, EClient):
        def __init__(self) -> None:
            EWrapper.__init__(self)
            EClient.__init__(self, self)
            self.connected_event = threading.Event()
            self._request_ids = count(1)
            self._states: dict[int, _RequestState] = {}
            self._lock = threading.RLock()

        def new_request(self) -> tuple[int, _RequestState]:
            request_id = next(self._request_ids)
            state = _RequestState()
            with self._lock:
                self._states[request_id] = state
            return request_id, state

        def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
            self.connected_event.set()

        def error(self, reqId: int, errorCode: int, errorString: str, *args: object) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None:
                state.errors.append(f"{errorCode}: {errorString}")

        def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None:
                state.bars.append(_bar_from_ibkr(bar))

        def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None:
                state.event.set()

        def tickPrice(self, reqId: int, tickType: int, price: float, attrib: object) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None and price >= 0:
                state.prices[tickType] = price

        def tickSize(self, reqId: int, tickType: int, size: int) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None and size >= 0:
                state.sizes[tickType] = size

        def tickSnapshotEnd(self, reqId: int) -> None:  # noqa: N802
            with self._lock:
                state = self._states.get(reqId)
            if state is not None:
                state.event.set()

    return _IbkrApp()


def _stock_contract(symbol: str) -> object:
    try:
        from ibapi.contract import Contract
    except ImportError as exc:
        raise RuntimeError("Install the IBKR TWS API package with `pip install ibapi` to use IBKR data.") from exc
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


def _bar_from_ibkr(raw_bar: object) -> Bar:
    return Bar(
        symbol="",
        open=float(getattr(raw_bar, "open")),
        high=float(getattr(raw_bar, "high")),
        low=float(getattr(raw_bar, "low")),
        close=float(getattr(raw_bar, "close")),
        volume=int(float(getattr(raw_bar, "volume", 0) or 0)),
        timestamp=_parse_ibkr_timestamp(str(getattr(raw_bar, "date", ""))),
        vwap=float(getattr(raw_bar, "wap")) if getattr(raw_bar, "wap", None) not in {None, ""} else None,
    )


def _parse_ibkr_timestamp(raw: str) -> datetime:
    value = raw.strip()
    if value.isdigit():
        if len(value) == 8:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC)
        return datetime.fromtimestamp(int(value), tz=UTC)
    parts = value.split()
    if len(parts) >= 2:
        return datetime.strptime(" ".join(parts[:2]), "%Y%m%d %H:%M:%S").replace(tzinfo=UTC)
    return datetime.now(UTC)


def _quote_from_state(symbol: str, state: _RequestState) -> Quote:
    last = _first_price(state, 4, 68, 9)
    bid = _first_price(state, 1, 66)
    ask = _first_price(state, 2, 67)
    if last is None:
        last = bid or ask
    if last is None:
        detail = f" Details: {'; '.join(state.errors)}" if state.errors else ""
        raise ValueError(f"IBKR returned no quote price for {symbol}.{detail}")
    bid = bid if bid is not None else round(last * 0.9999, 4)
    ask = ask if ask is not None else round(last * 1.0001, 4)
    volume = _first_size(state, 8, 74, 5) or 0
    return Quote(
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        relative_volume=1.0,
        timestamp=datetime.now(UTC),
    )


def _first_price(state: _RequestState, *tick_types: int) -> float | None:
    for tick_type in tick_types:
        if tick_type in state.prices:
            return state.prices[tick_type]
    return None


def _first_size(state: _RequestState, *tick_types: int) -> int | None:
    for tick_type in tick_types:
        if tick_type in state.sizes:
            return state.sizes[tick_type]
    return None


def _snapshot_from_bar(symbol: str, recent_bars: tuple[Bar, ...], provider: str) -> MarketSnapshot:
    current = recent_bars[-1]
    normalized_bars = tuple(
        Bar(
            symbol=symbol,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            timestamp=bar.timestamp,
            vwap=bar.vwap,
        )
        for bar in recent_bars
    )
    bid = round(current.close * 0.9999, 4)
    ask = round(current.close * 1.0001, 4)
    return MarketSnapshot(
        symbol=symbol,
        quote=Quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=current.close,
            volume=current.volume,
            relative_volume=_relative_volume(normalized_bars),
            timestamp=current.timestamp,
        ),
        recent_closes=tuple(bar.close for bar in normalized_bars),
        recent_volumes=tuple(bar.volume for bar in normalized_bars),
        recent_bars=normalized_bars,
        provider=provider,
        received_at=datetime.now(UTC),
    )


def _snapshot_from_quote(symbol: str, quote: Quote, bars: tuple[Bar, ...], provider: str) -> MarketSnapshot:
    normalized_bars = tuple(
        Bar(
            symbol=symbol,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            timestamp=bar.timestamp,
            vwap=bar.vwap,
        )
        for bar in bars[-120:]
    )
    return MarketSnapshot(
        symbol=symbol,
        quote=Quote(
            symbol=symbol,
            bid=quote.bid,
            ask=quote.ask,
            last=quote.last,
            volume=quote.volume,
            relative_volume=_relative_volume(normalized_bars),
            timestamp=quote.timestamp,
        ),
        recent_closes=tuple(bar.close for bar in normalized_bars),
        recent_volumes=tuple(bar.volume for bar in normalized_bars),
        recent_bars=normalized_bars,
        provider=provider,
        received_at=datetime.now(UTC),
    )


def _relative_volume(bars: tuple[Bar, ...]) -> float:
    if len(bars) < 2:
        return 1.0
    baseline = sum(bar.volume for bar in bars[:-1]) / (len(bars) - 1)
    if baseline <= 0:
        return 1.0
    return round(bars[-1].volume / baseline, 3)
