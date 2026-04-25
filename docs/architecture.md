# zTrade Architecture

## Current Pipeline

```text
DataProvider
  -> MarketSnapshot
  -> Strategy.evaluate()
  -> TradeIdea
  -> GuardrailEngine.check()
  -> Recommendation
  -> ExecutionEngine
  -> PaperBroker
  -> TradingStore
```

## Design Principles

- Keep data, strategy, risk, execution, and broker code separated.
- Make paper trading the default and live trading opt-in only.
- Every recommendation/order/fill should be auditable and replayable.
- Strategy logic should work in live feeds and backtests without separate implementations.
- Broker integrations should be adapters, not dependencies inside strategy code.

## Important Boundaries

### Data

Data providers emit normalized `MarketSnapshot` objects. A provider may be real-time, replayed from historical data, or synthetic for testing.

### Strategy

Strategies read snapshots and emit `TradeIdea` objects. Strategies do not know whether a trade will be staged, paper-filled, or live-traded.

### Risk

The guardrail layer decides whether a trade idea is allowed and may adjust quantity. It is the enforcement layer for no-margin behavior, PDT constraints, sizing, liquidity, stale quotes, and circuit breakers.

### Execution

The execution layer applies bot mode behavior:

- Stage only.
- Auto paper.
- Auto-exit only.
- Limited live trading when eventually enabled.

### Storage

SQLite stores market snapshots, recommendations, orders, fills, account snapshots, and paper positions. This is the audit layer and future backtest/research substrate.

## Next Architectural Additions

- Provider registry with named provider configs.
- Historical replay provider for backtesting.
- Indicator library shared across strategies.
- Backtest metrics and trade-performance reporting.
- UI views for account, positions, audit log, and strategy performance.

## Added During Autonomous Build

- `analysis/indicators.py` centralizes SMA, EMA, RSI, VWAP, ATR, percent change, and z-score.
- `analytics/performance.py` produces trade records and backtest performance summaries.
- `backtest/engine.py` now uses the same strategy, guardrail, execution, and paper-broker path as the live paper app.
- `cli.py` exposes desktop, stream, demo backtest, CSV backtest, and database summary commands.
- Desktop UI now has recommendation, account/position, and audit tabs.
