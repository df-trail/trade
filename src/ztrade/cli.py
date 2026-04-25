from __future__ import annotations

import argparse
import asyncio
import sqlite3
from pathlib import Path

from ztrade.backtest.engine import BacktestConfig, BacktestEngine
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, BotMode, DataProviderKind
from ztrade.data.factory import create_data_provider
from ztrade.env import load_env_file
from ztrade.execution.engine import ExecutionEngine
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.storage.sqlite import TradingStore
from ztrade.strategies.registry import default_strategies
from ztrade.ui.desktop import main as desktop_main


def main() -> None:
    load_env_file()
    parser = argparse.ArgumentParser(prog="ztrade", description="zTrade personal paper-trading workstation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("desktop", help="Open the desktop UI")

    stream_parser = subparsers.add_parser("stream", help="Run recommendation stream in the terminal")
    stream_parser.add_argument("--limit", type=int, default=30, help="Maximum snapshots to process")
    stream_parser.add_argument("--auto-paper", action="store_true", help="Auto-fill accepted paper trades")
    stream_parser.add_argument(
        "--provider",
        choices=[provider.value for provider in DataProviderKind],
        default=DataProviderKind.DEMO.value,
        help="Data provider to use",
    )
    stream_parser.add_argument("--symbols", default=None, help="Comma-separated watchlist override")
    stream_parser.add_argument("--csv-path", default=None, help="CSV path when using csv_replay provider")
    stream_parser.add_argument("--poll-interval", type=float, default=1.0, help="Live provider poll interval")
    stream_parser.add_argument("--no-news", action="store_true", help="Disable optional Finnhub news enrichment")

    backtest_parser = subparsers.add_parser("backtest-demo", help="Run a demo-data backtest")
    backtest_parser.add_argument("--snapshots", type=int, default=120, help="Number of demo snapshots to replay")
    backtest_parser.add_argument("--max-hold", type=int, default=20, help="Max snapshots to hold a simulated trade")

    csv_parser = subparsers.add_parser("backtest-csv", help="Run a CSV OHLCV replay backtest")
    csv_parser.add_argument("path", help="CSV path with symbol,timestamp,open,high,low,close,volume")
    csv_parser.add_argument("--snapshots", type=int, default=None, help="Maximum snapshots to replay")
    csv_parser.add_argument("--max-hold", type=int, default=40, help="Max snapshots to hold a simulated trade")

    db_parser = subparsers.add_parser("db-summary", help="Print audit database table counts")
    db_parser.add_argument("--path", default="data/ztrade.sqlite3", help="SQLite database path")

    args = parser.parse_args()
    if args.command == "desktop":
        desktop_main()
    elif args.command == "stream":
        asyncio.run(_stream(args))
    elif args.command == "backtest-demo":
        asyncio.run(_backtest_demo(args.snapshots, args.max_hold))
    elif args.command == "backtest-csv":
        asyncio.run(_backtest_csv(args.path, args.snapshots, args.max_hold))
    elif args.command == "db-summary":
        _db_summary(args.path)


async def _stream(args: argparse.Namespace) -> None:
    watchlist = tuple(symbol.strip().upper() for symbol in args.symbols.split(",")) if args.symbols else None
    config = AppConfig(
        bot_mode=BotMode.AUTO_PAPER if args.auto_paper else BotMode.STAGE_ONLY,
        data_provider=DataProviderKind(args.provider),
        default_watchlist=watchlist or AppConfig().default_watchlist,
        csv_replay_path=args.csv_path,
        live_poll_interval_seconds=args.poll_interval,
        enable_finnhub_news=not args.no_news,
    )
    store = TradingStore(config.database_path)
    store.initialize()
    guardrails = GuardrailEngine(config.guardrails)
    broker = PaperBroker(config.guardrails.account_equity, store=store)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    execution = ExecutionEngine(config, broker, guardrails, store=store)
    provider = create_data_provider(config)

    seen = 0
    async for snapshot in provider.stream():
        seen += 1
        if config.record_market_events:
            store.record_market_snapshot(snapshot)
        for recommendation in recommender.evaluate(snapshot):
            fill = await execution.handle_recommendation(recommendation)
            idea = recommendation.idea
            print(
                f"{recommendation.status.value:9} {idea.strategy:26} "
                f"{idea.symbol:28} {idea.confidence:.2f} {idea.ta_summary}"
            )
            if fill:
                print(f"FILLED    {fill.order.symbol} qty={fill.quantity} price={fill.price:.2f}")
        if seen >= args.limit:
            break
    account = broker.account_state()
    print(f"Account cash=${account.cash:,.2f} equity=${account.equity:,.2f} realized=${account.realized_pnl:,.2f}")
    store.close()


async def _backtest_demo(snapshots: int, max_hold: int) -> None:
    config = AppConfig()
    await _run_backtest(config, max_snapshots=snapshots, max_hold=max_hold)


async def _backtest_csv(path: str, snapshots: int | None, max_hold: int) -> None:
    config = AppConfig(
        data_provider=DataProviderKind.CSV_REPLAY,
        csv_replay_path=path,
        replay_delay_seconds=0.0,
    )
    await _run_backtest(config, max_snapshots=snapshots, max_hold=max_hold)


async def _run_backtest(config: AppConfig, max_snapshots: int | None, max_hold: int) -> None:
    guardrails = GuardrailEngine(config.guardrails)
    broker = PaperBroker(config.guardrails.account_equity)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    execution = ExecutionEngine(config, broker, guardrails)
    backtest = BacktestEngine(
        config,
        recommender,
        execution,
        broker,
        BacktestConfig(max_snapshots=max_snapshots, max_hold_snapshots=max_hold),
    )
    result = await backtest.run(create_data_provider(config))
    report = result.report
    print("Backtest Report")
    print(f"Recommendations: {report.total_recommendations}")
    print(f"Fills:           {report.total_fills}")
    print(f"Closed trades:   {report.closed_trades}")
    print(f"Win rate:        {report.win_rate:.2f}%")
    print(f"Return:          {report.return_pct:.3f}%")
    print(f"Realized P/L:    ${report.realized_pnl:,.2f}")
    print(f"Ending equity:   ${report.ending_equity:,.2f}")
    print(f"Max drawdown:    {report.max_drawdown_pct:.3f}%")
    for trade in result.trades[:10]:
        print(
            f"{trade.exit_reason:15} {trade.strategy:26} {trade.symbol:28} "
            f"pnl=${trade.pnl:8.2f} pnl%={trade.pnl_pct:7.3f}"
        )


def _db_summary(path: str) -> None:
    database = Path(path)
    if not database.exists():
        print(f"Database not found: {database}")
        return
    tables = (
        "events",
        "recommendations",
        "orders",
        "fills",
        "paper_account_snapshots",
        "paper_positions",
    )
    with sqlite3.connect(database) as connection:
        for table in tables:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table:24} {count}")


if __name__ == "__main__":
    main()
