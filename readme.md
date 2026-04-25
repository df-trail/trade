# zTrade

Advanced personal stock and single-leg options trading workstation. The first milestone is paper trading with realistic strategy scoring, one-click staged trades, bot guardrails, and a broker adapter boundary that can later connect to Robinhood or another broker with supported API access.

This project is for personal research and paper trading first. It should not place live orders until the strategy, risk controls, data feeds, credentials, and broker terms are reviewed.

## Requirements Captured

### Speed

- Target decision loop: execute or stage a trade within 1-2 seconds of new incoming news, Twitter/social feed, or market-data event.
- The app should prioritize low-latency ingestion, fast signal scoring, and precomputed trade templates where possible.
- "High speed" here means fast retail/event-driven trading, not exchange-colocated high-frequency trading.

### Instruments

- Stocks.
- Single-leg options.
- No margin.
- Account starts below $25k, so Robinhood PDT constraints must be respected.

### Strategy Scope

The system should support multiple strategy families and let the recommendation engine choose from all available options based on market context:

- Chart/history-driven technical setups.
- News/event-driven setups.
- Volume and relative-volume setups.
- Momentum and breakout setups.
- Mean reversion setups.
- Gap and continuation setups.
- Options volatility setups.
- Unusual options activity/options-flow assisted setups.

Initial recommendation inputs should focus on:

1. Real-time quotes/trades for stocks.
2. Options chains, bid/ask, volume, open interest, implied volatility, and Greeks.
3. Historical intraday candles/ticks.
4. News and earnings calendar.
5. Unusual options activity/options flow.

### Recommendation UX

- Recommendations should be simple and fast to understand.
- Each recommendation should include a small technical-analysis summary.
- The user should be able to approve a staged trade with one click.
- Recommendations should include confidence, thesis, entry, stop, target, and risk notes.

### Bot Modes

The app should support these modes:

- Stage trades for one-click approval.
- Auto-enter paper trades.
- Auto-exit only.
- Fully auto-trade with limits.

Live trading must remain disabled until explicitly implemented and enabled.

### Guardrails

The app should expose a broad set of configurable guardrails:

- Max portfolio allocation per trade.
- Confidence-based sizing.
- 5-15% max portfolio bid/position sizing based on confidence.
- Max daily loss.
- Max loss per trade.
- Max open positions.
- Max open options contracts.
- Max trades per day.
- PDT protection for accounts under $25k.
- No margin.
- Liquidity filters for stocks and options.
- Max bid/ask spread.
- Min volume and relative volume.
- Min option open interest.
- Max option premium.
- Max option days-to-expiration range.
- Earnings blackout windows.
- News-event cooldown windows.
- Loss-streak cooldown.
- Symbol cooldown after trade.
- Market-hours restrictions.
- No market orders unless explicitly allowed.
- Circuit breaker after data-feed outage or stale quotes.
- Manual kill switch.
- Live-trading disabled by default.

### Fill Model

- In paper trading, if a trade is accepted by guardrails, it should receive a fill.
- Initial paper broker can fill immediately at the quoted last price or option mid.
- Later versions should support conservative slippage, partial fills, fees, rejected orders, and stale-quote simulation.

### Backtesting

- Backtesting is required.
- The strategy engine should be shared by backtests, paper trading, recommendations, and future live trading.
- Every recommendation and fill should be logged for audit and later performance analysis.

### UI

- Desktop UI for personal use.
- The first UI can be a Python desktop app.
- It should show incoming recommendations, confidence, simple TA, account state, bot mode, guardrail status, and one-click approve/reject controls.

### Data Budget

- Data budget depends on paper-trading results.
- Goal is to materially outperform the market, with an aspirational target of 5x market performance.
- Better paper-trading performance justifies higher-quality paid data feeds.
- Data quality is critical; delayed or incomplete options data can invalidate recommendations.

### Broker Notes

- Robinhood is the desired broker eventually.
- Current scaffold keeps broker integration behind an adapter.
- Paper trading must work without Robinhood credentials.
- Live Robinhood securities trading should only be added through supported/authorized API access and after reviewing broker terms, rate limits, order behavior, and market-data limitations.

## Architecture

```text
data feeds
  -> normalization/cache
  -> signal engine
  -> strategy scorer
  -> risk engine/guardrails
  -> recommendation queue
  -> paper broker
  -> optional live broker adapter
  -> audit log
```

### Package Layout

```text
zTrade/
  pyproject.toml
  readme.md
  src/ztrade/
    app.py                 # CLI demo entry point
    cli.py                 # Command-line runner for desktop, streams, backtests, and DB summaries
    config.py              # App and guardrail settings
    models.py              # Shared typed domain objects
    analysis/              # Shared indicators
    analytics/             # Performance reporting
    backtest/              # Historical replay engine
    brokers/               # Paper and future live broker adapters
    data/                  # Feed abstractions and demo feed
    execution/             # Bot mode and order-routing decisions
    recommendations/       # Strategy orchestration and scoring
    risk/                  # Guardrail checks
    storage/               # SQLite audit log and paper ledger persistence
    strategies/            # Strategy plugins
    ui/                    # Desktop UI
```

## Current Scaffold

The scaffold includes:

- Event-driven market/news feed abstractions.
- Demo feed that emits stock quote, option quote, and news events.
- CSV replay feed for historical OHLCV files.
- Credential-ready adapters for Polygon/Massive stock snapshots, Finnhub company news, and Tradier option chains.
- SQLite audit store for market events, recommendations, orders, fills, account snapshots, and paper positions.
- Strategy registry with news momentum, relative-volume breakout, VWAP reclaim, RSI mean reversion, and options-flow momentum.
- Recommendation engine with simple scoring and TA summaries.
- Guardrail engine with PDT, sizing, liquidity, confidence, and bot-safety checks.
- Paper broker with guaranteed fills for accepted paper orders plus cash and position tracking.
- Execution engine supporting staged and auto-paper modes.
- Robinhood adapter placeholder.
- Desktop UI with recommendation, account/positions, and audit tabs.
- Backtest replay engine with stop/target/max-hold/end-of-test exits and performance reporting.

Runtime state is stored in `data/ztrade.sqlite3` by default and is intentionally ignored by Git.

## Run The Demo

From the repository root:

```powershell
cd C:\zTrade
python -m pip install -e .
python -m ztrade.ui.desktop
```

Windows launcher:

```powershell
cd C:\zTrade
.\launch_ztrade.cmd
```

The current desktop build shows `zTrade v0.2.0` in the window title and header. If you do not see that, close the old zTrade window and relaunch from `C:\zTrade\launch_ztrade.cmd`.

CLI demo:

```powershell
cd C:\zTrade
python -m pip install -e .
python -m ztrade.app
```

Unified CLI:

```powershell
cd C:\zTrade
python -m ztrade.cli stream --limit 30
python -m ztrade.cli stream --limit 30 --auto-paper
python -m ztrade.cli stream --provider csv_replay --csv-path path\to\ohlcv.csv --limit 100
python -m ztrade.cli stream --provider polygon_snapshot --symbols SPY,QQQ,AAPL --limit 30
python -m ztrade.cli backtest-demo --snapshots 120 --max-hold 20
python -m ztrade.cli backtest-csv path\to\ohlcv.csv --snapshots 1000
python -m ztrade.cli db-summary
```

The desktop and CLI demos create `data/ztrade.sqlite3` for runtime audit data.

For live snapshot polling, set environment variables first:

```powershell
$env:POLYGON_API_KEY='your-key'
$env:FINNHUB_API_KEY='optional-news-key'
python -m ztrade.cli stream --provider polygon_snapshot --symbols SPY,QQQ,AAPL --limit 30
```

You can also copy `.env.example` to `.env`; zTrade loads `.env` automatically at startup.

Tradier option-chain normalization is available through `TradierOptionsClient` and expects `TRADIER_TOKEN` when wired into a provider workflow.

## Demo Data Source

The table is currently fed by `DemoDataProvider` in `src/ztrade/data/providers.py`. It emits deterministic fake stock quotes, option quotes, and occasional demo news items for the default watchlist so the UI, recommendation engine, guardrails, paper broker, and audit log can be tested before real provider credentials are added.

CSV backtests can use `CsvReplayDataProvider`. Required columns:

```text
symbol,timestamp,open,high,low,close,volume
```

Optional columns:

```text
bid,ask,relative_volume,vwap
```

## Test And Smoke Commands

```powershell
cd C:\zTrade
$env:PYTHONPATH='C:\zTrade\src'
python -m unittest discover -s tests
python scripts\smoke.py
python -m compileall src tests scripts
```

## Completed Foundation

1. Captured product requirements and guardrails.
2. Created package scaffold and desktop demo.
3. Added SQLite audit logging for market events, recommendations, orders, fills, paper account snapshots, and paper positions.
4. Added a stateful paper broker with cash, position tracking, guaranteed fills, and no-margin rejection behavior.
5. Added indicator library, expanded strategy pack, CSV replay provider, backtest engine, performance analytics, CLI commands, smoke tests, and richer desktop UI.
6. Added credential-ready Polygon/Massive stock snapshot, Finnhub news, and Tradier option-chain adapters with offline parser tests.

## Near-Term Milestones

1. Wire option-chain selection into live provider workflows.
2. Add websocket providers for lower-latency stock/news/options feeds.
3. Add richer paper-trading fill models, slippage modes, and fee assumptions.
4. Add account/PDT day-trade tracking.
5. Add daily performance reports and strategy analytics.
6. Harden desktop UI trade review workflows.
7. Add broker integration only after paper-trading performance and API/legal constraints are settled.
