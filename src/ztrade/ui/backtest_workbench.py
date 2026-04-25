from __future__ import annotations

import asyncio
import threading
import time
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from ztrade.analytics.performance import TradeRecord
from ztrade.backtest.events import BacktestEvent, BacktestEventType
from ztrade.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult, relax_guardrails_for_backtest
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, DataProviderKind
from ztrade.data.factory import create_data_provider
from ztrade.data.providers import ReplayDataProvider
from ztrade.execution.engine import ExecutionEngine
from ztrade.models import Bar, MarketSnapshot
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.settings import RecommendationSettingsPolicy, TickerTradeSettings, TradingSettings
from ztrade.strategies.registry import default_strategies


@dataclass(frozen=True, slots=True)
class WorkbenchDefaults:
    provider_kind: DataProviderKind
    csv_path: str = ""
    max_snapshots: int = 120
    max_hold: int = 20


@dataclass(frozen=True, slots=True)
class WorkbenchRun:
    result: BacktestResult
    events: tuple[BacktestEvent, ...]


class BacktestWorkbenchWindow:
    def __init__(
        self,
        master: tk.Tk | tk.Toplevel,
        row: TickerTradeSettings,
        defaults: WorkbenchDefaults,
        *,
        on_complete: Callable[[TickerTradeSettings, BacktestResult], None] | None = None,
    ) -> None:
        self.master = master
        self.row = row
        self.on_complete = on_complete
        self.bars: tuple[Bar, ...] = ()
        self.result: BacktestResult | None = None
        self.events: tuple[BacktestEvent, ...] = ()
        self.is_running = False
        self.replay_running = False
        self.replay_after_id: str | None = None
        self.replay_index = 0
        self.replay_bar_count = 0
        self.replay_signals = 0
        self.replay_fills = 0
        self.replay_trades: list[TradeRecord] = []
        self.replay_equity: list[float] = []

        self.window = tk.Toplevel(master)
        self.window.title(f"zTrade Backtest Workbench - {row.normalized_symbol}")
        self.window.geometry("1240x820")
        self.window.minsize(980, 680)
        self.window.configure(bg="#eaf0f7")

        self.provider_var = tk.StringVar(value=defaults.provider_kind.value)
        self.csv_path_var = tk.StringVar(value=defaults.csv_path)
        self.max_snapshots_var = tk.StringVar(value=str(defaults.max_snapshots))
        self.max_hold_var = tk.StringVar(value=str(defaults.max_hold))
        self.duration_var = tk.StringVar(value="2 D")
        self.bar_size_var = tk.StringVar(value="5 mins")
        self.use_rth_var = tk.BooleanVar(value=True)
        self.speed_var = tk.StringVar(value="4x")
        self.status_var = tk.StringVar(value="Ready. Load history or execute a backtest.")

        self.metric_vars = {
            "bars": tk.StringVar(value="-"),
            "recs": tk.StringVar(value="-"),
            "fills": tk.StringVar(value="-"),
            "trades": tk.StringVar(value="-"),
            "win": tk.StringVar(value="-"),
            "return": tk.StringVar(value="-"),
            "buy_hold": tk.StringVar(value="-"),
            "pnl": tk.StringVar(value="-"),
            "drawdown": tk.StringVar(value="-"),
            "equity": tk.StringVar(value="-"),
        }

        self._build_ui()
        self.chart_canvas.bind("<Configure>", lambda _event: self._redraw_all())
        self.equity_canvas.bind("<Configure>", lambda _event: self._draw_equity_curve())

    def _build_ui(self) -> None:
        header = tk.Frame(self.window, bg="#102a43", padx=14, pady=10)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"{self.row.normalized_symbol} Backtest Workbench",
            bg="#102a43",
            fg="#f8fafc",
            font=("Segoe UI", 15, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"{len(self.row.strategies)} enabled strategies | paper execution model",
            bg="#102a43",
            fg="#bfdbfe",
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(18, 0))

        toolbar = tk.Frame(self.window, bg="#dbeafe", padx=10, pady=8)
        toolbar.pack(fill=tk.X)
        self._toolbar_field(toolbar, "Source")
        source = ttk.Combobox(
            toolbar,
            textvariable=self.provider_var,
            values=(DataProviderKind.DEMO.value, DataProviderKind.CSV_REPLAY.value, DataProviderKind.IBKR_HISTORICAL.value),
            state="readonly",
            width=16,
        )
        source.pack(side=tk.LEFT, padx=(4, 12))
        self._entry_field(toolbar, "Bars", self.max_snapshots_var, 8)
        self._entry_field(toolbar, "Max Hold", self.max_hold_var, 8)
        self._entry_field(toolbar, "IBKR Duration", self.duration_var, 10)
        self._combo_field(toolbar, "Bar Size", self.bar_size_var, ("1 min", "5 mins", "15 mins", "30 mins", "1 hour", "1 day"), 10)
        tk.Checkbutton(
            toolbar,
            text="RTH",
            variable=self.use_rth_var,
            bg="#dbeafe",
            activebackground="#dbeafe",
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.load_button = ttk.Button(toolbar, text="Load Chart", command=self.load_history)
        self.load_button.pack(side=tk.LEFT, padx=(0, 8))
        self.execute_button = ttk.Button(toolbar, text="Execute Backtest", command=self.execute)
        self.execute_button.pack(side=tk.LEFT, padx=(0, 8))
        self.play_button = ttk.Button(toolbar, text="Play", command=self.play_replay)
        self.play_button.pack(side=tk.LEFT, padx=(0, 4))
        self.pause_button = ttk.Button(toolbar, text="Pause", command=self.pause_replay)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 4))
        self.step_button = ttk.Button(toolbar, text="Step", command=self.step_replay)
        self.step_button.pack(side=tk.LEFT, padx=(0, 4))
        self.reset_button = ttk.Button(toolbar, text="Reset Replay", command=self.reset_replay)
        self.reset_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Combobox(toolbar, textvariable=self.speed_var, values=("1x", "2x", "4x", "8x", "16x"), state="readonly", width=5).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        ttk.Button(toolbar, text="Clear", command=self._clear_results).pack(side=tk.LEFT)

        csv_row = tk.Frame(self.window, bg="#f8fafc", padx=10, pady=6)
        csv_row.pack(fill=tk.X)
        tk.Label(csv_row, text="CSV path", bg="#f8fafc", fg="#475569").pack(side=tk.LEFT)
        tk.Entry(csv_row, textvariable=self.csv_path_var, width=100).pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        body = tk.PanedWindow(self.window, orient=tk.HORIZONTAL, bg="#cbd5e1", sashwidth=6)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 10))

        left = tk.Frame(body, bg="#f8fafc")
        right = tk.Frame(body, bg="#f8fafc", width=310)
        body.add(left, stretch="always")
        body.add(right, minsize=280)

        chart_frame = tk.LabelFrame(
            left,
            text="Underlying Price, Volume, Entries, And Exits",
            bg="#f8fafc",
            fg="#0f172a",
            padx=8,
            pady=8,
        )
        chart_frame.pack(fill=tk.BOTH, expand=True)
        self.chart_canvas = tk.Canvas(chart_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#93a4b8")
        self.chart_canvas.pack(fill=tk.BOTH, expand=True)

        equity_frame = tk.LabelFrame(
            left,
            text="Equity Curve Versus Underlying",
            bg="#f8fafc",
            fg="#0f172a",
            padx=8,
            pady=8,
        )
        equity_frame.pack(fill=tk.X, pady=(8, 0))
        self.equity_canvas = tk.Canvas(equity_frame, height=120, bg="#ffffff", highlightthickness=1, highlightbackground="#93a4b8")
        self.equity_canvas.pack(fill=tk.X)

        metrics = tk.LabelFrame(right, text="Run Metrics", bg="#f8fafc", fg="#0f172a", padx=8, pady=8)
        metrics.pack(fill=tk.X)
        metric_rows = (
            ("Bars", "bars"),
            ("Recommendations", "recs"),
            ("Fills", "fills"),
            ("Closed Trades", "trades"),
            ("Win Rate", "win"),
            ("Strategy Return", "return"),
            ("Buy/Hold Return", "buy_hold"),
            ("Realized P/L", "pnl"),
            ("Max Drawdown", "drawdown"),
            ("Ending Equity", "equity"),
        )
        for row_index, (label, key) in enumerate(metric_rows):
            tk.Label(metrics, text=label, bg="#f8fafc", fg="#475569").grid(row=row_index, column=0, sticky=tk.W, pady=2)
            tk.Label(metrics, textvariable=self.metric_vars[key], bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).grid(
                row=row_index,
                column=1,
                sticky=tk.E,
                pady=2,
                padx=(16, 0),
            )
        metrics.grid_columnconfigure(1, weight=1)

        ledger_frame = tk.LabelFrame(right, text="Trade Ledger", bg="#f8fafc", fg="#0f172a", padx=8, pady=8)
        ledger_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        ledger_columns = ("strategy", "asset", "entry", "exit", "pnl", "reason")
        self.ledger = ttk.Treeview(ledger_frame, columns=ledger_columns, show="headings", height=10)
        headings = {
            "strategy": "Strategy",
            "asset": "Asset",
            "entry": "Entry",
            "exit": "Exit",
            "pnl": "P/L",
            "reason": "Exit",
        }
        widths = {"strategy": 115, "asset": 55, "entry": 60, "exit": 60, "pnl": 70, "reason": 80}
        for column in ledger_columns:
            self.ledger.heading(column, text=headings[column])
            self.ledger.column(column, width=widths[column], anchor=tk.W)
        self.ledger.pack(fill=tk.BOTH, expand=True)
        self.ledger.bind("<<TreeviewSelect>>", self._select_trade)

        events_frame = tk.LabelFrame(right, text="Replay Events", bg="#f8fafc", fg="#0f172a", padx=8, pady=8)
        events_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        event_columns = ("index", "type", "detail")
        self.event_tree = ttk.Treeview(events_frame, columns=event_columns, show="headings", height=8)
        self.event_tree.heading("index", text="#")
        self.event_tree.heading("type", text="Event")
        self.event_tree.heading("detail", text="Detail")
        self.event_tree.column("index", width=38, anchor=tk.E)
        self.event_tree.column("type", width=92, anchor=tk.W)
        self.event_tree.column("detail", width=175, anchor=tk.W)
        self.event_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = tk.Frame(right, bg="#f8fafc")
        log_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(log_frame, textvariable=self.status_var, bg="#f8fafc", fg="#1e3a8a", wraplength=290, justify=tk.LEFT).pack(fill=tk.X)
        self._set_playback_controls_enabled(False)

    def _toolbar_field(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, bg="#dbeafe", fg="#334155").pack(side=tk.LEFT)

    def _entry_field(self, parent: tk.Widget, label: str, variable: tk.StringVar, width: int) -> None:
        self._toolbar_field(parent, label)
        tk.Entry(parent, textvariable=variable, width=width).pack(side=tk.LEFT, padx=(4, 12))

    def _combo_field(self, parent: tk.Widget, label: str, variable: tk.StringVar, values: tuple[str, ...], width: int) -> None:
        self._toolbar_field(parent, label)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width).pack(side=tk.LEFT, padx=(4, 12))

    def load_history(self) -> None:
        self._start_worker(run_backtest=False)

    def execute(self) -> None:
        self._start_worker(run_backtest=True)

    def _start_worker(self, *, run_backtest: bool) -> None:
        if self.is_running:
            self.status_var.set("A workbench job is already running.")
            return
        try:
            config = self._build_config()
            max_snapshots = max(1, _parse_int(self.max_snapshots_var.get(), 120))
            max_hold = self._max_hold()
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self.is_running = True
        self._set_buttons_enabled(False)
        self.status_var.set("Loading historical bars..." if not run_backtest else "Loading bars and preparing backtest...")
        thread = threading.Thread(target=self._run_worker, args=(run_backtest, config, max_snapshots, max_hold), daemon=True)
        thread.start()

    def _run_worker(self, run_backtest: bool, config: AppConfig, max_snapshots: int, max_hold: int) -> None:
        started = time.perf_counter()
        try:
            snapshots = asyncio.run(_collect_snapshots(config, self.row.normalized_symbol, max_snapshots))
            if not snapshots:
                raise ValueError(f"No snapshots returned for {self.row.normalized_symbol}.")
            bars = tuple(_bar_for_snapshot(snapshot) for snapshot in snapshots)
            run = None
            if run_backtest:
                run = asyncio.run(_run_backtest_with_events_from_snapshots(config, self.row, snapshots, max_hold))
            elapsed = time.perf_counter() - started
            self.window.after(0, lambda: self._show_worker_result(bars, run, elapsed))
        except Exception as exc:
            message = str(exc)
            self.window.after(0, lambda: self._show_worker_error(message))

    def _build_config(self) -> AppConfig:
        try:
            provider_kind = DataProviderKind(self.provider_var.get())
        except ValueError as exc:
            raise ValueError("Unsupported backtest source.") from exc
        csv_path = self.csv_path_var.get().strip()
        if provider_kind == DataProviderKind.CSV_REPLAY and not csv_path:
            raise ValueError("CSV replay requires a CSV path.")
        config = AppConfig(
            data_provider=provider_kind,
            default_watchlist=(self.row.normalized_symbol,),
            csv_replay_path=csv_path or None,
            replay_delay_seconds=0.0,
            record_market_events=False,
        )
        config.ibkr_historical_duration = self.duration_var.get().strip() or "2 D"
        config.ibkr_historical_bar_size = self.bar_size_var.get().strip() or "5 mins"
        config.ibkr_use_rth = self.use_rth_var.get()
        relax_guardrails_for_backtest(config)
        return config

    def _max_hold(self) -> int:
        return max(1, _parse_int(self.max_hold_var.get(), 20))

    def _show_worker_result(self, bars: tuple[Bar, ...], run: WorkbenchRun | None, elapsed: float) -> None:
        self.bars = bars
        self.result = run.result if run else None
        self.events = run.events if run else ()
        self._populate_metrics()
        self._prepare_replay()
        self._redraw_all()
        self._set_buttons_enabled(True)
        self._set_playback_controls_enabled(bool(self.events))
        self.is_running = False
        if run is None:
            self.status_var.set(f"Loaded {len(bars)} bars in {elapsed:.1f}s.")
            return
        self.status_var.set(
            f"Backtest generated {len(self.events)} replay events in {elapsed:.1f}s. Press Play, Step, or Reset Replay."
        )
        if self.on_complete is not None:
            self.on_complete(self.row, run.result)
        self.play_replay()

    def _show_worker_error(self, message: str) -> None:
        self._set_buttons_enabled(True)
        self.is_running = False
        self.status_var.set(message)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.load_button.configure(state=state)
        self.execute_button.configure(state=state)

    def _set_playback_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.play_button.configure(state=state)
        self.pause_button.configure(state=state)
        self.step_button.configure(state=state)
        self.reset_button.configure(state=state)

    def _prepare_replay(self) -> None:
        self.pause_replay()
        self.replay_index = 0
        self.replay_bar_count = 0
        self.replay_signals = 0
        self.replay_fills = 0
        self.replay_trades = []
        self.replay_equity = []
        self._clear_ledger()
        self._clear_event_log()
        if not self.events:
            self._populate_ledger()
        self._refresh_replay_metrics()

    def play_replay(self) -> None:
        if not self.events:
            self.status_var.set("Execute a backtest before playing replay events.")
            return
        if self.replay_index >= len(self.events):
            self.status_var.set("Replay is already complete. Use Reset Replay to watch it again.")
            return
        self.replay_running = True
        self._schedule_replay()

    def pause_replay(self) -> None:
        self.replay_running = False
        if self.replay_after_id is not None:
            self.window.after_cancel(self.replay_after_id)
            self.replay_after_id = None

    def step_replay(self) -> None:
        if not self.events:
            return
        self.pause_replay()
        self._advance_replay()

    def reset_replay(self) -> None:
        if not self.events:
            return
        self._prepare_replay()
        self._redraw_all()
        self.status_var.set("Replay reset. Press Play or Step.")

    def _schedule_replay(self) -> None:
        if not self.replay_running:
            return
        self._advance_replay()
        if self.replay_running:
            self.replay_after_id = self.window.after(self._replay_delay_ms(), self._schedule_replay)

    def _advance_replay(self) -> None:
        if self.replay_index >= len(self.events):
            self.replay_running = False
            self.replay_after_id = None
            self._populate_metrics()
            self.status_var.set("Replay complete. Select a ledger row to highlight a trade.")
            return
        event = self.events[self.replay_index]
        self.replay_index += 1
        self._apply_replay_event(event)
        self._refresh_replay_metrics()
        self._redraw_all()
        if self.replay_index >= len(self.events):
            self.replay_running = False
            self.replay_after_id = None

    def _apply_replay_event(self, event: BacktestEvent) -> None:
        if event.event_type == BacktestEventType.BAR:
            self.replay_bar_count = max(self.replay_bar_count, event.snapshot_index)
        elif event.event_type in {BacktestEventType.SIGNAL, BacktestEventType.FILTERED_SIGNAL}:
            if event.event_type == BacktestEventType.SIGNAL:
                self.replay_signals += 1
        elif event.event_type in {BacktestEventType.ENTRY_FILL, BacktestEventType.EXIT_FILL}:
            self.replay_fills += 1
        elif event.event_type == BacktestEventType.TRADE_CLOSED and event.trade is not None:
            self.replay_trades.append(event.trade)
            self._insert_trade(event.trade, len(self.replay_trades) - 1)
        if event.equity is not None and event.event_type in {BacktestEventType.BAR, BacktestEventType.EQUITY, BacktestEventType.COMPLETE}:
            self.replay_equity.append(event.equity)
        self._log_event(event)
        if event.message:
            self.status_var.set(event.message)

    def _replay_delay_ms(self) -> int:
        speed = self.speed_var.get().strip().lower()
        multiplier = {
            "1x": 1,
            "2x": 2,
            "4x": 4,
            "8x": 8,
            "16x": 16,
        }.get(speed, 4)
        return max(40, int(420 / multiplier))

    def _refresh_replay_metrics(self) -> None:
        if not self.events:
            return
        self.metric_vars["bars"].set(f"{min(self.replay_bar_count, len(self.bars))}/{len(self.bars)}")
        self.metric_vars["recs"].set(f"{self.replay_signals}/{self.result.report.total_recommendations if self.result else 0}")
        self.metric_vars["fills"].set(f"{self.replay_fills}/{self.result.report.total_fills if self.result else 0}")
        self.metric_vars["trades"].set(f"{len(self.replay_trades)}/{self.result.report.closed_trades if self.result else 0}")
        self.metric_vars["buy_hold"].set(_pct(self._buy_hold_return_pct(self._visible_bars())))
        if self.replay_equity:
            self.metric_vars["equity"].set(f"${self.replay_equity[-1]:,.2f}")

    def _clear_event_log(self) -> None:
        for item_id in self.event_tree.get_children(""):
            self.event_tree.delete(item_id)

    def _log_event(self, event: BacktestEvent) -> None:
        detail = event.message or event.event_type.value
        self.event_tree.insert(
            "",
            tk.END,
            values=(event.snapshot_index, event.event_type.value, detail[:120]),
        )
        children = self.event_tree.get_children("")
        if len(children) > 500:
            self.event_tree.delete(children[0])
        latest = self.event_tree.get_children("")[-1]
        self.event_tree.see(latest)

    def _clear_results(self) -> None:
        self.pause_replay()
        self.bars = ()
        self.result = None
        self.events = ()
        self.replay_trades = []
        self.replay_equity = []
        for variable in self.metric_vars.values():
            variable.set("-")
        self._clear_ledger()
        self._clear_event_log()
        self.chart_canvas.delete("all")
        self.equity_canvas.delete("all")
        self._set_playback_controls_enabled(False)
        self.status_var.set("Cleared. Load history or execute a backtest.")

    def _populate_metrics(self) -> None:
        self.metric_vars["bars"].set(str(len(self.bars)) if self.bars else "-")
        self.metric_vars["buy_hold"].set(_pct(self._buy_hold_return_pct()))
        if self.result is None:
            for key in ("recs", "fills", "trades", "win", "return", "pnl", "drawdown", "equity"):
                self.metric_vars[key].set("-")
            return
        report = self.result.report
        self.metric_vars["recs"].set(str(report.total_recommendations))
        self.metric_vars["fills"].set(str(report.total_fills))
        self.metric_vars["trades"].set(str(report.closed_trades))
        self.metric_vars["win"].set(_pct(report.win_rate))
        self.metric_vars["return"].set(_pct(report.return_pct))
        self.metric_vars["pnl"].set(f"${report.realized_pnl:,.2f}")
        self.metric_vars["drawdown"].set(_pct(report.max_drawdown_pct))
        self.metric_vars["equity"].set(f"${report.ending_equity:,.2f}")

    def _populate_ledger(self) -> None:
        self._clear_ledger()
        if self.result is None:
            return
        for index, trade in enumerate(self.result.trades):
            self._insert_trade(trade, index)

    def _clear_ledger(self) -> None:
        for item_id in self.ledger.get_children(""):
            self.ledger.delete(item_id)

    def _insert_trade(self, trade: TradeRecord, index: int) -> None:
        item_id = str(index)
        if self.ledger.exists(item_id):
            return
        self.ledger.insert(
            "",
            tk.END,
            iid=item_id,
            values=(
                trade.strategy,
                trade.asset_class,
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}",
                f"{trade.pnl:.2f}",
                trade.exit_reason,
            ),
        )
        self.ledger.see(item_id)

    def _redraw_all(self) -> None:
        self._draw_price_chart()
        self._draw_equity_curve()

    def _draw_price_chart(self, highlight: TradeRecord | None = None) -> None:
        canvas = self.chart_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 720)
        height = max(canvas.winfo_height(), 360)
        bars = self._visible_bars()
        if not bars:
            canvas.create_text(width / 2, height / 2, text="Load chart history to begin.", fill="#64748b", font=("Segoe UI", 13, "bold"))
            return
        left, right, top, volume_height, bottom = 56, 24, 20, 74, 26
        price_bottom = height - volume_height - bottom
        chart_width = width - left - right
        price_height = price_bottom - top
        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]
        min_price = min(lows)
        max_price = max(highs)
        if max_price <= min_price:
            max_price += 1
            min_price -= 1
        max_volume = max((bar.volume for bar in self.bars), default=1)

        canvas.create_rectangle(0, 0, width, height, fill="#ffffff", outline="")
        for step in range(5):
            y = top + (price_height * step / 4)
            price = max_price - ((max_price - min_price) * step / 4)
            canvas.create_line(left, y, width - right, y, fill="#e2e8f0")
            canvas.create_text(left - 8, y, text=f"{price:.2f}", fill="#64748b", anchor=tk.E, font=("Segoe UI", 8))
        canvas.create_line(left, price_bottom, width - right, price_bottom, fill="#94a3b8")

        n = len(bars)
        span = chart_width / max(1, n - 1)
        candle_width = max(2, min(9, span * 0.55))
        for index, bar in enumerate(bars):
            x = left + index * span if n > 1 else left + chart_width / 2
            high_y = _scale(bar.high, min_price, max_price, price_bottom, top)
            low_y = _scale(bar.low, min_price, max_price, price_bottom, top)
            open_y = _scale(bar.open, min_price, max_price, price_bottom, top)
            close_y = _scale(bar.close, min_price, max_price, price_bottom, top)
            color = "#16a34a" if bar.close >= bar.open else "#dc2626"
            canvas.create_line(x, high_y, x, low_y, fill=color, width=1)
            canvas.create_rectangle(
                x - candle_width / 2,
                min(open_y, close_y),
                x + candle_width / 2,
                max(open_y, close_y) + 1,
                fill=color,
                outline=color,
            )
            volume_top = price_bottom + 16
            volume_bottom = height - bottom
            volume_y = volume_bottom - ((bar.volume / max_volume) * (volume_bottom - volume_top))
            canvas.create_rectangle(x - candle_width / 2, volume_y, x + candle_width / 2, volume_bottom, fill="#93c5fd", outline="")

        if self.result is not None:
            trades = tuple(self.replay_trades) if self.events else self.result.trades
            for trade in trades:
                self._draw_trade_marker(canvas, trade, bars, left, span, min_price, max_price, price_bottom, top, trade == highlight)

        first = bars[0].timestamp.strftime("%m-%d %H:%M")
        last = bars[-1].timestamp.strftime("%m-%d %H:%M")
        canvas.create_text(left, height - 8, text=first, fill="#64748b", anchor=tk.W, font=("Segoe UI", 8))
        canvas.create_text(width - right, height - 8, text=last, fill="#64748b", anchor=tk.E, font=("Segoe UI", 8))
        canvas.create_text(width - right, top, text=f"{self.row.normalized_symbol} {len(bars)}/{len(self.bars)} bars", fill="#0f172a", anchor=tk.NE, font=("Segoe UI", 9, "bold"))

    def _draw_trade_marker(
        self,
        canvas: tk.Canvas,
        trade: TradeRecord,
        bars: tuple[Bar, ...],
        left: int,
        span: float,
        min_price: float,
        max_price: float,
        price_bottom: float,
        top: int,
        highlight: bool,
    ) -> None:
        entry_index = _clamped_index(trade.entry_index, len(bars))
        exit_index = _clamped_index(trade.exit_index, len(bars))
        if entry_index is None or exit_index is None:
            return
        entry_bar_price = bars[entry_index].close if trade.asset_class == "option" else trade.entry_price
        exit_bar_price = bars[exit_index].close if trade.asset_class == "option" else trade.exit_price
        entry_x = left + entry_index * span
        exit_x = left + exit_index * span
        entry_y = _scale(entry_bar_price, min_price, max_price, price_bottom, top)
        exit_y = _scale(exit_bar_price, min_price, max_price, price_bottom, top)
        line_color = "#1d4ed8" if trade.pnl >= 0 else "#991b1b"
        width = 3 if highlight else 1
        canvas.create_line(entry_x, entry_y, exit_x, exit_y, fill=line_color, width=width, dash=() if highlight else (4, 3))
        canvas.create_polygon(entry_x, entry_y - 10, entry_x - 7, entry_y + 5, entry_x + 7, entry_y + 5, fill="#2563eb", outline="#1e3a8a")
        canvas.create_polygon(exit_x, exit_y + 10, exit_x - 7, exit_y - 5, exit_x + 7, exit_y - 5, fill="#f97316", outline="#9a3412")
        if highlight:
            text = f"{trade.strategy} | {trade.pnl:+.2f}"
            canvas.create_rectangle(entry_x + 8, entry_y - 24, entry_x + 190, entry_y - 3, fill="#eff6ff", outline="#2563eb")
            canvas.create_text(entry_x + 12, entry_y - 14, text=text[:34], fill="#1e3a8a", anchor=tk.W, font=("Segoe UI", 8, "bold"))

    def _draw_equity_curve(self) -> None:
        canvas = self.equity_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 720)
        height = max(canvas.winfo_height(), 120)
        bars = self._visible_bars()
        if not bars:
            canvas.create_text(width / 2, height / 2, text="Equity benchmark appears after loading bars.", fill="#64748b")
            return
        equity = tuple(self.replay_equity) if self.events and self.replay_equity else (self.result.equity_curve if self.result else ())
        if not equity:
            equity = tuple(100.0 + self._buy_hold_return_pct(bars) * (index / max(1, len(bars) - 1)) for index in range(len(bars)))
        starting_equity = equity[0] if equity else 100.0
        first_close = bars[0].close
        benchmark = tuple(starting_equity * (bar.close / first_close) for bar in bars if first_close)
        values = list(equity) + list(benchmark)
        if not values:
            return
        left, right, top, bottom = 54, 20, 14, 24
        min_value = min(values)
        max_value = max(values)
        if max_value <= min_value:
            max_value += 1
            min_value -= 1
        canvas.create_rectangle(0, 0, width, height, fill="#ffffff", outline="")
        for step in range(3):
            y = top + ((height - top - bottom) * step / 2)
            value = max_value - ((max_value - min_value) * step / 2)
            canvas.create_line(left, y, width - right, y, fill="#e2e8f0")
            canvas.create_text(left - 8, y, text=f"{value:,.0f}", fill="#64748b", anchor=tk.E, font=("Segoe UI", 8))
        self._plot_series(canvas, equity, "#2563eb", left, right, top, bottom, min_value, max_value, width, height)
        self._plot_series(canvas, benchmark, "#64748b", left, right, top, bottom, min_value, max_value, width, height)
        canvas.create_text(width - right, top, text="strategy", fill="#2563eb", anchor=tk.NE, font=("Segoe UI", 8, "bold"))
        canvas.create_text(width - right, top + 16, text="underlying", fill="#64748b", anchor=tk.NE, font=("Segoe UI", 8, "bold"))

    def _plot_series(
        self,
        canvas: tk.Canvas,
        values: tuple[float, ...],
        color: str,
        left: int,
        right: int,
        top: int,
        bottom: int,
        min_value: float,
        max_value: float,
        width: int,
        height: int,
    ) -> None:
        if len(values) < 2:
            return
        x_span = (width - left - right) / max(1, len(values) - 1)
        points: list[float] = []
        for index, value in enumerate(values):
            x = left + index * x_span
            y = _scale(value, min_value, max_value, height - bottom, top)
            points.extend((x, y))
        canvas.create_line(*points, fill=color, width=2)

    def _select_trade(self, _event: object) -> None:
        if self.result is None:
            return
        selected = self.ledger.selection()
        if not selected:
            return
        source_trades = tuple(self.replay_trades) if self.events else self.result.trades
        trade_index = int(selected[0])
        if trade_index >= len(source_trades):
            return
        trade = source_trades[trade_index]
        self._draw_price_chart(highlight=trade)
        self.status_var.set(
            f"{trade.strategy}: {trade.asset_class} {trade.quantity} from {trade.entry_price:.2f} to {trade.exit_price:.2f}; "
            f"P/L {trade.pnl:+.2f} ({trade.exit_reason})."
        )

    def _visible_bars(self) -> tuple[Bar, ...]:
        if not self.events:
            return self.bars
        if not self.bars:
            return ()
        visible_count = max(1, min(len(self.bars), self.replay_bar_count or 1))
        return self.bars[:visible_count]

    def _buy_hold_return_pct(self, bars: tuple[Bar, ...] | None = None) -> float:
        bars = self.bars if bars is None else bars
        if len(bars) < 2 or bars[0].close <= 0:
            return 0.0
        return ((bars[-1].close - bars[0].close) / bars[0].close) * 100


async def _collect_snapshots(config: AppConfig, symbol: str, max_snapshots: int) -> tuple[MarketSnapshot, ...]:
    provider = create_data_provider(config)
    snapshots: list[MarketSnapshot] = []
    async for snapshot in provider.stream():
        underlying = snapshot.option_contract.underlying if snapshot.option_contract else snapshot.symbol
        if underlying == symbol:
            snapshots.append(snapshot)
        if len(snapshots) >= max_snapshots:
            break
    return tuple(snapshots)


async def _run_backtest_from_snapshots(
    config: AppConfig,
    row: TickerTradeSettings,
    snapshots: tuple[MarketSnapshot, ...],
    max_hold: int,
) -> BacktestResult:
    return (await _run_backtest_with_events_from_snapshots(config, row, snapshots, max_hold)).result


async def _run_backtest_with_events_from_snapshots(
    config: AppConfig,
    row: TickerTradeSettings,
    snapshots: tuple[MarketSnapshot, ...],
    max_hold: int,
) -> WorkbenchRun:
    guardrails = GuardrailEngine(config.guardrails)
    broker = PaperBroker(config.guardrails.account_equity)
    recommender = RecommendationEngine(default_strategies(), guardrails)
    execution = ExecutionEngine(config, broker, guardrails)
    policy = RecommendationSettingsPolicy(TradingSettings(tickers=(row,)), config.guardrails)
    backtest = BacktestEngine(
        config,
        recommender,
        execution,
        broker,
        BacktestConfig(max_snapshots=len(snapshots), max_hold_snapshots=max_hold),
        recommendation_filter=policy.apply,
    )
    events: list[BacktestEvent] = []
    result = await backtest.run(ReplayDataProvider(list(snapshots), delay_seconds=0.0), event_sink=events.append)
    return WorkbenchRun(result=result, events=tuple(events))


def _bar_for_snapshot(snapshot: MarketSnapshot) -> Bar:
    if snapshot.recent_bars:
        return snapshot.recent_bars[-1]
    last = snapshot.quote.last
    return Bar(
        symbol=snapshot.symbol,
        open=last,
        high=max(last, snapshot.quote.ask),
        low=min(last, snapshot.quote.bid),
        close=last,
        volume=snapshot.quote.volume,
        timestamp=snapshot.quote.timestamp,
    )


def _scale(value: float, min_value: float, max_value: float, lower: float, upper: float) -> float:
    if max_value <= min_value:
        return (upper + lower) / 2
    pct = (value - min_value) / (max_value - min_value)
    return lower - pct * (lower - upper)


def _clamped_index(index: int | None, length: int) -> int | None:
    if index is None or length <= 0:
        return None
    return max(0, min(length - 1, index - 1))


def _pct(value: float) -> str:
    return f"{value:.3f}%"


def _parse_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except ValueError:
        return default
