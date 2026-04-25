# Backtest Workbench And Strategy Dataminer Plan

This document is the working plan for turning zTrade into an exhaustive research environment for testing ticker-specific strategy setups, then promoting validated setups into paper and eventually live IBKR trading.

Related planning document: `docs/exhaust_backtest_model.md` translates the local `docs/trade_strategies.pdf` strategy taxonomy into the concrete Exhaust candidate model, search dimensions, validation rules, and implementation phases.

## Goal

Build two linked research tools:

- Backtest Workbench: one ticker, one configuration, visual replay, detailed trade explanation.
- Strategy Dataminer: one ticker, many configurations, batch testing, ranking, comparison, and promotion to paper/live presets.

The long-term workflow should be:

1. Select a ticker row from Settings.
2. Open the Backtest Workbench for that ticker.
3. Inspect underlying price history, configure assumptions, and run visual replay.
4. Launch the Strategy Dataminer to brute-force strategy combinations and risk settings.
5. Review ranked reports against buy-and-hold performance.
6. Open promising results back in the Workbench for visual inspection.
7. Promote validated winners into paper-trading presets.
8. Require paper validation and guardrail checks before live trading can use a preset.

## Product Principles

- Every backtest must be reproducible from saved settings, data source, strategy versions, and assumptions.
- Strategy mining should optimize for durable performance, not just maximum historical return.
- Failed and mediocre configurations should be saved too, because they help avoid repeated dead ends.
- Stock backtesting should be solid before advanced options backtesting is trusted.
- Live trading should only use strategies that have a saved research record, paper validation, and explicit guardrails.

## Backtest Workbench

### Entry Point

- Each Settings ticker row has a Backtest button.
- Clicking it opens a dedicated Backtest Workbench window for that ticker and row configuration.
- The window owns its own data-loading, controls, chart state, run state, and results.
- The main app receives a summarized result when the run completes.

### Window Layout

- Top toolbar:
  - Ticker.
  - Data source.
  - Date range.
  - Bar size.
  - Timeframe preset.
  - Regular-hours toggle.
  - Asset mode.
  - Strategy preset.
  - Execute, Pause, Step, Reset, and Export buttons.
- Left control panel:
  - Backtest assumptions.
  - Strategy toggles.
  - Strategy-specific settings.
  - Risk settings.
  - Fill assumptions.
  - Fees/slippage assumptions.
- Center chart area:
  - Candlestick or OHLC price chart.
  - Volume panel.
  - Indicator overlays.
  - Entry and exit markers.
  - Stop and target lines.
  - Rejected-signal markers.
- Right inspection panel:
  - Current replay timestamp.
  - Active trade details.
  - Latest signal details.
  - Guardrail pass/fail reasons.
  - Live summary metrics.
- Bottom panel:
  - Equity curve.
  - Drawdown curve.
  - Trade ledger.
  - Strategy event log.

### Backtest Controls

- Data source:
  - demo.
  - csv_replay.
  - ibkr_historical.
- Bar size:
  - 1 min.
  - 5 mins.
  - 15 mins.
  - 30 mins.
  - 1 hour.
  - 1 day.
- Date selection:
  - Start date.
  - End date.
  - Lookback preset.
- Trading session:
  - Regular trading hours only.
  - Extended hours.
  - Open-only window.
  - Close-only window.
  - Custom intraday window.
- Asset mode:
  - Shares only.
  - Long calls only.
  - Long puts only.
  - Shares plus options.
  - Future: spreads, straddles, strangles.
- Fill model:
  - Conservative.
  - Midpoint.
  - Aggressive.
  - Slippage-adjusted.
  - Partial-fill simulation.
- Position sizing:
  - Fixed dollar.
  - Percent of portfolio.
  - Confidence-weighted.
  - Volatility-adjusted.
  - Max shares/contracts.
- Exit model:
  - Fixed stop.
  - Fixed target.
  - ATR stop.
  - Trailing stop.
  - Max hold time.
  - End-of-day flatten.

### Replay Behavior

The backtest engine should emit events one bar at a time so the UI can animate and explain the run:

- Bar loaded.
- Indicators updated.
- Strategy evaluated.
- Signal generated.
- Guardrail accepted or rejected.
- Order simulated.
- Trade entered.
- Stop or target updated.
- Trade exited.
- P&L updated.
- Equity curve updated.

The Workbench should support:

- Execute full run.
- Pause.
- Step one bar.
- Step to next signal.
- Step to next trade.
- Playback speed slider.
- Reset.
- Jump to selected trade.

### Chart Overlays

The chart should show:

- Candles or OHLC bars.
- Volume.
- VWAP.
- SMA and EMA overlays.
- Optional RSI, MACD, ATR, and relative-volume panels.
- Entry marker with strategy label.
- Exit marker with reason.
- Stop and target lines.
- Rejected signals, dimmed by default.
- P&L annotation on completed trades.
- Buy-and-hold benchmark line in lower performance panel.

Clicking a ledger row should focus the chart on that trade.

### Metrics

Each run should calculate:

- Total return.
- Dollar P&L.
- Return versus buy-and-hold.
- Win rate.
- Profit factor.
- Average win.
- Average loss.
- Max drawdown.
- Sharpe-like score.
- Number of trades.
- Exposure time.
- Average hold time.
- Best trade.
- Worst trade.
- Strategy-by-strategy contribution.
- Guardrail rejection counts.
- Fill quality estimate.

## Strategy Dataminer

### Purpose

The Strategy Dataminer is a brute-force research environment. It should test many combinations of strategy logic, strategy parameters, asset modes, and risk settings for a specific ticker, then rank the results and produce an explainable report.

### Entry Point

- From a Settings ticker row: Datamine button.
- From Backtest Workbench: Mine Variations button.
- From a saved backtest result: Explore Around This Setup button.

### Search Space

The dataminer should support controlled combinations across:

- Strategies:
  - RSI mean reversion.
  - VWAP reclaim.
  - Relative-volume breakout.
  - EMA trend.
  - Opening-range breakout.
  - Gap continuation.
  - ATR breakout.
  - Squeeze breakout.
  - Market-regime trend.
  - Moving-average bounce.
  - Earnings drift.
  - High-tight flag.
  - News momentum.
  - Options-flow momentum.
  - Multi-timeframe momentum.
- Strategy composition:
  - Single strategy.
  - Any-of strategy bundle.
  - All-of confirmation bundle.
  - Weighted voting.
  - Primary strategy plus confirmation strategy.
  - Entry strategy plus exit strategy.
- Asset mode:
  - Shares only.
  - Long calls.
  - Long puts.
  - Shares plus long calls.
  - Shares plus long puts.
  - Future: spreads, straddles, strangles.
- Bar size:
  - 1 min.
  - 5 mins.
  - 15 mins.
  - 30 mins.
  - 1 hour.
  - 1 day.
- Time windows:
  - Full session.
  - Opening range.
  - Midday.
  - Power hour.
  - Earnings windows.
  - High-volume days only.
- Risk settings:
  - Stop percent.
  - Target percent.
  - ATR multiple.
  - Trailing stop percent.
  - Max hold bars.
  - Max trades per day.
  - Max allocation.
  - Daily loss cap.
- Guardrails:
  - Minimum volume.
  - Minimum relative volume.
  - Maximum spread.
  - Minimum confidence.
  - Market-regime filter.
  - Cooldown after loss.

### Search Modes

- Exhaustive grid:
  - Tests every allowed combination.
  - Best for small search spaces.
- Bounded grid:
  - User caps max runs and selected parameter ranges.
  - Best default for desktop use.
- Random search:
  - Samples many combinations without full explosion.
  - Useful for large spaces.
- Walk-forward search:
  - Optimizes on one period, tests on the next.
  - Required before promoting to live presets.
- Explore around winner:
  - Mutates a strong configuration to test robustness.

### Ranking

Results should not be ranked by raw return only.

A composite score should include:

- Return.
- Return versus buy-and-hold.
- Max drawdown penalty.
- Profit factor.
- Win rate.
- Trade count confidence.
- Exposure efficiency.
- Out-of-sample performance.
- Walk-forward consistency.
- Liquidity penalty.
- Overfit penalty.
- Options spread/fill penalty.

Example scoring shape:

```text
score =
  return_score
  + benchmark_outperformance
  + profit_factor_score
  + consistency_score
  - drawdown_penalty
  - overfit_penalty
  - low_trade_count_penalty
  - liquidity_penalty
```

### Anti-Overfitting Rules

The dataminer should include these safeguards early:

- Train/test split.
- Walk-forward validation.
- Minimum trade count.
- Maximum drawdown threshold.
- Minimum profit factor.
- Compare against buy-and-hold.
- Compare across different market regimes.
- Penalize single-trade winners.
- Penalize parameter cliffs where tiny changes destroy performance.
- Save losing configurations too.
- Require paper-trading validation before live trading.

### Dataminer Report

The final report should include:

- Ranked result table.
- Top configurations by composite score.
- Top configurations by raw return.
- Lowest drawdown configurations.
- Best risk-adjusted configurations.
- Strategy frequency among winners.
- Parameter heatmaps.
- Equity curves versus buy-and-hold.
- Drawdown curves.
- Underlying chart with entry/exit overlays for selected result.
- Trade ledger for selected result.
- Train/test and walk-forward comparison.
- Rejection and guardrail breakdown.
- Notes explaining why the winner ranked well.

### Promotion Flow

Promoting a dataminer result should create a saved strategy preset:

- Ticker.
- Asset mode.
- Strategy composition.
- Strategy settings.
- Risk settings.
- Fill assumptions used in research.
- Data source used in research.
- Backtest metrics snapshot.
- Validation status.
- Paper-trading requirements before live use.

Promotion states:

- Research only.
- Paper candidate.
- Paper active.
- Live candidate.
- Live active.
- Disabled.

Live activation should require:

- Explicit user action.
- IBKR account connected.
- Kill switch enabled.
- Max daily loss configured.
- Max position size configured.
- Paper validation minimum met.
- No unresolved data-feed warnings.

## Data Requirements

### Underlying Data

- OHLCV bars.
- Bid/ask snapshots when available.
- Volume and relative volume.
- VWAP-ready intraday data.
- Corporate actions awareness for longer history.
- Market session calendar.

### Options Data

Options backtesting should start conservative and improve over time.

Needed for trustworthy option testing:

- Option chain by expiration and strike.
- Bid/ask spread.
- Volume.
- Open interest.
- Implied volatility.
- Greeks.
- Historical option bars when available.
- Contract selection rules by DTE, delta, strike distance, and liquidity.

Initial options phase:

- Use underlying chart as the main visual.
- Simulate option entries/exits using contract snapshots and conservative fill assumptions.
- Clearly label option backtests as lower-confidence until historical option data is deeper.

## Storage Plan

SQLite should store:

- Backtest runs.
- Dataminer batches.
- Strategy configurations.
- Parameter grids.
- Signal events.
- Guardrail decisions.
- Orders and fills.
- Trade records.
- Equity curves.
- Result metrics.
- Promoted presets.

Suggested tables:

- `backtest_runs`.
- `backtest_events`.
- `backtest_trades`.
- `backtest_equity_curve`.
- `dataminer_batches`.
- `dataminer_candidates`.
- `strategy_presets`.

## Architecture Changes

### New Modules

- `ztrade.backtest.events`
  - Event objects for replay and UI updates.
- `ztrade.backtest.runner`
  - Stepwise runner used by Workbench and Dataminer.
- `ztrade.backtest.metrics`
  - Metrics and benchmark comparison.
- `ztrade.backtest.persistence`
  - Save/load runs and results.
- `ztrade.dataminer.search_space`
  - Parameter grid and combination builders.
- `ztrade.dataminer.runner`
  - Batch execution coordinator.
- `ztrade.dataminer.scoring`
  - Composite scoring and anti-overfit penalties.
- `ztrade.dataminer.reports`
  - Report models and export helpers.
- `ztrade.ui.backtest_workbench`
  - Workbench window.
- `ztrade.ui.dataminer`
  - Dataminer window and reports.

### Shared Contract

Live trading, backtesting, and datamining should share:

- Strategy classes.
- Guardrail engine.
- Position sizing logic.
- Execution assumptions where practical.
- Normalized market snapshots.
- Trade idea and recommendation models.

## Implementation Phases

### Phase 1: Workbench Shell

- Add Backtest Workbench window.
- Launch it from individual Settings ticker rows.
- Load demo, csv, or IBKR historical bars.
- Show ticker, source, date range, bar size, and strategy controls.
- Display a basic price chart and volume panel.
- Keep existing row-level quick backtest as a fallback if needed.

### Phase 2: Stepwise Backtest Runner

- Refactor current backtest engine into a stepwise runner.
- Emit replay events.
- Add Execute, Pause, Step, Reset, and playback speed.
- Update chart and metrics while the run progresses.

### Phase 3: Trade Overlays And Ledger

- Add entry and exit markers to the chart.
- Show stop and target overlays.
- Add trade ledger.
- Add signal/guardrail event log.
- Clicking a trade focuses the chart.

### Phase 4: Metrics And Persistence

- Add richer metrics.
- Save run settings, trades, events, and equity curve to SQLite.
- Show recent runs for the ticker.
- Add export to CSV/JSON.

### Phase 5: Dataminer MVP

- Add Dataminer window.
- Define search-space models.
- Support single ticker, shares-only, existing strategies, fixed bar sizes.
- Run bounded grid batches in a background thread.
- Store all candidate results.
- Show ranked table and top result summary.

### Phase 6: Dataminer Reports

- Add report charts:
  - Equity curve versus underlying.
  - Drawdown.
  - Strategy heatmap.
  - Parameter heatmap.
  - Selected-result trade overlays.
- Add open-in-Workbench from selected candidate.

### Phase 7: Robustness And Anti-Overfitting

- Add train/test split.
- Add walk-forward validation.
- Add overfit penalties.
- Add minimum-trade and drawdown filters.
- Add winner stability checks.

### Phase 8: Options Research

- Add IBKR option-chain lookup.
- Add option contract selection rules.
- Add conservative option fill simulation.
- Add option-specific metrics.
- Add underlying-plus-option synchronized replay.

### Phase 9: Promotion To Paper And Live

- Add strategy preset model.
- Promote dataminer winners to paper candidate presets.
- Show preset status in Settings.
- Require paper validation before live candidate status.
- Keep live IBKR trading gated behind explicit user controls and kill-switch limits.

## Near-Term Build Slice

The next concrete implementation slice should be:

1. Add `docs/backtest_dataminer_plan.md`.
2. Add Backtest Workbench window shell.
3. Launch the Workbench from each ticker row Backtest button.
4. Load historical bars and render a basic chart.
5. Add controls for source, bar size, date range, and regular-hours mode.
6. Add Execute button using the current backtest engine.
7. Draw entry/exit markers after completion.
8. Add metrics summary and trade ledger.

This gives the app a useful visual backtesting surface before adding the heavier dataminer batch engine.
