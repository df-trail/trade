from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BotMode(StrEnum):
    STAGE_ONLY = "stage_only"
    AUTO_PAPER = "auto_paper"
    AUTO_EXIT_ONLY = "auto_exit_only"
    AUTO_TRADE_LIMITED = "auto_trade_limited"


class DataProviderKind(StrEnum):
    DEMO = "demo"
    CSV_REPLAY = "csv_replay"
    POLYGON_SNAPSHOT = "polygon_snapshot"
    IBKR_SNAPSHOT = "ibkr_snapshot"
    IBKR_HISTORICAL = "ibkr_historical"


@dataclass(slots=True)
class GuardrailConfig:
    account_equity: float = 10_000.0
    min_confidence_to_stage: float = 0.55
    min_confidence_to_auto_trade: float = 0.75
    min_position_fraction: float = 0.05
    max_position_fraction: float = 0.15
    max_daily_loss_fraction: float = 0.03
    max_trade_loss_fraction: float = 0.01
    max_open_positions: int = 5
    max_open_option_contracts: int = 10
    max_trades_per_day: int = 3
    pdt_protection_enabled: bool = True
    account_under_25k: bool = True
    margin_enabled: bool = False
    allow_market_orders: bool = False
    live_trading_enabled: bool = False
    kill_switch_enabled: bool = False
    max_quote_age_ms: int = 1_500
    max_stock_spread_bps: float = 25.0
    max_option_spread_pct: float = 12.5
    min_stock_volume: int = 250_000
    min_relative_volume: float = 1.2
    min_option_open_interest: int = 100
    min_option_volume: int = 25
    max_option_premium: float = 5.00
    min_days_to_expiration: int = 0
    max_days_to_expiration: int = 45
    earnings_blackout_days: int = 1
    symbol_cooldown_seconds: int = 300
    loss_streak_cooldown_seconds: int = 900


@dataclass(slots=True)
class AppConfig:
    bot_mode: BotMode = BotMode.STAGE_ONLY
    data_provider: DataProviderKind = DataProviderKind.DEMO
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    default_watchlist: tuple[str, ...] = ("SPY", "QQQ", "AAPL", "NVDA", "TSLA")
    decision_timeout_ms: int = 2_000
    paper_fill_guaranteed: bool = True
    database_path: str = "data/ztrade.sqlite3"
    record_market_events: bool = True
    csv_replay_path: str | None = None
    replay_delay_seconds: float = 0.0
    polygon_api_key_env: str = "POLYGON_API_KEY"
    finnhub_api_key_env: str = "FINNHUB_API_KEY"
    tradier_token_env: str = "TRADIER_TOKEN"
    live_poll_interval_seconds: float = 1.0
    enable_finnhub_news: bool = True
    ibkr_historical_duration: str = "2 D"
    ibkr_historical_bar_size: str = "5 mins"
    ibkr_historical_what_to_show: str = "TRADES"
    ibkr_use_rth: bool = True
    ibkr_market_data_type: int = 3
    ibkr_history_timeout_seconds: float = 20.0
    ibkr_quote_timeout_seconds: float = 8.0
