# Backtest Workbench Replay Progress

This file tracks Agent A work on the Backtest Workbench and stepwise replay path while Agent B works on the Exhaust Dataminer core.

## 2026-04-25

Added backend replay events:

- `BacktestEventType.BAR`
- `BacktestEventType.SIGNAL`
- `BacktestEventType.FILTERED_SIGNAL`
- `BacktestEventType.ENTRY_FILL`
- `BacktestEventType.EXIT_FILL`
- `BacktestEventType.TRADE_CLOSED`
- `BacktestEventType.EQUITY`
- `BacktestEventType.COMPLETE`

Added `BacktestEvent` model in `src/ztrade/backtest/events.py` and exported it from `ztrade.backtest`.

Updated `BacktestEngine` so callers can pass an optional `event_sink` callback. Existing callers still work without the callback.

Updated the Backtest Workbench:

- Added Play, Pause, Step, Reset Replay, and speed controls.
- Added replay event log.
- Execute Backtest now captures event timeline data.
- The chart progressively reveals candles and trade markers during replay.
- The ledger fills as trades close during replay.
- Metrics update with replay progress.

Verification:

- `python -m compileall src tests scripts` passed.
- `python -m unittest discover -s tests -p test_pipeline.py` passed.
- `python -m unittest discover -s tests` passed with 42 tests.
- Workbench Tk construction check passed.
- Workbench helper smoke produced 35 snapshots, 338 replay events, and 3 closed trades.

Next Workbench items:

- Add stop and target line overlays.
- Add rejected signal markers on chart.
- Add VEI/ATR lower panel.
- Add guardrail reason drilldown in event log.
- Add export of replay events and ledger.
