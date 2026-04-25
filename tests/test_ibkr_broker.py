from __future__ import annotations

import asyncio
import os
import socket
import threading
import unittest
from unittest.mock import patch

from ztrade.brokers.ibkr import IbkrBroker, IbkrConnectionConfig, check_ibkr_socket
from ztrade.models import AssetClass, Order, OrderSide, OrderType


class IbkrBrokerTests(unittest.TestCase):
    def test_default_config_targets_local_paper_tws_port(self) -> None:
        config = IbkrConnectionConfig()
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 7497)
        self.assertFalse(config.live_trading_enabled)

    def test_config_loads_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "IBKR_ACCOUNT_ID": "DU123",
                "IBKR_HOST": "localhost",
                "IBKR_PORT": "7496",
                "IBKR_CLIENT_ID": "7",
                "IBKR_USE_TWS_API": "true",
                "IBKR_LIVE_TRADING_ENABLED": "false",
            },
        ):
            config = IbkrConnectionConfig.from_env()
        self.assertEqual(config.account_id, "DU123")
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 7496)
        self.assertEqual(config.client_id, 7)
        self.assertFalse(config.live_trading_enabled)

    def test_socket_health_reports_reachable_port(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def accept_once() -> None:
            connection, _address = server.accept()
            connection.close()
            server.close()

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()
        health = check_ibkr_socket(IbkrConnectionConfig(port=port), timeout_seconds=1.0)
        thread.join(timeout=1.0)
        self.assertTrue(health.ok)
        self.assertEqual(health.port, port)
        self.assertIsNotNone(health.latency_ms)

    def test_socket_health_reports_closed_port(self) -> None:
        health = check_ibkr_socket(IbkrConnectionConfig(host="127.0.0.1", port=1), timeout_seconds=0.1)
        self.assertFalse(health.ok)
        self.assertIn("Cannot reach IBKR API socket", health.message)

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
