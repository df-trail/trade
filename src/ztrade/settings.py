from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from ztrade.config import GuardrailConfig
from ztrade.models import AssetClass, GuardrailDecision, Recommendation


@dataclass(frozen=True, slots=True)
class StrategySpec:
    key: str
    label: str
    description: str
    default_min_confidence: float = 0.55
    default_max_position_fraction: float = 0.10
    default_max_trades_per_day: int = 3


@dataclass(frozen=True, slots=True)
class TransactionSpec:
    key: str
    label: str
    description: str


STRATEGY_CATALOG: dict[str, StrategySpec] = {
    "news_momentum": StrategySpec(
        "news_momentum",
        "News",
        "Trades positive high-urgency news when price trend and relative volume confirm.",
    ),
    "relative_volume_breakout": StrategySpec(
        "relative_volume_breakout",
        "Breakout",
        "Trades range breaks backed by elevated relative volume.",
    ),
    "vwap_reclaim": StrategySpec(
        "vwap_reclaim",
        "VWAP Reclaim",
        "Trades a reclaim of VWAP after price had been below it.",
    ),
    "rsi_mean_reversion": StrategySpec(
        "rsi_mean_reversion",
        "RSI Revert",
        "Looks for oversold symbols near range lows that may bounce.",
    ),
    "options_flow_momentum": StrategySpec(
        "options_flow_momentum",
        "Options Flow",
        "Trades bullish options activity aligned with short-term momentum.",
    ),
    "gap_continuation": StrategySpec(
        "gap_continuation",
        "Gap Continue",
        "Looks for strong intraday continuation after a large move away from the session open.",
    ),
    "opening_range_breakout": StrategySpec(
        "opening_range_breakout",
        "Opening Range",
        "Trades a break above the early-session range with volume confirmation.",
    ),
    "ema_trend": StrategySpec(
        "ema_trend",
        "EMA Trend",
        "Follows short EMA over long EMA alignment when price stays above trend.",
    ),
    "atr_breakout": StrategySpec(
        "atr_breakout",
        "ATR Breakout",
        "Trades directional expansion beyond recent ATR-normalized movement.",
    ),
    "squeeze_breakout": StrategySpec(
        "squeeze_breakout",
        "Squeeze",
        "Looks for volatility compression followed by a range expansion.",
    ),
    "support_bounce": StrategySpec(
        "support_bounce",
        "Support Bounce",
        "Looks for a rebound from recent support with improving close location.",
    ),
    "liquidity_sweep_reversal": StrategySpec(
        "liquidity_sweep_reversal",
        "Sweep Reversal",
        "Looks for a sweep below recent lows followed by a reclaim.",
    ),
    "earnings_drift": StrategySpec(
        "earnings_drift",
        "Earnings Drift",
        "Trades post-catalyst continuation when news urgency and trend align.",
    ),
    "market_regime_trend": StrategySpec(
        "market_regime_trend",
        "Regime Trend",
        "Only trades when broad market regime is supportive of risk-on continuation.",
    ),
    "iv_expansion": StrategySpec(
        "iv_expansion",
        "IV Expansion",
        "Uses option IV and volume expansion as a momentum confirmation.",
    ),
    "volume_spike_momentum": StrategySpec(
        "volume_spike_momentum",
        "Volume Spike",
        "Trades fresh highs when current volume is sharply above its recent average.",
    ),
    "vwap_pullback_continuation": StrategySpec(
        "vwap_pullback_continuation",
        "VWAP Pullback",
        "Looks for a pullback into VWAP that holds and resumes in trend.",
    ),
    "trend_pullback_continuation": StrategySpec(
        "trend_pullback_continuation",
        "Trend Pullback",
        "Trades shallow pullbacks that resume while short EMAs remain above longer EMAs.",
    ),
    "high_tight_flag": StrategySpec(
        "high_tight_flag",
        "High Tight Flag",
        "Looks for a tight consolidation resolving after a strong impulse move.",
    ),
    "volume_dry_up_breakout": StrategySpec(
        "volume_dry_up_breakout",
        "VDU Breakout",
        "Trades breakouts after volume dries up through a base.",
    ),
    "bullish_engulfing_reversal": StrategySpec(
        "bullish_engulfing_reversal",
        "Engulfing",
        "Looks for a bullish engulfing candle with enough relative volume.",
    ),
    "moving_average_bounce": StrategySpec(
        "moving_average_bounce",
        "MA Bounce",
        "Trades a rebound from the 20-bar moving average.",
    ),
    "multi_timeframe_momentum": StrategySpec(
        "multi_timeframe_momentum",
        "MTF Momentum",
        "Requires short and medium timeframe trend alignment before staging a trade.",
    ),
    "news_dip_buy": StrategySpec(
        "news_dip_buy",
        "News Dip Buy",
        "Looks for recoveries from dips while positive news remains fresh.",
    ),
    "put_flow_momentum": StrategySpec(
        "put_flow_momentum",
        "Put Flow",
        "Stages bearish long-put ideas when put flow and downside price action align.",
    ),
    "vwap_failure_put": StrategySpec(
        "vwap_failure_put",
        "VWAP Failure",
        "Stages bearish long-put ideas after a VWAP rejection with elevated participation.",
    ),
}

STRATEGY_LABELS: dict[str, str] = {
    key: spec.label for key, spec in STRATEGY_CATALOG.items()
}

STRATEGY_DESCRIPTIONS: dict[str, str] = {
    key: spec.description for key, spec in STRATEGY_CATALOG.items()
}

TRANSACTION_GROUPS: dict[str, tuple[TransactionSpec, ...]] = {
    "Share Trades": (
        TransactionSpec("long_shares", "Long shares", "Buy shares when the strategy is bullish."),
        TransactionSpec("short_shares", "Short shares", "Sell short shares. Not used until shorting is explicitly supported."),
    ),
    "Simple Options": (
        TransactionSpec("long_call", "Long call", "Buy a call option for bullish directional setups."),
        TransactionSpec("long_put", "Long put", "Buy a put option for bearish directional setups."),
        TransactionSpec("covered_call", "Covered call", "Sell calls against long shares. Future workflow."),
        TransactionSpec("cash_secured_put", "Cash-secured put", "Sell puts against cash. Future workflow."),
    ),
    "Complex Options": (
        TransactionSpec("straddle", "Straddle", "Buy call and put at the same strike for volatility expansion."),
        TransactionSpec("strangle", "Strangle", "Buy out-of-the-money call and put for volatility expansion."),
        TransactionSpec("bull_call_spread", "Bull call spread", "Defined-risk bullish call spread."),
        TransactionSpec("bear_put_spread", "Bear put spread", "Defined-risk bearish put spread."),
        TransactionSpec("iron_condor", "Iron condor", "Defined-risk range-bound options structure."),
        TransactionSpec("calendar_spread", "Calendar spread", "Same strike, different expirations. Future workflow."),
    ),
}

TRANSACTION_DESCRIPTIONS: dict[str, str] = {
    item.key: item.description for items in TRANSACTION_GROUPS.values() for item in items
}

DEFAULT_ALLOWED_TRANSACTIONS: tuple[str, ...] = ("long_shares", "long_call", "long_put")


@dataclass(slots=True)
class StrategySettings:
    enabled: bool = True
    min_confidence: float = 0.55
    max_position_fraction: float = 0.10
    max_trades_per_day: int = 3


@dataclass(slots=True)
class TickerTradeSettings:
    symbol: str
    enabled: bool = True
    trade_shares: bool = True
    trade_simple: bool = True
    trade_complex: bool = False
    allowed_transactions: tuple[str, ...] = DEFAULT_ALLOWED_TRANSACTIONS
    strategies: tuple[str, ...] = field(default_factory=lambda: tuple(STRATEGY_LABELS))
    strategy_settings: dict[str, StrategySettings] = field(default_factory=dict)
    max_position_fraction: float = 0.10
    max_trades_per_day: int = 3
    max_option_contracts: int = 4
    min_confidence: float = 0.55

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()

    def setting_for_strategy(self, strategy: str) -> StrategySettings:
        if strategy in self.strategy_settings:
            return self.strategy_settings[strategy]
        spec = STRATEGY_CATALOG.get(strategy)
        if spec is None:
            return StrategySettings()
        return StrategySettings(
            enabled=strategy in self.strategies,
            min_confidence=spec.default_min_confidence,
            max_position_fraction=spec.default_max_position_fraction,
            max_trades_per_day=spec.default_max_trades_per_day,
        )


@dataclass(slots=True)
class TradingSettings:
    tickers: tuple[TickerTradeSettings, ...]

    @property
    def active_symbols(self) -> tuple[str, ...]:
        symbols: list[str] = []
        for row in self.tickers:
            symbol = row.normalized_symbol
            if row.enabled and symbol and symbol not in symbols:
                symbols.append(symbol)
        return tuple(symbols)

    def for_symbol(self, symbol: str) -> TickerTradeSettings | None:
        normalized = symbol.strip().upper()
        for row in self.tickers:
            if row.enabled and row.normalized_symbol == normalized:
                return row
        return None


class SettingsStore:
    def __init__(self, path: str | Path = "data/settings.json") -> None:
        self.path = Path(path)

    def load(self, defaults: tuple[str, ...]) -> TradingSettings:
        if not self.path.exists():
            return default_trading_settings(defaults)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = tuple(_row_from_dict(item) for item in payload.get("tickers", []))
        if not rows:
            return default_trading_settings(defaults)
        return TradingSettings(tickers=rows)

    def save(self, settings: TradingSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tickers": [_row_to_dict(row) for row in settings.tickers]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class RecommendationSettingsPolicy:
    def __init__(self, settings: TradingSettings, guardrails: GuardrailConfig) -> None:
        self._settings = settings
        self._guardrails = guardrails
        self._counts: dict[tuple[date, str], int] = {}

    def apply(self, recommendation: Recommendation) -> Recommendation | None:
        idea = recommendation.idea
        underlying = idea.option_contract.underlying if idea.option_contract else idea.symbol
        row = self._settings.for_symbol(underlying)
        if row is None:
            return None
        strategy_settings = row.setting_for_strategy(idea.strategy)
        if idea.strategy not in row.strategies or not strategy_settings.enabled:
            return None
        min_confidence = max(row.min_confidence, strategy_settings.min_confidence)
        if idea.confidence < min_confidence:
            return None
        transaction_type = _transaction_type_for_recommendation(recommendation)
        if not _row_allows_transaction(row, transaction_type):
            return None
        count_key = (datetime.now(UTC).date(), row.normalized_symbol)
        strategy_count_key = (datetime.now(UTC).date(), row.normalized_symbol, idea.strategy)
        if self._counts.get(count_key, 0) >= row.max_trades_per_day:
            return None
        if self._counts.get(strategy_count_key, 0) >= strategy_settings.max_trades_per_day:
            return None

        existing = recommendation.guardrail_decision
        if not existing.accepted:
            return recommendation

        quantity = existing.adjusted_quantity or idea.quantity
        max_quantity = self._max_quantity(row, strategy_settings, idea.asset_class, idea.limit_price)
        reasons: list[str] = []
        if max_quantity < 1:
            reasons.append("Ticker settings max position size is below one unit.")
        adjusted_quantity = min(quantity, max_quantity)
        if idea.asset_class == AssetClass.OPTION:
            adjusted_quantity = min(adjusted_quantity, row.max_option_contracts)
            if row.max_option_contracts < 1:
                reasons.append("Ticker settings max option contracts is below one.")
        if adjusted_quantity < 1:
            reasons.append("Ticker settings adjusted quantity is below one.")

        recommendation.guardrail_decision = GuardrailDecision(
            accepted=not reasons,
            reasons=existing.reasons + tuple(reasons),
            adjusted_quantity=adjusted_quantity if adjusted_quantity != idea.quantity else None,
        )
        if not recommendation.guardrail_decision.accepted:
            return None
        self._counts[count_key] = self._counts.get(count_key, 0) + 1
        self._counts[strategy_count_key] = self._counts.get(strategy_count_key, 0) + 1
        return recommendation

    def _max_quantity(
        self,
        row: TickerTradeSettings,
        strategy_settings: StrategySettings,
        asset_class: AssetClass,
        price: float,
    ) -> int:
        multiplier = 100 if asset_class == AssetClass.OPTION else 1
        unit_cost = price * multiplier
        if unit_cost <= 0:
            return 0
        position_fraction = min(row.max_position_fraction, strategy_settings.max_position_fraction)
        max_notional = self._guardrails.account_equity * max(0.0, position_fraction)
        return int(max_notional // unit_cost)


def default_trading_settings(symbols: tuple[str, ...]) -> TradingSettings:
    return TradingSettings(
        tickers=tuple(TickerTradeSettings(symbol=symbol) for symbol in symbols),
    )


def _row_from_dict(payload: dict[str, object]) -> TickerTradeSettings:
    strategies = payload.get("strategies", tuple(STRATEGY_LABELS))
    if not isinstance(strategies, list | tuple):
        strategies = tuple(STRATEGY_LABELS)
    allowed_transactions = payload.get("allowed_transactions")
    if not isinstance(allowed_transactions, list | tuple):
        allowed_transactions = _legacy_transactions(payload)
    strategy_settings_payload = payload.get("strategy_settings", {})
    if not isinstance(strategy_settings_payload, dict):
        strategy_settings_payload = {}
    parsed_strategy_settings = {
        key: _strategy_settings_from_dict(value)
        for key, value in strategy_settings_payload.items()
        if key in STRATEGY_LABELS and isinstance(value, dict)
    }
    return TickerTradeSettings(
        symbol=str(payload.get("symbol", "")).upper(),
        enabled=bool(payload.get("enabled", True)),
        trade_shares=bool(payload.get("trade_shares", True)),
        trade_simple=bool(payload.get("trade_simple", True)),
        trade_complex=bool(payload.get("trade_complex", False)),
        allowed_transactions=tuple(str(item) for item in allowed_transactions if str(item) in TRANSACTION_DESCRIPTIONS),
        strategies=tuple(str(item) for item in strategies if str(item) in STRATEGY_LABELS),
        strategy_settings=parsed_strategy_settings,
        max_position_fraction=float(payload.get("max_position_fraction", 0.10)),
        max_trades_per_day=int(payload.get("max_trades_per_day", 3)),
        max_option_contracts=int(payload.get("max_option_contracts", 4)),
        min_confidence=float(payload.get("min_confidence", 0.55)),
    )


def _row_to_dict(row: TickerTradeSettings) -> dict[str, object]:
    payload = asdict(row)
    payload["strategy_settings"] = {
        key: asdict(value) for key, value in row.strategy_settings.items()
    }
    return payload


def _strategy_settings_from_dict(payload: dict[str, object]) -> StrategySettings:
    return StrategySettings(
        enabled=bool(payload.get("enabled", True)),
        min_confidence=float(payload.get("min_confidence", 0.55)),
        max_position_fraction=float(payload.get("max_position_fraction", 0.10)),
        max_trades_per_day=int(payload.get("max_trades_per_day", 3)),
    )


def _legacy_transactions(payload: dict[str, object]) -> tuple[str, ...]:
    transactions: list[str] = []
    if bool(payload.get("trade_shares", True)):
        transactions.append("long_shares")
    if bool(payload.get("trade_simple", True)):
        transactions.extend(("long_call", "long_put"))
    if bool(payload.get("trade_complex", False)):
        transactions.extend(("straddle", "strangle", "bull_call_spread", "bear_put_spread"))
    return tuple(transactions)


def _row_allows_transaction(row: TickerTradeSettings, transaction_type: str) -> bool:
    if transaction_type not in row.allowed_transactions:
        return False
    if transaction_type in {"long_shares", "short_shares"} and not row.trade_shares:
        return False
    if transaction_type in {"long_call", "long_put", "covered_call", "cash_secured_put"} and not row.trade_simple:
        return False
    complex_transactions = {item.key for item in TRANSACTION_GROUPS["Complex Options"]}
    if transaction_type in complex_transactions and not row.trade_complex:
        return False
    return True


def _transaction_type_for_recommendation(recommendation: Recommendation) -> str:
    idea = recommendation.idea
    if idea.asset_class == AssetClass.STOCK:
        return "long_shares"
    if idea.option_contract:
        if idea.option_contract.option_type.lower() == "put":
            return "long_put"
        return "long_call"
    return "long_call"
