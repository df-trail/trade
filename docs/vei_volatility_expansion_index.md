# VEI - Volatility Expansion Index

Source reviewed: TradingView open-source indicator page, "VEI - Volatility Expansion Index" by PrabuddhaPeramuna, published December 5, 2025.

Source URL: https://www.tradingview.com/script/hrQeKYuH-VEI-Volatility-Expansion-Index/

This document summarizes the VEI concept for zTrade planning. It should be implemented from the concept and formula, not by copying TradingView Pine code.

## Summary

VEI is a volatility-regime classifier. It compares short-term volatility against a longer baseline so the app can decide whether the market is calm, controlled, expanding, or unstable.

Core calculation:

```text
VEI = ATR(short_window) / ATR(long_window)
```

The TradingView page suggests `ATR short = 10` and `ATR long = 50` as a starting configuration.

The important product idea is that VEI is not a buy/sell signal. It is context. In zTrade, it should answer:

- Is this ticker currently tradable for the selected strategy?
- Should position size be reduced?
- Should a trend, pullback, breakout, mean-reversion, or options-volatility strategy be allowed?
- Did a backtest perform well only during stable volatility regimes?
- Does a live setup match the volatility conditions where it backtested well?

## Regime Interpretation

Suggested zTrade regime labels:

- `compressed`: VEI below a low threshold and/or decreasing.
- `stable`: VEI below `1.0`.
- `normal`: VEI near `1.0`.
- `expanding`: VEI above an expansion threshold, initially `1.2`.
- `chaotic`: VEI materially above expansion threshold or rapidly rising.

Initial defaults:

```text
short_window = 10
long_window = 50
stable_threshold = 1.00
expansion_threshold = 1.20
chaotic_threshold = 1.50
slope_lookback = 3
```

These should be dataminer parameters, not hard-coded final truth.

## How To Incorporate VEI In zTrade

### 1. Indicator Library

Add VEI to `src/ztrade/analysis/indicators.py`.

Proposed function:

```python
def vei_from_bars(bars: Sequence[Bar], short_window: int = 10, long_window: int = 50) -> float | None:
    ...
```

Related helpers:

- `vei_series_from_bars(...)`
- `vei_regime(value, slope, thresholds) -> str`
- `vei_slope(series, lookback=3) -> float`

ATR already exists in zTrade, so VEI can reuse the existing ATR implementation.

### 2. Market Snapshot Feature

Add VEI into normalized analysis metadata rather than forcing every strategy to recompute it.

Near-term lightweight option:

- Calculate VEI inside strategy helpers when needed.

Better medium-term option:

- Add a `TechnicalContext` or `VolatilityContext` object.
- Attach it to `MarketSnapshot`.
- Include:
  - `atr_short`
  - `atr_long`
  - `vei`
  - `vei_slope`
  - `vei_regime`

### 3. Strategy Filters

VEI should be a strategy gate and sizing modifier.

Recommended use by strategy family:

- Trend continuation:
  - Prefer `stable`, `normal`, or gently `expanding`.
  - Size down or block during `chaotic`.
- VWAP pullback / moving-average bounce:
  - Prefer `stable` or `compressed`.
  - Block during fast expansion if historical testing shows whipsaw.
- Breakout:
  - Allow `normal` to `expanding`.
  - Avoid `chaotic` unless the strategy is explicitly built for shock moves.
- Mean reversion:
  - Prefer `stable` or `normal`.
  - Block during volatility expansion unless testing proves otherwise.
- News momentum:
  - Use VEI as a risk warning, not a total block by default.
  - High VEI should increase slippage assumptions and reduce size.
- Options-flow momentum:
  - Use VEI to decide whether long premium has enough underlying movement support.
- Straddle / strangle / volatility setups:
  - Expansion can be favorable if entered before or early in expansion.
  - Late chaotic expansion should be penalized because option premiums/spreads may already be inflated.

### 4. Guardrails And Position Sizing

Add optional guardrail rules:

- Block strategy if `vei_regime` is not allowed by that strategy.
- Reduce max position size when VEI is above expansion threshold.
- Increase required confidence when VEI is chaotic.
- Increase slippage assumption when VEI is rising quickly.
- For options, tighten max spread and minimum volume requirements during expansion.

Example sizing policy:

```text
stable/normal: normal size
expanding: 50-75% size unless strategy explicitly prefers expansion
chaotic: block or 25-50% size
```

### 5. Backtest Workbench

Add VEI to the visual Workbench:

- Lower indicator panel with VEI line.
- Horizontal regime lines at `1.0`, `1.2`, and optional `1.5`.
- Background shading for stable, expanding, and chaotic windows.
- Entry/exit marker tooltip should include VEI value and regime at entry.
- Metrics should include performance grouped by VEI regime.

Workbench report additions:

- Trades by VEI regime.
- Win rate by VEI regime.
- Return by VEI regime.
- Max drawdown by VEI regime.
- Average slippage/fill penalty by VEI regime.

### 6. Exhaust Dataminer

VEI belongs directly in the Exhaust candidate search space.

Add these candidate dimensions:

- `vei_short_window`: 5, 10, 14, 20.
- `vei_long_window`: 30, 50, 100.
- `vei_allowed_regimes`: stable, normal, expanding, chaotic.
- `vei_expansion_threshold`: 1.10, 1.20, 1.30.
- `vei_chaotic_threshold`: 1.40, 1.50, 1.75.
- `vei_slope_filter`: none, rising, falling, flat.
- `vei_action`: allow, block, size_down, confidence_boost, confidence_penalty.

Dataminer questions:

- Does this ticker's breakout strategy only work when VEI is already expanding?
- Does its mean-reversion strategy fail when VEI rises above `1.2`?
- Is options performance better when VEI is stable-before-expansion rather than already chaotic?
- Does VEI improve drawdown more than it reduces return?
- Which VEI thresholds survive walk-forward testing?

### 7. Live Trading Presets

When a mined strategy is promoted to paper/live, store its VEI assumptions:

- VEI windows.
- Allowed regimes.
- Position-size modifier by regime.
- Confidence adjustment by regime.
- Backtested performance by regime.

Live recommendation detail should show:

```text
VEI 0.92 stable: strategy allowed at normal size
VEI 1.28 expanding: strategy allowed at reduced size
VEI 1.63 chaotic: strategy blocked by preset
```

## Implementation Plan

### Phase 1: Indicator

- Add VEI calculation to `analysis/indicators.py`.
- Add unit tests for ATR-ratio behavior.
- Add regime classification helper.

### Phase 2: Strategy Context

- Add VEI to strategy helper summaries.
- Add VEI regime to recommendation `ta_summary`.
- Use VEI as an optional filter in selected strategy plugins.

Suggested first strategies:

- `relative_volume_breakout`
- `opening_range_breakout`
- `vwap_pullback_continuation`
- `rsi_mean_reversion`
- `options_flow_momentum`

### Phase 3: Backtest Workbench

- Plot VEI in a lower panel.
- Add regime shading.
- Add VEI at entry/exit into ledger details.
- Add performance-by-regime metrics.

### Phase 4: Dataminer

- Add VEI thresholds to candidate specs.
- Run search comparing strategy performance with and without VEI filters.
- Add VEI parameter heatmap.
- Add "VEI improved/damaged this strategy" report note.

### Phase 5: Live Guardrails

- Add per-strategy VEI live rules.
- Add position size modifiers.
- Add live recommendation warning when current VEI is outside the winning backtest regime.

## Risks And Caveats

- VEI is a context filter, not an edge by itself.
- ATR ratio thresholds may vary by ticker, timeframe, and asset class.
- Short ATR windows can overreact on thin or gappy tickers.
- Option spreads can widen during high VEI, so options backtests need conservative fill assumptions.
- VEI can improve drawdowns while reducing total opportunity count; score it on risk-adjusted performance, not only return.

## zTrade Fit

VEI is a strong fit for zTrade because the app already has:

- ATR in the indicator library.
- Strategy plugins that need volatility context.
- Backtesting and Workbench views where regime overlays are useful.
- An Exhaust dataminer plan that needs parameterized filters.
- Guardrails where VEI can directly affect size, confidence, and trade blocking.

The best first use is not to create a "VEI strategy." The best first use is to make VEI a common filter that every strategy can opt into and the dataminer can test exhaustively.
