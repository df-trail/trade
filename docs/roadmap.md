# zTrade Roadmap

This file tracks important items that are not finished yet.

## Data Feeds

- Add live option-chain selection to the provider workflow.
- Add websocket streaming for lower-latency quotes, news, and option updates.
- Add provider health checks, stale-feed warnings, and latency measurements in the UI.
- Add market calendar and earnings calendar feeds.
- Add options-flow provider integration beyond demo flow signals.

## Strategy And Settings

- Add a strategy detail editor for stop/target formulas, DTE windows, delta ranges, and IV filters.
- Add bearish variants for applicable strategies.
- Add market-regime filters that can reduce confidence or block trades.
- Add per-strategy backtest summaries inside the desktop UI.
- Add settings import/export profiles.

## Paper Trading

- Add fill-model modes: optimistic, mid, bid/ask, slippage, partial fill, and rejected order simulation.
- Add fee/commission assumptions.
- Add persistent PDT/day-trade tracking using SQLite history.
- Add open-position auto-exit rules tied to stop, target, max hold time, and trailing stop.
- Add daily kill-switch and drawdown enforcement from persistent account history.

## Options Workflows

- Implement long put recommendations and execution simulation.
- Implement straddle and strangle paper workflows.
- Implement vertical spreads.
- Add option-chain contract selection by DTE, delta, spread, open interest, and IV.
- Add risk graph and max loss/max profit estimates for complex options.

## IBKR

- Add IBKR connection health check for TWS or IB Gateway.
- Add account lookup and paper account verification.
- Add stock and option contract lookup.
- Add IBKR paper order preview.
- Add IBKR paper order placement and fill reconciliation.
- Keep live IBKR trading disabled until paper execution, logs, and kill switch behavior are proven.

## Desktop UI

- Add a market data status panel.
- Add strategy performance dashboard.
- Add trade journal and notes.
- Add notification settings.
- Add clearer dark/light theme support.
