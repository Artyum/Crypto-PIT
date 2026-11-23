from __future__ import annotations

import queue
import time
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
_RATE_LOADING = "Pobieranie…"
_RATE_MISSING = "Brak kursu"
_USD_COLUMN = 4
_PLN_COLUMN = 5


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
        self._fetch_generation = 0
        self._fetch_token: int | None = None
        self._rate_updates: queue.Queue[str] = queue.Queue()
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
        pending = any(not self._price_ready(asset) for asset in assets)
        if not self._rates_loaded or pending:
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
        self._fetch_generation += 1
        generation = self._fetch_generation
        self._drain_rate_updates()
        for asset in assets:
            self._apply_rate_labels(asset)
        autosize_columns(self.summary)
        if not self.status_var.get():
            self.status_var.set("Pobieranie kursów…")
        rates = self.app.crypto_rates
        holdings = self.app.db.list_holdings()
        self.frame.after(100, lambda: self._poll_rate_updates(generation))

        def publish(asset: str) -> None:
            self._rate_updates.put(asset)

        def retry_limited(ids: list[str]) -> None:
            failed = [
                cid
                for cid in ids
                if (price := rates.get_cached_price(cid)) is not None
                and not price.ok
                and "429" in (price.error or "")
            ]
            if not failed:
                return
            time.sleep(1.5)
            rates.fetch_prices(failed)

        def work() -> str:
            for holding in holdings:
                rates.remember_symbol(holding.symbol, holding.coin_id)
            pending_ids: list[str] = []
            seen_ids: set[str] = set()
            unknown: list[str] = []
            for asset in assets:
                coin_id = rates.coin_id_for_symbol(asset)
                if not coin_id:
                    unknown.append(asset)
                    continue
                cached = rates.get_cached_price(coin_id)
                if cached is not None and cached.ok and not force:
                    publish(asset)
                    continue
                if coin_id not in seen_ids:
                    seen_ids.add(coin_id)
                    pending_ids.append(coin_id)
            if pending_ids:
                rates.fetch_prices(pending_ids, force_refresh=force)
                retry_limited(pending_ids)
                for asset in assets:
                    if asset not in unknown:
                        publish(asset)
            resolved: list[str] = []
            missing_ids: list[str] = []
            seen_missing: set[str] = set()
            for asset in unknown:
                coin_id = rates.resolve_symbols([asset]).get(asset.strip().upper())
                if not coin_id:
                    continue
                resolved.append(asset)
                cached = rates.get_cached_price(coin_id)
                if cached is not None and cached.ok and not force:
                    publish(asset)
                    continue
                if coin_id not in seen_missing:
                    seen_missing.add(coin_id)
                    missing_ids.append(coin_id)
            if missing_ids:
                rates.fetch_prices(missing_ids, force_refresh=force)
                retry_limited(missing_ids)
                for asset in resolved:
                    publish(asset)
            messages: list[str] = []
            seen_messages: set[str] = set()
            for asset in assets:
                price = rates.get_cached_price_for_symbol(asset)
                if price is not None and price.ok:
                    continue
                message = price.error if price is not None and price.error else ""
                if not message:
                    message = f"{asset}: brak kursu"
                if message not in seen_messages:
                    seen_messages.add(message)
                    messages.append(message)
            return " · ".join(messages)

        def ok(result: str) -> None:
            self._fetch_token = None
            self._on_fetch_done(result)

        def err(exc: BaseException) -> None:
            self._fetch_token = None
            self._on_fetch_done(str(exc))

        self._fetch_token = self.app.tasks.submit(work, ok, err)

    def _on_fetch_done(self, error: str) -> None:
        self._fetch_busy = False
        self._rates_loaded = True
        for row in self._result.rows:
            self._apply_rate_labels(row.asset)
        autosize_columns(self.summary)
        if error:
            self.status_var.set(error)
        elif self.status_var.get() == "Pobieranie kursów…":
            self.status_var.set("")

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
            usd_s, pln_s = self._rate_labels(row.asset)
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

    def _price_ready(self, asset: str) -> bool:
        price = self.app.crypto_rates.get_cached_price_for_symbol(asset)
        return price is not None and price.ok

    def _drain_rate_updates(self) -> None:
        while True:
            try:
                self._rate_updates.get_nowait()
            except queue.Empty:
                return

    def _poll_rate_updates(self, generation: int) -> None:
        if generation != self._fetch_generation:
            return
        changed = False
        while True:
            try:
                asset = self._rate_updates.get_nowait()
            except queue.Empty:
                break
            self._apply_rate_labels(asset)
            changed = True
        if changed:
            autosize_columns(self.summary)
        if self._fetch_busy and generation == self._fetch_generation:
            try:
                self.frame.after(100, lambda: self._poll_rate_updates(generation))
            except tk.TclError:
                return

    def _rate_labels(self, asset: str) -> tuple[str, str]:
        price = self.app.crypto_rates.get_cached_price_for_symbol(asset)
        if price is not None and price.usd is not None and price.pln is not None:
            return fmt_rate(price.usd), fmt_rate(price.pln)
        if self._fetch_busy or not self._rates_loaded:
            return _RATE_LOADING, _RATE_LOADING
        if price is None:
            return _RATE_MISSING, _RATE_MISSING
        return (
            fmt_rate(price.usd) if price.usd is not None else _RATE_MISSING,
            fmt_rate(price.pln) if price.pln is not None else _RATE_MISSING,
        )

    def _apply_rate_labels(self, asset: str) -> None:
        if not self.summary.exists(asset):
            return
        usd_s, pln_s = self._rate_labels(asset)
        values = list(self.summary.item(asset, "values"))
        if len(values) <= _PLN_COLUMN:
            return
        values[_USD_COLUMN] = usd_s
        values[_PLN_COLUMN] = pln_s
        self.summary.item(asset, values=values)

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
