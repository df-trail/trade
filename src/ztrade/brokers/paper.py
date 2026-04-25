from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ztrade.brokers.base import Broker, OrderRejectedError
from ztrade.models import AccountState, AssetClass, Fill, Order, OrderSide, Position

if TYPE_CHECKING:
    from ztrade.storage.sqlite import TradingStore


class PaperBroker(Broker):
    """Paper broker that fills accepted orders and tracks cash/positions."""

    def __init__(self, starting_cash: float, store: TradingStore | None = None) -> None:
        self._starting_cash = starting_cash
        self._cash = starting_cash
        self._realized_pnl = 0.0
        self._positions: dict[tuple[str, AssetClass], Position] = {}
        self._store = store
        self._lock = threading.RLock()
        if self._store:
            self._store.record_account_snapshot(self.account_state())

    async def place_order(self, order: Order) -> Fill:
        if order.limit_price is None:
            raise ValueError("Paper broker requires a reference price for guaranteed fills.")
        fill = Fill(order=order, price=order.limit_price, quantity=order.quantity)
        with self._lock:
            self._apply_fill(fill)
            if self._store:
                self._store.record_account_snapshot(self.account_state())
        return fill

    def account_state(self) -> AccountState:
        with self._lock:
            return AccountState(
                starting_cash=self._starting_cash,
                cash=round(self._cash, 2),
                realized_pnl=round(self._realized_pnl, 2),
                positions=tuple(self._positions.values()),
            )

    def _apply_fill(self, fill: Fill) -> None:
        order = fill.order
        key = (order.symbol, order.asset_class)
        multiplier = 100 if order.asset_class == AssetClass.OPTION else 1
        notional = fill.price * fill.quantity * multiplier
        existing = self._positions.get(key)

        if order.side == OrderSide.BUY:
            if notional > self._cash:
                raise OrderRejectedError("Paper broker rejected buy order because cash is insufficient.")
            previous_quantity = existing.quantity if existing else 0
            previous_cost = existing.avg_price * previous_quantity * multiplier if existing else 0.0
            new_quantity = previous_quantity + fill.quantity
            new_avg = (previous_cost + notional) / (new_quantity * multiplier)
            self._cash -= notional
            self._positions[key] = Position(
                symbol=order.symbol,
                asset_class=order.asset_class,
                quantity=new_quantity,
                avg_price=round(new_avg, 4),
                realized_pnl=existing.realized_pnl if existing else 0.0,
                option_contract=order.option_contract,
                updated_at=datetime.now(UTC),
            )
            if self._store:
                self._store.upsert_position(self._positions[key])
            return

        if existing is None or existing.quantity < fill.quantity:
            raise OrderRejectedError("Paper broker rejected sell order because position is insufficient.")

        remaining_quantity = existing.quantity - fill.quantity
        realized = (fill.price - existing.avg_price) * fill.quantity * multiplier
        self._cash += notional
        self._realized_pnl += realized
        if remaining_quantity == 0:
            closed = Position(
                symbol=order.symbol,
                asset_class=order.asset_class,
                quantity=0,
                avg_price=existing.avg_price,
                realized_pnl=existing.realized_pnl + realized,
                option_contract=order.option_contract,
                updated_at=datetime.now(UTC),
            )
            del self._positions[key]
            if self._store:
                self._store.upsert_position(closed)
            return

        self._positions[key] = Position(
            symbol=order.symbol,
            asset_class=order.asset_class,
            quantity=remaining_quantity,
            avg_price=existing.avg_price,
            realized_pnl=existing.realized_pnl + realized,
            option_contract=order.option_contract,
            updated_at=datetime.now(UTC),
        )
        if self._store:
            self._store.upsert_position(self._positions[key])
