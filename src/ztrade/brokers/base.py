from __future__ import annotations

from abc import ABC, abstractmethod

from ztrade.models import Fill, Order


class OrderRejectedError(RuntimeError):
    pass


class Broker(ABC):
    @abstractmethod
    async def place_order(self, order: Order) -> Fill:
        raise NotImplementedError
