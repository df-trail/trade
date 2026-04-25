# Data Feed Plan

The data feed is the highest-leverage part of zTrade. The app should treat broker execution and market data as separate concerns.

## Required Feed Categories

1. Real-time stock quotes and trades.
2. Real-time options chains with bid/ask, volume, open interest, implied volatility, and Greeks.
3. Historical intraday candles/ticks.
4. News and earnings calendar.
5. Unusual options activity/options flow.

## Current Source

The current source is `DemoDataProvider`, which emits deterministic fake quotes, option quotes, and occasional demo news. It exists only to test app behavior before real credentials are added.

## Provider Candidates

### Stock Quotes/Trades

- Polygon.io
- Alpaca Market Data
- IEX Cloud or similar exchange-data provider
- Twelve Data for lower-cost prototypes

### Options Data

- Polygon.io options
- Tradier
- ThetaData
- Cboe/OPRA-backed vendor feeds

### News

- Benzinga
- Finnhub
- Polygon news
- Alpha Vantage news for lower-cost prototyping

### Options Flow

- Unusual Whales
- Cheddar Flow
- Tradytics
- Polygon/OPRA-derived custom scans if raw options data is available

## Feed Quality Rules

- Store quote timestamp and reject stale quotes.
- Record provider/source on snapshots.
- Keep bid/ask, not just last price.
- Track spread, volume, relative volume, open interest, IV, and Greeks for options.
- Treat incomplete options chains as lower confidence or blocked trades.
- Keep raw provider payloads when possible for debugging.

## Implementation Approach

1. Build provider interfaces and normalized models first.
2. Add replay provider for deterministic backtests.
3. Add HTTP polling adapters that use environment variables for credentials.
4. Add websocket adapters later for lower-latency real-time operation.
5. Compare provider timestamp, local receive timestamp, and decision latency in the audit log.

## Implemented Providers

- `DemoDataProvider`: deterministic fake stock quotes, option quotes, demo news, option-flow hints, and market-regime context.
- `ReplayDataProvider`: in-memory replay of normalized snapshots.
- `CsvReplayDataProvider`: OHLCV CSV replay for backtests.
- `PolygonStockSnapshotProvider`: credential-ready polling adapter for Polygon/Massive stock snapshots.
- `FinnhubNewsClient`: credential-ready company-news adapter.
- `TradierOptionsClient`: credential-ready option-chain adapter with Greeks normalization.

## Live Environment Variables

```powershell
$env:POLYGON_API_KEY='your-polygon-or-massive-key'
$env:FINNHUB_API_KEY='optional-finnhub-news-key'
$env:TRADIER_TOKEN='optional-tradier-token'
```

Example:

```powershell
python -m ztrade.cli stream --provider polygon_snapshot --symbols SPY,QQQ,AAPL --limit 30
```

## References

- Polygon/Massive single stock snapshot: `GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}`
- Polygon/Massive options data overview: real-time prices, historical data, reference data, IV, Greeks, and open interest.
- Finnhub company news client is based on the official `companyNews` examples from Finnhub client docs.
- Tradier endpoints use HTTPS base URLs for live and sandbox Brokerage APIs and the option-chain endpoint under market data.

## CSV Replay Format

Required:

```text
symbol,timestamp,open,high,low,close,volume
```

Optional:

```text
bid,ask,relative_volume,vwap
```
