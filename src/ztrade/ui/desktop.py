from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from queue import Queue
from tkinter import ttk

from ztrade import __version__
from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, BotMode
from ztrade.data.factory import create_data_provider
from ztrade.env import load_env_file
from ztrade.execution.engine import ExecutionEngine
from ztrade.models import Fill, Recommendation, RecommendationStatus
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.settings import (
    STRATEGY_DESCRIPTIONS,
    STRATEGY_LABELS,
    TRANSACTION_GROUPS,
    RecommendationSettingsPolicy,
    SettingsStore,
    StrategySettings,
    TickerTradeSettings,
    TradingSettings,
)
from ztrade.storage.sqlite import TradingStore
from ztrade.strategies.registry import default_strategies


class SettingsRowWidgets:
    def __init__(self, row_id: int, settings: TickerTradeSettings, expanded: bool = False) -> None:
        self.row_id = row_id
        self.expanded = tk.BooleanVar(value=expanded)
        self.symbol = tk.StringVar(value=settings.normalized_symbol)
        self.enabled = tk.BooleanVar(value=settings.enabled)
        self.trade_shares = tk.BooleanVar(value=settings.trade_shares)
        self.trade_simple = tk.BooleanVar(value=settings.trade_simple)
        self.trade_complex = tk.BooleanVar(value=settings.trade_complex)
        self.transaction_vars = {
            item.key: tk.BooleanVar(value=item.key in settings.allowed_transactions)
            for items in TRANSACTION_GROUPS.values()
            for item in items
        }
        self.strategy_vars = {
            strategy: tk.BooleanVar(value=settings.setting_for_strategy(strategy).enabled)
            for strategy in STRATEGY_LABELS
        }
        self.strategy_min_confidence = {
            strategy: tk.StringVar(value=f"{settings.setting_for_strategy(strategy).min_confidence:.2f}")
            for strategy in STRATEGY_LABELS
        }
        self.strategy_position_pct = {
            strategy: tk.StringVar(value=f"{settings.setting_for_strategy(strategy).max_position_fraction * 100:.1f}")
            for strategy in STRATEGY_LABELS
        }
        self.strategy_max_trades = {
            strategy: tk.StringVar(value=str(settings.setting_for_strategy(strategy).max_trades_per_day))
            for strategy in STRATEGY_LABELS
        }
        self.max_position_pct = tk.StringVar(value=f"{settings.max_position_fraction * 100:.1f}")
        self.max_trades_per_day = tk.StringVar(value=str(settings.max_trades_per_day))
        self.max_option_contracts = tk.StringVar(value=str(settings.max_option_contracts))
        self.min_confidence = tk.StringVar(value=f"{settings.min_confidence:.2f}")
        self.summary = tk.StringVar()
        self.details_frame: tk.Frame | None = None
        self.toggle_button: tk.Button | None = None

    def to_settings(self) -> TickerTradeSettings:
        symbol = self.symbol.get().strip().upper()
        strategies = tuple(strategy for strategy, value in self.strategy_vars.items() if value.get())
        allowed_transactions = tuple(
            transaction for transaction, value in self.transaction_vars.items() if value.get()
        )
        share_keys = {item.key for item in TRANSACTION_GROUPS["Share Trades"]}
        simple_keys = {item.key for item in TRANSACTION_GROUPS["Simple Options"]}
        complex_keys = {item.key for item in TRANSACTION_GROUPS["Complex Options"]}
        strategy_settings = {
            strategy: StrategySettings(
                enabled=self.strategy_vars[strategy].get(),
                min_confidence=min(1.0, max(0.0, _parse_float(self.strategy_min_confidence[strategy].get(), 0.55))),
                max_position_fraction=max(0.0, _parse_float(self.strategy_position_pct[strategy].get(), 10.0) / 100),
                max_trades_per_day=max(0, _parse_int(self.strategy_max_trades[strategy].get(), 3)),
            )
            for strategy in STRATEGY_LABELS
        }
        return TickerTradeSettings(
            symbol=symbol,
            enabled=self.enabled.get(),
            trade_shares=bool(share_keys.intersection(allowed_transactions)),
            trade_simple=bool(simple_keys.intersection(allowed_transactions)),
            trade_complex=bool(complex_keys.intersection(allowed_transactions)),
            allowed_transactions=allowed_transactions,
            strategies=strategies,
            strategy_settings=strategy_settings,
            max_position_fraction=max(0.0, _parse_float(self.max_position_pct.get(), 10.0) / 100),
            max_trades_per_day=max(0, _parse_int(self.max_trades_per_day.get(), 3)),
            max_option_contracts=max(0, _parse_int(self.max_option_contracts.get(), 4)),
            min_confidence=min(1.0, max(0.0, _parse_float(self.min_confidence.get(), 0.55))),
        )


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event: object) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify=tk.LEFT,
            background="#fff7d6",
            foreground="#1f2937",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=360,
        )
        label.pack()

    def _hide(self, _event: object) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class DesktopApp:
    def __init__(self) -> None:
        load_env_file()
        self.config = AppConfig(bot_mode=BotMode.STAGE_ONLY)
        self.settings_store = SettingsStore()
        self.has_saved_settings = self.settings_store.path.exists()
        self.trading_settings = self.settings_store.load(self.config.default_watchlist)
        self._apply_settings_to_config()
        self.store = TradingStore(self.config.database_path)
        self.store.initialize()
        self.guardrails = GuardrailEngine(self.config.guardrails)
        self.broker = PaperBroker(self.config.guardrails.account_equity, store=self.store)
        self.execution = ExecutionEngine(self.config, self.broker, self.guardrails, store=self.store)
        self.recommender = RecommendationEngine(default_strategies(), self.guardrails)
        self.settings_policy = RecommendationSettingsPolicy(self.trading_settings, self.config.guardrails)
        self.queue: Queue[Recommendation | Fill] = Queue()
        self.recommendations: dict[str, Recommendation] = {}
        self.sort_reverse: dict[str, bool] = {}
        self.settings_rows: list[SettingsRowWidgets] = []
        self._settings_row_id = 0
        self.feed_paused = False

        self.root = tk.Tk()
        self.root.title(f"zTrade v{__version__} Collapsible Settings Build - Paper Trading Workstation")
        self.root.geometry("1280x760")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.mode_var = tk.StringVar(value=self.config.bot_mode.value)
        self.status_var = tk.StringVar(value=self._account_message())
        self.account_var = tk.StringVar(value=self._account_message())
        self._build_ui()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_feed_loop, args=(self._stop_event,), daemon=True)
        self._thread.start()
        self.root.after(250, self._drain_queue)

    def _build_ui(self) -> None:
        palette = {
            "bg": "#edf2f7",
            "panel": "#f8fafc",
            "panel_alt": "#eef6ff",
            "line": "#9fb7d4",
            "accent": "#1f6feb",
            "text": "#0f172a",
            "muted": "#475569",
            "danger": "#9a1b1b",
        }
        self.palette = palette
        self.root.configure(bg=palette["bg"])
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 9), background=palette["bg"], foreground=palette["text"])
        style.configure("TFrame", background=palette["bg"])
        style.configure("Panel.TFrame", background=palette["panel"])
        style.configure("Toolbar.TFrame", background="#dceafe")
        style.configure("TNotebook", background=palette["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), background="#dbeafe")
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")])
        style.configure("Accent.TButton", background=palette["accent"], foreground="#ffffff")
        style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Subtle.TLabel", foreground=palette["muted"])
        style.configure("Danger.TLabel", foreground=palette["danger"])

        header = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"zTrade v{__version__} Collapsible Settings Build", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            header,
            text=(
                f"Provider: {self.config.data_provider.value} | "
                f"DB: {self.config.database_path} | "
                "Live trading disabled"
            ),
            style="Subtle.TLabel",
        ).pack(side=tk.LEFT, padx=(18, 0))
        ttk.Label(header, text="PAPER MODE", style="Danger.TLabel").pack(side=tk.RIGHT)

        top = ttk.Frame(self.root, padding=10, style="Toolbar.TFrame")
        top.pack(fill=tk.X)

        ttk.Label(top, text="Bot Mode").pack(side=tk.LEFT)
        mode = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=[mode.value for mode in BotMode],
            state="readonly",
            width=22,
        )
        mode.pack(side=tk.LEFT, padx=(8, 18))
        mode.bind("<<ComboboxSelected>>", self._change_mode)

        self.pause_button = ttk.Button(top, text="Pause Feed", command=self._toggle_feed)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 18))
        self.open_settings_button = ttk.Button(top, text="Open Settings", command=self._open_settings_tab)
        self.open_settings_button.pack(side=tk.LEFT, padx=(0, 18))

        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        recommendations_tab = ttk.Frame(self.notebook)
        account_tab = ttk.Frame(self.notebook)
        audit_tab = ttk.Frame(self.notebook)
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(recommendations_tab, text="Recommendations + Trade Review")
        self.notebook.add(account_tab, text="Paper Account + Positions")
        self.notebook.add(audit_tab, text="SQLite Audit Log")
        self.notebook.add(settings_tab, text="Settings")

        columns = (
            "status",
            "symbol",
            "asset",
            "side",
            "price",
            "confidence",
            "strategy",
            "stop",
            "target",
            "provider",
            "ta",
        )
        self.tree = ttk.Treeview(recommendations_tab, columns=columns, show="headings", height=18)
        for column in columns:
            self.tree.heading(
                column,
                text=column.title(),
                command=lambda selected_column=column: self._sort_by_column(selected_column),
            )
        self.tree.column("status", width=90)
        self.tree.column("symbol", width=160)
        self.tree.column("asset", width=70)
        self.tree.column("side", width=70)
        self.tree.column("price", width=90)
        self.tree.column("confidence", width=100)
        self.tree.column("strategy", width=150)
        self.tree.column("stop", width=80)
        self.tree.column("target", width=80)
        self.tree.column("provider", width=85)
        self.tree.column("ta", width=420)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_details)

        self.details = tk.Text(recommendations_tab, height=7, wrap=tk.WORD)
        self.details.pack(fill=tk.X, pady=(8, 0))
        self.details.insert(
            "1.0",
            f"zTrade v{__version__} Collapsible Settings Build loaded. Select a recommendation to inspect thesis, guardrails, and trade plan.",
        )
        self.details.configure(state=tk.DISABLED)

        account_top = ttk.Frame(account_tab, padding=10)
        account_top.pack(fill=tk.X)
        ttk.Label(account_top, textvariable=self.account_var).pack(side=tk.LEFT)
        ttk.Button(account_top, text="Refresh Account", command=self._refresh_account).pack(side=tk.RIGHT)

        position_columns = ("symbol", "asset", "quantity", "avg_price", "cost_basis", "realized_pnl")
        self.positions_tree = ttk.Treeview(account_tab, columns=position_columns, show="headings", height=12)
        for column in position_columns:
            self.positions_tree.heading(column, text=column.title())
        self.positions_tree.column("symbol", width=180)
        self.positions_tree.column("asset", width=80)
        self.positions_tree.column("quantity", width=90)
        self.positions_tree.column("avg_price", width=100)
        self.positions_tree.column("cost_basis", width=120)
        self.positions_tree.column("realized_pnl", width=120)
        self.positions_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        audit_top = ttk.Frame(audit_tab, padding=10)
        audit_top.pack(fill=tk.X)
        ttk.Button(audit_top, text="Refresh Audit", command=self._refresh_audit).pack(side=tk.RIGHT)

        audit_columns = ("occurred_at", "event_type", "symbol")
        self.audit_tree = ttk.Treeview(audit_tab, columns=audit_columns, show="headings", height=16)
        for column in audit_columns:
            self.audit_tree.heading(column, text=column.title())
        self.audit_tree.column("occurred_at", width=260)
        self.audit_tree.column("event_type", width=180)
        self.audit_tree.column("symbol", width=180)
        self.audit_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._build_settings_tab(settings_tab)
        if not self.has_saved_settings:
            self.notebook.select(settings_tab)
            self.status_var.set("Collapsible Settings Build loaded. Configure tickers, then click Save + Apply.")

        actions = ttk.Frame(self.root, padding=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Approve Selected", command=self._approve_selected).pack(side=tk.LEFT)
        ttk.Button(actions, text="Reject Selected", command=self._reject_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Kill Switch", command=self._kill_switch).pack(side=tk.LEFT, padx=8)

    def run(self) -> None:
        self.root.mainloop()

    def _change_mode(self, _event: object) -> None:
        self.config.bot_mode = BotMode(self.mode_var.get())
        self.status_var.set(f"Mode changed to {self.config.bot_mode.value}.")

    def _run_feed_loop(self, stop_event: threading.Event) -> None:
        asyncio.run(self._consume_feed(stop_event))

    async def _consume_feed(self, stop_event: threading.Event) -> None:
        if not self.config.default_watchlist:
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
            return
        provider = create_data_provider(self.config)
        async for snapshot in provider.stream():
            if stop_event.is_set():
                return
            if self.feed_paused:
                continue
            if self.config.record_market_events:
                self.store.record_market_snapshot(snapshot)
            for recommendation in self.recommender.evaluate(snapshot):
                recommendation = self.settings_policy.apply(recommendation)
                if recommendation is None:
                    continue
                fill = await self.execution.handle_recommendation(recommendation)
                if fill:
                    self.queue.put(fill)
                self.queue.put(recommendation)

    def _drain_queue(self) -> None:
        while not self.queue.empty():
            recommendation = self.queue.get_nowait()
            if isinstance(recommendation, Fill):
                self.status_var.set(f"{self._fill_message(recommendation)} {self._account_message()}")
                continue
            self.recommendations[recommendation.id] = recommendation
            idea = recommendation.idea
            self.tree.insert(
                "",
                0,
                iid=recommendation.id,
                values=(
                    recommendation.status.value,
                    idea.symbol,
                    idea.asset_class.value,
                    idea.side.value,
                    f"{idea.limit_price:.2f}",
                    f"{idea.confidence:.2f}",
                    idea.strategy,
                    _format_optional_price(idea.stop_price),
                    _format_optional_price(idea.target_price),
                    idea.provider,
                    idea.ta_summary,
                ),
            )
            self._refresh_account()
        self.root.after(250, self._drain_queue)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, padding=10, style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Add Ticker Row", command=self._add_settings_row, style="Accent.TButton").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Save + Apply", command=self._save_settings, style="Accent.TButton").pack(side=tk.LEFT, padx=8)
        ttk.Button(toolbar, text="Reset Defaults", command=self._reset_settings_defaults).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Expand All", command=self._expand_all_settings_rows).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Collapse All", command=self._collapse_all_settings_rows).pack(side=tk.LEFT, padx=(8, 0))
        self.settings_status_var = tk.StringVar(value=f"{len(self.trading_settings.tickers)} ticker rows loaded")
        ttk.Label(
            toolbar,
            text="Settings control which symbols and strategies feed the recommendations page.",
            style="Subtle.TLabel",
        ).pack(side=tk.LEFT, padx=(18, 0))
        ttk.Label(toolbar, textvariable=self.settings_status_var, style="Subtle.TLabel").pack(side=tk.RIGHT)

        self.settings_canvas = tk.Canvas(parent, highlightthickness=0, background=self.palette["bg"])
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.settings_canvas.yview)
        self.settings_frame = ttk.Frame(self.settings_canvas, padding=(10, 10, 10, 10))
        self.settings_frame.bind(
            "<Configure>",
            lambda _event: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all")),
        )
        self.settings_window = self.settings_canvas.create_window((0, 0), window=self.settings_frame, anchor="nw")
        self.settings_canvas.bind(
            "<Configure>",
            lambda event: self.settings_canvas.itemconfigure(self.settings_window, width=event.width),
        )
        self.settings_canvas.configure(yscrollcommand=scrollbar.set)
        self.settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._render_settings_rows(self.trading_settings)

    def _render_settings_rows(self, settings: TradingSettings) -> None:
        for child in self.settings_frame.winfo_children():
            child.destroy()
        self.settings_rows = []
        for settings_row in settings.tickers:
            self._add_settings_row(settings_row)
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"{len(self.settings_rows)} ticker rows loaded")

    def _add_settings_row(self, settings: TickerTradeSettings | None = None) -> None:
        self._settings_row_id += 1
        row_widgets = SettingsRowWidgets(
            self._settings_row_id,
            settings or TickerTradeSettings(symbol=""),
            expanded=settings is None,
        )
        row_widgets.summary.set(self._settings_summary(row_widgets))
        self.settings_rows.append(row_widgets)
        card = tk.Frame(
            self.settings_frame,
            background=self.palette["panel"],
            highlightbackground=self.palette["line"],
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        card.pack(fill=tk.X, pady=(0, 12))

        top = tk.Frame(card, background=self.palette["panel"])
        top.pack(fill=tk.X)
        toggle_button = tk.Button(top, text="Collapse" if row_widgets.expanded.get() else "Expand", width=9)
        toggle_button.pack(side=tk.LEFT, padx=(0, 8))
        row_widgets.toggle_button = toggle_button
        tk.Checkbutton(top, text="Enabled", variable=row_widgets.enabled, background=self.palette["panel"]).pack(side=tk.LEFT)
        tk.Label(top, text="Ticker", background=self.palette["panel"], foreground=self.palette["text"], font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(14, 4))
        tk.Entry(top, textvariable=row_widgets.symbol, width=10).pack(side=tk.LEFT)
        tk.Label(
            top,
            textvariable=row_widgets.summary,
            background=self.palette["panel"],
            foreground=self.palette["muted"],
        ).pack(side=tk.LEFT, padx=(16, 0))
        tk.Button(top, text="Delete Row", command=lambda target=row_widgets: self._delete_settings_row(target)).pack(side=tk.RIGHT)

        details = tk.Frame(card, background=self.palette["panel"])
        row_widgets.details_frame = details
        if row_widgets.expanded.get():
            details.pack(fill=tk.X, pady=(8, 0))
        toggle_button.configure(command=lambda target=row_widgets: self._toggle_settings_details(target))
        self._bind_settings_summary(row_widgets)

        limits = tk.Frame(details, background=self.palette["panel"])
        limits.pack(fill=tk.X, pady=(8, 4))
        self._field(limits, "Max position %", row_widgets.max_position_pct, "Maximum account-equity percentage this ticker may use per recommendation.").pack(side=tk.LEFT, padx=(0, 12))
        self._field(limits, "Max trades/day", row_widgets.max_trades_per_day, "Maximum recommendations allowed for this ticker per day in this app session.").pack(side=tk.LEFT, padx=(0, 12))
        self._field(limits, "Max contracts", row_widgets.max_option_contracts, "Maximum option contracts allowed for this ticker recommendation.").pack(side=tk.LEFT, padx=(0, 12))
        self._field(limits, "Min confidence", row_widgets.min_confidence, "Ticker-level minimum confidence required before a recommendation reaches the main page.").pack(side=tk.LEFT)

        transactions = tk.Frame(details, background=self.palette["panel"])
        transactions.pack(fill=tk.X, pady=(8, 4))
        for group, items in TRANSACTION_GROUPS.items():
            group_frame = tk.LabelFrame(
                transactions,
                text=group,
                background=self.palette["panel_alt"],
                foreground=self.palette["text"],
                padx=8,
                pady=5,
                labelanchor="n",
            )
            group_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
            for item in items:
                check = tk.Checkbutton(
                    group_frame,
                    text=item.label,
                    variable=row_widgets.transaction_vars[item.key],
                    background=self.palette["panel_alt"],
                    activebackground=self.palette["panel_alt"],
                    anchor="w",
                )
                check.pack(fill=tk.X, anchor=tk.W)
                ToolTip(check, item.description)

        strategies = tk.LabelFrame(
            details,
            text="Strategy Settings",
            background=self.palette["panel"],
            foreground=self.palette["text"],
            padx=8,
            pady=6,
        )
        strategies.pack(fill=tk.X, pady=(8, 0))
        for index, (strategy, label) in enumerate(STRATEGY_LABELS.items()):
            row = index // 3
            column = index % 3
            strategy_card = tk.Frame(strategies, background="#ffffff", highlightbackground="#d1d5db", highlightthickness=1, padx=6, pady=5)
            strategy_card.grid(row=row, column=column, sticky=tk.EW, padx=4, pady=4)
            strategies.grid_columnconfigure(column, weight=1)
            check = tk.Checkbutton(
                strategy_card,
                text=label,
                variable=row_widgets.strategy_vars[strategy],
                background="#ffffff",
                activebackground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                anchor="w",
            )
            check.grid(row=0, column=0, columnspan=6, sticky=tk.W)
            ToolTip(check, STRATEGY_DESCRIPTIONS.get(strategy, ""))
            self._mini_field(strategy_card, "Min", row_widgets.strategy_min_confidence[strategy], 1)
            self._mini_field(strategy_card, "Max%", row_widgets.strategy_position_pct[strategy], 2)
            self._mini_field(strategy_card, "Trades", row_widgets.strategy_max_trades[strategy], 3)
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"{len(self.settings_rows)} ticker rows loaded")

    def _field(self, parent: tk.Widget, label: str, variable: tk.StringVar, tooltip: str) -> tk.Frame:
        frame = tk.Frame(parent, background=self.palette["panel"])
        label_widget = tk.Label(frame, text=label, background=self.palette["panel"], foreground=self.palette["muted"])
        label_widget.pack(anchor=tk.W)
        ToolTip(label_widget, tooltip)
        tk.Entry(frame, textvariable=variable, width=10).pack(anchor=tk.W)
        return frame

    def _mini_field(self, parent: tk.Widget, label: str, variable: tk.StringVar, column: int) -> None:
        tk.Label(parent, text=label, background="#ffffff", foreground=self.palette["muted"]).grid(row=1, column=(column - 1) * 2, sticky=tk.W, padx=(0, 3))
        tk.Entry(parent, textvariable=variable, width=6).grid(row=1, column=(column - 1) * 2 + 1, sticky=tk.W, padx=(0, 8))

    def _settings_summary(self, row_widgets: SettingsRowWidgets) -> str:
        enabled = "enabled" if row_widgets.enabled.get() else "disabled"
        transactions = sum(1 for value in row_widgets.transaction_vars.values() if value.get())
        strategies = sum(1 for value in row_widgets.strategy_vars.values() if value.get())
        return (
            f"{enabled} | {transactions} transaction types | {strategies} strategies | "
            f"max {row_widgets.max_position_pct.get()}% | {row_widgets.max_trades_per_day.get()}/day | "
            f"{row_widgets.max_option_contracts.get()} contracts | min {row_widgets.min_confidence.get()}"
        )

    def _bind_settings_summary(self, row_widgets: SettingsRowWidgets) -> None:
        variables: list[tk.Variable] = [
            row_widgets.enabled,
            row_widgets.max_position_pct,
            row_widgets.max_trades_per_day,
            row_widgets.max_option_contracts,
            row_widgets.min_confidence,
        ]
        variables.extend(row_widgets.transaction_vars.values())
        variables.extend(row_widgets.strategy_vars.values())
        for variable in variables:
            variable.trace_add(
                "write",
                lambda *_args, target=row_widgets: target.summary.set(self._settings_summary(target)),
            )

    def _toggle_settings_details(self, row_widgets: SettingsRowWidgets) -> None:
        self._set_settings_row_expanded(row_widgets, not row_widgets.expanded.get())

    def _set_settings_row_expanded(self, row_widgets: SettingsRowWidgets, expanded: bool) -> None:
        row_widgets.expanded.set(expanded)
        if row_widgets.details_frame is None or row_widgets.toggle_button is None:
            return
        if expanded:
            if not row_widgets.details_frame.winfo_manager():
                row_widgets.details_frame.pack(fill=tk.X, pady=(8, 0))
            row_widgets.toggle_button.configure(text="Collapse")
        else:
            row_widgets.details_frame.pack_forget()
            row_widgets.toggle_button.configure(text="Expand")
        row_widgets.summary.set(self._settings_summary(row_widgets))
        if hasattr(self, "settings_canvas"):
            self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all"))

    def _expand_all_settings_rows(self) -> None:
        for row_widgets in self.settings_rows:
            self._set_settings_row_expanded(row_widgets, True)
        self.settings_status_var.set(f"{len(self.settings_rows)} ticker rows expanded")

    def _collapse_all_settings_rows(self) -> None:
        for row_widgets in self.settings_rows:
            self._set_settings_row_expanded(row_widgets, False)
        self.settings_status_var.set(f"{len(self.settings_rows)} ticker rows collapsed")

    def _delete_settings_row(self, target: SettingsRowWidgets) -> None:
        settings = TradingSettings(
            tickers=tuple(row.to_settings() for row in self.settings_rows if row is not target),
        )
        self._render_settings_rows(settings)

    def _save_settings(self) -> None:
        rows = [row.to_settings() for row in self.settings_rows if row.to_settings().normalized_symbol]
        deduped: dict[str, TickerTradeSettings] = {}
        for row in rows:
            deduped[row.normalized_symbol] = row
        self.trading_settings = TradingSettings(tickers=tuple(deduped.values()))
        self.settings_store.save(self.trading_settings)
        self._render_settings_rows(self.trading_settings)
        self._apply_settings_to_config()
        self.settings_policy = RecommendationSettingsPolicy(self.trading_settings, self.config.guardrails)
        self._clear_recommendations()
        self._restart_feed()
        self.status_var.set(f"Settings saved. Active tickers: {', '.join(self.config.default_watchlist) or 'none'}.")

    def _reset_settings_defaults(self) -> None:
        self.trading_settings = TradingSettings(
            tickers=tuple(TickerTradeSettings(symbol=symbol) for symbol in AppConfig().default_watchlist),
        )
        self._render_settings_rows(self.trading_settings)

    def _clear_recommendations(self) -> None:
        self.recommendations.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
        for item_id in self.tree.get_children(""):
            self.tree.delete(item_id)
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", "Settings applied. Waiting for matching recommendations.")
        self.details.configure(state=tk.DISABLED)

    def _apply_settings_to_config(self) -> None:
        self.config.default_watchlist = self.trading_settings.active_symbols

    def _restart_feed(self) -> None:
        self._stop_event.set()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_feed_loop, args=(self._stop_event,), daemon=True)
        self._thread.start()

    def _sort_by_column(self, column: str) -> None:
        reverse = not self.sort_reverse.get(column, False)
        self.sort_reverse[column] = reverse
        rows = [(self._sort_value(column, self.tree.set(item_id, column)), item_id) for item_id in self.tree.get_children("")]
        rows.sort(reverse=reverse)
        for index, (_value, item_id) in enumerate(rows):
            self.tree.move(item_id, "", index)
        direction = "descending" if reverse else "ascending"
        self.status_var.set(f"Sorted {column} {direction}.")

    def _sort_value(self, column: str, value: str) -> str | float:
        if column in {"price", "confidence", "stop", "target"}:
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return 0.0
        return value.casefold()

    def _toggle_feed(self) -> None:
        self.feed_paused = not self.feed_paused
        if self.feed_paused:
            self.pause_button.configure(text="Resume Feed")
            self.status_var.set("Feed paused. Existing rows remain available for sorting and review.")
            return
        self.pause_button.configure(text="Pause Feed")
        self.status_var.set("Feed resumed.")

    def _open_settings_tab(self) -> None:
        self.notebook.select(3)
        self.status_var.set("Settings tab open. Changes affect the recommendation feed after Save + Apply.")

    def _approve_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        recommendation = self.recommendations[selected[0]]
        fill = asyncio.run(self.execution.approve(recommendation))
        self.tree.set(selected[0], "status", recommendation.status.value)
        if fill:
            self.status_var.set(f"{self._fill_message(fill)} {self._account_message()}")
            self._refresh_account()

    def _reject_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        recommendation = self.recommendations[selected[0]]
        recommendation.status = RecommendationStatus.REJECTED
        self.execution.record_manual_status(recommendation)
        self.tree.set(selected[0], "status", recommendation.status.value)
        self.status_var.set(f"Rejected {recommendation.idea.symbol}.")
        self._refresh_audit()

    def _kill_switch(self) -> None:
        self.config.guardrails.kill_switch_enabled = True
        self.status_var.set("Kill switch enabled. New trades will be blocked.")

    def _fill_message(self, fill: Fill) -> str:
        return f"Filled {fill.order.side.value} {fill.quantity} {fill.order.symbol} @ {fill.price:.2f}."

    def _account_message(self) -> str:
        account = self.broker.account_state()
        return (
            f"Paper trading ready. Cash ${account.cash:,.2f}; "
            f"equity ${account.equity:,.2f}; live trading disabled."
        )

    def _refresh_account(self) -> None:
        account = self.broker.account_state()
        self.account_var.set(
            f"Cash ${account.cash:,.2f} | Equity ${account.equity:,.2f} | "
            f"Realized P/L ${account.realized_pnl:,.2f} | Open positions {len(account.positions)}"
        )
        for item_id in self.positions_tree.get_children(""):
            self.positions_tree.delete(item_id)
        for position in account.positions:
            self.positions_tree.insert(
                "",
                tk.END,
                values=(
                    position.symbol,
                    position.asset_class.value,
                    position.quantity,
                    f"{position.avg_price:.2f}",
                    f"{position.cost_basis:.2f}",
                    f"{position.realized_pnl:.2f}",
                ),
            )

    def _refresh_audit(self) -> None:
        for item_id in self.audit_tree.get_children(""):
            self.audit_tree.delete(item_id)
        for event in self.store.recent_events(limit=100):
            self.audit_tree.insert(
                "",
                tk.END,
                values=(
                    event.get("occurred_at", ""),
                    event.get("event_type", ""),
                    event.get("symbol") or "",
                ),
            )

    def _show_selected_details(self, _event: object) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        recommendation = self.recommendations[selected[0]]
        idea = recommendation.idea
        decision = recommendation.guardrail_decision
        details = [
            f"{idea.strategy} | {idea.symbol} | confidence {idea.confidence:.2f} | status {recommendation.status.value}",
            "",
            f"Thesis: {idea.thesis}",
            f"TA: {idea.ta_summary}",
            f"Plan: {idea.side.value} {idea.quantity} @ {idea.limit_price:.2f}; stop {_format_optional_price(idea.stop_price)}; target {_format_optional_price(idea.target_price)}.",
            f"Guardrails: {'accepted' if decision.accepted else 'blocked'}",
        ]
        if decision.reasons:
            details.append(f"Reasons: {'; '.join(decision.reasons)}")
        if decision.adjusted_quantity:
            details.append(f"Adjusted quantity: {decision.adjusted_quantity}")
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", "\n".join(details))
        self.details.configure(state=tk.DISABLED)

    def _close(self) -> None:
        self._stop_event.set()
        self.store.close()
        self.root.destroy()


def main() -> None:
    DesktopApp().run()


def _format_optional_price(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _parse_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except ValueError:
        return default


if __name__ == "__main__":
    main()
