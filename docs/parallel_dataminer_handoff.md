# Parallel Agent Handoff - Exhaust Dataminer Core

This document is for a second agent working in parallel on the zTrade Exhaust Dataminer while another agent continues the Backtest Workbench and replay UI path.

## Current State

Implemented foundation:

- `src/ztrade/backtest/engine.py`
  - Shared backtest engine.
  - Returns recommendations, fills, trades, equity curve, and performance report.
- `src/ztrade/ui/backtest_workbench.py`
  - Per-ticker visual Backtest Workbench.
  - Loads demo, CSV replay, and IBKR historical bars.
  - Shows candle/volume chart, equity-vs-underlying, metrics, ledger, and entry/exit markers.
- `docs/exhaust_backtest_model.md`
  - Product and architecture plan for Exhaust.
- `docs/backtest_dataminer_plan.md`
  - Workbench and dataminer roadmap.
- `docs/vei_volatility_expansion_index.md`
  - VEI volatility-regime integration notes.

Not implemented yet:

- No `src/ztrade/dataminer/` package.
- No candidate spec model.
- No grid/search-space generator.
- No dataminer batch runner.
- No candidate scoring/ranking.
- No dataminer persistence.
- No dataminer UI.

## Parallel Ownership

### Agent A: Backtest Workbench Path

Owns:

- `src/ztrade/backtest/`
- `src/ztrade/ui/backtest_workbench.py`
- Workbench replay events.
- Workbench chart overlays.
- Workbench UI controls.

### Agent B: Exhaust Dataminer Core Path

Owns:

- New `src/ztrade/dataminer/` package.
- New `tests/test_dataminer_*.py` files.
- Minimal exports in `src/ztrade/dataminer/__init__.py`.
- Optional doc updates only if needed.

Agent B should avoid editing:

- `src/ztrade/ui/backtest_workbench.py`
- `src/ztrade/ui/desktop.py`
- `src/ztrade/backtest/engine.py`, unless absolutely required and discussed.
- Existing strategy plugin behavior, unless adding read-only metadata helpers.

## Important Working Tree Warning

The current working tree may contain uncommitted edits related to paper fill models:

- `src/ztrade/brokers/paper.py`
- `src/ztrade/config.py`
- `src/ztrade/execution/engine.py`
- `src/ztrade/models.py`
- `src/ztrade/storage/sqlite.py`
- strategy helper files
- `tests/test_paper_broker.py`

Do not revert these. Treat them as user/other-agent work. If you need fill-model assumptions, read the current working tree and integrate with it, but keep dataminer writes isolated unless explicitly assigned otherwise.

## Goal For Agent B

Build the first non-UI Exhaust Dataminer core:

1. Define candidate specs.
2. Generate bounded search spaces.
3. Run candidates through the existing `BacktestEngine`.
4. Score candidates.
5. Return ranked results.
6. Add tests.

This is a backend foundation only. The UI can plug into it later.

## Proposed Package Layout

```text
src/ztrade/dataminer/
  __init__.py
  specs.py
  search_space.py
  runner.py
  scoring.py
  reports.py
```

### `specs.py`

Define dataclasses:

- `DataSpec`
- `SignalSpec`
- `CompositionSpec`
- `InstrumentSpec`
- `EntrySpec`
- `ExitSpec`
- `PositionSizingSpec`
- `GuardrailSpec`
- `FillModelSpec`
- `ValidationSpec`
- `ScoringSpec`
- `CandidateSpec`
- `CandidateResult`
- `DataminerBatch`

Initial fields should be practical, not exhaustive.

Minimum candidate fields:

```text
candidate_id
symbol
data_provider
max_snapshots
max_hold_snapshots
strategies
composition_mode
allowed_transactions
min_confidence
max_position_fraction
max_trades_per_day
starting_cash
tags
```

The `candidate_id` should be deterministic from the serialized spec so a result can be reproduced.

### `search_space.py`

Build candidate grids.

Initial API:

```python
def generate_bounded_candidates(request: SearchSpaceRequest) -> tuple[CandidateSpec, ...]:
    ...
```

`SearchSpaceRequest` should include:

- symbol
- data provider
- strategy keys
- strategy bundle sizes
- composition modes
- min confidence values
- max position fractions
- max hold values
- allowed transactions
- max candidates

Search modes:

- Single strategy.
- Strategy pairs.
- Any-of bundle.
- All-of confirmation bundle.

Keep the first generator deterministic and small enough for tests.

### `runner.py`

Run candidates through current backtest infrastructure.

Initial API:

```python
async def run_candidate(candidate: CandidateSpec, snapshots: tuple[MarketSnapshot, ...]) -> CandidateResult:
    ...

async def run_batch(batch: DataminerBatch, snapshots: tuple[MarketSnapshot, ...]) -> tuple[CandidateResult, ...]:
    ...
```

Important:

- Prefer passing preloaded snapshots into the runner so multiple candidates reuse the same data.
- Do not make every candidate hit IBKR separately.
- Use `ReplayDataProvider` for candidate execution.
- Use `RecommendationSettingsPolicy` to apply strategy/transaction/limit settings.
- Use `BacktestEngine` rather than duplicating backtest logic.

### `scoring.py`

Implement composite scoring.

Inputs:

- `BacktestResult`
- buy-and-hold return for the same snapshots
- candidate spec

Initial score components:

- return score
- buy-and-hold outperformance
- win rate
- closed trade count
- max drawdown penalty
- low trade count penalty
- no-trade penalty

Suggested initial formula:

```text
score =
  return_pct
  + outperformance_pct
  + min(win_rate, 75) * 0.05
  + min(closed_trades, 20) * 0.25
  - max_drawdown_pct * 1.5
  - low_trade_count_penalty
```

Keep it explainable. Store component values in the result.

### `reports.py`

Add lightweight report helpers:

- sort ranked candidates
- get top N
- summarize by strategy
- summarize by composition mode
- summarize by allowed transaction type

No UI work in this phase.

## Tests To Add

Create tests:

```text
tests/test_dataminer_specs.py
tests/test_dataminer_search_space.py
tests/test_dataminer_scoring.py
tests/test_dataminer_runner.py
```

Minimum test coverage:

- Candidate IDs are deterministic.
- Search generator respects max candidate cap.
- Search generator creates single and pair strategy bundles.
- Scoring penalizes no-trade candidates.
- Buy-and-hold return calculation works.
- Runner can execute at least two candidates from the same preloaded demo snapshots.
- Ranked results come back sorted descending by score.

## Near-Term Constraints

- Shares-only first is acceptable.
- Long calls/puts can be represented in specs but do not need full options-chain mining yet.
- No live order placement.
- No database persistence yet unless the core is already stable.
- No UI yet.
- No multiprocessing yet.

## Expected Deliverable

Agent B should finish with:

- New `src/ztrade/dataminer/` package.
- New unit tests.
- All tests passing.
- A short progress note in `docs/progress.md` if editing docs is safe.
- No changes to Workbench UI files.

Suggested commit message:

```text
Add Exhaust dataminer core
```

## Suggested Agent Prompt

```text
You are Agent B working on zTrade's Exhaust Dataminer core. Read docs/exhaust_backtest_model.md, docs/backtest_dataminer_plan.md, and docs/parallel_dataminer_handoff.md. Own only new src/ztrade/dataminer/* files and tests/test_dataminer_*.py unless a tiny export/doc update is necessary. Do not edit UI files. Do not revert unrelated working-tree changes. Build candidate spec dataclasses, bounded search-space generation, candidate/batch runner using the existing BacktestEngine with ReplayDataProvider, composite scoring versus buy-and-hold, report helpers, and unit tests. Keep the first version deterministic and backend-only.
```

