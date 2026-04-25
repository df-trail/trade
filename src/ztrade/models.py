from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class AssetClass(StrEnum):
    STOCK = "stock"
    OPTION = "option"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"


class RecommendationStatus(StrEnum):
    STAGED = "staged"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class OptionContract:
    underlying: str
    expiration: str
    strike: float
    option_type: str
    symbol: str


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    relative_volume: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    days_to_expiration: int | None = None

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2, 4)

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)

    @property
    def spread_pct(self) -> float:
        if self.mid <= 0:
            return 100.0
        return (self.spread / self.mid) * 100

    @property
    def spread_bps(self) -> float:
        if self.mid <= 0:
            return 10_000.0
        return (self.spread / self.mid) * 10_000


@dataclass(frozen=True, slots=True)
class NewsItem:
    headline: str
    symbols: tuple[str, ...]
    source: str
    sentiment: float
    urgency: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    quote: Quote
    recent_closes: tuple[float, ...] = ()
    recent_volumes: tuple[int, ...] = ()
    option_quote: Quote | None = None
    option_contract: OptionContract | None = None
    latest_news: NewsItem | None = None


@dataclass(frozen=True, slots=True)
class TradeIdea:
    symbol: str
    asset_class: AssetClass
    side: OrderSide
    quantity: int
    limit_price: float
    confidence: float
    strategy: str
    thesis: str
    ta_summary: str
    stop_price: float | None = None
    target_price: float | None = None
    option_contract: OptionContract | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    accepted: bool
    reasons: tuple[str, ...] = ()
    adjusted_quantity: int | None = None


@dataclass(slots=True)
class Recommendation:
    idea: TradeIdea
    guardrail_decision: GuardrailDecision
    status: RecommendationStatus = RecommendationStatus.STAGED
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True, slots=True)
class Order:
    symbol: str
    asset_class: AssetClass
    side: OrderSide
    quantity: int
    order_type: OrderType
    limit_price: float | None
    option_contract: OptionContract | None = None
    client_order_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True, slots=True)
class Fill:
    order: Order
    price: float
    quantity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    venue: str = "paper"
