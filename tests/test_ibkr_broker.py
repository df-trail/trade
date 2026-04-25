from __future__ import annotations

import asyncio
import unittest

from ztrade.brokers.ibkr import IbkrBroker, IbkrConnectionConfig
from ztrade.models import AssetClass, Order, OrderSide, OrderType


class IbkrBrokerTests(unittest.TestCase):
    def test_default_config_targets_local_paper_tws_port(self) -> None:
        config = IbkrConnectionConfig()
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 7497)
        self.assertFalse(config.live_trading_enabled)

    def test_ibkr_broker_refuses_orders_until_implemented(self) -> None:
        async def run() -> None:
            broker = IbkrBroker()
            order = Order(
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=100.0,
            )
            with self.assertRaises(NotImplementedError):
                await broker.place_order(order)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
