from __future__ import annotations

from dataclasses import dataclass

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


class IbkrBroker(Broker):
    """Placeholder for future IBKR paper/live brokerage integration."""

    def __init__(self, config: IbkrConnectionConfig | None = None) -> None:
        self.config = config or IbkrConnectionConfig()

    async def place_order(self, order: Order) -> Fill:
        raise NotImplementedError(
            "IBKR brokerage execution is intentionally disabled in this scaffold. "
            "Use PaperBroker while implementing IBKR paper account connectivity, contract lookup, "
            "order preview, order status reconciliation, and live-trading kill-switch checks."
        )
