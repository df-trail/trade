from __future__ import annotations

from ztrade.brokers.base import Broker
from ztrade.models import Fill, Order


class RobinhoodBroker(Broker):
    """Placeholder for future supported/authorized Robinhood securities trading access."""

    async def place_order(self, order: Order) -> Fill:
        raise NotImplementedError(
            "Robinhood live securities trading is intentionally disabled in this scaffold. "
            "Implement only after supported API access, credentials, terms, and risk controls are reviewed."
        )
