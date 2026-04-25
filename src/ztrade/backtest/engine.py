from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from ztrade.analytics.performance import PerformanceReport, TradeRecord, build_performance_report
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig
from ztrade.data.providers import DataProvider
from ztrade.execution.engine import ExecutionEngine
from ztrade.models import AssetClass, Fill, MarketSnapshot, Order, OrderSide, OrderType, Recommendation, TradeIdea
from ztrade.recommendations.engine import RecommendationEngine


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    max_snapshots: int | None = None
    max_hold_snapshots: int = 40
    close_at_end: bool = True


@dataclass(slots=True)
class OpenTrade:
    recommendation: Recommendation
    entry_fill: Fill
    opened_index: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    recommendations: tuple[Recommendation, ...]
    fills: tuple[Fill, ...]
    trades: tuple[TradeRecord, ...]
    report: PerformanceReport


class BacktestEngine:
    def __init__(
        self,
        config: AppConfig,
        recommendation_engine: RecommendationEngine,
        execution_engine: ExecutionEngine,
        paper_broker: PaperBroker,
        backtest_config: BacktestConfig | None = None,
        recommendation_filter: Callable[[Recommendation], Recommendation | None] | None = None,
    ) -> None:
        self._config = config
        self._recommendation_engine = recommendation_engine
        self._execution_engine = execution_engine
        self._paper_broker = paper_broker
        self._backtest_config = backtest_config or BacktestConfig()
        self._recommendation_filter = recommendation_filter

    def replay(self, snapshots: list[MarketSnapshot]) -> BacktestResult:
        return _run_async_replay(self.run(_ListProvider(snapshots)))

    async def run(self, provider: DataProvider) -> BacktestResult:
        return await self.run_snapshots(provider.stream())

    async def run_snapshots(self, snapshots: AsyncIterator[MarketSnapshot]) -> BacktestResult:
        recommendations: list[Recommendation] = []
        fills: list[Fill] = []
        closed_trades: list[TradeRecord] = []
        open_trades: list[OpenTrade] = []
        last_snapshot_by_symbol: dict[str, MarketSnapshot] = {}
        equity_curve: list[float] = [self._paper_broker.account_state().equity]

        snapshot_index = 0
        async for snapshot in snapshots:
            snapshot_index += 1
            last_snapshot_by_symbol[snapshot.symbol] = snapshot
            exit_fills, trade_records = await self._process_exits(snapshot, open_trades, snapshot_index)
            fills.extend(exit_fills)
            closed_trades.extend(trade_records)

            for recommendation in self._recommendation_engine.evaluate(snapshot):
                if self._recommendation_filter:
                    recommendation = self._recommendation_filter(recommendation)
                    if recommendation is None:
                        continue
                recommendations.append(recommendation)
                fill = await self._execution_engine.approve(recommendation)
                if fill is None:
                    continue
                fills.append(fill)
                open_trades.append(OpenTrade(recommendation=recommendation, entry_fill=fill, opened_index=snapshot_index))

            equity_curve.append(self._paper_broker.account_state().equity)
            if self._backtest_config.max_snapshots and snapshot_index >= self._backtest_config.max_snapshots:
                break

        if self._backtest_config.close_at_end:
            exit_fills, trade_records = await self._close_all(open_trades, last_snapshot_by_symbol)
            fills.extend(exit_fills)
            closed_trades.extend(trade_records)
            equity_curve.append(self._paper_broker.account_state().equity)

        account = self._paper_broker.account_state()
        report = build_performance_report(
            starting_cash=account.starting_cash,
            ending_cash=account.cash,
            ending_equity=account.equity,
            realized_pnl=account.realized_pnl,
            recommendations=len(recommendations),
            fills=len(fills),
            trades=tuple(closed_trades),
            equity_curve=tuple(equity_curve),
        )
        return BacktestResult(
            recommendations=tuple(recommendations),
            fills=tuple(fills),
            trades=tuple(closed_trades),
            report=report,
        )

    async def _process_exits(
        self,
        snapshot: MarketSnapshot,
        open_trades: list[OpenTrade],
        snapshot_index: int,
    ) -> tuple[list[Fill], list[TradeRecord]]:
        fills: list[Fill] = []
        records: list[TradeRecord] = []
        remaining: list[OpenTrade] = []
        for trade in open_trades:
            price = _exit_price_for_snapshot(snapshot, trade.recommendation.idea)
            if price is None:
                remaining.append(trade)
                continue
            exit_reason = _exit_reason(trade.recommendation.idea, price)
            if exit_reason is None and snapshot_index - trade.opened_index >= self._backtest_config.max_hold_snapshots:
                exit_reason = "max_hold"
            if exit_reason is None:
                remaining.append(trade)
                continue
            fill = await self._sell(trade, price)
            fills.append(fill)
            records.append(_trade_record(trade, fill, exit_reason))
        open_trades[:] = remaining
        return fills, records

    async def _close_all(
        self,
        open_trades: list[OpenTrade],
        last_snapshot_by_symbol: dict[str, MarketSnapshot],
    ) -> tuple[list[Fill], list[TradeRecord]]:
        fills: list[Fill] = []
        records: list[TradeRecord] = []
        for trade in list(open_trades):
            snapshot = last_snapshot_by_symbol.get(trade.recommendation.idea.option_contract.underlying) if (
                trade.recommendation.idea.option_contract
            ) else last_snapshot_by_symbol.get(trade.recommendation.idea.symbol)
            if snapshot is None:
                continue
            price = _exit_price_for_snapshot(snapshot, trade.recommendation.idea)
            if price is None:
                continue
            fill = await self._sell(trade, price)
            fills.append(fill)
            records.append(_trade_record(trade, fill, "end_of_backtest"))
            open_trades.remove(trade)
        return fills, records

    async def _sell(self, trade: OpenTrade, price: float) -> Fill:
        order = Order(
            symbol=trade.entry_fill.order.symbol,
            asset_class=trade.entry_fill.order.asset_class,
            side=OrderSide.SELL,
            quantity=trade.entry_fill.quantity,
            order_type=OrderType.LIMIT,
            limit_price=round(price, 4),
            option_contract=trade.entry_fill.order.option_contract,
        )
        return await self._paper_broker.place_order(order)


class _ListProvider(DataProvider):
    def __init__(self, snapshots: list[MarketSnapshot]) -> None:
        self._snapshots = snapshots

    async def stream(self) -> AsyncIterator[MarketSnapshot]:
        for snapshot in self._snapshots:
            yield snapshot


def _run_async_replay(coro: object) -> BacktestResult:
    import asyncio

    return asyncio.run(coro)


def _exit_price_for_snapshot(snapshot: MarketSnapshot, idea: TradeIdea) -> float | None:
    if idea.asset_class == AssetClass.STOCK:
        if snapshot.symbol != idea.symbol:
            return None
        return snapshot.quote.bid
    if snapshot.option_quote and snapshot.option_quote.symbol == idea.symbol:
        return snapshot.option_quote.bid
    return None


def _exit_reason(idea: TradeIdea, price: float) -> str | None:
    if idea.stop_price is not None and price <= idea.stop_price:
        return "stop"
    if idea.target_price is not None and price >= idea.target_price:
        return "target"
    return None


def _trade_record(open_trade: OpenTrade, exit_fill: Fill, exit_reason: str) -> TradeRecord:
    entry = open_trade.entry_fill
    multiplier = 100 if entry.order.asset_class == AssetClass.OPTION else 1
    pnl = (exit_fill.price - entry.price) * entry.quantity * multiplier
    pnl_pct = ((exit_fill.price - entry.price) / entry.price) * 100 if entry.price else 0.0
    return TradeRecord(
        symbol=entry.order.symbol,
        strategy=open_trade.recommendation.idea.strategy,
        asset_class=entry.order.asset_class.value,
        quantity=entry.quantity,
        entry_price=entry.price,
        exit_price=exit_fill.price,
        pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 3),
        exit_reason=exit_reason,
    )
