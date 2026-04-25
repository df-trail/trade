from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from ztrade.models import AccountState, Fill, MarketSnapshot, Order, Position, Recommendation


class TradingStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            connection = self._connect()
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_type_time
                    ON events(event_type, occurred_at);

                CREATE INDEX IF NOT EXISTS idx_events_symbol_time
                    ON events(symbol, occurred_at);

                CREATE TABLE IF NOT EXISTS recommendations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    limit_price REAL NOT NULL,
                    confidence REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    ta_summary TEXT NOT NULL,
                    stop_price REAL,
                    target_price REAL,
                    guardrail_accepted INTEGER NOT NULL,
                    guardrail_reasons TEXT NOT NULL,
                    adjusted_quantity INTEGER,
                    option_symbol TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    client_order_id TEXT PRIMARY KEY,
                    recommendation_id TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    order_type TEXT NOT NULL,
                    limit_price REAL,
                    option_symbol TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL,
                    recommendation_id TEXT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    notional REAL NOT NULL,
                    venue TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    updated_at TEXT NOT NULL,
                    starting_cash REAL NOT NULL,
                    cash REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    equity REAL NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    starting_cash REAL NOT NULL,
                    cash REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    equity REAL NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_positions (
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    option_symbol TEXT,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (symbol, asset_class)
                );
                """
            )
            connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def record_event(
        self,
        event_type: str,
        payload: Any,
        symbol: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        occurred_at = occurred_at or datetime.now(UTC)
        with self._lock:
            self._connect().execute(
                """
                INSERT INTO events (occurred_at, event_type, symbol, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (occurred_at.isoformat(), event_type, symbol, self._json(payload)),
            )
            self._connect().commit()

    def record_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        self.record_event(
            "market_snapshot",
            snapshot,
            symbol=snapshot.symbol,
            occurred_at=snapshot.quote.timestamp,
        )

    def record_recommendation(self, recommendation: Recommendation) -> None:
        idea = recommendation.idea
        decision = recommendation.guardrail_decision
        now = datetime.now(UTC).isoformat()
        option_symbol = idea.option_contract.symbol if idea.option_contract else None
        with self._lock:
            self._connect().execute(
                """
                INSERT INTO recommendations (
                    id, created_at, updated_at, status, symbol, asset_class, side,
                    quantity, limit_price, confidence, strategy, thesis, ta_summary,
                    stop_price, target_price, guardrail_accepted, guardrail_reasons,
                    adjusted_quantity, option_symbol, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    guardrail_accepted=excluded.guardrail_accepted,
                    guardrail_reasons=excluded.guardrail_reasons,
                    adjusted_quantity=excluded.adjusted_quantity,
                    payload_json=excluded.payload_json
                """,
                (
                    recommendation.id,
                    idea.created_at.isoformat(),
                    now,
                    recommendation.status.value,
                    idea.symbol,
                    idea.asset_class.value,
                    idea.side.value,
                    idea.quantity,
                    idea.limit_price,
                    idea.confidence,
                    idea.strategy,
                    idea.thesis,
                    idea.ta_summary,
                    idea.stop_price,
                    idea.target_price,
                    1 if decision.accepted else 0,
                    json.dumps(decision.reasons),
                    decision.adjusted_quantity,
                    option_symbol,
                    self._json(recommendation),
                ),
            )
            self._connect().commit()
        self.record_event("recommendation", recommendation, symbol=idea.symbol)

    def update_recommendation_status(self, recommendation: Recommendation) -> None:
        with self._lock:
            self._connect().execute(
                """
                UPDATE recommendations
                SET status = ?, updated_at = ?, payload_json = ?
                WHERE id = ?
                """,
                (
                    recommendation.status.value,
                    datetime.now(UTC).isoformat(),
                    self._json(recommendation),
                    recommendation.id,
                ),
            )
            self._connect().commit()
        self.record_event(
            "recommendation_status",
            {"id": recommendation.id, "status": recommendation.status.value},
            symbol=recommendation.idea.symbol,
        )

    def record_order(
        self,
        order: Order,
        recommendation_id: str | None = None,
        status: str = "submitted",
    ) -> None:
        option_symbol = order.option_contract.symbol if order.option_contract else None
        with self._lock:
            self._connect().execute(
                """
                INSERT INTO orders (
                    client_order_id, recommendation_id, created_at, status, symbol,
                    asset_class, side, quantity, order_type, limit_price,
                    option_symbol, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_order_id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json
                """,
                (
                    order.client_order_id,
                    recommendation_id,
                    datetime.now(UTC).isoformat(),
                    status,
                    order.symbol,
                    order.asset_class.value,
                    order.side.value,
                    order.quantity,
                    order.order_type.value,
                    order.limit_price,
                    option_symbol,
                    self._json(order),
                ),
            )
            self._connect().commit()
        self.record_event("order", {"order": order, "status": status}, symbol=order.symbol)

    def record_fill(self, fill: Fill, recommendation_id: str | None = None) -> None:
        order = fill.order
        with self._lock:
            self._connect().execute(
                """
                INSERT INTO fills (
                    id, client_order_id, recommendation_id, timestamp, symbol,
                    asset_class, side, quantity, price, notional, venue, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    order.client_order_id,
                    recommendation_id,
                    fill.timestamp.isoformat(),
                    order.symbol,
                    order.asset_class.value,
                    order.side.value,
                    fill.quantity,
                    fill.price,
                    _notional(order.asset_class.value, fill.quantity, fill.price),
                    fill.venue,
                    self._json(fill),
                ),
            )
            self._connect().commit()
        self.record_event("fill", fill, symbol=order.symbol)

    def record_account_snapshot(self, account: AccountState) -> None:
        payload = self._json(account)
        with self._lock:
            self._connect().execute(
                """
                INSERT INTO paper_account (
                    id, updated_at, starting_cash, cash, realized_pnl, equity, payload_json
                )
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    starting_cash=excluded.starting_cash,
                    cash=excluded.cash,
                    realized_pnl=excluded.realized_pnl,
                    equity=excluded.equity,
                    payload_json=excluded.payload_json
                """,
                (
                    account.timestamp.isoformat(),
                    account.starting_cash,
                    account.cash,
                    account.realized_pnl,
                    account.equity,
                    payload,
                ),
            )
            self._connect().execute(
                """
                INSERT INTO paper_account_snapshots (
                    timestamp, starting_cash, cash, realized_pnl, equity, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    account.timestamp.isoformat(),
                    account.starting_cash,
                    account.cash,
                    account.realized_pnl,
                    account.equity,
                    payload,
                ),
            )
            self._connect().commit()

    def upsert_position(self, position: Position) -> None:
        option_symbol = position.option_contract.symbol if position.option_contract else None
        with self._lock:
            if position.quantity == 0:
                self._connect().execute(
                    """
                    DELETE FROM paper_positions
                    WHERE symbol = ? AND asset_class = ?
                    """,
                    (position.symbol, position.asset_class.value),
                )
            else:
                self._connect().execute(
                    """
                    INSERT INTO paper_positions (
                        symbol, asset_class, quantity, avg_price, realized_pnl,
                        option_symbol, updated_at, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, asset_class) DO UPDATE SET
                        quantity=excluded.quantity,
                        avg_price=excluded.avg_price,
                        realized_pnl=excluded.realized_pnl,
                        option_symbol=excluded.option_symbol,
                        updated_at=excluded.updated_at,
                        payload_json=excluded.payload_json
                    """,
                    (
                        position.symbol,
                        position.asset_class.value,
                        position.quantity,
                        position.avg_price,
                        position.realized_pnl,
                        option_symbol,
                        position.updated_at.isoformat(),
                        self._json(position),
                    ),
                )
            self._connect().commit()

    def table_counts(self) -> dict[str, int]:
        tables = (
            "events",
            "recommendations",
            "orders",
            "fills",
            "paper_account_snapshots",
            "paper_positions",
        )
        with self._lock:
            return {
                table: self._connect().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables
            }

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connect().execute(
                """
                SELECT occurred_at, event_type, symbol, payload_json
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _json(self, value: Any) -> str:
        return json.dumps(_to_jsonable(value), separators=(",", ":"), sort_keys=True)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _notional(asset_class: str, quantity: int, price: float) -> float:
    multiplier = 100 if asset_class == "option" else 1
    return quantity * price * multiplier
