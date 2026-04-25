from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from queue import Queue
from tkinter import ttk

from ztrade.brokers.paper import PaperBroker
from ztrade.config import AppConfig, BotMode
from ztrade.data.providers import DemoDataProvider
from ztrade.execution.engine import ExecutionEngine
from ztrade.models import Fill, Recommendation, RecommendationStatus
from ztrade.recommendations.engine import RecommendationEngine
from ztrade.risk.guardrails import GuardrailEngine
from ztrade.strategies.registry import default_strategies


class DesktopApp:
    def __init__(self) -> None:
        self.config = AppConfig(bot_mode=BotMode.STAGE_ONLY)
        self.guardrails = GuardrailEngine(self.config.guardrails)
        self.execution = ExecutionEngine(self.config, PaperBroker(), self.guardrails)
        self.recommender = RecommendationEngine(default_strategies(), self.guardrails)
        self.queue: Queue[Recommendation | Fill] = Queue()
        self.recommendations: dict[str, Recommendation] = {}

        self.root = tk.Tk()
        self.root.title("zTrade Paper Trading Workstation")
        self.root.geometry("1120x680")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.mode_var = tk.StringVar(value=self.config.bot_mode.value)
        self.status_var = tk.StringVar(value="Paper trading ready. Live trading disabled.")
        self._build_ui()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_feed_loop, daemon=True)
        self._thread.start()
        self.root.after(250, self._drain_queue)

    def _build_ui(self) -> None:
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

        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT)

        columns = ("status", "symbol", "side", "price", "confidence", "strategy", "ta")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=22)
        for column in columns:
            self.tree.heading(column, text=column.title())
        self.tree.column("status", width=90)
        self.tree.column("symbol", width=160)
        self.tree.column("side", width=70)
        self.tree.column("price", width=90)
        self.tree.column("confidence", width=100)
        self.tree.column("strategy", width=150)
        self.tree.column("ta", width=440)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

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
        provider = DemoDataProvider(self.config.default_watchlist)
        async for snapshot in provider.stream():
            if self._stop_event.is_set():
                return
            for recommendation in self.recommender.evaluate(snapshot):
                fill = await self.execution.handle_recommendation(recommendation)
                if fill:
                    self.queue.put(fill)
                self.queue.put(recommendation)

    def _drain_queue(self) -> None:
        while not self.queue.empty():
            recommendation = self.queue.get_nowait()
            if isinstance(recommendation, Fill):
                self.status_var.set(self._fill_message(recommendation))
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
                    idea.side.value,
                    f"{idea.limit_price:.2f}",
                    f"{idea.confidence:.2f}",
                    idea.strategy,
                    idea.ta_summary,
                ),
            )
        self.root.after(250, self._drain_queue)

    def _approve_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        recommendation = self.recommendations[selected[0]]
        fill = asyncio.run(self.execution.approve(recommendation))
        self.tree.set(selected[0], "status", recommendation.status.value)
        if fill:
            self.status_var.set(self._fill_message(fill))

    def _reject_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        recommendation = self.recommendations[selected[0]]
        recommendation.status = RecommendationStatus.REJECTED
        self.tree.set(selected[0], "status", recommendation.status.value)
        self.status_var.set(f"Rejected {recommendation.idea.symbol}.")

    def _kill_switch(self) -> None:
        self.config.guardrails.kill_switch_enabled = True
        self.status_var.set("Kill switch enabled. New trades will be blocked.")

    def _fill_message(self, fill: Fill) -> str:
        return f"Filled {fill.order.side.value} {fill.quantity} {fill.order.symbol} @ {fill.price:.2f}."

    def _close(self) -> None:
        self._stop_event.set()
        self.root.destroy()


def main() -> None:
    DesktopApp().run()


if __name__ == "__main__":
    main()
