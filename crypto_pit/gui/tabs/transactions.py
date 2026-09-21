from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction
from crypto_pit.gui.dialogs import open_transaction_dialog
from crypto_pit.gui.formatters import fmt_datetime, fmt_money
from crypto_pit.gui.widgets import (
    FilterDropdown,
    autosize_columns,
    create_tree,
    insert_row,
    setup_columns,
)
from crypto_pit.gui.window_pos import askyesno, showinfo

if TYPE_CHECKING:
    from crypto_pit.gui.app import CryptoPitApp

GAP = 8

_TYPE_VALUES = ("Wszystkie", "Kupno", "Sprzedaż", "Inne")

_TX_COLUMNS = (
    ("lp", "Lp.", "e"),
    ("exchange", "Giełda", "w"),
    ("date", "Data", "w"),
    ("type", "Typ", "w"),
    ("asset", "Walor", "w"),
    ("amount", "Ilość", "e"),
    ("currency", "Waluta", "w"),
    ("value_curr", "Wartość", "e"),
    ("price", "Cena", "e"),
    ("rate", "Kurs", "e"),
    ("value", "Wartość PLN", "e"),
    ("fee", "Prowizja PLN", "e"),
    ("fee_coin", "Prowizja (walor)", "e"),
    ("final_coin", "Finalna ilość", "e"),
)


def _fmt_qty(v: float, digits: int = 8) -> str:
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _tx_values(lp: int, tx: Transaction) -> tuple[object, ...]:
    return (
        lp,
        tx.exchange,
        fmt_datetime(tx.date),
        tx.type.label_pl,
        (tx.asset or "").upper(),
        _fmt_qty(tx.coin_amount),
        tx.currency or "PLN",
        fmt_money(tx.value),
        _fmt_qty(tx.price, 6),
        _fmt_qty(tx.curr_to_pln, 6) if tx.curr_to_pln else "1",
        fmt_money(tx.value_pln),
        fmt_money(tx.fee_pln),
        _fmt_qty(tx.fee_coin),
        _fmt_qty(tx.final_coin),
    )


class TransactionsTab:
    def __init__(self, parent: ttk.Frame, app: CryptoPitApp) -> None:
        self.app = app
        self.frame = parent
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, GAP))

        self.year_var = tk.StringVar(value="Wszystkie")
        self.type_var = tk.StringVar(value="Wszystkie")

        ttk.Label(toolbar, text="Rok").pack(side=tk.LEFT)
        self.year_filter = FilterDropdown(
            toolbar,
            self.year_var,
            ["Wszystkie"],
            width=10,
            on_change=self.refresh,
        )
        self.year_filter.pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(toolbar, text="Typ").pack(side=tk.LEFT)
        self.type_filter = FilterDropdown(
            toolbar,
            self.type_var,
            _TYPE_VALUES,
            width=12,
            on_change=self.refresh,
        )
        self.type_filter.pack(side=tk.LEFT, padx=(6, 20))

        ttk.Button(
            toolbar, text="Dodaj…", style="Accent.TButton", command=self.add
        ).pack(side=tk.LEFT, padx=(0, GAP))
        ttk.Button(toolbar, text="Edytuj…", command=self.edit).pack(
            side=tk.LEFT, padx=(0, GAP)
        )
        ttk.Button(toolbar, text="Usuń", command=self.delete).pack(side=tk.LEFT)

        tree_wrap, self.tree = create_tree(self.frame)
        tree_wrap.grid(row=1, column=0, sticky="nsew")
        setup_columns(
            self.tree,
            tuple(c[0] for c in _TX_COLUMNS),
            {c[0]: c[1] for c in _TX_COLUMNS},
            anchors={c[0]: c[2] for c in _TX_COLUMNS},
        )
        self.tree.bind("<Double-1>", lambda _e: self.edit())

        self.sum_label = ttk.Label(self.frame, text="", style="Muted.TLabel")
        self.sum_label.grid(row=2, column=0, sticky="ew", pady=(GAP, 0))

    def _type_filter(self) -> TxType | None:
        return {
            "Kupno": TxType.BUY,
            "Sprzedaż": TxType.SELL,
            "Inne": TxType.OTHER,
        }.get(self.type_var.get())

    def refresh(self) -> None:
        years = sorted({t.year for t in self.app.db.list_transactions()})
        year_values = ["Wszystkie"] + [str(y) for y in years]
        self.year_filter.set_values(year_values)
        if self.year_var.get() not in year_values:
            self.year_var.set("Wszystkie")

        year = None
        if self.year_var.get() not in ("", "Wszystkie"):
            year = int(self.year_var.get())
        txs = self.app.db.list_transactions(year=year, tx_type=self._type_filter())

        self.tree.delete(*self.tree.get_children())
        sum_rev = sum_cost = 0.0
        for i, tx in enumerate(txs):
            sum_rev += round(tx.pit_revenue(), 2)
            sum_cost += round(tx.pit_cost(), 2)
            insert_row(self.tree, _tx_values(i + 1, tx), iid=str(tx.id), index=i)
        self.sum_label.config(
            text=(
                f"Widoczne: {len(txs)}    |    "
                f"suma przychodów: {fmt_money(sum_rev)} PLN    |    "
                f"suma kosztów: {fmt_money(sum_cost)} PLN"
            )
        )
        autosize_columns(self.tree)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add(self) -> None:
        open_transaction_dialog(self.app, self.app.db, self.app.refresh_all)

    def edit(self) -> None:
        tx_id = self._selected_id()
        if tx_id is None:
            showinfo("Edycja", "Wybierz transakcję.", parent=self.app)
            return
        tx = self.app.db.get_transaction(tx_id)
        if tx:
            open_transaction_dialog(self.app, self.app.db, self.app.refresh_all, tx)

    def delete(self) -> None:
        tx_id = self._selected_id()
        if tx_id is None:
            showinfo("Usuń", "Wybierz transakcję.", parent=self.app)
            return
        tx = self.app.db.get_transaction(tx_id)
        if tx and tx.confirmed:
            showinfo(
                "Usuń",
                "Transakcja jest zatwierdzona. Odznacz „Zatwierdzone” w edycji, "
                "aby ją usunąć.",
                parent=self.app,
            )
            return
        sel = self.tree.selection()[0]
        lp = self.tree.item(sel, "values")[0]
        if askyesno("Usuń", f"Usunąć transakcję Lp. {lp}?", parent=self.app):
            self.app.db.delete_transaction(tx_id)
            self.app.refresh_all()
