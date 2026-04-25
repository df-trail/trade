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
    config.py              # App and guardrail settings
    models.py              # Shared typed domain objects
    backtest/              # Historical replay engine
    brokers/               # Paper and future live broker adapters
    data/                  # Feed abstractions and demo feed
    execution/             # Bot mode and order-routing decisions
    recommendations/       # Strategy orchestration and scoring
    risk/                  # Guardrail checks
    strategies/            # Strategy plugins
    ui/                    # Desktop UI
```

## Current Scaffold

The scaffold includes:

- Event-driven market/news feed abstractions.
- Demo feed that emits stock quote, option quote, and news events.
- Strategy registry with starter momentum/news strategies.
- Recommendation engine with simple scoring and TA summaries.
- Guardrail engine with PDT, sizing, liquidity, confidence, and bot-safety checks.
- Paper broker with guaranteed fills for accepted paper orders.
- Execution engine supporting staged and auto-paper modes.
- Robinhood adapter placeholder.
- Minimal desktop UI for recommendations and one-click approval.
- Backtest replay skeleton.

## Run The Demo

From the repository root:

```powershell
cd zTrade
python -m pip install -e .
python -m ztrade.ui.desktop
```

CLI demo:

```powershell
cd zTrade
python -m pip install -e .
python -m ztrade.app
```

## Near-Term Milestones

1. Add persistent audit logging with SQLite.
2. Add real data provider adapters for quotes, options chains, news, and options flow.
3. Add historical data ingestion for backtesting.
4. Expand strategy plugins and shared indicators.
5. Add richer paper-trading fill models and performance analytics.
6. Add account/PDT day-trade tracking.
7. Harden desktop UI and add trade review workflows.
8. Add broker integration only after paper-trading performance and API/legal constraints are settled.
