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
from ztrade.execution.engine import ExecutionEngine
from ztrade.models import Fill, Recommendation, RecommendationStatus
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.storage.sqlite import TradingStore
from ztrade.strategies.registry import default_strategies


class DesktopApp:
    def __init__(self) -> None:
        self.config = AppConfig(bot_mode=BotMode.STAGE_ONLY)
        self.store = TradingStore(self.config.database_path)
        self.store.initialize()
        self.guardrails = GuardrailEngine(self.config.guardrails)
        self.broker = PaperBroker(self.config.guardrails.account_equity, store=self.store)
        self.execution = ExecutionEngine(self.config, self.broker, self.guardrails, store=self.store)
        self.recommender = RecommendationEngine(default_strategies(), self.guardrails)
        self.queue: Queue[Recommendation | Fill] = Queue()
        self.recommendations: dict[str, Recommendation] = {}
        self.sort_reverse: dict[str, bool] = {}
        self.feed_paused = False

        self.root = tk.Tk()
        self.root.title(f"zTrade v{__version__} - Paper Trading Workstation")
        self.root.geometry("1280x760")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.mode_var = tk.StringVar(value=self.config.bot_mode.value)
        self.status_var = tk.StringVar(value=self._account_message())
        self.account_var = tk.StringVar(value=self._account_message())
        self._build_ui()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_feed_loop, daemon=True)
        self._thread.start()
        self.root.after(250, self._drain_queue)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Subtle.TLabel", foreground="#555555")
        style.configure("Danger.TLabel", foreground="#9a1b1b")

        header = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"zTrade v{__version__}", style="Header.TLabel").pack(side=tk.LEFT)
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

        top = ttk.Frame(self.root, padding=10)
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

        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        recommendations_tab = ttk.Frame(notebook)
        account_tab = ttk.Frame(notebook)
        audit_tab = ttk.Frame(notebook)
        notebook.add(recommendations_tab, text="Recommendations + Trade Review")
        notebook.add(account_tab, text="Paper Account + Positions")
        notebook.add(audit_tab, text="SQLite Audit Log")

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
            "zTrade v0.2 desktop loaded. Select a recommendation to inspect thesis, guardrails, and trade plan.",
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

    def _run_feed_loop(self) -> None:
        asyncio.run(self._consume_feed())

    async def _consume_feed(self) -> None:
        provider = create_data_provider(self.config)
        async for snapshot in provider.stream():
            if self._stop_event.is_set():
                return
            if self.feed_paused:
                continue
            if self.config.record_market_events:
                self.store.record_market_snapshot(snapshot)
            for recommendation in self.recommender.evaluate(snapshot):
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


if __name__ == "__main__":
    main()
