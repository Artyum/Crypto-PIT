from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from crypto_pit.domain.pit38 import pit38_short_header
from crypto_pit.gui.formatters import fmt_money
from crypto_pit.gui.widgets import (
    autosize_columns,
    create_tree,
    insert_row,
    setup_columns,
)
from crypto_pit.services.calculator import settle_years

if TYPE_CHECKING:
    from crypto_pit.gui.app import CryptoPitApp


class YearsTab:
    def __init__(self, parent: ttk.Frame, app: CryptoPitApp) -> None:
        self.app = app
        self.frame = parent
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        tree_wrap, self.tree = create_tree(self.frame)
        tree_wrap.grid(row=0, column=0, sticky="nsew")
        setup_columns(
            self.tree,
            (
                "year",
                "revenue",
                "costs_cur",
                "costs_prior",
                "costs_tot",
                "income",
                "carry",
                "tax",
                "tx",
            ),
            {
                "year": "Rok",
                "revenue": pit38_short_header("przychod"),
                "costs_cur": pit38_short_header("koszty_biezace"),
                "costs_prior": pit38_short_header("koszty_lat_ubieglych"),
                "costs_tot": "Razem",
                "income": pit38_short_header("dochod"),
                "carry": pit38_short_header("koszty_do_przeniesienia"),
                "tax": "Podatek 19%",
                "tx": "Liczba transakcji",
            },
            anchors={
                "year": tk.CENTER,
                "revenue": tk.E,
                "costs_cur": tk.E,
                "costs_prior": tk.E,
                "costs_tot": tk.E,
                "income": tk.E,
                "carry": tk.E,
                "tax": tk.E,
                "tx": tk.CENTER,
            },
        )
        self.tree.bind("<ButtonRelease-1>", self._on_row_click)

    def refresh(self) -> None:
        txs = self.app.db.list_transactions()
        settlements = settle_years(txs)
        self.app.settlements = {s.year: s for s in settlements}

        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(settlements):
            insert_row(
                self.tree,
                (
                    s.year,
                    fmt_money(s.revenue),
                    fmt_money(s.costs_current),
                    fmt_money(s.costs_prior),
                    fmt_money(s.costs_total),
                    fmt_money(s.income),
                    fmt_money(s.carried_forward),
                    fmt_money(s.tax_19),
                    s.tx_count,
                ),
                iid=str(s.year),
                index=i,
            )

        autosize_columns(self.tree)
        self.app.tab_pit.set_years([str(s.year) for s in settlements])

    def _on_row_click(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.app.tab_pit.select_year(row)
