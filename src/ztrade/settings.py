from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from ztrade.config import GuardrailConfig
from ztrade.models import AssetClass, GuardrailDecision, Recommendation


STRATEGY_LABELS: dict[str, str] = {
    "news_momentum": "News",
    "relative_volume_breakout": "Breakout",
    "vwap_reclaim": "VWAP",
    "rsi_mean_reversion": "RSI",
    "options_flow_momentum": "Flow",
}


@dataclass(slots=True)
class TickerTradeSettings:
    symbol: str
    enabled: bool = True
    trade_shares: bool = True
    trade_simple: bool = True
    trade_complex: bool = False
    strategies: tuple[str, ...] = field(default_factory=lambda: tuple(STRATEGY_LABELS))
    max_position_fraction: float = 0.10
    max_trades_per_day: int = 3
    max_option_contracts: int = 4
    min_confidence: float = 0.55

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


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
        payload = {"tickers": [asdict(row) for row in settings.tickers]}
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
        if idea.strategy not in row.strategies:
            return None
        if idea.confidence < row.min_confidence:
            return None
        if idea.asset_class == AssetClass.STOCK and not row.trade_shares:
            return None
        if idea.asset_class == AssetClass.OPTION and not row.trade_simple:
            return None
        count_key = (datetime.now(UTC).date(), row.normalized_symbol)
        if self._counts.get(count_key, 0) >= row.max_trades_per_day:
            return None

        existing = recommendation.guardrail_decision
        if not existing.accepted:
            return recommendation

        quantity = existing.adjusted_quantity or idea.quantity
        max_quantity = self._max_quantity(row, idea.asset_class, idea.limit_price)
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
        return recommendation

    def _max_quantity(self, row: TickerTradeSettings, asset_class: AssetClass, price: float) -> int:
        multiplier = 100 if asset_class == AssetClass.OPTION else 1
        unit_cost = price * multiplier
        if unit_cost <= 0:
            return 0
        max_notional = self._guardrails.account_equity * max(0.0, row.max_position_fraction)
        return int(max_notional // unit_cost)


def default_trading_settings(symbols: tuple[str, ...]) -> TradingSettings:
    return TradingSettings(
        tickers=tuple(TickerTradeSettings(symbol=symbol) for symbol in symbols),
    )


def _row_from_dict(payload: dict[str, object]) -> TickerTradeSettings:
    strategies = payload.get("strategies", tuple(STRATEGY_LABELS))
    if not isinstance(strategies, list | tuple):
        strategies = tuple(STRATEGY_LABELS)
    return TickerTradeSettings(
        symbol=str(payload.get("symbol", "")).upper(),
        enabled=bool(payload.get("enabled", True)),
        trade_shares=bool(payload.get("trade_shares", True)),
        trade_simple=bool(payload.get("trade_simple", True)),
        trade_complex=bool(payload.get("trade_complex", False)),
        strategies=tuple(str(item) for item in strategies if str(item) in STRATEGY_LABELS),
        max_position_fraction=float(payload.get("max_position_fraction", 0.10)),
        max_trades_per_day=int(payload.get("max_trades_per_day", 3)),
        max_option_contracts=int(payload.get("max_option_contracts", 4)),
        min_confidence=float(payload.get("min_confidence", 0.55)),
    )
