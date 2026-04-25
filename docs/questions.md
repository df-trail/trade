# Deferred Questions

Questions are saved here during autonomous work instead of interrupting the build.

## Data Vendor Decisions

- Which paid market-data provider should be tried first for real-time stock quotes and trades?
- Which paid options provider should be tried first for full chains, Greeks, IV, volume, and open interest?
- Which news/social vendor should be used first for the 1-2 second event-driven workflow?
- Do you want Twitter/X data specifically, or are Benzinga/TradeTheNews/Dow Jones style feeds acceptable if they are faster and cleaner?

## Trading Preferences

- Should options recommendations prefer calls/puts near 0.40-0.60 delta, or should each strategy choose delta dynamically?
- Should 0DTE options be allowed in paper trading initially, or excluded until the backtester proves the strategy?
- Should the app avoid trading during the first/last 5 minutes of the market session?
- Should SPY/QQQ market-regime filters block individual-stock trades, or only reduce confidence?

## Product Decisions

- Should the desktop UI remain Tkinter for speed, or eventually move to a richer local web UI?
- Should paper-trading results be pushed to a dashboard/report file automatically each day?
- Should the app send notifications via desktop toast, email, Discord, or SMS?

## Implementation Follow-Ups

- Should backtests relax intraday `max_trades_per_day` so strategy research can evaluate more signals, or keep the exact live guardrails by default?
- Should live provider configuration live in `.env`, a local YAML file, or only environment variables?
- Which source should own option-chain selection in live mode: Polygon/Massive, Tradier, or a dedicated options vendor?
