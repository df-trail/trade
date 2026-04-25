from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class TradeRecord:
    symbol: str
    strategy: str
    asset_class: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    exit_reason: str


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    starting_cash: float
    ending_cash: float
    ending_equity: float
    realized_pnl: float
    return_pct: float
    total_recommendations: int
    total_fills: int
    closed_trades: int
    win_rate: float
    average_trade_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    max_drawdown_pct: float


def build_performance_report(
    *,
    starting_cash: float,
    ending_cash: float,
    ending_equity: float,
    realized_pnl: float,
    recommendations: int,
    fills: int,
    trades: tuple[TradeRecord, ...],
    equity_curve: tuple[float, ...],
) -> PerformanceReport:
    wins = [trade for trade in trades if trade.pnl > 0]
    pnl_values = [trade.pnl for trade in trades]
    return_pct = ((ending_equity - starting_cash) / starting_cash) * 100 if starting_cash else 0.0
    return PerformanceReport(
        starting_cash=round(starting_cash, 2),
        ending_cash=round(ending_cash, 2),
        ending_equity=round(ending_equity, 2),
        realized_pnl=round(realized_pnl, 2),
        return_pct=round(return_pct, 3),
        total_recommendations=recommendations,
        total_fills=fills,
        closed_trades=len(trades),
        win_rate=round((len(wins) / len(trades)) * 100, 2) if trades else 0.0,
        average_trade_pnl=round(mean(pnl_values), 2) if pnl_values else 0.0,
        best_trade_pnl=round(max(pnl_values), 2) if pnl_values else 0.0,
        worst_trade_pnl=round(min(pnl_values), 2) if pnl_values else 0.0,
        max_drawdown_pct=round(_max_drawdown_pct(equity_curve), 3),
    )


def _max_drawdown_pct(equity_curve: tuple[float, ...]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak <= 0:
            continue
        max_drawdown = min(max_drawdown, (equity - peak) / peak)
    return abs(max_drawdown) * 100
