from __future__ import annotations

import os
import socket
from contextlib import closing
from dataclasses import dataclass
from time import perf_counter

from ztrade.brokers.base import Broker
from ztrade.models import Fill, Order


@dataclass(frozen=True, slots=True)
class IbkrConnectionConfig:
    account_id: str = ""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    use_tws_api: bool = True
    client_portal_base_url: str = "https://localhost:5000/v1/api"
    live_trading_enabled: bool = False

    @classmethod
    def from_env(cls) -> IbkrConnectionConfig:
        return cls(
            account_id=os.getenv("IBKR_ACCOUNT_ID", ""),
            host=os.getenv("IBKR_HOST", "127.0.0.1"),
            port=_env_int("IBKR_PORT", 7497),
            client_id=_env_int("IBKR_CLIENT_ID", 1),
            use_tws_api=_env_bool("IBKR_USE_TWS_API", True),
            client_portal_base_url=os.getenv("IBKR_CLIENT_PORTAL_BASE_URL", "https://localhost:5000/v1/api"),
            live_trading_enabled=_env_bool("IBKR_LIVE_TRADING_ENABLED", False),
        )


@dataclass(frozen=True, slots=True)
class IbkrConnectionHealth:
    ok: bool
    host: str
    port: int
    client_id: int
    latency_ms: float | None = None
    message: str = ""


class IbkrBroker(Broker):
    """Placeholder for future IBKR paper/live brokerage integration."""

    def __init__(self, config: IbkrConnectionConfig | None = None) -> None:
        self.config = config or IbkrConnectionConfig()

    def check_connection(self, timeout_seconds: float = 1.5) -> IbkrConnectionHealth:
        return check_ibkr_socket(self.config, timeout_seconds=timeout_seconds)

    async def place_order(self, order: Order) -> Fill:
        raise NotImplementedError(
            "IBKR brokerage execution is intentionally disabled in this scaffold. "
            "Use PaperBroker while implementing IBKR paper account connectivity, contract lookup, "
            "order preview, order status reconciliation, and live-trading kill-switch checks."
        )


def check_ibkr_socket(
    config: IbkrConnectionConfig | None = None,
    timeout_seconds: float = 1.5,
) -> IbkrConnectionHealth:
    cfg = config or IbkrConnectionConfig.from_env()
    started = perf_counter()
    try:
        with closing(socket.create_connection((cfg.host, cfg.port), timeout=timeout_seconds)):
            latency_ms = (perf_counter() - started) * 1000
    except OSError as exc:
        return IbkrConnectionHealth(
            ok=False,
            host=cfg.host,
            port=cfg.port,
            client_id=cfg.client_id,
            message=f"Cannot reach IBKR API socket at {cfg.host}:{cfg.port}: {exc}",
        )
    warning = ""
    if cfg.port in {7496, 4001} and not cfg.live_trading_enabled:
        warning = " Connected to a default live-session port; keep Read-Only API on until paper routing is proven."
    return IbkrConnectionHealth(
        ok=True,
        host=cfg.host,
        port=cfg.port,
        client_id=cfg.client_id,
        latency_ms=round(latency_ms, 1),
        message=f"IBKR API socket reachable at {cfg.host}:{cfg.port} in {latency_ms:.1f} ms.{warning}",
    )


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
