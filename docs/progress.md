# zTrade Progress Log

This file records autonomous build progress so overnight or long-running work leaves a readable trail.

## 2026-04-24 Autonomous Build Session

### Starting State

- Project lives at `C:\zTrade`.
- Git remote is `https://github.com/df-trail/trade.git`.
- App scaffold already includes a demo data provider, strategy/recommendation pipeline, guardrails, paper broker, SQLite audit store, desktop UI, launcher, and README requirements.
- Current UI table is fed by deterministic `DemoDataProvider` fake stock, option, and news events.

### Work Plan

1. Record docs for progress, architecture, data feeds, and deferred questions.
2. Expand domain models for richer snapshots, bars, provider metadata, and analytics.
3. Add provider interfaces/adapters for demo, replay, and future real feeds.
4. Add technical indicators and more strategy plugins.
5. Add a backtest runner and performance analytics.
6. Improve the desktop UI for review workflows and runtime visibility.
7. Add smoke tests/scripts and update README.
8. Commit and push if verification is clean.

### Progress Entries

- Created docs/progress.md, docs/questions.md, docs/architecture.md, and docs/data_feeds.md.
- Expanded normalized market models with OHLCV bars, provider metadata, option-flow hints, and market-regime context.
- Added replay-capable data providers: in-memory replay and CSV OHLCV replay.
- Added provider factory driven by `AppConfig.data_provider`.
- Added shared technical indicators: SMA, EMA, RSI, VWAP, ATR, percent change, and z-score.
- Added strategy pack: relative-volume breakout, VWAP reclaim, RSI mean reversion, and options-flow momentum.
- Tuned demo data so smoke tests exercise news momentum, relative-volume breakout, and options-flow momentum.
- Added analytics package with performance reports and trade records.
- Rebuilt backtest engine to run the same recommendation, guardrail, execution, and paper broker path used by the app.
- Added stop/target/max-hold/end-of-test simulated exits for paper backtests.
- Added CLI entry point with `desktop`, `stream`, `backtest-demo`, `backtest-csv`, and `db-summary` commands.
- Expanded desktop UI into tabs for recommendations, account/positions, and audit events.
- Added recommendation details pane with thesis, TA summary, stop/target plan, and guardrail reasons.
- Added credential-ready live-data adapters for Polygon/Massive stock snapshots, Finnhub company news, and Tradier option chains.
- Added offline parser tests for live-data adapters.
- Added `--provider`, `--symbols`, `--csv-path`, and live polling flags to the stream CLI command.
- Final verification target: compile, unit tests, smoke script, CLI demo stream, and demo backtest.
- Pivoted future broker target to IBKR and added an IBKR broker placeholder plus integration notes.
- Added persistent desktop settings in `data/settings.json` with add/delete ticker rows, instrument checkboxes, strategy checkboxes, and trade-limit fields.
- Wired settings into the desktop feed so enabled tickers and selected strategies are the only inputs reaching the recommendations page.
- Bumped the visible desktop version to `zTrade v0.3.0 Settings Build` and added a top-bar Open Settings button.
- Expanded settings into `zTrade v0.4.0 Advanced Settings Build` with separated share/simple-option/complex-option transaction groups, 26 strategy hover descriptions, and per-strategy min confidence/max position/max trades settings.
