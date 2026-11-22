from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from crypto_pit.datetime_fmt import local_now, make_local_datetime
from crypto_pit.domain.models import Transaction
from crypto_pit.gui.datetime_picker import ask_datetime
from crypto_pit.gui.formatters import fmt_datetime, fmt_money, fmt_qty, fmt_rate
from crypto_pit.gui.widgets import (
    FilterDropdown,
    autosize_columns,
    create_tree,
    insert_row,
    setup_columns,
)
from crypto_pit.services.crypto_rates import CryptoRateFetchError
from crypto_pit.services.dca import (
    DcaResult,
    buy_years,
    dca_year_bounds,
    default_dca_dates,
    parse_dca_day,
    query_dca,
)

if TYPE_CHECKING:
    from crypto_pit.gui.app import CryptoPitApp

GAP = 8
_ALL_YEARS = "Wszystkie"


class DcaTab:
    def __init__(self, parent: ttk.Frame, app: CryptoPitApp) -> None:
        self.app = app
        self.frame = parent
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=2)
        self.frame.rowconfigure(3, weight=3)

        self._defaults_applied = False
        self._applying = False
        self._rates_loaded = False
        self._fetch_busy = False
        self._result = DcaResult((), {}, 0, "")
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        self.year_var = tk.StringVar(value=_ALL_YEARS)
        self.status_var = tk.StringVar()

        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, GAP))
        self._build_toolbar(toolbar)

        summary_wrap, self.summary = create_tree(self.frame)
        summary_wrap.grid(row=1, column=0, sticky="nsew")
        setup_columns(
            self.summary,
            ("asset", "count", "total_pln", "total_qty", "usd", "pln", "dca"),
            {
                "asset": "Walor",
                "count": "Zakupy",
                "total_pln": "Suma PLN",
                "total_qty": "Ilość",
                "usd": "Kurs USD",
                "pln": "Kurs PLN",
                "dca": "DCA PLN",
            },
            anchors={
                "usd": tk.E,
                "pln": tk.E,
                "count": tk.E,
                "total_pln": tk.E,
                "total_qty": tk.E,
                "dca": tk.E,
            },
        )
        self.summary.bind("<<TreeviewSelect>>", self._on_summary_select)

        ttk.Label(self.frame, text="Zakupy wybranego waloru").grid(
            row=2, column=0, sticky="w", pady=(GAP, 4)
        )

        detail_wrap, self.detail = create_tree(self.frame)
        detail_wrap.grid(row=3, column=0, sticky="nsew")
        setup_columns(
            self.detail,
            ("date", "quantity", "value_pln", "unit_price"),
            {
                "date": "Data",
                "quantity": "Ilość",
                "value_pln": "Wartość PLN",
                "unit_price": "Cena PLN",
            },
            anchors={"quantity": tk.E, "value_pln": tk.E, "unit_price": tk.E},
        )

        footer = ttk.Frame(self.frame)
        footer.grid(row=4, column=0, sticky="ew", pady=(GAP, 0))
        footer.columnconfigure(0, weight=1)
        self.sum_label = ttk.Label(footer, text="Zakupy: 0", style="Muted.TLabel")
        self.sum_label.grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.from_var.trace_add("write", self._on_date_edited)
        self.to_var.trace_add("write", self._on_date_edited)

    def _build_toolbar(self, toolbar: ttk.Frame) -> None:
        ttk.Label(toolbar, text="Rok").pack(side=tk.LEFT)
        self.year_filter = FilterDropdown(
            toolbar,
            self.year_var,
            [_ALL_YEARS],
            width=10,
            on_change=self._on_year_chosen,
        )
        self.year_filter.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(toolbar, text="Data od").pack(side=tk.LEFT)
        ttk.Entry(toolbar, textvariable=self.from_var, width=12, takefocus=False).pack(
            side=tk.LEFT, padx=(6, 6)
        )
        ttk.Button(toolbar, text="Wybierz…", command=self._pick_from).pack(
            side=tk.LEFT, padx=(0, 16)
        )
        ttk.Label(toolbar, text="Data do").pack(side=tk.LEFT)
        ttk.Entry(toolbar, textvariable=self.to_var, width=12, takefocus=False).pack(
            side=tk.LEFT, padx=(6, 6)
        )
        ttk.Button(toolbar, text="Wybierz…", command=self._pick_to).pack(side=tk.LEFT)

    def on_show(self) -> None:
        self.refresh()
        assets = [row.asset for row in self._result.rows]
        missing = any(
            self.app.crypto_rates.get_cached_price_for_symbol(asset) is None
            for asset in assets
        )
        if not self._rates_loaded or missing:
            self._fetch_rates(force=False)

    def refresh(self) -> None:
        transactions = self.app.db.list_transactions()
        self._refresh_years(transactions)
        self._apply_default_dates(transactions)
        self._render(transactions)

    def _fetch_rates(self, *, force: bool) -> None:
        if self._fetch_busy:
            return
        assets = [row.asset for row in self._result.rows]
        if not assets:
            self._rates_loaded = True
            return
        self._fetch_busy = True
        rates = self.app.crypto_rates
        holdings = self.app.db.list_holdings()

        def worker() -> None:
            try:
                for holding in holdings:
                    rates.remember_symbol(holding.symbol, holding.coin_id)
                mapping = rates.resolve_symbols(assets)
                rates.fetch_prices(list(mapping.values()), force_refresh=force)
                err = ""
            except CryptoRateFetchError as exc:
                err = str(exc)
            self.frame.after(0, lambda: self._on_fetch_done(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_done(self, error: str) -> None:
        self._fetch_busy = False
        self._rates_loaded = True
        transactions = self.app.db.list_transactions()
        self._render(transactions)
        if error:
            self.status_var.set(error)

    def _refresh_years(self, transactions: list[Transaction]) -> None:
        values = [_ALL_YEARS, *[str(year) for year in buy_years(transactions)]]
        self.year_filter.set_values(values)
        if self.year_var.get() not in values:
            self.year_var.set(_ALL_YEARS)
            date_from, date_to = default_dca_dates(transactions, local_now().date())
            self._set_dates(date_from, date_to)

    def _on_year_chosen(self) -> None:
        transactions = self.app.db.list_transactions()
        selected = self.year_var.get()
        if selected == _ALL_YEARS:
            date_from, date_to = default_dca_dates(transactions, local_now().date())
        else:
            date_from, date_to = dca_year_bounds(int(selected))
        self._defaults_applied = True
        self._set_dates(date_from, date_to)
        self._render(transactions)

    def _apply_default_dates(self, transactions: list[Transaction]) -> None:
        if self._defaults_applied:
            return
        date_from, date_to = default_dca_dates(transactions, local_now().date())
        self._set_dates(date_from, date_to)
        if date_from:
            self._defaults_applied = True

    def _set_dates(self, date_from: str, date_to: str) -> None:
        self._applying = True
        self.from_var.set(date_from)
        self.to_var.set(date_to)
        self._applying = False

    def _on_date_edited(self, *_args: object) -> None:
        if self._applying:
            return
        self._defaults_applied = True
        transactions = self.app.db.list_transactions()
        self._sync_year_from_dates(transactions)
        self._render(transactions)

    def _sync_year_from_dates(self, transactions: list[Transaction]) -> None:
        date_from = self.from_var.get().strip()
        date_to = self.to_var.get().strip()
        if (date_from, date_to) == default_dca_dates(transactions, local_now().date()):
            self.year_var.set(_ALL_YEARS)
            return
        start = parse_dca_day(date_from)
        end = parse_dca_day(date_to)
        if (
            start is not None
            and end is not None
            and start.year == end.year
            and (date_from, date_to) == dca_year_bounds(start.year)
        ):
            self.year_var.set(str(start.year))
            return
        self.year_var.set(_ALL_YEARS)

    def _pick_from(self) -> None:
        self._pick_date(self.from_var)

    def _pick_to(self) -> None:
        self._pick_date(self.to_var)

    def _pick_date(self, variable: tk.StringVar) -> None:
        current = parse_dca_day(variable.get())
        initial = (
            make_local_datetime(current.year, current.month, current.day)
            if current is not None
            else local_now()
        )
        chosen = ask_datetime(self.app, initial)
        if chosen is None:
            return
        variable.set(chosen.date().isoformat())

    def _render(self, transactions: list[Transaction]) -> None:
        kept = self._selected_asset()
        query = query_dca(transactions, self.from_var.get(), self.to_var.get())
        self._result = query.result
        self.status_var.set(query.message)
        self.sum_label.config(text=f"Zakupy: {query.result.total_purchases}")
        self.summary.delete(*self.summary.get_children())
        self.detail.delete(*self.detail.get_children())
        for index, row in enumerate(query.result.rows):
            price = self.app.crypto_rates.get_cached_price_for_symbol(row.asset)
            usd_s = pln_s = "—"
            if price is not None:
                usd_s = fmt_rate(price.usd)
                pln_s = fmt_rate(price.pln)
            insert_row(
                self.summary,
                (
                    row.asset,
                    row.count,
                    fmt_money(row.total_pln),
                    fmt_qty(row.total_qty),
                    usd_s,
                    pln_s,
                    fmt_money(row.dca),
                ),
                iid=row.asset,
                index=index,
            )
        autosize_columns(self.summary)
        if not query.result.rows:
            return
        assets = [row.asset for row in query.result.rows]
        target = kept if kept in assets else assets[0]
        self.summary.selection_set(target)
        self.summary.focus(target)
        self._fill_detail(target)

    def _selected_asset(self) -> str | None:
        selected = self.summary.selection()
        if not selected:
            return None
        return str(selected[0])

    def _on_summary_select(self, _event: object | None = None) -> None:
        asset = self._selected_asset()
        if asset is None:
            return
        self._fill_detail(asset)

    def _fill_detail(self, asset: str) -> None:
        self.detail.delete(*self.detail.get_children())
        purchases = self._result.purchases_by_asset.get(asset, ())
        for index, purchase in enumerate(purchases):
            insert_row(
                self.detail,
                (
                    fmt_datetime(purchase.date),
                    fmt_qty(purchase.quantity),
                    fmt_money(purchase.value_pln),
                    fmt_money(purchase.unit_price),
                ),
                index=index,
            )
        autosize_columns(self.detail)
