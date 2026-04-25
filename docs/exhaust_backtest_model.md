# Exhaust Backtest Model

This is the planning document for the zTrade "Exhaust" model: a strategy mining system that can brute-force many combinations of signals, instruments, exits, risk rules, and validation methods for a selected ticker.

Source reviewed: `docs/trade_strategies.pdf`, a local copy of "151 Trading Strategies" by Zura Kakushadze and Juan Andres Serur, dated 2018. This plan uses the document as a taxonomy and research prompt. It does not copy the source formulas into zTrade. The goal is to convert the strategy universe into an implementation roadmap for personal paper trading, IBKR data, and eventually guarded live execution.

## What The Source Adds

The PDF is useful to zTrade in four ways:

- It gives a broad strategy taxonomy across options, stocks, ETFs, indexes, volatility, futures, macro, crypto, and other assets.
- It shows that many named strategies are really reusable building blocks: trend, mean reversion, carry, spread, volatility, event, factor, optimization, and machine learning.
- It reinforces that backtests must control for out-of-sample timing, trading costs, liquidity, position bounds, and survivorship/data bias.
- It gives a large options structure vocabulary that can become zTrade transaction templates once IBKR option-chain and options historical data are stronger.

The current zTrade scope is narrower than the whole PDF:

- Primary assets: US stocks and listed options through IBKR.
- Current execution default: paper trading.
- Account constraints: no margin, PDT awareness, small account sizing, and strict guardrails.
- Near-term focus: ticker-level backtesting and strategy mining for shares and long/defined-risk options.

## Exhaust Goal

For a selected ticker, Exhaust should answer:

- Which strategy families work best on this underlying?
- Which combinations are stronger than single strategies?
- Which timeframes and holding periods are durable?
- Does shares-only, options-only, or mixed shares/options perform better?
- Does the strategy beat the underlying buy-and-hold return after costs and slippage?
- Is the result robust out-of-sample, or just curve-fitted noise?
- Can this result be promoted into a live paper preset with guardrails?

## Core Candidate Model

Every dataminer candidate should be represented as a structured object:

```text
Candidate =
  DataSpec
  + SignalSpec[]
  + CompositionSpec
  + InstrumentSpec
  + EntrySpec
  + ExitSpec
  + PositionSizingSpec
  + GuardrailSpec
  + FillModelSpec
  + ValidationSpec
  + ScoringSpec
```

This matters because a result is only useful if zTrade can reproduce it, explain it, compare it, and promote it.

## Candidate Dimensions

### DataSpec

- Ticker.
- Benchmark ticker: usually `SPY`, `QQQ`, or sector ETF.
- Data source: `demo`, `csv_replay`, `ibkr_historical`.
- Bar size: `1 min`, `5 mins`, `15 mins`, `30 mins`, `1 hour`, `1 day`.
- Date range.
- Regular-hours only or extended-hours included.
- Corporate action adjustment policy.
- Required feeds:
  - OHLCV bars.
  - Quotes.
  - Option chain.
  - Option bid/ask.
  - Option volume and open interest.
  - Implied volatility and Greeks.
  - Earnings calendar.
  - News/social feed.
  - Market regime indicators.

### SignalSpec

Signals should be small, testable modules. They produce a directional or volatility view, not a trade by themselves.

Each signal should define:

- Name.
- Direction: bullish, bearish, neutral, volatility-up, volatility-down.
- Required data.
- Lookback windows.
- Thresholds.
- Confidence score.
- Explanation fields for chart overlays.
- Whether it can run live.
- Whether it can run historically.

### CompositionSpec

The dataminer should test how signals combine:

- Single signal.
- Any-of bundle.
- All-of confirmation bundle.
- Weighted vote.
- Primary signal plus confirmation filter.
- Entry signal plus separate exit signal.
- Regime-gated signal.
- Conflict resolver where bullish and bearish signals both fire.

### InstrumentSpec

The same signal can be expressed with different instruments:

- Shares.
- Long call.
- Long put.
- Protective put.
- Covered call.
- Bull call spread.
- Bear put spread.
- Long straddle.
- Long strangle.
- Collar.
- Future: iron condor, butterfly, calendar, diagonal, ratio, synthetic, and volatility structures.

For the small-account/no-margin constraint, Exhaust should gate instruments:

- Phase 1 allowed: shares, long calls, long puts.
- Phase 2 allowed: defined-risk vertical spreads and collars.
- Phase 3 allowed: straddles, strangles, calendars, diagonals, butterflies, condors.
- Block until explicitly enabled: naked short options, undefined-risk structures, short straddles/strangles, margin-heavy strategies.

### EntrySpec

- Enter at next bar open.
- Enter at next bar close.
- Enter on breakout stop.
- Enter on limit pullback.
- Enter on quote midpoint.
- Enter on ask for long options.
- Delay model:
  - Delay 0 research only.
  - Delay 1 default realistic mode.
  - Custom seconds or bars for news/feed reaction testing.

### ExitSpec

- Fixed target.
- Fixed stop.
- ATR target and stop.
- Trailing stop.
- VWAP failure.
- Moving-average cross exit.
- Time stop.
- End-of-day flatten.
- Earnings/news event exit.
- Strategy reversal exit.
- Option-specific exit:
  - Percent premium gain.
  - Percent premium loss.
  - DTE cutoff.
  - Delta cutoff.
  - IV crush cutoff.
  - Spread/liquidity deterioration cutoff.

### PositionSizingSpec

- Fixed shares/contracts.
- Fixed dollar allocation.
- Percent of equity.
- Confidence weighted.
- Volatility adjusted.
- Stop-distance risk budget.
- Kelly-like research score, not live default.
- Max allocation cap.
- Max loss per trade.
- Max trades per day.

### GuardrailSpec

- Minimum price.
- Minimum volume.
- Minimum relative volume.
- Maximum spread.
- Maximum quote age.
- Maximum allocation.
- Maximum daily loss.
- Maximum open positions.
- PDT/day-trade budget.
- No margin.
- No live order unless promoted preset is active.
- Cooldown after loss.
- Kill switch.

### FillModelSpec

- Optimistic: fill at close or midpoint.
- Realistic: next bar open plus slippage.
- Conservative: bid/ask adverse fill.
- Volume-capped partial fill.
- Option liquidity penalty.
- Commission and fees.
- Spread widening during high volatility.
- News-latency slippage.

### ValidationSpec

- Full-period backtest.
- Train/test split.
- Walk-forward validation.
- Rolling window validation.
- Market-regime slices.
- Earnings versus non-earnings slices.
- High-volume versus normal-volume slices.
- In-sample and out-of-sample labels stored with each result.

### ScoringSpec

Rank by robust performance, not raw return alone:

- Total return.
- Return versus buy-and-hold.
- Dollar P&L.
- Profit factor.
- Max drawdown.
- Drawdown duration.
- Win rate.
- Average win/loss.
- Trade count confidence.
- Exposure time.
- Average hold time.
- Sharpe-like score.
- Sortino-like score.
- Out-of-sample score.
- Walk-forward consistency.
- Liquidity penalty.
- Slippage penalty.
- Overfit penalty.

## Source Strategy Families Adapted For zTrade

### Options Structures

The PDF has the richest immediate vocabulary in options. zTrade should treat these as instrument templates, not standalone alpha signals.

Priority templates:

- Long call.
- Long put.
- Covered call.
- Protective put.
- Collar.
- Bull call spread.
- Bear put spread.
- Bull put spread, only after cash-secured and margin checks are implemented.
- Bear call spread, only after margin and risk checks are implemented.
- Long straddle.
- Long strangle.
- Calendar spread.
- Diagonal spread.
- Butterfly.
- Condor.
- Iron condor.

Dataminer tests for options should vary:

- DTE.
- Moneyness.
- Delta target.
- Strike distance.
- IV rank.
- Spread width.
- Minimum option volume.
- Minimum open interest.
- Maximum bid/ask spread.
- Exit by premium change.
- Exit by underlying signal.
- Exit by DTE cutoff.

First implementation should visualize trades on the underlying chart. Option-specific price charts can come later.

### Stock Signal Families

The stock section maps directly into zTrade signal modules:

- Price momentum.
- Earnings momentum.
- Value or fundamental score.
- Low-volatility anomaly.
- Implied-volatility signal.
- Multifactor portfolio score.
- Residual momentum.
- Pairs trading.
- Mean reversion.
- Moving average systems.
- Support and resistance.
- Channel trading.
- Event-driven signals.
- Single-stock machine learning.
- Statistical arbitrage.
- Market-making style liquidity signals.
- Alpha combination models.

For a single ticker, cross-sectional ideas should be translated into ticker-relative features:

- Ticker versus its own history.
- Ticker versus `SPY`.
- Ticker versus `QQQ`.
- Ticker versus sector ETF.
- Ticker versus peer basket.
- Ticker versus market regime.

### ETF And Index Families

These are useful even if zTrade trades one ticker row at a time:

- Sector momentum rotation becomes a sector-regime input.
- Dual momentum becomes a benchmark confirmation filter.
- ETF mean reversion becomes a market context filter.
- Index volatility targeting becomes a position-sizing modifier.
- Index/ETF arbitrage becomes a future multi-symbol strategy, not a near-term single-ticker strategy.

### Volatility Families

Volatility strategies should become both signals and instrument selectors:

- Volatility risk premium.
- IV versus realized volatility.
- IV skew.
- VIX or volatility ETF regime.
- Straddle/strangle event-volatility setups.
- Risk reversal as directional skew expression.

Near-term use:

- Prefer long options when IV is acceptable and directional confidence is high.
- Avoid long premium when IV is extremely elevated unless event-volatility logic specifically supports it.
- Prefer shares when option liquidity or spread quality is weak.

### Machine Learning And Sentiment Families

The PDF includes neural network, KNN, and naive Bayes style ideas. In zTrade these should be treated carefully:

- Start with feature-based scoring before complex ML.
- Save feature vectors for every signal.
- Require walk-forward validation.
- Require out-of-sample performance.
- Penalize unstable models.
- Avoid promoting ML strategies to live without paper-trading evidence.

Near-term feature set:

- Price returns.
- Volatility.
- Relative volume.
- VWAP distance.
- Moving-average slopes.
- RSI.
- ATR.
- Gap size.
- Benchmark relative strength.
- News count.
- News sentiment.
- Earnings proximity.
- Option IV rank.
- Option volume/open-interest changes.

### Macro And Event Families

These can feed ticker-level filters:

- Earnings announcements.
- Economic announcements.
- Inflation/rate-sensitive regime.
- Market-wide momentum.
- Sector trend.
- News shock.

Near-term event types:

- Earnings date.
- Pre-market news.
- Social/news velocity spike.
- Large gap.
- Abnormal volume.

### Excluded Or Future Families

Some source categories are outside current zTrade scope:

- Fixed income.
- Structured credit.
- Tax arbitrage.
- Distressed debt.
- Real estate.
- Cash strategies unrelated to market trading.
- Illegal or abusive cash strategies.
- Physical commodities.
- Most futures.
- Infrastructure investing.

These should not be implemented in the personal stock/options trading app unless the product scope changes.

## Strategy Catalog For Exhaust V1

### V1 Signal Modules

- Price momentum.
- Gap continuation.
- Relative-volume breakout.
- Opening-range breakout.
- EMA trend.
- SMA trend.
- VWAP reclaim.
- VWAP pullback continuation.
- RSI mean reversion.
- ATR breakout.
- Channel breakout.
- Support/resistance bounce.
- Moving-average bounce.
- Squeeze breakout.
- Earnings drift.
- News momentum.
- Benchmark relative strength.
- Low-volatility filter.
- IV rank filter.
- Options-flow momentum.
- Market-regime trend.

### V1 Instrument Modes

- Shares only.
- Long call.
- Long put.
- Shares plus long call.
- Shares plus long put.

### V1 Composition Modes

- Single signal.
- Any-of bundle.
- All-of confirmation bundle.
- Weighted vote.
- Primary plus confirmation.

### V1 Exits

- Fixed stop/target.
- ATR stop/target.
- Trailing stop.
- VWAP failure.
- Moving-average failure.
- Max hold bars.
- End-of-day flatten.

## Exhaust Search Modes

### Tiny Search

Purpose: fast interactive testing from the Workbench.

- One ticker.
- One data source.
- One bar size.
- Selected strategies only.
- Small parameter grid.
- Runs in seconds to minutes.

### Bounded Search

Purpose: default dataminer mode.

- One ticker.
- Multiple bar sizes.
- Multiple strategy combinations.
- Shares and long options.
- Capped candidate count.
- Background execution with progress updates.

### Exhaustive Grid

Purpose: overnight research.

- Wide parameter grid.
- Many strategy combinations.
- Multiple validation windows.
- Saves every candidate result.
- Requires estimated runtime and cancel/resume.

### Random Search

Purpose: explore large spaces without combinatorial explosion.

- Randomly samples parameter combinations.
- Can bias sampling around promising regions.
- Useful after a bounded search finds a good family.

### Walk-Forward Search

Purpose: promotion-quality validation.

- Optimize on training window.
- Test on following out-of-sample window.
- Roll forward.
- Score consistency across windows.
- Required before live candidate status.

### Explore Around Winner

Purpose: robustness testing.

- Start from one high-ranking candidate.
- Perturb parameters.
- Retest nearby combinations.
- Penalize winners that collapse under small changes.

## Candidate Explosion Control

The system needs controls so "exhaustive" does not become unusable:

- Estimate candidate count before running.
- Estimate runtime before running.
- Let user cap max candidates.
- Let user cap max strategy bundle size.
- Start with one ticker.
- Prefer staged funnels:
  - Stage 1: broad cheap scan.
  - Stage 2: deeper run on top families.
  - Stage 3: walk-forward validation.
  - Stage 4: paper-trading promotion.
- Cache historical bars.
- Reuse indicator calculations across candidates.
- Parallelize candidates later, after persistence is reliable.

## Data Quality Rules

Backtests should fail loudly when data is not good enough.

- Missing bars must be counted.
- Stale quotes must be counted.
- Split/dividend adjustments must be known.
- Option chains must include timestamp.
- Option fills must know bid/ask spread.
- Earnings/news timestamps must be timezone-normalized.
- Extended-hours inclusion must be explicit.
- IBKR pacing limits must be handled with cache and retry behavior.

## Out-Of-Sample Rules

From the source appendix, the most important engineering lesson is timing discipline.

zTrade should store and display:

- Signal observation time.
- Decision time.
- Simulated order time.
- Fill time.
- Data delay assumption.
- Whether the run is delay-0 research, delay-1 realistic, or custom latency.

Hard rule:

- A strategy cannot use bar-close information to enter at that same bar's open.

Allowed modes:

- Research mode can run delay-0 to measure raw signal strength.
- Realistic mode should default to next-bar execution.
- News-speed mode should model seconds of feed and decision latency.

## Cost And Liquidity Rules

Every candidate should include:

- Commission assumptions.
- Slippage assumptions.
- Bid/ask spread cost.
- Option spread penalty.
- Volume participation cap.
- Minimum ADV or intraday volume.
- Max contract spread percent.
- Minimum option open interest.

Scoring should penalize:

- Low-liquidity winners.
- Strategies dependent on perfect fills.
- Strategies with too few trades.
- Strategies that only win during one regime.

## Report Requirements

Each Exhaust batch should produce a report with:

- Ranked candidates.
- Composite score.
- Return versus underlying.
- Equity curve versus buy-and-hold.
- Drawdown curve.
- Underlying chart with selected candidate entries/exits.
- Strategy family heatmap.
- Parameter heatmap.
- Bar-size comparison.
- Asset-mode comparison.
- Train/test comparison.
- Walk-forward comparison.
- Guardrail rejection summary.
- Cost and slippage summary.
- Top winning trades.
- Worst losing trades.
- Overfit warning flags.

The report should make it easy to answer:

- Did this beat holding the underlying?
- Was the outperformance worth the drawdown?
- Did it survive out-of-sample?
- Did it require unrealistic fills?
- Did options help or just add noise?
- Is it stable enough to paper trade live?

## Promotion To Paper And Live

An Exhaust candidate can become a strategy preset only if it has:

- Saved candidate spec.
- Saved data source and date range.
- Saved strategy versions.
- Saved metrics.
- Saved chart/report artifact.
- Out-of-sample result.
- Guardrail settings.
- Paper validation requirement.

Promotion states:

- Research result.
- Paper candidate.
- Paper active.
- Live candidate.
- Live active.
- Disabled.

Live candidate requirements:

- Positive out-of-sample score.
- Minimum trade count.
- Max drawdown below configured threshold.
- Profit factor above configured threshold.
- No critical data-quality warnings.
- Paper run completed for configured number of trades or days.
- Kill switch enabled.
- Daily loss cap enabled.
- IBKR account connected.
- Explicit user approval.

## Persistence Model

Suggested tables:

- `strategy_catalog`
- `instrument_templates`
- `candidate_specs`
- `dataminer_batches`
- `dataminer_candidates`
- `backtest_runs`
- `backtest_events`
- `backtest_trades`
- `backtest_equity_curve`
- `backtest_metrics`
- `strategy_presets`
- `paper_validation_runs`

Each candidate should store a serialized spec so old research remains reproducible even after code evolves.

## Implementation Phases

### Phase 1: Document And Catalog

- Add this Exhaust model plan.
- Build a first strategy catalog in code.
- Tag strategies by required data, direction, asset compatibility, and implementation status.
- Add metadata for option structure templates.

### Phase 2: Workbench Integration

- Launch Backtest Workbench from a ticker row.
- Load historical bars.
- Chart underlying price and volume.
- Run one candidate.
- Show entries, exits, metrics, and trade ledger.

### Phase 3: Candidate Spec Engine

- Add structured candidate spec classes.
- Convert current strategy settings into candidate specs.
- Store and reload specs.
- Add deterministic candidate IDs.

### Phase 4: Exhaust MVP

- Add Dataminer window.
- Select ticker and search mode.
- Generate bounded candidate grid.
- Run candidates in a background thread.
- Store every result.
- Show progress and ranked table.

### Phase 5: Report And Overlay

- Add selected-candidate chart overlay.
- Add equity versus underlying chart.
- Add drawdown chart.
- Add strategy and parameter heatmaps.
- Export report to markdown or HTML.

### Phase 6: Robust Validation

- Add train/test split.
- Add walk-forward validation.
- Add overfit and liquidity penalties.
- Add winner-neighborhood robustness tests.

### Phase 7: Options Expansion

- Add IBKR option-chain selection.
- Add long call/put backtesting.
- Add defined-risk spread templates.
- Add option fill/slippage models.
- Add synchronized underlying and option replay.

### Phase 8: Promotion Workflow

- Promote candidate to paper preset.
- Show preset on Settings row.
- Run live paper validation.
- Track promoted preset performance.
- Gate live trading behind validation and guardrails.

## Near-Term Build Order

1. Keep `docs/trade_strategies.pdf` as source material, but work from this markdown plan.
2. Add strategy catalog metadata to code.
3. Build the Backtest Workbench window shell.
4. Refactor backtest execution to produce events.
5. Add candidate specs and deterministic candidate IDs.
6. Add the Dataminer MVP with bounded grid search.
7. Add report overlays and equity-vs-underlying charts.
8. Add promotion to paper preset.

## Open Questions

- Should Exhaust default to shares-only until option historical data is deep enough?
- Which benchmark should each ticker use: `SPY`, `QQQ`, sector ETF, or user-selected?
- How large should the default bounded search be before requiring overnight mode?
- Should delay-0 research results be blocked from promotion automatically?
- What paper-validation threshold is required before live candidate status?
- Should reports be saved as markdown, HTML, or both?

