from __future__ import annotations

from ztrade.brokers.base import Broker
from ztrade.models import Fill, Order


class PaperBroker(Broker):
    """Paper broker that fills every accepted order immediately."""

    async def place_order(self, order: Order) -> Fill:
        if order.limit_price is None:
            raise ValueError("Paper broker requires a reference price for guaranteed fills.")
        return Fill(order=order, price=order.limit_price, quantity=order.quantity)
